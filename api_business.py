"""
api_business.py — Module Business : Entreprises, Finances, RH
Blueprint Flask nommé 'business' — compatible avec api.py
"""

from flask import Blueprint, request, jsonify
from functools import wraps
from datetime import datetime, date, timedelta
import json
import time

from database import get_db, row_to_dict, rows_to_list
from auth import verifier_token

# ── BLUEPRINT ── (nom de variable = 'business', obligatoire pour api.py)
business = Blueprint('business', __name__)


# ─────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────

def ok(data, message="Succès", code=200):
    return jsonify({"statut": "ok", "message": message, "data": data}), code

def err(message, code=400):
    return jsonify({"statut": "erreur", "message": message}), code

def get_json():
    return request.get_json() or {}

def gen_id(prefix="ID"):
    return f"{prefix}_{int(time.time() * 1000000)}"

def token_requis(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            return err("Token manquant", 401)
        user_id = verifier_token(token)
        if not user_id:
            return err("Token invalide ou expiré", 401)
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated

def get_entreprise_ids(user_id):
    """Retourne les IDs d'entreprises accessibles par l'utilisateur."""
    conn = get_db()
    rows = conn.execute("""
        SELECT e.id FROM entreprises e
        JOIN membres_entreprise m ON m.entreprise_id = e.id
        WHERE m.user_id = ? AND m.actif = 1
    """, (user_id,)).fetchall()
    conn.close()
    return [r["id"] for r in rows]

def check_access(entreprise_id, user_id):
    """Vérifie que l'utilisateur a accès à cette entreprise."""
    conn = get_db()
    row = conn.execute("""
        SELECT role FROM membres_entreprise
        WHERE entreprise_id = ? AND user_id = ? AND actif = 1
    """, (entreprise_id, user_id)).fetchone()
    conn.close()
    return row["role"] if row else None


# ─────────────────────────────────────────────
# ENTREPRISES
# ─────────────────────────────────────────────

@business.route("/business/entreprises", methods=["GET"])
@token_requis
def get_entreprises():
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT e.*, m.role FROM entreprises e
            JOIN membres_entreprise m ON m.entreprise_id = e.id
            WHERE m.user_id = ? AND m.actif = 1
            ORDER BY e.created_at DESC
        """, (request.user_id,)).fetchall()
        conn.close()
        entreprises = []
        for r in rows_to_list(rows):
            r["role_label"] = {
                "admin": "Dirigeant / CEO",
                "rh": "Responsable RH",
                "comptable": "Comptable",
                "commercial": "Commercial",
                "employe": "Employé"
            }.get(r.get("role", ""), r.get("role", ""))
            entreprises.append(r)
        return ok({"entreprises": entreprises, "total": len(entreprises)})
    except Exception as e:
        return err(str(e))


@business.route("/business/entreprises", methods=["POST"])
@token_requis
def creer_entreprise():
    try:
        data = get_json()
        if not data.get("nom"):
            return err("Nom de l'entreprise requis")
        conn = get_db()
        eid = gen_id("ENT")
        conn.execute("""
            INSERT INTO entreprises
                (id, nom, siren, secteur, adresse, telephone, email,
                 tva_intracommunautaire, forme_juridique, date_creation_entreprise,
                 nb_employes_max, plan, owner_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eid, data["nom"],
            data.get("siren", ""), data.get("secteur", ""),
            data.get("adresse", ""), data.get("telephone", ""),
            data.get("email", ""), data.get("tva_intracommunautaire", ""),
            data.get("forme_juridique", "SAS"),
            data.get("date_creation_entreprise", ""),
            int(data.get("nb_employes_max", 50)),
            data.get("plan", "business"), request.user_id
        ))
        mid = gen_id("MBR")
        conn.execute("""
            INSERT INTO membres_entreprise (id, entreprise_id, user_id, role, actif)
            VALUES (?, ?, ?, 'admin', 1)
        """, (mid, eid, request.user_id))
        conn.commit()
        row = row_to_dict(conn.execute("SELECT * FROM entreprises WHERE id=?", (eid,)).fetchone())
        conn.close()
        row["role"] = "admin"
        row["role_label"] = "Dirigeant / CEO"
        return ok(row, "Entreprise créée", 201)
    except Exception as e:
        return err(str(e))


