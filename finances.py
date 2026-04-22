"""
finances.py — Gestion financière PME
Transactions, catégories, trésorerie, projections, import CSV
NOTE: Les salaires ne sont PAS générés automatiquement.
      Saisir manuellement dans Finances > + Transaction > Dépense > Salaires.
"""

import json
import csv
import io
import calendar
from datetime import datetime, date, timedelta
from database import get_db, row_to_dict, rows_to_list


def _generer_id(prefix="TRX"):
    import time
    return f"{prefix}_{int(time.time() * 1000000)}"


# ─────────────────────────────────────────────
# CATÉGORISATION AUTOMATIQUE
# ─────────────────────────────────────────────

def _auto_categoriser(description: str) -> str:
    """Catégorisation automatique étendue par mots-clés."""
    desc = description.lower()

    REGLES = [
        ("salaires",          ["salaire", "paie", "virement employe", "virement employé",
                                "urssaf", "cotisation", "dsn"]),
        ("loyer",             ["loyer", "bail", "foncière", "fonciere",
                                "immobilier", "charges locatives"]),
        ("charges_fixes",     ["edf", "engie", "orange", "sfr", "bouygues", "free",
                                "eau", "gaz", "electricite", "électricité", "internet",
                                "ovh", "scaleway", "online.net",
                                "tenue de compte", "frais bancaire"]),
        ("fournitures",       ["amazon", "fnac", "darty", "fourniture", "bureau",
                                "papier", "office depot", "staples", "ldlc"]),
        ("marketing",         ["google", "facebook", "meta", "publicite", "publicité",
                                "ads", "marketing", "instagram", "linkedin", "twitter",
                                "tiktok", "mailchimp"]),
        ("deplacement_repas", ["restaurant", "repas", "hotel", "hôtel", "train", "sncf",
                                "avion", "air france", "easyjet", "taxi", "uber", "bolt",
                                "deliveroo", "just eat", "uber eats", "parking"]),
        ("assurances",        ["assurance", "mutuelle", "maif", "matmut", "axa", "macif",
                                "covea", "allianz", "groupama"]),
        ("honoraires",        ["expert", "comptable", "avocat", "juridique", "notaire",
                                "consultant", "freelance", "prestataire", "agence"]),
        ("revenus",           ["facture", "honoraires client", "paiement client", "reglement",
                                "règlement", "acompte", "virement client", "virement recu",
                                "prestation", "invoice"]),
    ]

    for categorie, mots in REGLES:
        if any(m in desc for m in mots):
            return categorie

    return "autre"


def _parser_date(date_str: str) -> str:
    """Tente de parser différents formats de date bancaire."""
    if not date_str:
        return date.today().isoformat()
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date.today().isoformat()


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
        sql    = "SELECT * FROM transactions WHERE entreprise_id=?"
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
            conn.execute(
                f"UPDATE transactions SET {','.join(sets)} WHERE id=? AND entreprise_id=?",
                vals
            )
            conn.commit()
        return row_to_dict(
            conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
        )
    finally:
        conn.close()


