"""
database.py — Base de données PostgreSQL (Railway) avec fallback SQLite
"""

import os
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Détecter si on utilise PostgreSQL ou SQLite
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgresql"))


# ─────────────────────────────────────────────
# ADAPTATEUR UNIVERSEL
# ─────────────────────────────────────────────

class _PGConnection:
    def __init__(self, conn):
        self._conn = conn

    def _adapt(self, sql):
        return sql.replace("?", "%s")

    def execute(self, sql, params=()):
        cur = self._conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)
        cur.execute(self._adapt(sql), params)
        return _PGCursor(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


class _PGCursor:
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        rows = self._cur.fetchall()
        return [dict(r) for r in rows]

    @property
    def lastrowid(self):
        return None


class _SQLiteConnection:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.execute(sql, params)
        return _SQLiteCursor(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


class _SQLiteCursor:
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        return [dict(r) for r in self._cur.fetchall()]

    @property
    def lastrowid(self):
        return self._cur.lastrowid


def get_db():
    """Retourne une connexion adaptée (PostgreSQL ou SQLite)."""
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        conn.autocommit = False
        return _PGConnection(conn)
    else:
        import sqlite3
        # timeout + busy_timeout => evite "database is locked" sur ecritures concurrentes
        conn = sqlite3.connect(
            os.environ.get("DB_PATH", "database.db"),
            timeout=30,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        # foreign_keys volontairement OFF (defaut SQLite) : sur Render free-tier
        # le FS est ephemere, la DB peut etre recreee alors que des JWT contenant
        # un user_id ancien restent valides. Sans cette ligne, on echoue sur
        # "FOREIGN KEY constraint failed" a chaque INSERT post-redemarrage.
        return _SQLiteConnection(conn)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


def rows_to_list(rows):
    if not rows:
        return []
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


# ─────────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────────

def init_db():
    """Crée toutes les tables si elles n'existent pas."""
    conn = get_db()

    if USE_POSTGRES:
        sql_users = """
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            prenom      TEXT NOT NULL,
            nom         TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            metier      TEXT,
            localisation TEXT,
            experience  TEXT,
            secteurs    TEXT,
            offre       TEXT,
            tarif_type  TEXT DEFAULT 'jour',
            tarif_journalier REAL DEFAULT 0,
            tarif_horaire    REAL DEFAULT 0,
            objectif_ca      REAL DEFAULT 0,
            objectif_clients INTEGER DEFAULT 0,
            charges          REAL DEFAULT 0,
            plan        TEXT DEFAULT 'starter',
            modules     TEXT DEFAULT 'dashboard,devis,factures,taches',
            profil_legal TEXT DEFAULT '{}',
            date_inscription TEXT,
            created_at  TEXT DEFAULT (to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )"""

        sql_prospects = """
        CREATE TABLE IF NOT EXISTS prospects (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            nom         TEXT NOT NULL,
            entreprise  TEXT,
            email       TEXT,
            telephone   TEXT,
            linkedin    TEXT,
            secteur     TEXT,
            besoin      TEXT,
            source      TEXT,
            notes       TEXT,
            statut      TEXT DEFAULT 'nouveau',
            score       INTEGER DEFAULT 0,
            valeur_estimee REAL DEFAULT 0,
            dernier_contact TEXT,
            prochain_contact TEXT,
            nb_interactions INTEGER DEFAULT 0,
            date_ajout  TEXT DEFAULT (to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )"""

        sql_interactions = """
        CREATE TABLE IF NOT EXISTS interactions (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            prospect_id TEXT NOT NULL,
            type        TEXT NOT NULL,
            contenu     TEXT,
            resultat    TEXT,
            prochain_contact TEXT,
            date        TEXT DEFAULT (to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )"""

        sql_taches = """
        CREATE TABLE IF NOT EXISTS taches (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            titre       TEXT NOT NULL,
            description TEXT,
            priorite    TEXT DEFAULT 'moyenne',
            categorie   TEXT DEFAULT 'autre',
            statut      TEXT DEFAULT 'a_faire',
            date_echeance TEXT,
            duree_estimee_min INTEGER DEFAULT 30,
            duree_reelle_min  INTEGER,
            prospect_id TEXT,
            tags        TEXT DEFAULT '[]',
            notes       TEXT,
            completee_le TEXT,
            date_creation TEXT DEFAULT (to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )"""

        sql_routines = """
        CREATE TABLE IF NOT EXISTS routines (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            titre       TEXT NOT NULL,
            description TEXT,
            frequence   TEXT DEFAULT 'quotidien',
            heure_ideale TEXT DEFAULT 'matin',
            duree_min   INTEGER DEFAULT 30,
            categorie   TEXT DEFAULT 'autre',
            active      INTEGER DEFAULT 1,
            derniere_execution TEXT,
            nb_executions INTEGER DEFAULT 0,
            date_creation TEXT DEFAULT (to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )"""

        sql_objectifs = """
        CREATE TABLE IF NOT EXISTS objectifs (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            titre       TEXT NOT NULL,
            description TEXT,
            valeur_cible REAL DEFAULT 0,
            valeur_actuelle REAL DEFAULT 0,
            unite       TEXT,
            date_limite TEXT,
            categorie   TEXT DEFAULT 'autre',
            atteint     INTEGER DEFAULT 0,
            historique  TEXT DEFAULT '[]',
            date_creation TEXT DEFAULT (to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )"""

        sql_devis = """
        CREATE TABLE IF NOT EXISTS devis (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            numero      TEXT NOT NULL,
            client      TEXT NOT NULL,
            adresse_client TEXT,
            objet       TEXT,
            lignes      TEXT DEFAULT '[]',
            montant_ht  REAL DEFAULT 0,
            montant_ttc REAL DEFAULT 0,
            tva         REAL DEFAULT 20,
            statut      TEXT DEFAULT 'brouillon',
            date        TEXT,
            validite    TEXT,
            delai       TEXT,
            conditions  TEXT,
            commercial_id TEXT,
            date_creation TEXT DEFAULT (to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )"""

        sql_factures = """
        CREATE TABLE IF NOT EXISTS factures (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            numero      TEXT NOT NULL,
            client      TEXT NOT NULL,
            adresse_client TEXT,
            objet       TEXT,
            lignes      TEXT DEFAULT '[]',
            montant_ht  REAL DEFAULT 0,
            montant_ttc REAL DEFAULT 0,
            tva         REAL DEFAULT 20,
            statut      TEXT DEFAULT 'non_payee',
            date        TEXT,
            date_echeance TEXT,
            paiement    TEXT DEFAULT 'Virement bancaire',
            conditions  TEXT,
            devis_id    TEXT,
            mentions    TEXT,
            commercial_id TEXT,
            date_creation TEXT DEFAULT (to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )"""

        for sql in [sql_users, sql_prospects, sql_interactions, sql_taches,
                    sql_routines, sql_objectifs, sql_devis, sql_factures]:
            conn.execute(sql)

    else:
        # SQLite (local)
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, prenom TEXT NOT NULL, nom TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, metier TEXT,
            localisation TEXT, experience TEXT, secteurs TEXT, offre TEXT,
            tarif_type TEXT DEFAULT 'jour', tarif_journalier REAL DEFAULT 0,
            tarif_horaire REAL DEFAULT 0, objectif_ca REAL DEFAULT 0,
            objectif_clients INTEGER DEFAULT 0, charges REAL DEFAULT 0,
            plan TEXT DEFAULT 'starter',
            modules TEXT DEFAULT 'dashboard,devis,factures,taches',
            profil_legal TEXT DEFAULT '{}', date_inscription TEXT,
            created_at TEXT DEFAULT (datetime('now')))""")

        conn.execute("""CREATE TABLE IF NOT EXISTS prospects (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, nom TEXT NOT NULL,
            entreprise TEXT, email TEXT, telephone TEXT, linkedin TEXT,
            secteur TEXT, besoin TEXT, source TEXT, notes TEXT,
            statut TEXT DEFAULT 'nouveau', score INTEGER DEFAULT 0,
            valeur_estimee REAL DEFAULT 0, dernier_contact TEXT,
            prochain_contact TEXT, nb_interactions INTEGER DEFAULT 0,
            date_ajout TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id))""")

        conn.execute("""CREATE TABLE IF NOT EXISTS interactions (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, prospect_id TEXT NOT NULL,
            type TEXT NOT NULL, contenu TEXT, resultat TEXT, prochain_contact TEXT,
            date TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (prospect_id) REFERENCES prospects(id))""")

        conn.execute("""CREATE TABLE IF NOT EXISTS taches (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, titre TEXT NOT NULL,
            description TEXT, priorite TEXT DEFAULT 'moyenne',
            categorie TEXT DEFAULT 'autre', statut TEXT DEFAULT 'a_faire',
            date_echeance TEXT, duree_estimee_min INTEGER DEFAULT 30,
            duree_reelle_min INTEGER, prospect_id TEXT, tags TEXT DEFAULT '[]',
            notes TEXT, completee_le TEXT,
            date_creation TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id))""")

        conn.execute("""CREATE TABLE IF NOT EXISTS routines (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, titre TEXT NOT NULL,
            description TEXT, frequence TEXT DEFAULT 'quotidien',
            heure_ideale TEXT DEFAULT 'matin', duree_min INTEGER DEFAULT 30,
            categorie TEXT DEFAULT 'autre', active INTEGER DEFAULT 1,
            derniere_execution TEXT, nb_executions INTEGER DEFAULT 0,
            date_creation TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id))""")

        conn.execute("""CREATE TABLE IF NOT EXISTS objectifs (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, titre TEXT NOT NULL,
            description TEXT, valeur_cible REAL DEFAULT 0,
            valeur_actuelle REAL DEFAULT 0, unite TEXT, date_limite TEXT,
            categorie TEXT DEFAULT 'autre', atteint INTEGER DEFAULT 0,
            historique TEXT DEFAULT '[]',
            date_creation TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id))""")

        conn.execute("""CREATE TABLE IF NOT EXISTS devis (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, numero TEXT NOT NULL,
            client TEXT NOT NULL, adresse_client TEXT, objet TEXT,
            lignes TEXT DEFAULT '[]', montant_ht REAL DEFAULT 0,
            montant_ttc REAL DEFAULT 0, tva REAL DEFAULT 20,
            statut TEXT DEFAULT 'brouillon', date TEXT, validite TEXT,
            delai TEXT, conditions TEXT, commercial_id TEXT,
            date_creation TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id))""")

        conn.execute("""CREATE TABLE IF NOT EXISTS factures (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, numero TEXT NOT NULL,
            client TEXT NOT NULL, adresse_client TEXT, objet TEXT,
            lignes TEXT DEFAULT '[]', montant_ht REAL DEFAULT 0,
            montant_ttc REAL DEFAULT 0, tva REAL DEFAULT 20,
            statut TEXT DEFAULT 'non_payee', date TEXT, date_echeance TEXT,
            paiement TEXT DEFAULT 'Virement bancaire', conditions TEXT,
            devis_id TEXT, mentions TEXT, commercial_id TEXT,
            date_creation TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id))""")

    conn.commit()
    conn.close()
    print(f"✅ Base de données initialisée ({'PostgreSQL' if USE_POSTGRES else 'SQLite'})")