@business.route("/business/entreprises/<eid>", methods=["PUT"])
@token_requis
def update_entreprise(eid):
    try:
        if not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        data = get_json()
        champs = ["nom", "siren", "secteur", "adresse", "telephone", "email",
                  "tva_intracommunautaire", "forme_juridique", "nb_employes_max"]
        sets, vals = [], []
        for k in champs:
            if k in data:
                sets.append(f"{k}=?")
                vals.append(data[k])
        if sets:
            vals.append(eid)
            conn = get_db()
            conn.execute(f"UPDATE entreprises SET {','.join(sets)} WHERE id=?", vals)
            conn.commit()
            row = row_to_dict(conn.execute("SELECT * FROM entreprises WHERE id=?", (eid,)).fetchone())
            conn.close()
            return ok(row, "Entreprise mise à jour")
        return err("Aucun champ à modifier")
    except Exception as e:
        return err(str(e))


# ─────────────────────────────────────────────
# MEMBRES
# ─────────────────────────────────────────────

@business.route("/business/membres", methods=["GET"])
@token_requis
def get_membres():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        conn = get_db()
        rows = conn.execute("""
            SELECT m.*, u.prenom, u.nom, u.email, u.metier
            FROM membres_entreprise m
            JOIN users u ON u.id = m.user_id
            WHERE m.entreprise_id = ? AND m.actif = 1
        """, (eid,)).fetchall()
        conn.close()
        membres = rows_to_list(rows)
        for m in membres:
            m["role_label"] = {
                "admin": "Administrateur", "rh": "Responsable RH",
                "comptable": "Comptable", "commercial": "Commercial",
                "employe": "Employé"
            }.get(m.get("role", ""), m.get("role", ""))
        return ok({"membres": membres, "total": len(membres)})
    except Exception as e:
        return err(str(e))


@business.route("/business/membres", methods=["POST"])
@token_requis
def ajouter_membre():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        role = check_access(eid, request.user_id)
        if role != "admin":
            return err("Seul un admin peut ajouter des membres", 403)
        conn = get_db()
        user_row = conn.execute("SELECT id FROM users WHERE email=?", (data.get("email", ""),)).fetchone()
        if not user_row:
            conn.close()
            return err("Utilisateur non trouvé avec cet email", 404)
        uid = user_row["id"]
        existing = conn.execute(
            "SELECT id FROM membres_entreprise WHERE entreprise_id=? AND user_id=?",
            (eid, uid)).fetchone()
        if existing:
            conn.execute("UPDATE membres_entreprise SET actif=1, role=? WHERE entreprise_id=? AND user_id=?",
                         (data.get("role", "employe"), eid, uid))
        else:
            mid = gen_id("MBR")
            conn.execute("""
                INSERT INTO membres_entreprise (id, entreprise_id, user_id, role, actif)
                VALUES (?, ?, ?, ?, 1)
            """, (mid, eid, uid, data.get("role", "employe")))
        conn.commit()
        conn.close()
        return ok({}, "Membre ajouté", 201)
    except Exception as e:
        return err(str(e))


# ─────────────────────────────────────────────
# FINANCES — TRANSACTIONS
# ─────────────────────────────────────────────

@business.route("/business/finances/transactions", methods=["GET"])
@token_requis
def get_transactions():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        mois = request.args.get("mois", "")
        conn = get_db()
        if mois:
            rows = conn.execute("""
                SELECT * FROM transactions
                WHERE entreprise_id=? AND date LIKE ?
                ORDER BY date DESC
            """, (eid, f"{mois}%")).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM transactions WHERE entreprise_id=? ORDER BY date DESC
            """, (eid,)).fetchall()
        conn.close()
        txns = rows_to_list(rows)
        return ok({"transactions": txns, "total": len(txns)})
    except Exception as e:
        return err(str(e))


@business.route("/business/finances/transactions", methods=["POST"])
@token_requis
def creer_transaction():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        if not data.get("type") or not data.get("montant"):
            return err("Type et montant requis")
        conn = get_db()
        tid = gen_id("TXN")
        conn.execute("""
            INSERT INTO transactions
                (id, entreprise_id, type, montant, categorie, sous_categorie,
                 description, date, mode_paiement, reference, employe_id, projet_id, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tid, eid,
            data["type"], float(data["montant"]),
            data.get("categorie", "autre"), data.get("sous_categorie", ""),
            data.get("description", ""),
            data.get("date", date.today().isoformat()),
            data.get("mode_paiement", "virement"),
            data.get("reference", ""),
            data.get("employe_id"), data.get("projet_id"),
            json.dumps(data.get("tags", []))
        ))
        conn.commit()
        row = row_to_dict(conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone())
        conn.close()
        return ok(row, "Transaction créée", 201)
    except Exception as e:
        return err(str(e))