def supprimer_transaction(tid: str, entreprise_id: str) -> bool:
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM transactions WHERE id=? AND entreprise_id=?",
            (tid, entreprise_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ─────────────────────────────────────────────
# IMPORT CSV BANCAIRE — VERSION AMÉLIORÉE
# ─────────────────────────────────────────────

def importer_csv(entreprise_id: str, contenu_csv: str, mapping: dict = None) -> dict:
    """
    Importe des transactions depuis un relevé CSV bancaire brut.
    Détecte automatiquement le séparateur et les colonnes.
    Supporte : montant unique ET Débit/Crédit séparés (banques françaises).
    """
    if not contenu_csv or not contenu_csv.strip():
        return {"importees": 0, "doublons_ignores": 0, "erreurs": ["Fichier vide"], "total_lignes": 0}

    # Détecter le séparateur
    premiere_ligne = contenu_csv.split("\n")[0]
    sep = ";"
    if premiere_ligne.count(",") > premiere_ligne.count(";"):
        sep = ","
    elif "\t" in premiere_ligne:
        sep = "\t"

    ALIASES = {
        "date":        ["date", "date opération", "date operation", "date valeur",
                        "date comptable", "date transaction", "date mouvement",
                        "booking date", "transaction date"],
        "montant":     ["montant", "amount", "montant eur", "montant €",
                        "valeur", "net amount"],
        "debit":       ["débit", "debit", "débit ttc", "montant débit",
                        "montant debit", "debit eur"],
        "credit":      ["crédit", "credit", "crédit ttc", "montant crédit",
                        "montant credit", "credit eur"],
        "description": ["libellé", "libelle", "description", "label", "motif",
                        "intitulé", "intitule", "operation", "wording",
                        "transaction details", "narrative"],
        "reference":   ["ref", "référence", "reference", "no", "numéro",
                        "id", "transaction id"],
    }

    reader = csv.DictReader(io.StringIO(contenu_csv), delimiter=sep)
    if not reader.fieldnames:
        return {"importees": 0, "doublons_ignores": 0, "erreurs": ["Format invalide"], "total_lignes": 0}

    headers_norm = {h.lower().strip(): h for h in reader.fieldnames}

    if not mapping:
        mapping = {}
        for field, aliases in ALIASES.items():
            for alias in aliases:
                if alias in headers_norm:
                    mapping[field] = headers_norm[alias]
                    break

    # Détecter format Débit/Crédit
    format_debit_credit = bool(mapping.get("debit") and mapping.get("credit"))

    importees = 0
    erreurs   = []
    doublons  = 0
    conn = get_db()

    try:
        for i, ligne in enumerate(reader):
            try:
                ligne_norm = {k.lower().strip(): (v or "").strip() for k, v in ligne.items()}

                def parse_float(raw):
                    if not raw: return 0.0
                    return float(
                        raw.replace("\xa0", "").replace(" ", "").replace(",", ".")
                        .replace("−", "-").replace("–", "-")
                    ) or 0.0

                if format_debit_credit:
                    col_d = (mapping.get("debit")  or "").lower()
                    col_c = (mapping.get("credit") or "").lower()
                    debit  = parse_float(ligne_norm.get(col_d, "0"))
                    credit = parse_float(ligne_norm.get(col_c, "0"))
                    if credit > 0:
                        montant  = credit
                        type_txn = "revenu"
                    elif debit > 0:
                        montant  = debit
                        type_txn = "depense"
                    else:
                        continue
                else:
                    col_m    = (mapping.get("montant") or "montant").lower()
                    raw_m    = ligne_norm.get(col_m, "0")
                    val      = parse_float(raw_m)
                    if val == 0:
                        continue
                    type_txn = "revenu" if val >= 0 else "depense"
                    montant  = abs(val)

                col_date = (mapping.get("date")        or "date").lower()
                col_desc = (mapping.get("description") or "libelle").lower()
                col_ref  = (mapping.get("reference")   or "ref").lower()

                date_parsed = _parser_date(ligne_norm.get(col_date, ""))
                desc        = ligne_norm.get(col_desc, "") or f"Import ligne {i + 1}"
                ref         = ligne_norm.get(col_ref, "")

                doublon = conn.execute(
                    "SELECT id FROM transactions "
                    "WHERE entreprise_id=? AND date=? AND montant=? AND description=?",
                    (entreprise_id, date_parsed, montant, desc)
                ).fetchone()
                if doublon:
                    doublons += 1
                    continue

                categorie = _auto_categoriser(desc)
                tid       = _generer_id("TRX")
                conn.execute("""
                    INSERT INTO transactions
                        (id, entreprise_id, type, montant, categorie, description, date, reference)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (tid, entreprise_id, type_txn, montant, categorie, desc, date_parsed, ref))
                importees += 1

            except Exception as e:
                erreurs.append(f"Ligne {i + 1}: {str(e)}")

        conn.commit()
        return {
            "importees":        importees,
            "doublons_ignores": doublons,
            "erreurs":          erreurs[:10],
            "total_lignes":     importees + doublons + len(erreurs),
        }
    finally:
        conn.close()


def importer_bulk(entreprise_id: str, transactions: list) -> dict:
    """
    Importe des transactions déjà parsées et catégorisées côté front.
    """
    if not transactions:
        return {"importees": 0, "doublons_ignores": 0, "erreurs": [], "total_lignes": 0}

    CATS_VALIDES = [
        "revenus", "salaires", "loyer", "charges_fixes", "fournitures",
        "marketing", "deplacement_repas", "assurances", "honoraires", "autre",
    ]

    importees = 0
    doublons  = 0
    erreurs   = []
    conn = get_db()

    try:
        for i, txn in enumerate(transactions):
            try:
                montant = float(txn.get("montant", 0))
                if montant <= 0:
                    erreurs.append(f"Ligne {i + 1}: montant invalide ({montant})")
                    continue

                type_txn = txn.get("type", "")
                if type_txn not in ("revenu", "depense"):
                    erreurs.append(f"Ligne {i + 1}: type invalide ({type_txn})")
                    continue

                date_parsed = _parser_date(str(txn.get("date", "")))
                desc        = str(txn.get("description", f"Import {i + 1}"))[:500]
                categorie   = txn.get("categorie", "autre")
                ref         = str(txn.get("reference", ""))[:200]

                if categorie not in CATS_VALIDES:
                    categorie = "autre"

                doublon = conn.execute(
                    "SELECT id FROM transactions "
                    "WHERE entreprise_id=? AND date=? AND montant=? AND description=?",
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
                """, (tid, entreprise_id, type_txn, montant, categorie, desc, date_parsed, ref))
                importees += 1

            except Exception as e:
                erreurs.append(f"Ligne {i + 1}: {str(e)}")

        conn.commit()
        return {
            "importees":        importees,
            "doublons_ignores": doublons,
            "erreurs":          erreurs[:10],
            "total_lignes":     len(transactions),
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────
# GÉNÉRATION PAIE
# Crée une transaction de dépense par employé actif pour le mois donné.
# Détecte les doublons : si une transaction salaire existe déjà pour cet
# employé et ce mois, elle est ignorée (évite les doubles avec import CSV).
# ─────────────────────────────────────────────

def generer_paie_mensuelle(entreprise_id: str, mois: str) -> dict:
    """
    Génère les transactions de salaire pour tous les employés actifs du mois donné.
    mois : format YYYY-MM
    - Crée une transaction de dépense / catégorie 'salaires' par employé
    - Ignore les doublons (même employé, même mois déjà présent)
    - Retourne le détail : generes, doublons, total_brut
    """
    conn = get_db()
    try:
        # Récupérer les employés actifs avec un salaire
        employes = rows_to_list(conn.execute(
            "SELECT id, prenom, nom, salaire_brut FROM employes "
            "WHERE entreprise_id=? AND statut='actif' AND salaire_brut > 0",
            (entreprise_id,)
        ).fetchall())

        if not employes:
            return {"generes": 0, "doublons": 0, "total_brut": 0, "detail": [],
                    "message": "Aucun employé actif avec un salaire défini."}

        generes   = 0
        doublons  = 0
        total_brut = 0
        detail    = []
        date_paie = f"{mois}-28"  # Jour de paie conventionnel

        for emp in employes:
            prenom = emp.get("prenom", "")
            nom    = emp.get("nom", "")
            brut   = float(emp.get("salaire_brut") or 0)
            emp_id = emp.get("id")
            desc   = f"Salaire {prenom} {nom}"

            # Vérifier si une transaction salaire existe déjà pour cet employé ce mois
            existant = conn.execute(
                "SELECT id FROM transactions "
                "WHERE entreprise_id=? AND type='depense' AND categorie='salaires' "
                "AND employe_id=? AND substr(date,1,7)=?",
                (entreprise_id, emp_id, mois)
            ).fetchone()

            if existant:
                doublons += 1
                detail.append({"employe": f"{prenom} {nom}", "montant": brut, "statut": "doublon"})
                continue

            # Créer la transaction
            tid = _generer_id("TRX")
            conn.execute("""
                INSERT INTO transactions
                    (id, entreprise_id, type, montant, categorie, description,
                     date, mode_paiement, employe_id)
                VALUES (?, ?, 'depense', ?, 'salaires', ?, ?, 'virement', ?)
            """, (tid, entreprise_id, brut, desc, date_paie, emp_id))

            generes    += 1
            total_brut += brut
            detail.append({"employe": f"{prenom} {nom}", "montant": brut, "statut": "cree"})

        conn.commit()
        return {
            "generes":    generes,
            "doublons":   doublons,
            "total_brut": round(total_brut, 2),
            "detail":     detail,
            "message":    f"{generes} salaire(s) généré(s) pour {mois}, {doublons} doublon(s) ignoré(s)."
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────
# TABLEAU DE BORD FINANCIER
# ─────────────────────────────────────────────

def get_dashboard_financier(entreprise_id: str, periode: str = None) -> dict:
    """
    Retourne les KPIs financiers pour le dashboard.
    periode: 'mois_courant' | 'trimestre' | 'annee' | YYYY-MM
    """
    today = date.today()

    # ── CORRECTION : date_fin couvre toujours la fin complète de la période ──
    if not periode or periode == "mois_courant":
        date_debut   = today.replace(day=1).isoformat()
        dernier_jour = calendar.monthrange(today.year, today.month)[1]
        date_fin     = today.replace(day=dernier_jour).isoformat()
    elif periode == "trimestre":
        mois_debut   = ((today.month - 1) // 3) * 3 + 1
        mois_fin     = mois_debut + 2
        dernier_jour = calendar.monthrange(today.year, mois_fin)[1]
        date_debut   = today.replace(month=mois_debut, day=1).isoformat()
        date_fin     = today.replace(month=mois_fin, day=dernier_jour).isoformat()
    elif periode == "annee":
        date_debut = today.replace(month=1, day=1).isoformat()
        date_fin   = today.replace(month=12, day=31).isoformat()
    else:
        # format YYYY-MM
        annee, num_mois = int(periode[:4]), int(periode[5:7])
        dernier_jour    = calendar.monthrange(annee, num_mois)[1]
        date_debut      = f"{periode}-01"
        date_fin        = f"{periode}-{dernier_jour:02d}"

    conn = get_db()
    try:
        def scalar(row, key="c"):
            if not row: return 0
            v = row.get(key) if isinstance(row, dict) else row[0]
            return float(v or 0)

        revenus = scalar(conn.execute(
            "SELECT COALESCE(SUM(montant),0) as c FROM transactions "
            "WHERE entreprise_id=? AND type='revenu' AND date BETWEEN ? AND ?",
            (entreprise_id, date_debut, date_fin)
        ).fetchone())

        depenses = scalar(conn.execute(
            "SELECT COALESCE(SUM(montant),0) as c FROM transactions "
            "WHERE entreprise_id=? AND type='depense' AND date BETWEEN ? AND ?",
            (entreprise_id, date_debut, date_fin)
        ).fetchone())

        # Dépenses par catégorie
        rows_cat = conn.execute(
            "SELECT categorie, SUM(montant) as total FROM transactions "
            "WHERE entreprise_id=? AND type='depense' AND date BETWEEN ? AND ? "
            "GROUP BY categorie ORDER BY total DESC",
            (entreprise_id, date_debut, date_fin)
        ).fetchall()
        depenses_par_categorie = [
            {"categorie": r["categorie"], "montant": float(r["total"] or 0)}
            for r in rows_to_list(rows_cat)
        ]

        # Évolution mensuelle (12 derniers mois)
        evolution = []
        for i in range(11, -1, -1):
            d        = today.replace(day=1) - timedelta(days=i * 30)
            mois_str = d.strftime("%Y-%m")
            rev = scalar(conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions "
                "WHERE entreprise_id=? AND type='revenu' AND substr(date, 1, 7)=?",
                (entreprise_id, mois_str)
            ).fetchone())
            dep = scalar(conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions "
                "WHERE entreprise_id=? AND type='depense' AND substr(date, 1, 7)=?",
                (entreprise_id, mois_str)
            ).fetchone())
            evolution.append({"mois": mois_str, "revenus": rev, "depenses": dep, "marge": rev - dep})

        marge_nette = revenus - depenses
        taux_marge  = round((marge_nette / revenus * 100), 1) if revenus > 0 else 0

        return {
            "periode":                {"debut": date_debut, "fin": date_fin},
            "revenus":                revenus,
            "depenses":               depenses,
            "marge_nette":            marge_nette,
            "taux_marge":             taux_marge,
            "depenses_par_categorie": depenses_par_categorie,
            "evolution_mensuelle":    evolution,
            "projection_tresorerie":  calculer_projection(entreprise_id, 6),
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────
# PROJECTION TRÉSORERIE
# ─────────────────────────────────────────────

def calculer_projection(entreprise_id: str, nb_mois: int = 6) -> list:
    """Projection de trésorerie sur N mois basée sur la moyenne des 3 derniers mois."""
    today = date.today()
    conn  = get_db()

    def sc(row):
        if not row: return 0
        v = row.get("c") if isinstance(row, dict) else row[0]
        return float(v or 0)

    try:
        revenus_moy  = 0
        depenses_moy = 0

        for i in range(1, 4):
            d        = today.replace(day=1) - timedelta(days=i * 30)
            mois_str = d.strftime("%Y-%m")

            revenus_moy += sc(conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions "
                "WHERE entreprise_id=? AND type='revenu' AND substr(date, 1, 7)=?",
                (entreprise_id, mois_str)
            ).fetchone())

            depenses_moy += sc(conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions "
                "WHERE entreprise_id=? AND type='depense' AND substr(date, 1, 7)=?",
                (entreprise_id, mois_str)
            ).fetchone())

        revenus_moy  /= 3
        depenses_moy /= 3

        # NOTE: La masse salariale n'est PAS ajoutée ici automatiquement.
        # Elle n'est projetée que si des transactions de salaires réelles existent.

        projection  = []
        solde_cumul = 0
        for i in range(1, nb_mois + 1):
            d = today.replace(day=1) + timedelta(days=i * 30)
            solde_cumul += revenus_moy - depenses_moy
            projection.append({
                "mois":               d.strftime("%Y-%m"),
                "revenus_prevus":     round(revenus_moy, 2),
                "depenses_prevues":   round(depenses_moy, 2),
                "solde_mensuel":      round(revenus_moy - depenses_moy, 2),
                "tresorerie_cumulee": round(solde_cumul, 2),
                "dont_salaires":      0,
            })
        return projection
    finally:
        conn.close()


# ─────────────────────────────────────────────
# DÉTECTION ANOMALIES
# ─────────────────────────────────────────────

def detecter_anomalies(entreprise_id: str) -> list:
    """Détecte les dépenses anormales par rapport à la moyenne des 3 derniers mois."""
    conn    = get_db()
    alertes = []
    try:
        categories = conn.execute(
            "SELECT DISTINCT categorie FROM transactions "
            "WHERE entreprise_id=? AND type='depense'",
            (entreprise_id,)
        ).fetchall()

        today        = date.today()
        mois_courant = today.strftime("%Y-%m")

        for cat_row in rows_to_list(categories):
            cat    = cat_row["categorie"]
            totaux = []

            for i in range(1, 4):
                d        = today.replace(day=1) - timedelta(days=i * 30)
                mois_str = d.strftime("%Y-%m")
                row = conn.execute(
                    "SELECT COALESCE(SUM(montant),0) as c FROM transactions "
                    "WHERE entreprise_id=? AND type='depense' AND categorie=? AND substr(date, 1, 7)=?",
                    (entreprise_id, cat, mois_str)
                ).fetchone()
                val = float((row.get("c") if isinstance(row, dict) else row[0]) or 0)
                totaux.append(val)

            moyenne = sum(totaux) / 3 if totaux else 0
            if moyenne == 0:
                continue

            # Mois courant
            row_actuel = conn.execute(
                "SELECT COALESCE(SUM(montant),0) as c FROM transactions "
                "WHERE entreprise_id=? AND type='depense' AND categorie=? AND substr(date, 1, 7)=?",
                (entreprise_id, cat, mois_courant)
            ).fetchone()
            actuel = float((row_actuel.get("c") if isinstance(row_actuel, dict) else row_actuel[0]) or 0)

            if actuel > moyenne * 1.5 and actuel - moyenne > 500:
                alertes.append({
                    "categorie":      cat,
                    "montant_actuel": round(actuel, 2),
                    "montant_moyen":  round(moyenne, 2),
                    "ecart_pct":      round((actuel - moyenne) / moyenne * 100, 1),
                    "niveau":         "critique" if actuel > moyenne * 2 else "attention"
                })

        return sorted(alertes, key=lambda x: x["ecart_pct"], reverse=True)
    finally:
        conn.close()