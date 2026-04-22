"""
api_business.py — Routes API pour Agent IA Business
"""

from flask import Blueprint, request, jsonify
import json
import jwt
import os
from functools import wraps
import uuid

# ── Fonctions utilitaires ──

def reponse_ok(data, message="Succès", code=200):
    return jsonify({"statut": "ok", "message": message, "data": data}), code

def reponse_erreur(message, code=400):
    return jsonify({"statut": "erreur", "message": message}), code

def get_json():
    return request.get_json() or {}

def generer_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"

def token_requis(f):
    @wraps(f)
    def decorateur(*args, **kwargs):
        if request.method == "OPTIONS":
            return jsonify({}), 200
        token = None
        auth  = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ")[1]
        if not token:
            return reponse_erreur("Token manquant", 401)
        from auth import verifier_token
        user_id = verifier_token(token)
        if not user_id:
            return reponse_erreur("Token invalide ou expiré", 401)
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorateur


from users import (
    creer_entreprise, get_entreprises_user, get_entreprise, modifier_entreprise,
    inviter_membre, get_membres, modifier_role_membre, retirer_membre, get_role_user
)
from finances import (
    creer_transaction, get_transactions, modifier_transaction, supprimer_transaction,
    importer_csv, importer_bulk, generer_paie_mensuelle,
    get_dashboard_financier, calculer_projection, detecter_anomalies
)
from rh import (
    creer_employe, get_employes, get_employe, modifier_employe, supprimer_employe,
    calculer_charges, get_masse_salariale,
    creer_conge, get_conges, valider_conge,
    pointer_heures, get_pointages,
    creer_evaluation, get_evaluations
)
from database import get_db, row_to_dict, rows_to_list

business = Blueprint("business", __name__, url_prefix="/business")


# ─────────────────────────────────────────────
# HELPER PERMISSION
# ─────────────────────────────────────────────

def _check_acces(entreprise_id: str, user_id: str) -> bool:
    return get_role_user(entreprise_id, user_id) is not None


# ─────────────────────────────────────────────
# ENTREPRISES
# ─────────────────────────────────────────────

@business.route("/entreprises", methods=["GET", "POST", "OPTIONS"])
@token_requis
def entreprises_route():
    if request.method == "POST":
        try:
            data = get_json()
            ent  = creer_entreprise(request.user_id, data)
            return reponse_ok(ent, "Entreprise créée", 201)
        except ValueError as e:
            return reponse_erreur(str(e))
        except Exception as e:
            return reponse_erreur(str(e), 500)
    else:
        try:
            entreprises = get_entreprises_user(request.user_id)
            return reponse_ok({"entreprises": entreprises, "total": len(entreprises)})
        except Exception as e:
            return reponse_erreur(str(e), 500)


@business.route("/entreprises/<eid>", methods=["GET", "PUT", "OPTIONS"])
@token_requis
def entreprise_detail(eid):
    if request.method == "PUT":
        try:
            data = get_json()
            ent  = modifier_entreprise(eid, request.user_id, data)
            return reponse_ok(ent, "Entreprise mise à jour")
        except PermissionError as e:
            return reponse_erreur(str(e), 403)
        except Exception as e:
            return reponse_erreur(str(e))
    else:
        if not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        ent = get_entreprise(eid)
        if not ent:
            return reponse_erreur("Entreprise non trouvée", 404)
        return reponse_ok(ent)


# ─────────────────────────────────────────────
# MEMBRES
# ─────────────────────────────────────────────

@business.route("/membres", methods=["GET", "OPTIONS"])
@token_requis
def list_membres():
    eid = request.args.get("entreprise_id")
    if not eid or not _check_acces(eid, request.user_id):
        return reponse_erreur("Accès refusé", 403)
    return reponse_ok({"membres": get_membres(eid)})


@business.route("/membres/inviter", methods=["POST", "OPTIONS"])
@token_requis
def inviter():
    try:
        data = get_json()
        eid  = data.get("entreprise_id")
        if not eid:
            return reponse_erreur("entreprise_id requis")
        result = inviter_membre(eid, request.user_id, data.get("email", ""), data.get("role", "employe"))
        return reponse_ok(result, "Membre invité", 201)
    except (PermissionError, ValueError) as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/membres/<uid>/role", methods=["PUT", "OPTIONS"])
@token_requis
def update_role(uid):
    try:
        data = get_json()
        eid  = data.get("entreprise_id")
        modifier_role_membre(eid, request.user_id, uid, data.get("role"))
        return reponse_ok({}, "Rôle modifié")
    except (PermissionError, ValueError) as e:
        return reponse_erreur(str(e))