@business.route("/business/finances/transactions/<tid>", methods=["PUT"])
@token_requis
def update_transaction(tid):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        conn = get_db()
        champs = ["type", "montant", "categorie", "sous_categorie", "description",
                  "date", "mode_paiement", "reference"]
        sets, vals = [], []
        for k in champs:
            if k in data:
                sets.append(f"{k}=?")
                vals.append(data[k])
        if sets:
            vals.append(tid)
            conn.execute(f"UPDATE transactions SET {','.join(sets)} WHERE id=?", vals)
            conn.commit()
        row = row_to_dict(conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone())
        conn.close()
        return ok(row, "Transaction mise à jour")
    except Exception as e:
        return err(str(e))


@business.route("/business/finances/transactions/<tid>", methods=["DELETE"])
@token_requis
def delete_transaction(tid):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        conn = get_db()
        conn.execute("DELETE FROM transactions WHERE id=? AND entreprise_id=?", (tid, eid))
        conn.commit()
        conn.close()
        return ok({}, "Transaction supprimée")
    except Exception as e:
        return err(str(e))


# ─────────────────────────────────────────────
# FINANCES — DASHBOARD & KPIs
# ─────────────────────────────────────────────

@business.route("/business/finances/dashboard", methods=["GET"])
@token_requis
def dashboard_finances():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        periode = request.args.get("periode", date.today().strftime("%Y-%m"))

        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM transactions WHERE entreprise_id=? AND date LIKE ?
            ORDER BY date DESC
        """, (eid, f"{periode}%")).fetchall()
        txns = rows_to_list(rows)

        revenus = sum(t["montant"] for t in txns if t["type"] == "revenu")
        depenses = sum(t["montant"] for t in txns if t["type"] == "depense")
        marge = revenus - depenses
        taux_marge = round((marge / revenus * 100), 1) if revenus > 0 else 0

        # Dépenses par catégorie
        dep_cat = {}
        for t in txns:
            if t["type"] == "depense":
                cat = t.get("categorie", "autre")
                dep_cat[cat] = dep_cat.get(cat, 0) + t["montant"]

        # Évolution 6 derniers mois
        evolution = []
        for i in range(5, -1, -1):
            d = date.today().replace(day=1)
            mois_i = (d.month - i - 1) % 12 + 1
            annee_i = d.year + ((d.month - i - 1) // 12)
            mois_str = f"{annee_i:04d}-{mois_i:02d}"
            rows_m = conn.execute("""
                SELECT type, SUM(montant) as total FROM transactions
                WHERE entreprise_id=? AND date LIKE ?
                GROUP BY type
            """, (eid, f"{mois_str}%")).fetchall()
            rev_m = dep_m = 0
            for r in rows_m:
                if r["type"] == "revenu": rev_m = r["total"] or 0
                elif r["type"] == "depense": dep_m = r["total"] or 0
            evolution.append({
                "mois": mois_str,
                "revenus": rev_m,
                "depenses": dep_m,
                "marge": rev_m - dep_m
            })

        # Projection trésorerie (moyenne des 3 derniers mois)
        moy_rev = sum(e["revenus"] for e in evolution[-3:]) / 3 if len(evolution) >= 3 else revenus
        moy_dep = sum(e["depenses"] for e in evolution[-3:]) / 3 if len(evolution) >= 3 else depenses

        conn.close()
        return ok({
            "revenus": revenus,
            "depenses": depenses,
            "marge_nette": marge,
            "taux_marge": taux_marge,
            "depenses_par_categorie": dep_cat,
            "evolution_mensuelle": evolution,
            "projection_tresorerie": {
                "revenus_estimes": round(moy_rev),
                "depenses_estimees": round(moy_dep),
                "marge_estimee": round(moy_rev - moy_dep)
            }
        })
    except Exception as e:
        return err(str(e))


# ─────────────────────────────────────────────
# FINANCES — IMPORT CSV
# ─────────────────────────────────────────────

@business.route("/business/finances/import-csv", methods=["POST"])
@token_requis
def import_csv():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        contenu = data.get("contenu_csv", "")
        lignes = [l.strip() for l in contenu.split("\n") if l.strip()]
        if len(lignes) < 2:
            return err("CSV vide ou sans données")

        importees = doublons = 0
        erreurs = []
        conn = get_db()

        for i, ligne in enumerate(lignes[1:], 2):
            try:
                cols = [c.strip().strip('"') for c in ligne.split(",")]
                if len(cols) < 4:
                    erreurs.append(f"Ligne {i}: colonnes insuffisantes")
                    continue
                # Format attendu: date, type, montant, description[, categorie]
                date_txn = cols[0]
                type_txn = cols[1].lower()
                montant = float(cols[2].replace("€", "").replace(" ", "").replace(",", "."))
                description = cols[3] if len(cols) > 3 else ""
                categorie = cols[4] if len(cols) > 4 else "autre"

                # Vérifier doublon (même date + montant + description)
                existing = conn.execute("""
                    SELECT id FROM transactions
                    WHERE entreprise_id=? AND date=? AND montant=? AND description=?
                """, (eid, date_txn, montant, description)).fetchone()
                if existing:
                    doublons += 1
                    continue

                tid = gen_id("TXN")
                conn.execute("""
                    INSERT INTO transactions
                        (id, entreprise_id, type, montant, categorie, description, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (tid, eid, type_txn, montant, categorie, description, date_txn))
                importees += 1
            except Exception as ex:
                erreurs.append(f"Ligne {i}: {str(ex)}")

        conn.commit()
        conn.close()
        return ok({
            "importees": importees,
            "doublons_ignores": doublons,
            "erreurs": erreurs
        }, f"{importees} transactions importées")
    except Exception as e:
        return err(str(e))


