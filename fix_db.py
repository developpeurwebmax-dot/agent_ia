"""
fix_db.py — Script de migration ponctuel pour réparer la base de données.

Applique les 6 migrations ALTER TABLE en transactions isolées.
Chaque migration réussie affiche ✅, chaque colonne déjà présente affiche ⏩.
Lister ensuite toutes les colonnes de la table users pour confirmation.

Usage :
    python fix_db.py
"""

import os
import sys

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES  = bool(DATABASE_URL and DATABASE_URL.startswith("postgresql"))
DB_PATH       = os.environ.get("DB_PATH", "database.db")

print("=" * 60)
print(f"  fix_db.py — Migration ponctuelle")
print(f"  Moteur : {'PostgreSQL' if USE_POSTGRES else f'SQLite ({DB_PATH})'}")
print("=" * 60)


# ─────────────────────────────────────────────
# Helpers connexion bas niveau (sans passer par database.py)
# pour rester 100 % autonome et exécutable sans serveur.
# ─────────────────────────────────────────────

def _get_sqlite():
    import sqlite3
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _get_postgres():
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    conn.autocommit = False
    return conn


def _apply_migration(sql: str) -> str:
    """
    Applique un ALTER TABLE dans une connexion isolée.
    Retourne "ok" si la colonne a été ajoutée, "skip" si elle existait déjà,
    ou "error:<message>" en cas d'erreur inattendue.
    """
    if USE_POSTGRES:
        conn = _get_postgres()
        try:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
            return "ok"
        except Exception as e:
            msg = str(e).strip().splitlines()[0]
            try:
                conn.rollback()
            except Exception:
                pass
            # psycopg2 : "column X of relation Y already exists" → DuplicateColumn
            if "already exists" in msg.lower() or "duplicate" in msg.lower():
                return "skip"
            return f"error:{msg}"
        finally:
            conn.close()
    else:
        conn = _get_sqlite()
        try:
            conn.execute(sql)
            conn.commit()
            return "ok"
        except Exception as e:
            msg = str(e).strip()
            # SQLite : "duplicate column name: X"
            if "duplicate column" in msg.lower():
                return "skip"
            return f"error:{msg}"
        finally:
            conn.close()


def _lister_colonnes_users() -> list:
    """Retourne la liste des colonnes de la table users."""
    if USE_POSTGRES:
        conn = _get_postgres()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'users'
                ORDER BY ordinal_position
            """)
            return [(r[0], r[1]) for r in cur.fetchall()]
        finally:
            conn.close()
    else:
        conn = _get_sqlite()
        try:
            cur = conn.execute("PRAGMA table_info(users)")
            return [(r["name"], r["type"]) for r in cur.fetchall()]
        finally:
            conn.close()


# ─────────────────────────────────────────────
# Migrations à appliquer
# La colonne critique est en premier pour un diagnostic rapide.
# ─────────────────────────────────────────────

MIGRATIONS = [
    ("users",      "must_change_password", "ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0"),
    ("projets",    "notes",               "ALTER TABLE projets ADD COLUMN notes TEXT DEFAULT ''"),
    ("projets",    "notes_taches",        "ALTER TABLE projets ADD COLUMN notes_taches TEXT DEFAULT '[]'"),
    ("employes",   "horaires",            "ALTER TABLE employes ADD COLUMN horaires TEXT DEFAULT '{}'"),
    ("evaluations","priorite",            "ALTER TABLE evaluations ADD COLUMN priorite TEXT DEFAULT 'normale'"),
    ("evaluations","lue",                 "ALTER TABLE evaluations ADD COLUMN lue INTEGER DEFAULT 0"),
]

print()
ok_count   = 0
skip_count = 0
err_count  = 0

for table, colonne, sql in MIGRATIONS:
    resultat = _apply_migration(sql)
    if resultat == "ok":
        print(f"  ✅  {table}.{colonne} ajoutée")
        ok_count += 1
    elif resultat == "skip":
        print(f"  ⏩  {table}.{colonne} déjà présente")
        skip_count += 1
    else:
        print(f"  ❌  {table}.{colonne} — {resultat}")
        err_count += 1

print()
print(f"  Résultat : {ok_count} ajoutée(s), {skip_count} ignorée(s), {err_count} erreur(s)")
print()

# ─────────────────────────────────────────────
# Vérification finale : colonnes de la table users
# ─────────────────────────────────────────────

print("─" * 60)
print("  Colonnes de la table users :")
print("─" * 60)

try:
    colonnes = _lister_colonnes_users()
    for nom, type_ in colonnes:
        marqueur = " ◀ CIBLE" if nom == "must_change_password" else ""
        print(f"    {nom:<30} {type_}{marqueur}")

    noms = [c[0] for c in colonnes]
    print()
    if "must_change_password" in noms:
        print("  ✅  must_change_password est bien présente dans users.")
    else:
        print("  ❌  ATTENTION : must_change_password est ABSENTE de users !")
        print("      Vérifiez que la table users existe bien dans cette base.")
        sys.exit(1)

except Exception as e:
    print(f"  ❌  Impossible de lister les colonnes : {e}")
    sys.exit(1)

print()
print("  Migration terminée. Vous pouvez redémarrer le serveur Flask.")
print("=" * 60)
