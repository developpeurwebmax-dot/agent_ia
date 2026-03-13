"""
database_business.py — Tables supplémentaires pour Agent IA Business
À appeler depuis database.py init_db() ou séparément
"""

from database import get_db, USE_POSTGRES


def init_db_business():
    """Crée toutes les tables business si elles n'existent pas."""
    conn = get_db()

    if USE_POSTGRES:
        tables = _tables_postgres()
    else:
        tables = _tables_sqlite()

    for sql in tables:
        conn.execute(sql)

    conn.commit()
    conn.close()
    print("✅ Tables Business initialisées")


def _tables_sqlite():
    return [
        # ── ENTREPRISES ──
        """CREATE TABLE IF NOT EXISTS entreprises (
            id TEXT PRIMARY KEY,
            nom TEXT NOT NULL,
            siren TEXT,
            secteur TEXT,
            adresse TEXT,
            telephone TEXT,
            email TEXT,
            tva_intracommunautaire TEXT,
            forme_juridique TEXT DEFAULT 'SAS',
            date_creation_entreprise TEXT,
            nb_employes_max INTEGER DEFAULT 50,
            plan TEXT DEFAULT 'business',
            owner_id TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )""",

        # ── MEMBRES ENTREPRISE ──
        """CREATE TABLE IF NOT EXISTS membres_entreprise (
            id TEXT PRIMARY KEY,
            entreprise_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT DEFAULT 'employe',
            actif INTEGER DEFAULT 1,
            date_ajout TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id)
        )""",

        # ── TRANSACTIONS FINANCIÈRES ──
        """CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            entreprise_id TEXT NOT NULL,
            type TEXT NOT NULL,
            montant REAL NOT NULL,
            categorie TEXT DEFAULT 'autre',
            sous_categorie TEXT,
            description TEXT,
            date TEXT NOT NULL,
            mode_paiement TEXT DEFAULT 'virement',
            reference TEXT,
            employe_id TEXT,
            projet_id TEXT,
            tags TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id)
        )""",

        # ── EMPLOYÉS ──
        """CREATE TABLE IF NOT EXISTS employes (
            id TEXT PRIMARY KEY,
            entreprise_id TEXT NOT NULL,
            prenom TEXT NOT NULL,
            nom TEXT NOT NULL,
            email TEXT,
            telephone TEXT,
            poste TEXT,
            departement TEXT,
            type_contrat TEXT DEFAULT 'CDI',
            date_embauche TEXT,
            salaire_brut REAL DEFAULT 0,
            statut TEXT DEFAULT 'actif',
            conges_acquis REAL DEFAULT 25,
            conges_pris REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id)
        )""",

        # ── CONGÉS ──
        """CREATE TABLE IF NOT EXISTS conges (
            id TEXT PRIMARY KEY,
            entreprise_id TEXT NOT NULL,
            employe_id TEXT NOT NULL,
            type TEXT DEFAULT 'conges_payes',
            date_debut TEXT NOT NULL,
            date_fin TEXT NOT NULL,
            nb_jours REAL DEFAULT 0,
            statut TEXT DEFAULT 'en_attente',
            motif TEXT,
            commentaire_valideur TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id),
            FOREIGN KEY (employe_id) REFERENCES employes(id)
        )""",

        # ── POINTAGES ──
        """CREATE TABLE IF NOT EXISTS pointages (
            id TEXT PRIMARY KEY,
            entreprise_id TEXT NOT NULL,
            employe_id TEXT NOT NULL,
            date TEXT NOT NULL,
            heure_arrivee TEXT,
            heure_depart TEXT,
            heures_travaillees REAL DEFAULT 8,
            heures_supplementaires REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id),
            FOREIGN KEY (employe_id) REFERENCES employes(id)
        )""",

        # ── ÉVALUATIONS ──
        """CREATE TABLE IF NOT EXISTS evaluations (
            id TEXT PRIMARY KEY,
            entreprise_id TEXT NOT NULL,
            employe_id TEXT NOT NULL,
            periode TEXT,
            note_globale REAL DEFAULT 0,
            competences TEXT DEFAULT '{}',
            objectifs_atteints TEXT,
            commentaire TEXT,
            points_forts TEXT,
            axes_amelioration TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id),
            FOREIGN KEY (employe_id) REFERENCES employes(id)
        )""",

        # ── PROJETS ──
        """CREATE TABLE IF NOT EXISTS projets (
            id TEXT PRIMARY KEY,
            entreprise_id TEXT NOT NULL,
            nom TEXT NOT NULL,
            client TEXT,
            description TEXT,
            budget REAL DEFAULT 0,
            cout_reel REAL DEFAULT 0,
            statut TEXT DEFAULT 'en_cours',
            date_debut TEXT,
            date_fin_prevue TEXT,
            date_fin_reelle TEXT,
            responsable_id TEXT,
            membres TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id)
        )""",
    ]


def _tables_postgres():
    """Même structure adaptée PostgreSQL."""
    pg = []
    for sql in _tables_sqlite():
        sql = sql.replace("datetime('now')", "to_char(now(), 'YYYY-MM-DD\"T\"HH24:MI:SS')")
        pg.append(sql)
    return pg


# Initialiser automatiquement
init_db_business()