# ─────────────────────────────────────────────
# RH — EMPLOYÉS
# ─────────────────────────────────────────────

@business.route("/business/rh/employes", methods=["GET"])
@token_requis
def get_employes():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        statut = request.args.get("statut")
        conn = get_db()
        if statut:
            rows = conn.execute("""
                SELECT * FROM employes WHERE entreprise_id=? AND statut=?
                ORDER BY nom, prenom
            """, (eid, statut)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM employes WHERE entreprise_id=? ORDER BY nom, prenom
            """, (eid,)).fetchall()
        conn.close()
        employes = rows_to_list(rows)
        for e in employes:
            brut = float(e.get("salaire_brut", 0))
            charges = round(brut * 0.45, 2)
            e["charges_patronales"] = charges
            e["cout_total_employeur"] = round(brut + charges, 2)
            e["salaire_net"] = round(brut * 0.78, 2)
        return ok({"employes": employes, "total": len(employes)})
    except Exception as e:
        return err(str(e))


@business.route("/business/rh/employes", methods=["POST"])
@token_requis
def creer_employe():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        if not data.get("prenom") or not data.get("nom"):
            return err("Prénom et nom requis")
        conn = get_db()
        emp_id = gen_id("EMP")
        conn.execute("""
            INSERT INTO employes
                (id, entreprise_id, prenom, nom, email, telephone, poste,
                 departement, type_contrat, date_embauche, salaire_brut,
                 statut, conges_acquis, conges_pris, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            emp_id, eid,
            data["prenom"], data["nom"],
            data.get("email", ""), data.get("telephone", ""),
            data.get("poste", ""), data.get("departement", ""),
            data.get("type_contrat", "CDI"),
            data.get("date_embauche", date.today().isoformat()),
            float(data.get("salaire_brut", 0)),
            data.get("statut", "actif"),
            float(data.get("conges_acquis", 25)),
            float(data.get("conges_pris", 0)),
            data.get("notes", "")
        ))
        conn.commit()
        row = row_to_dict(conn.execute("SELECT * FROM employes WHERE id=?", (emp_id,)).fetchone())
        conn.close()
        return ok(row, "Employé créé", 201)
    except Exception as e:
        return err(str(e))


