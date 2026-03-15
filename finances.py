"""
finances.py — Gestion financière PME
Transactions, catégories, trésorerie, projections, import CSV
"""

import json
import csv
import io
from datetime import datetime, date, timedelta
from database import get_db, row_to_dict, rows_to_list


def _generer_id(prefix="TRX"):
    import time
    return f"{prefix}_{int(time.time() * 1000000)}"


# ─────────────────────────────────────────────
# TRANSACTIONS
# ─────────────────────────────────────────────

def creer_transaction(entreprise_id: str, data: dict) -> dict:
    """Crée une transaction (revenu ou dépense)."""
    if not data.get("montant") or not data.get("type"):
        raise ValueError("Montant et type requis")
    if data["type"] not in ("revenu", "depense"):
        raise ValueError("Type doit être 'revenu' ou 'depense'")

    conn = get_db()
    try:
        tid = _generer_id("TRX")
        conn.execute("""
            INSERT INTO transactions
                (id, entreprise_id, type, montant, categorie, sous_categorie,
                 description, date, mode_paiement, reference, employe_id, projet_id, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tid, entreprise_id,
            data["type"],
            float(data["montant"]),
            data.get("categorie", "autre"),
            data.get("sous_categorie", ""),
            data.get("description", ""),
            data.get("date", date.today().isoformat()),
            data.get("mode_paiement", "virement"),
            data.get("reference", ""),
            data.get("employe_id"),
            data.get("projet_id"),
            json.dumps(data.get("tags", []))
        ))
        conn.commit()
        row = conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def get_transactions(entreprise_id: str, filtres: dict = None) -> list:
    """Récupère les transactions avec filtres optionnels."""
    conn = get_db()
    try:
        sql = "SELECT * FROM transactions WHERE entreprise_id=?"
        params = [entreprise_id]

        if filtres:
            if filtres.get("type"):
                sql += " AND type=?"
                params.append(filtres["type"])
            if filtres.get("categorie"):
                sql += " AND categorie=?"
                params.append(filtres["categorie"])
            if filtres.get("date_debut"):
                sql += " AND date >= ?"
                params.append(filtres["date_debut"])
            if filtres.get("date_fin"):
                sql += " AND date <= ?"
                params.append(filtres["date_fin"])
            if filtres.get("mois"):  # format YYYY-MM
                # Compatible SQLite et PostgreSQL (date stockée en texte ISO YYYY-MM-DD)
                sql += " AND substr(date, 1, 7) = ?"
                params.append(filtres["mois"])

        sql += " ORDER BY date DESC"
        rows = conn.execute(sql, params).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def modifier_transaction(tid: str, entreprise_id: str, data: dict) -> dict:
    conn = get_db()
    try:
        champs_ok = ["montant", "categorie", "sous_categorie", "description",
                     "date", "mode_paiement", "reference", "tags"]
        sets, vals = [], []
        for k in champs_ok:
            if k in data:
                val = json.dumps(data[k]) if k == "tags" else data[k]
                sets.append(f"{k}=?")
                vals.append(val)
        if sets:
            vals += [tid, entreprise_id]
            conn.execute(f"UPDATE transactions SET {','.join(sets)} WHERE id=? AND entreprise_id=?", vals)
            conn.commit()
        return row_to_dict(conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone())
    finally:
        conn.close()


def supprimer_transaction(tid: str, entreprise_id: str) -> bool:
    conn = get_db()
    try:
        conn.execute("DELETE FROM transactions WHERE id=? AND entreprise_id=?", (tid, entreprise_id))
        conn.commit()
        return True
    finally:
        conn.close()


# ─────────────────────────────────────────────
# IMPORT CSV BANCAIRE
# ─────────────────────────────────────────────

def importer_csv(entreprise_id: str, contenu_csv: str, mapping: dict = None) -> dict:
    """
    Importe des transactions depuis un relevé CSV bancaire.
    mapping: {colonne_csv: champ_interne} ex: {"Date": "date", "Montant": "montant", "Libellé": "description"}
    """
    mapping = mapping or {
        "date": "date",
        "montant": "montant",
        "libelle": "description",
        "categorie": "categorie"
    }

    reader = csv.DictReader(io.StringIO(contenu_csv), delimiter=";")
    importees = 0
    erreurs = []
    doublons = 0

    conn = get_db()
    try:
        for i, ligne in enumerate(reader):
            try:
                # Normaliser les clés (minuscules, sans accents basiques)
                ligne_norm = {k.lower().strip(): v.strip() for k, v in ligne.items()}

                montant_raw = ligne_norm.get("montant", "0").replace(",", ".").replace(" ", "")
                montant = float(montant_raw) if montant_raw else 0
                type_txn = "revenu" if montant > 0 else "depense"
                montant = abs(montant)

                date_raw = ligne_norm.get("date", date.today().isoformat())
                # Essayer plusieurs formats de date
                date_parsed = _parser_date(date_raw)

                desc = ligne_norm.get("libelle", ligne_norm.get("description", f"Import ligne {i+1}"))
                ref = ligne_norm.get("reference", ligne_norm.get("ref", ""))

                # Vérifier doublon (même date + montant + description)
                doublon = conn.execute(
                    "SELECT id FROM transactions WHERE entreprise_id=? AND date=? AND montant=? AND description=?",
                    (entreprise_id, date_parsed, montant, desc)
                ).fetchone()
                if doublon:
                    doublons += 1
                    continue

                tid = _generer_id("TRX")
                conn.execute("""
                    INSERT INTO transactions
                        (id, entreprise_id, type, montant, categorie, description, date, reference)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (tid, entreprise_id, type_txn, montant,
                      _auto_categoriser(desc), desc, date_parsed, ref))
                importees += 1

            except Exception as e:
                erreurs.append(f"Ligne {i+1}: {str(e)}")

        conn.commit()
        return {
            "importees": importees,
            "doublons_ignores": doublons,
            "erreurs": erreurs[:10],  # max 10 erreurs remontées
            "total_lignes": i + 1 if 'i' in dir() else 0
        }
    finally:
        conn.close()


