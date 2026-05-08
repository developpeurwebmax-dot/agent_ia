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
# HELPERS PERMISSION
# ─────────────────────────────────────────────

def _check_acces(entreprise_id: str, user_id: str) -> bool:
    return get_role_user(entreprise_id, user_id) is not None


def _est_employe(entreprise_id: str, user_id: str) -> bool:
    """Retourne True si l'utilisateur a le rôle 'employe' dans cette entreprise."""
    return get_role_user(entreprise_id, user_id) == "employe"


def _get_employe_du_user(entreprise_id: str, user_id: str):
    """
    Retourne la fiche employé (dict) liée au compte user via son email.
    Retourne None si aucune fiche n'est associée.
    """
    from auth import get_user_by_id
    user = get_user_by_id(user_id)
    if not user or not user.get("email"):
        return None
    email = user["email"].strip().lower()
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM employes WHERE entreprise_id=? AND lower(trim(email))=?",
            (entreprise_id, email)
        ).fetchone()
        return row_to_dict(row) if row else None
    finally:
        conn.close()


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
    if _est_employe(eid, request.user_id):
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
        if _est_employe(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        role = data.get("role", "employe")
        if role == "employe":
            return reponse_erreur(
                "Pour ajouter un employé, utilisez la page Équipe & RH (création unifiée fiche + compte)",
                400
            )
        result = inviter_membre(eid, request.user_id, data.get("email", ""), role)
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
        if eid and _est_employe(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        modifier_role_membre(eid, request.user_id, uid, data.get("role"))
        return reponse_ok({}, "Rôle modifié")
    except (PermissionError, ValueError) as e:
        return reponse_erreur(str(e))


@business.route("/membres/<uid>", methods=["DELETE", "OPTIONS"])
@token_requis
def retirer(uid):
    try:
        eid = request.args.get("entreprise_id")
        if eid and _est_employe(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
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
            if _est_employe(eid, request.user_id):
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
            if _est_employe(eid, request.user_id):
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
            if _est_employe(eid, request.user_id):
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
            if _est_employe(eid, request.user_id):
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
        if _est_employe(eid, request.user_id):
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
        if _est_employe(eid, request.user_id):
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
        if _est_employe(eid, request.user_id):
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
        if _est_employe(eid, request.user_id):
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
        if _est_employe(eid, request.user_id):
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
        if _est_employe(eid, request.user_id):
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
            if _est_employe(eid, request.user_id):
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
            # Un employé ne voit que sa propre fiche
            if _est_employe(eid, request.user_id):
                ma_fiche = _get_employe_du_user(eid, request.user_id)
                if not ma_fiche:
                    return reponse_ok({"employes": [], "total": 0})
                return reponse_ok({"employes": [ma_fiche], "total": 1})
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
        # Un employé ne peut consulter que sa propre fiche
        if _est_employe(eid, request.user_id):
            ma_fiche = _get_employe_du_user(eid, request.user_id)
            if not ma_fiche or ma_fiche.get("id") != empid:
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
            if _est_employe(eid, request.user_id):
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
            if _est_employe(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            supprimer_employe(empid, eid)
            return reponse_ok({}, "Employé supprimé")
        except Exception as e:
            return reponse_erreur(str(e))


@business.route("/rh/employes-avec-compte", methods=["POST", "OPTIONS"])
@token_requis
def creer_employe_avec_compte():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        if _est_employe(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)

        creer_compte = data.get("creer_compte", False)
        email = (data.get("email") or "").strip()
        compte_cree = False
        mot_de_passe_temp = None

        if creer_compte:
            if not email:
                return reponse_erreur("L'email est requis pour créer un compte de connexion")
            try:
                result_invite = inviter_membre(eid, request.user_id, email, "employe")
                compte_cree = result_invite.get("compte_cree", False)
                mot_de_passe_temp = result_invite.get("mot_de_passe_temp")
            except ValueError as e:
                msg = str(e)
                # Si déjà membre, on continue quand même à créer la fiche
                if "déjà membre" not in msg.lower():
                    return reponse_erreur(msg)

        emp = creer_employe(eid, data)
        return reponse_ok({
            "employe": emp,
            "compte_cree": compte_cree,
            "mot_de_passe_temp": mot_de_passe_temp,
            "email": email if creer_compte else None
        }, "Employé créé", 201)
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/rh/masse-salariale", methods=["GET", "OPTIONS"])
@token_requis
def masse_sal():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        if _est_employe(eid, request.user_id):
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
            # Un employé ne peut créer une demande que pour lui-même
            if _est_employe(eid, request.user_id):
                ma_fiche = _get_employe_du_user(eid, request.user_id)
                if not ma_fiche:
                    return reponse_erreur("Fiche employé introuvable", 403)
                data["employe_id"] = ma_fiche["id"]
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
            # Un employé ne consulte que ses propres congés
            if _est_employe(eid, request.user_id):
                ma_fiche = _get_employe_du_user(eid, request.user_id)
                if not ma_fiche:
                    return reponse_ok([])
                emp_id_demande = request.args.get("employe_id")
                if emp_id_demande and emp_id_demande != ma_fiche["id"]:
                    return reponse_erreur("Accès refusé", 403)
                data = get_conges(eid, ma_fiche["id"], request.args.get("statut"))
                return reponse_ok(data)
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
        if _est_employe(eid, request.user_id):
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
            # Un employé ne peut pointer que pour lui-même
            if _est_employe(eid, request.user_id):
                ma_fiche = _get_employe_du_user(eid, request.user_id)
                if not ma_fiche:
                    return reponse_erreur("Fiche employé introuvable", 403)
                data["employe_id"] = ma_fiche["id"]
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
            # Un employé ne consulte que ses propres pointages
            if _est_employe(eid, request.user_id):
                ma_fiche = _get_employe_du_user(eid, request.user_id)
                if not ma_fiche:
                    return reponse_ok([])
                emp_id_demande = request.args.get("employe_id")
                if emp_id_demande and emp_id_demande != ma_fiche["id"]:
                    return reponse_erreur("Accès refusé", 403)
                data = get_pointages(eid, ma_fiche["id"], request.args.get("mois"))
                return reponse_ok(data)
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
            if _est_employe(eid, request.user_id):
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
            # Un employé ne consulte que ses propres évaluations
            if _est_employe(eid, request.user_id):
                ma_fiche = _get_employe_du_user(eid, request.user_id)
                if not ma_fiche:
                    return reponse_ok([])
                emp_id_demande = request.args.get("employe_id")
                if emp_id_demande and emp_id_demande != ma_fiche["id"]:
                    return reponse_erreur("Accès refusé", 403)
                data = get_evaluations(eid, ma_fiche["id"])
                return reponse_ok(data)
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
        if _est_employe(eid, request.user_id):
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

@business.route("/rh/mes-projets", methods=["GET", "OPTIONS"])
@token_requis
def mes_projets():
    """Retourne les projets où l'utilisateur connecté est responsable ou membre."""
    import json as _json
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        ma_fiche = _get_employe_du_user(eid, request.user_id)
        if not ma_fiche:
            return reponse_ok({"projets": [], "total": 0})
        emp_id = ma_fiche["id"]
        conn = get_db()
        try:
            # Utiliser des guillemets dans le LIKE pour éviter les faux positifs
            # (l'ID est stocké dans un tableau JSON sous la forme ["EMP_xxx", ...])
            like_pattern = f'%"{emp_id}"%'
            rows = conn.execute("""
                SELECT id, nom, client, statut, date_debut, date_fin_prevue,
                       description, responsable_id, membres
                FROM projets
                WHERE entreprise_id=?
                  AND (responsable_id=? OR membres LIKE ?)
                ORDER BY created_at DESC
            """, (eid, emp_id, like_pattern)).fetchall()
            projets = []
            for row in rows:
                p = row_to_dict(row)
                membres = _json.loads(p.get("membres") or "[]")
                p["membres"] = membres
                p["role_dans_projet"] = (
                    "responsable" if p.get("responsable_id") == emp_id else "membre"
                )
                # Ne pas exposer budget ni cout_reel
                p.pop("budget", None)
                p.pop("cout_reel", None)
                projets.append(p)
            return reponse_ok({"projets": projets, "total": len(projets)})
        finally:
            conn.close()
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/rh/planning", methods=["GET", "OPTIONS"])
@token_requis
def planning_route():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        if _est_employe(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)

        semaine_du = request.args.get("semaine_du")
        if not semaine_du:
            return reponse_erreur("semaine_du requis (YYYY-MM-DD)")

        from datetime import datetime as _dt, timedelta as _td
        from rh import get_employes as _get_emp, get_conges as _get_cong, \
                       _parser_horaires as _ph, HORAIRES_DEFAUT as _HD

        d = _dt.strptime(semaine_du, "%Y-%m-%d").date()
        lundi = d - _td(days=d.weekday())
        fin_semaine = lundi + _td(days=6)

        employes = _get_emp(eid, statut="actif")
        tous_conges = _get_cong(eid, statut="approuve")
        conges_semaine = [
            c for c in tous_conges
            if _dt.strptime(c["date_fin"],   "%Y-%m-%d").date() >= lundi
            and _dt.strptime(c["date_debut"], "%Y-%m-%d").date() <= fin_semaine
        ]

        jours_keys = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        planning = []
        for emp in employes:
            ligne = {
                "employe_id": emp["id"],
                "prenom":     emp["prenom"],
                "nom":        emp["nom"],
                "poste":      emp.get("poste", ""),
                "jours":      []
            }
            horaires = emp.get("horaires") or _ph(None)
            for i, jk in enumerate(jours_keys):
                date_jour = lundi + _td(days=i)
                jour_data = horaires.get(jk, _HD[jk])
                en_conge  = False
                type_conge = None
                for c in conges_semaine:
                    if c["employe_id"] != emp["id"]:
                        continue
                    debut_c = _dt.strptime(c["date_debut"], "%Y-%m-%d").date()
                    fin_c   = _dt.strptime(c["date_fin"],   "%Y-%m-%d").date()
                    if debut_c <= date_jour <= fin_c:
                        en_conge   = True
                        type_conge = c["type"]
                        break
                ligne["jours"].append({
                    "date":       date_jour.isoformat(),
                    "actif":      jour_data.get("actif", False),
                    "debut":      jour_data.get("debut", ""),
                    "fin":        jour_data.get("fin", ""),
                    "en_conge":   en_conge,
                    "type_conge": type_conge,
                })
            planning.append(ligne)

        return reponse_ok({
            "semaine_du": lundi.isoformat(),
            "planning":   planning,
        })
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/projets", methods=["GET", "POST", "OPTIONS"])
@token_requis
def projets_route():
    if request.method == "POST":
        try:
            data = get_json()
            eid  = data.get("entreprise_id")
            if not eid or not _check_acces(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            if _est_employe(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            if not data.get("nom"):
                return reponse_erreur("Nom du projet requis")

            conn = get_db()
            try:
                import time
                import json as _json
                pid = f"PRJ_{int(time.time() * 1000000)}"
                # notes_taches : accepter str (deja JSON) ou list (a serialiser)
                _nt = data.get("notes_taches")
                if isinstance(_nt, list):
                    _nt = _json.dumps(_nt)
                elif _nt is None:
                    _nt = "[]"
                conn.execute("""
                    INSERT INTO projets
                        (id, entreprise_id, nom, client, description, budget, cout_reel,
                         statut, date_debut, date_fin_prevue, date_fin_reelle,
                         responsable_id, membres, notes, notes_taches)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    data.get("notes", ""),
                    _nt,
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
            if _est_employe(eid, request.user_id):
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
            if _est_employe(eid, request.user_id):
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
            if _est_employe(eid, request.user_id):
                return reponse_erreur("Accès refusé", 403)
            conn = get_db()
            try:
                champs = ["nom", "client", "description", "budget", "cout_reel",
                          "statut", "date_debut", "date_fin_prevue", "date_fin_reelle",
                          "responsable_id", "membres", "notes", "notes_taches"]
                sets, vals = [], []
                for k in champs:
                    if k in data:
                        # membres et notes_taches : serialiser en JSON si c'est une liste
                        if k in ("membres", "notes_taches") and isinstance(data[k], list):
                            val = _json.dumps(data[k])
                        else:
                            val = data[k]
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
            if _est_employe(eid, request.user_id):
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