@business.route("/business/rh/employes/<emp_id>", methods=["PUT"])
@token_requis
def update_employe(emp_id):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        conn = get_db()
        champs = ["prenom", "nom", "email", "telephone", "poste", "departement",
                  "type_contrat", "date_embauche", "salaire_brut", "statut",
                  "conges_acquis", "conges_pris", "notes"]
        sets, vals = [], []
        for k in champs:
            if k in data:
                sets.append(f"{k}=?")
                vals.append(data[k])
        if sets:
            vals.append(emp_id)
            conn.execute(f"UPDATE employes SET {','.join(sets)} WHERE id=?", vals)
            conn.commit()
        row = row_to_dict(conn.execute("SELECT * FROM employes WHERE id=?", (emp_id,)).fetchone())
        conn.close()
        return ok(row, "Employé mis à jour")
    except Exception as e:
        return err(str(e))


@business.route("/business/rh/employes/<emp_id>", methods=["DELETE"])
@token_requis
def delete_employe(emp_id):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        conn = get_db()
        conn.execute("UPDATE employes SET statut='inactif' WHERE id=? AND entreprise_id=?",
                     (emp_id, eid))
        conn.commit()
        conn.close()
        return ok({}, "Employé archivé")
    except Exception as e:
        return err(str(e))


# ─────────────────────────────────────────────
# RH — CONGÉS
# ─────────────────────────────────────────────

@business.route("/business/rh/conges", methods=["GET"])
@token_requis
def get_conges():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        statut = request.args.get("statut")
        conn = get_db()
        if statut:
            rows = conn.execute("""
                SELECT c.*, e.prenom, e.nom FROM conges c
                JOIN employes e ON e.id = c.employe_id
                WHERE c.entreprise_id=? AND c.statut=?
                ORDER BY c.date_debut DESC
            """, (eid, statut)).fetchall()
        else:
            rows = conn.execute("""
                SELECT c.*, e.prenom, e.nom FROM conges c
                JOIN employes e ON e.id = c.employe_id
                WHERE c.entreprise_id=?
                ORDER BY c.date_debut DESC
            """, (eid,)).fetchall()
        conn.close()
        return ok(rows_to_list(rows))
    except Exception as e:
        return err(str(e))