@business.route("/membres/<uid>", methods=["DELETE", "OPTIONS"])
@token_requis
def retirer(uid):
    try:
        eid = request.args.get("entreprise_id")
        retirer_membre(eid, request.user_id, uid)
        return reponse_ok({}, "Membre retiré")
    except PermissionError as e:
        return reponse_erreur(str(e), 403)


# ─────────────────────────────────────────────
# FINANCES — TRANSACTIONS
# ─────────────────────────────────────────────

@business.route("/finances/transactions", methods=["GET", "POST", "OPTIONS"])
@token_requis
def transactions_route():
    if request.method == "POST":
        try:
            data = get_json()
            eid  = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            txn = creer_transaction(eid, data)
            return reponse_ok(txn, "Transaction créée", 201)
        except ValueError as e:
            return reponse_erreur(str(e))
        except Exception as e:
            return reponse_erreur(str(e), 500)
    else:
        try:
            eid = request.args.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            filtres = {
                "type":       request.args.get("type"),
                "categorie":  request.args.get("categorie"),
                "mois":       request.args.get("mois"),
                "date_debut": request.args.get("date_debut"),
                "date_fin":   request.args.get("date_fin"),
            }
            txns = get_transactions(eid, {k: v for k, v in filtres.items() if v})
            return reponse_ok({"transactions": txns, "total": len(txns)})
        except Exception as e:
            return reponse_erreur(str(e), 500)


@business.route("/finances/transactions/<tid>", methods=["PUT", "DELETE", "OPTIONS"])
@token_requis
def transaction_detail(tid):
    if request.method == "PUT":
        try:
            data = get_json()
            eid  = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            txn = modifier_transaction(tid, eid, data)
            return reponse_ok(txn, "Transaction mise à jour")
        except Exception as e:
            return reponse_erreur(str(e))
    elif request.method == "DELETE":
        try:
            data = get_json() or {}
            eid  = data.get("entreprise_id") or request.args.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            supprimer_transaction(tid, eid)
            return reponse_ok({}, "Transaction supprimée")
        except Exception as e:
            return reponse_erreur(str(e))


@business.route("/finances/import-csv", methods=["POST", "OPTIONS"])
@token_requis
def import_csv():
    try:
        data    = get_json()
        eid     = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        contenu = data.get("contenu_csv", "")
        if not contenu:
            return reponse_erreur("contenu_csv requis")
        result = importer_csv(eid, contenu, data.get("mapping"))
        return reponse_ok(result, f"{result['importees']} transactions importées")
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/finances/import-bulk", methods=["POST", "OPTIONS"])
@token_requis
def import_bulk():
    """Import de transactions déjà parsées côté front (nouvelle modale CSV)."""
    try:
        data         = get_json()
        eid          = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        transactions = data.get("transactions", [])
        if not transactions:
            return reponse_erreur("Aucune transaction fournie")
        result = importer_bulk(eid, transactions)
        return reponse_ok(result, f"{result['importees']} transactions importées")
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/finances/generer-paie", methods=["POST", "OPTIONS"])
@token_requis
def generer_paie():
    """Génère automatiquement les transactions de salaire pour tous les employés actifs."""
    try:
        data = get_json()
        eid  = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        mois = data.get("mois")
        if not mois:
            return reponse_erreur("mois requis (format YYYY-MM)")
        result = generer_paie_mensuelle(eid, mois)
        msg    = f"{result['generes']} salaire(s) généré(s) pour {mois}"
        return reponse_ok(result, msg)
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/finances/dashboard", methods=["GET", "OPTIONS"])
@token_requis
def dashboard_finances():
    try:
        eid     = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        periode = request.args.get("periode", "mois_courant")
        data    = get_dashboard_financier(eid, periode)
        return reponse_ok(data)
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/finances/projection", methods=["GET", "OPTIONS"])
@token_requis
def projection():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        data = calculer_projection(eid, int(request.args.get("mois", 3)))
        return reponse_ok(data)
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/finances/anomalies", methods=["GET", "OPTIONS"])
@token_requis
def anomalies():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        data = detecter_anomalies(eid)
        return reponse_ok(data)
    except Exception as e:
        return reponse_erreur(str(e), 500)


# ─────────────────────────────────────────────
# RH — EMPLOYÉS
# ─────────────────────────────────────────────

@business.route("/rh/employes", methods=["GET", "POST", "OPTIONS"])
@token_requis
def employes_route():
    if request.method == "POST":
        try:
            data = get_json()
            eid  = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            emp = creer_employe(eid, data)
            return reponse_ok(emp, "Employé créé", 201)
        except ValueError as e:
            return reponse_erreur(str(e))
        except Exception as e:
            return reponse_erreur(str(e), 500)
    else:
        try:
            eid = request.args.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            employes = get_employes(eid, request.args.get("statut"))
            return reponse_ok({"employes": employes, "total": len(employes)})
        except Exception as e:
            return reponse_erreur(str(e), 500)


