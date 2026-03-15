"""
rh.py — Gestion RH pour PME 1-50 employés
Fiches employés, congés, heures, charges salariales simplifiées
"""

import json
from datetime import datetime, date, timedelta
from database import get_db, row_to_dict, rows_to_list


def _generer_id(prefix="EMP"):
    import time
    return f"{prefix}_{int(time.time() * 1000000)}"


# ─────────────────────────────────────────────
# EMPLOYÉS
# ─────────────────────────────────────────────

def creer_employe(entreprise_id: str, data: dict) -> dict:
    """Crée une fiche employé."""
    if not data.get("prenom") or not data.get("nom"):
        raise ValueError("Prénom et nom requis")

    conn = get_db()
    try:
        eid = _generer_id("EMP")
        conn.execute("""
            INSERT INTO employes
                (id, entreprise_id, prenom, nom, email, telephone, poste, departement,
                 type_contrat, date_embauche, salaire_brut, statut,
                 conges_acquis, conges_pris, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eid, entreprise_id,
            data["prenom"], data["nom"],
            data.get("email", ""),
            data.get("telephone", ""),
            data.get("poste", ""),
            data.get("departement", ""),
            data.get("type_contrat", "CDI"),
            data.get("date_embauche", date.today().isoformat()),
            float(data.get("salaire_brut", 0)),
            data.get("statut", "actif"),
            float(data.get("conges_acquis", 25)),
            float(data.get("conges_pris", 0)),
            data.get("notes", "")
        ))
        conn.commit()
        return row_to_dict(conn.execute("SELECT * FROM employes WHERE id=?", (eid,)).fetchone())
    finally:
        conn.close()


def get_employes(entreprise_id: str, statut: str = None) -> list:
    conn = get_db()
    try:
        if statut:
            rows = conn.execute(
                "SELECT * FROM employes WHERE entreprise_id=? AND statut=? ORDER BY nom, prenom",
                (entreprise_id, statut)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM employes WHERE entreprise_id=? ORDER BY nom, prenom",
                (entreprise_id,)
            ).fetchall()
        employes = rows_to_list(rows)
        # Ajouter charges calculées pour chaque employé
        for e in employes:
            e["charges_patronales"] = calculer_charges(e.get("salaire_brut", 0))["charges_patronales"]
            e["cout_total_employeur"] = calculer_charges(e.get("salaire_brut", 0))["cout_total_employeur"]
        return employes
    finally:
        conn.close()


def get_employe(eid: str, entreprise_id: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM employes WHERE id=? AND entreprise_id=?", (eid, entreprise_id)
        ).fetchone()
        if not row:
            return None
        e = row_to_dict(row)
        e.update(calculer_charges(e.get("salaire_brut", 0)))
        return e
    finally:
        conn.close()


def modifier_employe(eid: str, entreprise_id: str, data: dict) -> dict:
    conn = get_db()
    try:
        champs_ok = ["prenom", "nom", "email", "telephone", "poste", "departement",
                     "type_contrat", "date_embauche", "salaire_brut", "statut",
                     "conges_acquis", "conges_pris", "notes"]
        sets, vals = [], []
        for k in champs_ok:
            if k in data:
                sets.append(f"{k}=?")
                vals.append(data[k])
        if sets:
            vals += [eid, entreprise_id]
            conn.execute(f"UPDATE employes SET {','.join(sets)} WHERE id=? AND entreprise_id=?", vals)
            conn.commit()
        return get_employe(eid, entreprise_id)
    finally:
        conn.close()


def supprimer_employe(eid: str, entreprise_id: str) -> bool:
    conn = get_db()
    try:
        conn.execute("DELETE FROM employes WHERE id=? AND entreprise_id=?", (eid, entreprise_id))
        conn.commit()
        return True
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CHARGES SALARIALES SIMPLIFIÉES (France)
# ─────────────────────────────────────────────

def calculer_charges(salaire_brut: float, regime: str = "general") -> dict:
    """
    Calcul simplifié des charges salariales françaises.
    Taux approximatifs 2024 — non contractuel, indicatif.
    """
    if salaire_brut <= 0:
        return {
            "salaire_brut": 0,
            "charges_salariales": 0,
            "salaire_net": 0,
            "charges_patronales": 0,
            "cout_total_employeur": 0,
            "detail_charges": {}
        }

    # Charges salariales (~22% du brut en moyenne)
    taux_salarial = 0.22
    charges_salariales = salaire_brut * taux_salarial
    salaire_net = salaire_brut - charges_salariales

    # Charges patronales (~42% du brut en moyenne)
    taux_patronal = 0.42
    charges_patronales = salaire_brut * taux_patronal
    cout_total = salaire_brut + charges_patronales

    return {
        "salaire_brut": round(salaire_brut, 2),
        "charges_salariales": round(charges_salariales, 2),
        "salaire_net": round(salaire_net, 2),
        "charges_patronales": round(charges_patronales, 2),
        "cout_total_employeur": round(cout_total, 2),
        "detail_charges": {
            "securite_sociale": round(salaire_brut * 0.13, 2),
            "retraite": round(salaire_brut * 0.10, 2),
            "chomage": round(salaire_brut * 0.04, 2),
            "formation": round(salaire_brut * 0.01, 2),
            "prevoyance": round(salaire_brut * 0.015, 2),
        },
        "note": "Taux indicatifs 2024 — consultez un expert-comptable pour le calcul officiel"
    }


def get_masse_salariale(entreprise_id: str) -> dict:
    """Calcule la masse salariale totale de l'entreprise."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT salaire_brut, statut FROM employes WHERE entreprise_id=?",
            (entreprise_id,)
        ).fetchall()
        employes = rows_to_list(rows)

        actifs = [e for e in employes if e.get("statut") == "actif"]
        total_brut = sum(e.get("salaire_brut", 0) for e in actifs)
        charges_pat = sum(e.get("salaire_brut", 0) * 0.42 for e in actifs)

        return {
            "nb_employes_actifs": len(actifs),
            "total_salaires_bruts": round(total_brut, 2),
            "charges_patronales_totales": round(charges_pat, 2),
            "cout_total_mensuel": round(total_brut + charges_pat, 2),
            "cout_total_annuel": round((total_brut + charges_pat) * 12, 2)
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CONGÉS & ABSENCES
# ─────────────────────────────────────────────

def creer_conge(entreprise_id: str, data: dict) -> dict:
    """Crée une demande de congé."""
    if not data.get("employe_id") or not data.get("date_debut") or not data.get("date_fin"):
        raise ValueError("Employé, date début et date fin requis")

    conn = get_db()
    try:
        # Calculer nb jours ouvrés
        debut = datetime.strptime(data["date_debut"], "%Y-%m-%d").date()
        fin = datetime.strptime(data["date_fin"], "%Y-%m-%d").date()
        nb_jours = sum(1 for i in range((fin - debut).days + 1)
                       if (debut + timedelta(days=i)).weekday() < 5)

        cid = _generer_id("CON")
        conn.execute("""
            INSERT INTO conges
                (id, entreprise_id, employe_id, type, date_debut, date_fin,
                 nb_jours, statut, motif)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cid, entreprise_id,
            data["employe_id"],
            data.get("type", "conges_payes"),
            data["date_debut"],
            data["date_fin"],
            nb_jours,
            "en_attente",
            data.get("motif", "")
        ))
        conn.commit()
        return row_to_dict(conn.execute("SELECT * FROM conges WHERE id=?", (cid,)).fetchone())
    finally:
        conn.close()


def get_conges(entreprise_id: str, employe_id: str = None, statut: str = None) -> list:
    conn = get_db()
    try:
        sql = "SELECT c.*, e.prenom, e.nom FROM conges c LEFT JOIN employes e ON c.employe_id=e.id WHERE c.entreprise_id=?"
        params = [entreprise_id]
        if employe_id:
            sql += " AND c.employe_id=?"
            params.append(employe_id)
        if statut:
            sql += " AND c.statut=?"
            params.append(statut)
        sql += " ORDER BY c.date_debut DESC"
        return rows_to_list(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def valider_conge(cid: str, entreprise_id: str, statut: str, commentaire: str = "") -> dict:
    """Valide ou refuse une demande de congé."""
    if statut not in ("approuve", "refuse"):
        raise ValueError("Statut doit être 'approuve' ou 'refuse'")

    conn = get_db()
    try:
        conge = row_to_dict(conn.execute("SELECT * FROM conges WHERE id=? AND entreprise_id=?",
                                          (cid, entreprise_id)).fetchone())
        if not conge:
            raise ValueError("Congé non trouvé")

        conn.execute("UPDATE conges SET statut=?, commentaire_valideur=? WHERE id=?",
                     (statut, commentaire, cid))

        # Si approuvé, décrémenter les congés disponibles
        if statut == "approuve" and conge.get("type") == "conges_payes":
            conn.execute(
                "UPDATE employes SET conges_pris = conges_pris + ? WHERE id=? AND entreprise_id=?",
                (conge["nb_jours"], conge["employe_id"], entreprise_id)
            )
        conn.commit()
        return row_to_dict(conn.execute("SELECT * FROM conges WHERE id=?", (cid,)).fetchone())
    finally:
        conn.close()


# ─────────────────────────────────────────────
# SUIVI DES HEURES
# ─────────────────────────────────────────────

def pointer_heures(entreprise_id: str, data: dict) -> dict:
    """Enregistre un pointage d'heures."""
    if not data.get("employe_id") or not data.get("date"):
        raise ValueError("Employé et date requis")

    conn = get_db()
    try:
        # Supprimer si déjà pointé ce jour
        conn.execute(
            "DELETE FROM pointages WHERE employe_id=? AND date=? AND entreprise_id=?",
            (data["employe_id"], data["date"], entreprise_id)
        )
        pid = _generer_id("PTG")
        heures_supp = max(0, float(data.get("heures_travaillees", 0)) - 8)
        conn.execute("""
            INSERT INTO pointages
                (id, entreprise_id, employe_id, date, heure_arrivee, heure_depart,
                 heures_travaillees, heures_supplementaires, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid, entreprise_id,
            data["employe_id"],
            data["date"],
            data.get("heure_arrivee", "09:00"),
            data.get("heure_depart", "18:00"),
            float(data.get("heures_travaillees", 8)),
            heures_supp,
            data.get("notes", "")
        ))
        conn.commit()
        return row_to_dict(conn.execute("SELECT * FROM pointages WHERE id=?", (pid,)).fetchone())
    finally:
        conn.close()


def get_pointages(entreprise_id: str, employe_id: str = None, mois: str = None) -> list:
    conn = get_db()
    try:
        sql = "SELECT p.*, e.prenom, e.nom FROM pointages p LEFT JOIN employes e ON p.employe_id=e.id WHERE p.entreprise_id=?"
        params = [entreprise_id]
        if employe_id:
            sql += " AND p.employe_id=?"
            params.append(employe_id)
        if mois:
            # Compatible SQLite et PostgreSQL (date stockée au format texte ISO YYYY-MM-DD)
            sql += " AND substr(p.date, 1, 7)=?"
            params.append(mois)
        sql += " ORDER BY p.date DESC"
        return rows_to_list(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


# ─────────────────────────────────────────────
# ÉVALUATIONS
# ─────────────────────────────────────────────

def creer_evaluation(entreprise_id: str, data: dict) -> dict:
    if not data.get("employe_id"):
        raise ValueError("Employé requis")
    conn = get_db()
    try:
        vid = _generer_id("EVA")
        conn.execute("""
            INSERT INTO evaluations
                (id, entreprise_id, employe_id, periode, note_globale,
                 competences, objectifs_atteints, commentaire, points_forts, axes_amelioration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vid, entreprise_id,
            data["employe_id"],
            data.get("periode", date.today().strftime("%Y")),
            float(data.get("note_globale", 0)),
            json.dumps(data.get("competences", {})),
            data.get("objectifs_atteints", ""),
            data.get("commentaire", ""),
            data.get("points_forts", ""),
            data.get("axes_amelioration", "")
        ))
        conn.commit()
        return row_to_dict(conn.execute("SELECT * FROM evaluations WHERE id=?", (vid,)).fetchone())
    finally:
        conn.close()


def get_evaluations(entreprise_id: str, employe_id: str = None) -> list:
    conn = get_db()
    try:
        if employe_id:
            rows = conn.execute(
                "SELECT * FROM evaluations WHERE entreprise_id=? AND employe_id=? ORDER BY periode DESC",
                (entreprise_id, employe_id)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM evaluations WHERE entreprise_id=? ORDER BY periode DESC",
                (entreprise_id,)
            ).fetchall()
        return rows_to_list(rows)
    finally:

        conn.close()