@business.route("/business/rh/conges", methods=["POST"])
@token_requis
def creer_conge():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        conn = get_db()
        cid = gen_id("CGE")
        # Calculer nb jours
        try:
            d1 = datetime.strptime(data["date_debut"], "%Y-%m-%d").date()
            d2 = datetime.strptime(data["date_fin"], "%Y-%m-%d").date()
            nb = float(data.get("nb_jours", (d2 - d1).days + 1))
        except:
            nb = float(data.get("nb_jours", 1))
        conn.execute("""
            INSERT INTO conges
                (id, entreprise_id, employe_id, type, date_debut, date_fin,
                 nb_jours, statut, motif)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cid, eid,
            data.get("employe_id"), data.get("type", "conges_payes"),
            data.get("date_debut"), data.get("date_fin"),
            nb, "en_attente", data.get("motif", "")
        ))
        conn.commit()
        row = row_to_dict(conn.execute("SELECT * FROM conges WHERE id=?", (cid,)).fetchone())
        conn.close()
        return ok(row, "Congé créé", 201)
    except Exception as e:
        return err(str(e))


@business.route("/business/rh/conges/<cid>/valider", methods=["PUT"])
@token_requis
def valider_conge(cid):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        role = check_access(eid, request.user_id)
        if role not in ["admin", "rh"]:
            return err("Accès refusé", 403)
        statut = data.get("statut", "approuve")  # approuve | refuse
        commentaire = data.get("commentaire", "")
        conn = get_db()
        conn.execute("""
            UPDATE conges SET statut=?, commentaire_valideur=? WHERE id=?
        """, (statut, commentaire, cid))
        # Si approuvé, décrémenter les congés de l'employé
        if statut == "approuve":
            conge = conn.execute("SELECT * FROM conges WHERE id=?", (cid,)).fetchone()
            if conge:
                conn.execute("""
                    UPDATE employes SET conges_pris = conges_pris + ?
                    WHERE id=?
                """, (conge["nb_jours"], conge["employe_id"]))
        conn.commit()
        conn.close()
        return ok({}, f"Congé {statut}")
    except Exception as e:
        return err(str(e))


# ─────────────────────────────────────────────
# RH — MASSE SALARIALE
# ─────────────────────────────────────────────

@business.route("/business/rh/masse-salariale", methods=["GET"])
@token_requis
def masse_salariale():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        conn = get_db()
        rows = conn.execute("""
            SELECT salaire_brut, type_contrat, statut FROM employes
            WHERE entreprise_id=? AND statut='actif'
        """, (eid,)).fetchall()
        conn.close()
        employes = rows_to_list(rows)
        total_brut = sum(float(e["salaire_brut"]) for e in employes)
        total_charges = round(total_brut * 0.45, 2)
        total_net = round(total_brut * 0.78, 2)
        return ok({
            "nb_employes": len(employes),
            "masse_salariale_brute": round(total_brut, 2),
            "charges_patronales": total_charges,
            "cout_total_employeur": round(total_brut + total_charges, 2),
            "masse_salariale_nette": total_net
        })
    except Exception as e:
        return err(str(e))


# ─────────────────────────────────────────────
# RH — POINTAGES
# ─────────────────────────────────────────────

@business.route("/business/rh/pointages", methods=["GET"])
@token_requis
def get_pointages():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        mois = request.args.get("mois", date.today().strftime("%Y-%m"))
        conn = get_db()
        rows = conn.execute("""
            SELECT p.*, e.prenom, e.nom FROM pointages p
            JOIN employes e ON e.id = p.employe_id
            WHERE p.entreprise_id=? AND p.date LIKE ?
            ORDER BY p.date DESC
        """, (eid, f"{mois}%")).fetchall()
        conn.close()
        return ok({"pointages": rows_to_list(rows)})
    except Exception as e:
        return err(str(e))


@business.route("/business/rh/pointages", methods=["POST"])
@token_requis
def creer_pointage():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        conn = get_db()
        pid = gen_id("PTG")
        h_arrivee = data.get("heure_arrivee", "09:00")
        h_depart = data.get("heure_depart", "17:00")
        try:
            t1 = datetime.strptime(h_arrivee, "%H:%M")
            t2 = datetime.strptime(h_depart, "%H:%M")
            heures = round((t2 - t1).seconds / 3600, 2)
        except:
            heures = float(data.get("heures_travaillees", 8))
        conn.execute("""
            INSERT INTO pointages
                (id, entreprise_id, employe_id, date, heure_arrivee, heure_depart,
                 heures_travaillees, heures_supplementaires, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid, eid,
            data.get("employe_id"),
            data.get("date", date.today().isoformat()),
            h_arrivee, h_depart, heures,
            max(0, heures - 8),
            data.get("notes", "")
        ))
        conn.commit()
        row = row_to_dict(conn.execute("SELECT * FROM pointages WHERE id=?", (pid,)).fetchone())
        conn.close()
        return ok(row, "Pointage enregistré", 201)
    except Exception as e:
        return err(str(e))


# ─────────────────────────────────────────────
# ALERTES DASHBOARD
# ─────────────────────────────────────────────

@business.route("/business/alertes", methods=["GET"])
@token_requis
def get_alertes():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not check_access(eid, request.user_id):
            return err("Accès refusé", 403)
        alertes = []
        conn = get_db()

        # Congés en attente
        nb_conges = conn.execute("""
            SELECT COUNT(*) as c FROM conges WHERE entreprise_id=? AND statut='en_attente'
        """, (eid,)).fetchone()["c"]
        if nb_conges > 0:
            alertes.append({
                "type": "warning",
                "titre": f"{nb_conges} congé(s) en attente",
                "message": "Des demandes de congés nécessitent votre validation",
                "lien": "employes.html"
            })

        # Marge négative ce mois
        mois = date.today().strftime("%Y-%m")
        rows_fin = conn.execute("""
            SELECT type, SUM(montant) as total FROM transactions
            WHERE entreprise_id=? AND date LIKE ?
            GROUP BY type
        """, (eid, f"{mois}%")).fetchall()
        rev = dep = 0
        for r in rows_fin:
            if r["type"] == "revenu": rev = r["total"] or 0
            elif r["type"] == "depense": dep = r["total"] or 0
        if dep > rev and (rev > 0 or dep > 0):
            alertes.append({
                "type": "danger",
                "titre": "Marge négative ce mois",
                "message": f"Dépenses ({dep:.0f}€) supérieures aux revenus ({rev:.0f}€)",
                "lien": "finances.html"
            })

        conn.close()
        return ok({"alertes": alertes})
    except Exception as e:
        return err(str(e))