@business.route("/rh/employes/<empid>", methods=["GET", "PUT", "DELETE", "OPTIONS"])
@token_requis
def employe_detail(empid):
    if request.method == "GET":
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        emp = get_employe(empid, eid)
        if not emp:
            return reponse_erreur("Employé non trouvé", 404)
        return reponse_ok(emp)
    elif request.method == "PUT":
        try:
            data = get_json()
            eid  = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            emp = modifier_employe(empid, eid, data)
            return reponse_ok(emp, "Employé mis à jour")
        except Exception as e:
            return reponse_erreur(str(e))
    elif request.method == "DELETE":
        try:
            eid = request.args.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            supprimer_employe(empid, eid)
            return reponse_ok({}, "Employé supprimé")
        except Exception as e:
            return reponse_erreur(str(e))


@business.route("/rh/masse-salariale", methods=["GET", "OPTIONS"])
@token_requis
def masse_sal():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        data = get_masse_salariale(eid)
        return reponse_ok(data)
    except Exception as e:
        return reponse_erreur(str(e), 500)


# ─────────────────────────────────────────────
# RH — CONGÉS
# ─────────────────────────────────────────────

@business.route("/rh/conges", methods=["GET", "POST", "OPTIONS"])
@token_requis
def conges_route():
    if request.method == "POST":
        try:
            data  = get_json()
            eid   = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            conge = creer_conge(eid, data)
            return reponse_ok(conge, "Demande de congé créée", 201)
        except ValueError as e:
            return reponse_erreur(str(e))
        except Exception as e:
            return reponse_erreur(str(e), 500)
    else:
        try:
            eid  = request.args.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            data = get_conges(eid, request.args.get("employe_id"), request.args.get("statut"))
            return reponse_ok(data)
        except Exception as e:
            return reponse_erreur(str(e), 500)


@business.route("/rh/conges/<cid>/valider", methods=["PUT", "OPTIONS"])
@token_requis
def valider(cid):
    try:
        data  = get_json()
        eid   = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        conge = valider_conge(cid, eid, data.get("statut"), data.get("commentaire", ""))
        return reponse_ok(conge, "Congé mis à jour")
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e))


# ─────────────────────────────────────────────
# RH — POINTAGES
# ─────────────────────────────────────────────

@business.route("/rh/pointages", methods=["GET", "POST", "OPTIONS"])
@token_requis
def pointages_route():
    if request.method == "POST":
        try:
            data = get_json()
            eid  = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            ptg  = pointer_heures(eid, data)
            return reponse_ok(ptg, "Pointage enregistré", 201)
        except ValueError as e:
            return reponse_erreur(str(e))
        except Exception as e:
            return reponse_erreur(str(e), 500)
    else:
        try:
            eid  = request.args.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            data = get_pointages(eid, request.args.get("employe_id"), request.args.get("mois"))
            return reponse_ok(data)
        except Exception as e:
            return reponse_erreur(str(e), 500)


# ─────────────────────────────────────────────
# RH — ÉVALUATIONS
# ─────────────────────────────────────────────

@business.route("/rh/evaluations", methods=["GET", "POST", "OPTIONS"])
@token_requis
def evaluations_route():
    if request.method == "POST":
        try:
            data  = get_json()
            eid   = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            eval_ = creer_evaluation(eid, data)
            return reponse_ok(eval_, "Évaluation créée", 201)
        except ValueError as e:
            return reponse_erreur(str(e))
        except Exception as e:
            return reponse_erreur(str(e), 500)
    else:
        try:
            eid  = request.args.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            data = get_evaluations(eid, request.args.get("employe_id"))
            return reponse_ok(data)
        except Exception as e:
            return reponse_erreur(str(e), 500)


# ─────────────────────────────────────────────
# ANALYTICS IA
# ─────────────────────────────────────────────

@business.route("/analytics/analyser", methods=["POST", "OPTIONS"])
@token_requis
def analyser_business():
    try:
        data = get_json()
        eid  = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)

        dashboard = get_dashboard_financier(eid, "annee")
        masse_sal = get_masse_salariale(eid)

        donnees = {
            "ca_annuel":                    dashboard.get("revenus", 0),
            "depenses_annuelles":           dashboard.get("depenses", 0),
            "marge_nette":                  dashboard.get("marge_nette", 0),
            "taux_marge":                   dashboard.get("taux_marge", 0),
            "nb_employes":                  masse_sal.get("nb_employes_actifs", 0),
            "cout_masse_salariale_mensuel":  masse_sal.get("cout_total_mensuel", 0),
            "part_salaires_depenses": round(
                masse_sal.get("cout_total_mensuel", 0) * 12
                / max(dashboard.get("depenses", 1), 1) * 100, 1
            ),
            "depenses_par_categorie": dashboard.get("depenses_par_categorie", []),
            "evolution_12_mois":      dashboard.get("evolution_mensuelle", []),
        }

        from agent import analyser_activite
        analyse = analyser_activite(donnees, "dirigeant de PME")
        return reponse_ok(analyse, "Analyse générée")
    except Exception as e:
        return reponse_erreur(str(e), 500)