def _parser_date(date_str: str) -> str:
    """Tente de parser différents formats de date bancaire."""
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date.today().isoformat()


def _auto_categoriser(description: str) -> str:
    """Catégorisation automatique basique par mots-clés."""
    desc = description.lower()
    if any(k in desc for k in ["salaire", "paie", "virement employé", "urssaf", "cotisation"]):
        return "salaires"
    if any(k in desc for k in ["loyer", "bail", "foncière", "immobilier"]):
        return "loyer"
    if any(k in desc for k in ["edf", "engie", "orange", "sfr", "bouygues", "eau", "gaz"]):
        return "charges_fixes"
    if any(k in desc for k in ["amazon", "fnac", "fourniture", "bureau", "papier"]):
        return "fournitures"
    if any(k in desc for k in ["google", "facebook", "meta", "publicité", "ads", "marketing"]):
        return "marketing"
    if any(k in desc for k in ["restaurant", "repas", "hotel", "train", "sncf", "avion", "taxi"]):
        return "deplacement_repas"
    if any(k in desc for k in ["assurance", "mutuelle"]):
        return "assurances"
    if any(k in desc for k in ["expert", "comptable", "avocat", "juridique", "notaire"]):
        return "honoraires"
    return "autre"


# ─────────────────────────────────────────────
# TABLEAU DE BORD FINANCIER
# ─────────────────────────────────────────────

def get_dashboard_financier(entreprise_id: str, periode: str = None) -> dict:
    """
    Retourne les KPIs financiers pour le dashboard.
    periode: 'mois_courant' | 'trimestre' | 'annee' | YYYY-MM
    """
    today = date.today()
    if not periode or periode == "mois_courant":
        date_debut = today.replace(day=1).isoformat()
        date_fin = today.isoformat()
    elif periode == "trimestre":
        mois_debut = ((today.month - 1) // 3) * 3 + 1
        date_debut = today.replace(month=mois_debut, day=1).isoformat()
        date_fin = today.isoformat()
    elif periode == "annee":
        date_debut = today.replace(month=1, day=1).isoformat()
        date_fin = today.isoformat()
    else:
        # format YYYY-MM
        date_debut = f"{periode}-01"
        date_fin = f"{periode}-31"

    conn = get_db()
    try:
        def scalar(row, key="c"):
            if not row: return 0
            v = row.get(key) if isinstance(row, dict) else row[0]
            return float(v or 0)

        revenus = scalar(conn.execute(
            "SELECT COALESCE(SUM(montant),0) as c FROM transactions WHERE entreprise_id=? AND type='revenu' AND date BETWEEN ? AND ?",
            (entreprise_id, date_debut, date_fin)
        ).fetchone())

        depenses = scalar(conn.execute(
            "SELECT COALESCE(SUM(montant),0) as c FROM transactions WHERE entreprise_id=? AND type='depense' AND date BETWEEN ? AND ?",
            (entreprise_id, date_debut, date_fin)
        ).fetchone())

        # Dépenses par catégorie
        rows_cat = conn.execute(
            "SELECT categorie, SUM(montant) as total FROM transactions WHERE entreprise_id=? AND type='depense' AND date BETWEEN ? AND ? GROUP BY categorie ORDER BY total DESC",
            (entreprise_id, date_debut, date_fin)
        ).fetchall()
        depenses_par_categorie = [{"categorie": r["categorie"], "montant": float(r["total"] or 0)} for r in rows_to_list(rows_cat)]

        # Évolution mensuelle (12 derniers mois)
        evolution = []
        for i in range(11, -1, -1):
            d = today.replace(day=1) - timedelta(days=i * 30)
            mois_str = d.strftime("%Y-%m")
            rev = scalar(conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions WHERE entreprise_id=? AND type='revenu' AND substr(date, 1, 7)=?",
                (entreprise_id, mois_str)
            ).fetchone())
            dep = scalar(conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions WHERE entreprise_id=? AND type='depense' AND substr(date, 1, 7)=?",
                (entreprise_id, mois_str)
            ).fetchone())
            evolution.append({"mois": mois_str, "revenus": rev, "depenses": dep, "marge": rev - dep})

        marge_nette = revenus - depenses
        taux_marge = round((marge_nette / revenus * 100), 1) if revenus > 0 else 0

        return {
            "periode": {"debut": date_debut, "fin": date_fin},
            "revenus": revenus,
            "depenses": depenses,
            "marge_nette": marge_nette,
            "taux_marge": taux_marge,
            "depenses_par_categorie": depenses_par_categorie,
            "evolution_mensuelle": evolution,
            "projection_tresorerie": calculer_projection(entreprise_id, 6)
        }
    finally:
        conn.close()


