"""
database.py — Base de données SQLite pour Agent IA
Toutes les tables : users, prospects, interactions, taches, routines, objectifs, devis, factures
"""

import sqlite3
import os
from datetime import datetime

DB_FILE = os.environ.get("DB_PATH", "database.db")


def get_db():
    """Retourne une connexion à la base de données."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Retourne des dicts
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crée toutes les tables si elles n'existent pas."""
    conn = get_db()
    c = conn.cursor()

    # ── USERS ──
    c.execute("""
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
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    # ── PROSPECTS ──
    c.execute("""
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
        date_ajout  TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # ── INTERACTIONS ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS interactions (
        id          TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL,
        prospect_id TEXT NOT NULL,
        type        TEXT NOT NULL,
        contenu     TEXT,
        resultat    TEXT,
        prochain_contact TEXT,
        date        TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (prospect_id) REFERENCES prospects(id)
    )""")

    # ── TACHES ──
    c.execute("""
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
        date_creation TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # ── ROUTINES ──
    c.execute("""
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
        date_creation TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # ── OBJECTIFS ──
    c.execute("""
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
        date_creation TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # ── DEVIS ──
    c.execute("""
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
        date_creation TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # ── FACTURES ──
    c.execute("""
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
        date_creation TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    conn.commit()
    conn.close()
    print("✅ Base de données initialisée")


def row_to_dict(row):
    """Convertit une Row SQLite en dict."""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    """Convertit une liste de Rows en liste de dicts."""
    return [dict(r) for r in rows]


# Initialiser au démarrage
init_db()