# ─────────────────────────────────────────────
# PROJETS
# ─────────────────────────────────────────────

@business.route("/projets", methods=["GET", "POST", "OPTIONS"])
@token_requis
def projets_route():
    if request.method == "POST":
        try:
            data = get_json()
            eid  = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            if not data.get("nom"):
                return reponse_erreur("Nom du projet requis")

            conn = get_db()
            try:
                import time
                import json as _json
                pid = f"PRJ_{int(time.time() * 1000000)}"
                conn.execute("""
                    INSERT INTO projets
                        (id, entreprise_id, nom, client, description, budget, cout_reel,
                         statut, date_debut, date_fin_prevue, date_fin_reelle,
                         responsable_id, membres)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pid, eid,
                    data.get("nom", ""),
                    data.get("client", ""),
                    data.get("description", ""),
                    float(data.get("budget", 0)),
                    float(data.get("cout_reel", 0)),
                    data.get("statut", "en_cours"),
                    data.get("date_debut", ""),
                    data.get("date_fin_prevue", ""),
                    data.get("date_fin_reelle", ""),
                    data.get("responsable_id"),
                    _json.dumps(data.get("membres", [])),
                ))
                conn.commit()
                row = conn.execute("SELECT * FROM projets WHERE id=?", (pid,)).fetchone()
                p = row_to_dict(row)
                p["membres"] = _json.loads(p.get("membres") or "[]")
                return reponse_ok(p, "Projet créé", 201)
            finally:
                conn.close()
        except Exception as e:
            return reponse_erreur(str(e), 500)
    else:  # GET
        try:
            import json as _json
            eid = request.args.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            statut = request.args.get("statut")
            conn = get_db()
            try:
                sql    = "SELECT * FROM projets WHERE entreprise_id=?"
                params = [eid]
                if statut:
                    sql += " AND statut=?"
                    params.append(statut)
                sql += " ORDER BY created_at DESC"
                rows = rows_to_list(conn.execute(sql, params).fetchall())
                for p in rows:
                    p["membres"] = _json.loads(p.get("membres") or "[]")
                return reponse_ok({"projets": rows, "total": len(rows)})
            finally:
                conn.close()
        except Exception as e:
            return reponse_erreur(str(e), 500)


@business.route("/projets/<pid>", methods=["GET", "PUT", "DELETE", "OPTIONS"])
@token_requis
def projet_detail(pid):
    import json as _json

    if request.method == "GET":
        try:
            eid = request.args.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            conn = get_db()
            try:
                row = conn.execute("SELECT * FROM projets WHERE id=? AND entreprise_id=?", (pid, eid)).fetchone()
                if not row:
                    return reponse_erreur("Projet non trouvé", 404)
                p = row_to_dict(row)
                p["membres"] = _json.loads(p.get("membres") or "[]")
                return reponse_ok(p)
            finally:
                conn.close()
        except Exception as e:
            return reponse_erreur(str(e), 500)

    elif request.method == "PUT":
        try:
            data = get_json()
            eid  = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            conn = get_db()
            try:
                champs = ["nom", "client", "description", "budget", "cout_reel",
                          "statut", "date_debut", "date_fin_prevue", "date_fin_reelle",
                          "responsable_id", "membres"]
                sets, vals = [], []
                for k in champs:
                    if k in data:
                        val = _json.dumps(data[k]) if k == "membres" and isinstance(data[k], list) else data[k]
                        sets.append(f"{k}=?")
                        vals.append(val)
                if sets:
                    vals += [pid, eid]
                    conn.execute(f"UPDATE projets SET {','.join(sets)} WHERE id=? AND entreprise_id=?", vals)
                    conn.commit()
                row = conn.execute("SELECT * FROM projets WHERE id=?", (pid,)).fetchone()
                p = row_to_dict(row)
                p["membres"] = _json.loads(p.get("membres") or "[]")
                return reponse_ok(p, "Projet mis à jour")
            finally:
                conn.close()
        except Exception as e:
            return reponse_erreur(str(e), 500)

    elif request.method == "DELETE":
        try:
            eid = request.args.get("entreprise_id") or (get_json() or {}).get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            conn = get_db()
            try:
                conn.execute("DELETE FROM projets WHERE id=? AND entreprise_id=?", (pid, eid))
                conn.commit()
                return reponse_ok({}, "Projet supprimé")
            finally:
                conn.close()
        except Exception as e:
            return reponse_erreur(str(e), 500)