def calculer_projection(entreprise_id: str, nb_mois: int = 6) -> list:
    """Projection de trésorerie sur N mois basée sur la moyenne des 3 derniers mois."""
    today = date.today()
    conn = get_db()
    try:
        revenus_moy = 0
        depenses_moy = 0
        for i in range(1, 4):
            d = today.replace(day=1) - timedelta(days=i * 30)
            mois_str = d.strftime("%Y-%m")

            def sc(row):
                if not row: return 0
                v = row.get("c") if isinstance(row, dict) else row[0]
                return float(v or 0)

            r = sc(conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions WHERE entreprise_id=? AND type='revenu' AND substr(date, 1, 7)=?",
                (entreprise_id, mois_str)
            ).fetchone())
            d_val = sc(conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions WHERE entreprise_id=? AND type='depense' AND substr(date, 1, 7)=?",
                (entreprise_id, mois_str)
            ).fetchone())
            revenus_moy += r
            depenses_moy += d_val

        revenus_moy /= 3
        depenses_moy /= 3

        projection = []
        solde_cumul = 0
        for i in range(1, nb_mois + 1):
            d = today.replace(day=1) + timedelta(days=i * 30)
            solde_cumul += revenus_moy - depenses_moy
            projection.append({
                "mois": d.strftime("%Y-%m"),
                "revenus_prevus": round(revenus_moy, 2),
                "depenses_prevues": round(depenses_moy, 2),
                "solde_mensuel": round(revenus_moy - depenses_moy, 2),
                "tresorerie_cumulee": round(solde_cumul, 2)
            })
        return projection
    finally:
        conn.close()


# ─────────────────────────────────────────────
# ALERTES FINANCIÈRES IA
# ─────────────────────────────────────────────

def detecter_anomalies(entreprise_id: str) -> list:
    """Détecte les dépenses anormales par rapport à la moyenne."""
    conn = get_db()
    alertes = []
    try:
        categories = conn.execute(
            "SELECT DISTINCT categorie FROM transactions WHERE entreprise_id=? AND type='depense'",
            (entreprise_id,)
        ).fetchall()

        today = date.today()
        mois_courant = today.strftime("%Y-%m")

        for cat_row in rows_to_list(categories):
            cat = cat_row["categorie"]

            # Moyenne des 3 derniers mois pour cette catégorie
            totaux = []
            for i in range(1, 4):
                d = today.replace(day=1) - timedelta(days=i * 30)
                mois_str = d.strftime("%Y-%m")
                row = conn.execute(
                    "SELECT COALESCE(SUM(montant),0) as c FROM transactions WHERE entreprise_id=? AND type='depense' AND categorie=? AND substr(date, 1, 7)=?",
                    (entreprise_id, cat, mois_str)
                ).fetchone()
                val = float((row.get("c") if isinstance(row, dict) else row[0]) or 0)
                totaux.append(val)

            moyenne = sum(totaux) / 3 if totaux else 0
            if moyenne == 0:
                continue

            # Mois courant
            row_actuel = conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions WHERE entreprise_id=? AND type='depense' AND categorie=? AND substr(date, 1, 7)=?",
                (entreprise_id, cat, mois_courant)
            ).fetchone()
            actuel = float((row_actuel.get("c") if isinstance(row_actuel, dict) else row_actuel[0]) or 0)

            if actuel > moyenne * 1.5 and actuel - moyenne > 500:
                alertes.append({
                    "categorie": cat,
                    "montant_actuel": round(actuel, 2),
                    "montant_moyen": round(moyenne, 2),
                    "ecart_pct": round((actuel - moyenne) / moyenne * 100, 1),
                    "niveau": "critique" if actuel > moyenne * 2 else "attention"
                })

        return sorted(alertes, key=lambda x: x["ecart_pct"], reverse=True)
    finally:
        conn.close()
