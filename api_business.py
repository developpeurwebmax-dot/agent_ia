"""
api_business.py — Routes API pour Agent IA Business
À importer dans api.py ou à lancer séparément sur un sous-préfixe /business
"""

from flask import Blueprint, request
import json

from api import reponse_ok, reponse_erreur, get_json, generer_id, token_requis
from users import (
    creer_entreprise, get_entreprises_user, get_entreprise, modifier_entreprise,
    inviter_membre, get_membres, modifier_role_membre, retirer_membre, get_role_user
)
from finances import (
    creer_transaction, get_transactions, modifier_transaction, supprimer_transaction,
    importer_csv, get_dashboard_financier, calculer_projection, detecter_anomalies
)
from rh import (
    creer_employe, get_employes, get_employe, modifier_employe, supprimer_employe,
    calculer_charges, get_masse_salariale,
    creer_conge, get_conges, valider_conge,
    pointer_heures, get_pointages,
    creer_evaluation, get_evaluations
)

business = Blueprint("business", __name__, url_prefix="/business")


# ─────────────────────────────────────────────
# HELPER PERMISSION
# ─────────────────────────────────────────────

def _check_acces(entreprise_id: str, user_id: str) -> bool:
    """Vérifie qu'un user a accès à cette entreprise."""
    return get_role_user(entreprise_id, user_id) is not None


# ─────────────────────────────────────────────
# ENTREPRISES
# ─────────────────────────────────────────────

@business.route("/entreprises", methods=["POST"])
@token_requis
def creer_ent():
    try:
        data = get_json()
        ent = creer_entreprise(request.user_id, data)
        return reponse_ok(ent, "Entreprise créée", 201)
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/entreprises", methods=["GET"])
@token_requis
def list_entreprises():
    try:
        entreprises = get_entreprises_user(request.user_id)
        return reponse_ok({"entreprises": entreprises, "total": len(entreprises)})
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/entreprises/<eid>", methods=["GET"])
@token_requis
def get_ent(eid):
    if not _check_acces(eid, request.user_id):
        return reponse_erreur("Accès refusé", 403)
    ent = get_entreprise(eid)
    if not ent:
        return reponse_erreur("Entreprise non trouvée", 404)
    return reponse_ok(ent)


@business.route("/entreprises/<eid>", methods=["PUT"])
@token_requis
def update_ent(eid):
    try:
        data = get_json()
        ent = modifier_entreprise(eid, request.user_id, data)
        return reponse_ok(ent, "Entreprise mise à jour")
    except PermissionError as e:
        return reponse_erreur(str(e), 403)
    except Exception as e:
        return reponse_erreur(str(e))


# ─────────────────────────────────────────────
# MEMBRES
# ─────────────────────────────────────────────

@business.route("/membres", methods=["GET"])
@token_requis
def list_membres():
    eid = request.args.get("entreprise_id")
    if not eid or not _check_acces(eid, request.user_id):
        return reponse_erreur("Accès refusé", 403)
    return reponse_ok({"membres": get_membres(eid)})


@business.route("/membres/inviter", methods=["POST"])
@token_requis
def inviter():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid:
            return reponse_erreur("entreprise_id requis")
        result = inviter_membre(eid, request.user_id, data.get("email", ""), data.get("role", "employe"))
        return reponse_ok(result, "Membre invité", 201)
    except (PermissionError, ValueError) as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/membres/<uid>/role", methods=["PUT"])
@token_requis
def update_role(uid):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        modifier_role_membre(eid, request.user_id, uid, data.get("role"))
        return reponse_ok({}, "Rôle modifié")
    except (PermissionError, ValueError) as e:
        return reponse_erreur(str(e))


@business.route("/membres/<uid>", methods=["DELETE"])
@token_requis
def retirer(uid):
    try:
        eid = request.args.get("entreprise_id")
        retirer_membre(eid, request.user_id, uid)
        return reponse_ok({}, "Membre retiré")
    except PermissionError as e:
        return reponse_erreur(str(e), 403)


# ─────────────────────────────────────────────
# FINANCES
# ─────────────────────────────────────────────

@business.route("/finances/transactions", methods=["POST"])
@token_requis
def ajouter_transaction():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        txn = creer_transaction(eid, data)
        return reponse_ok(txn, "Transaction créée", 201)
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/finances/transactions", methods=["GET"])
@token_requis
def lister_transactions():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        filtres = {
            "type": request.args.get("type"),
            "categorie": request.args.get("categorie"),
            "mois": request.args.get("mois"),
            "date_debut": request.args.get("date_debut"),
            "date_fin": request.args.get("date_fin")
        }
        txns = get_transactions(eid, {k: v for k, v in filtres.items() if v})
        return reponse_ok({"transactions": txns, "total": len(txns)})
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/finances/transactions/<tid>", methods=["PUT"])
@token_requis
def update_transaction(tid):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        txn = modifier_transaction(tid, eid, data)
        return reponse_ok(txn, "Transaction mise à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@business.route("/finances/transactions/<tid>", methods=["DELETE"])
@token_requis
def delete_transaction(tid):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        supprimer_transaction(tid, eid)
        return reponse_ok({}, "Transaction supprimée")
    except Exception as e:
        return reponse_erreur(str(e))


@business.route("/finances/import-csv", methods=["POST"])
@token_requis
def import_csv():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        contenu = data.get("contenu_csv", "")
        if not contenu:
            return reponse_erreur("contenu_csv requis")
        result = importer_csv(eid, contenu, data.get("mapping"))
        return reponse_ok(result, f"{result['importees']} transactions importées")
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/finances/dashboard", methods=["GET"])
@token_requis
def dashboard_finances():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        periode = request.args.get("periode", "mois_courant")
        data = get_dashboard_financier(eid, periode)
        return reponse_ok(data)
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/finances/anomalies", methods=["GET"])
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

@business.route("/rh/employes", methods=["POST"])
@token_requis
def add_employe():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        emp = creer_employe(eid, data)
        return reponse_ok(emp, "Employé créé", 201)
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/rh/employes", methods=["GET"])
@token_requis
def list_employes():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        statut = request.args.get("statut")
        employes = get_employes(eid, statut)
        return reponse_ok({"employes": employes, "total": len(employes)})
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/rh/employes/<empid>", methods=["GET"])
@token_requis
def get_emp(empid):
    eid = request.args.get("entreprise_id")
    if not eid or not _check_acces(eid, request.user_id):
        return reponse_erreur("Accès refusé", 403)
    emp = get_employe(empid, eid)
    if not emp:
        return reponse_erreur("Employé non trouvé", 404)
    return reponse_ok(emp)


@business.route("/rh/employes/<empid>", methods=["PUT"])
@token_requis
def update_emp(empid):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        emp = modifier_employe(empid, eid, data)
        return reponse_ok(emp, "Employé mis à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@business.route("/rh/employes/<empid>", methods=["DELETE"])
@token_requis
def delete_emp(empid):
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        supprimer_employe(empid, eid)
        return reponse_ok({}, "Employé supprimé")
    except Exception as e:
        return reponse_erreur(str(e))


@business.route("/rh/masse-salariale", methods=["GET"])
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

@business.route("/rh/conges", methods=["POST"])
@token_requis
def add_conge():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        conge = creer_conge(eid, data)
        return reponse_ok(conge, "Demande de congé créée", 201)
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/rh/conges", methods=["GET"])
@token_requis
def list_conges():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        data = get_conges(eid, request.args.get("employe_id"), request.args.get("statut"))
        return reponse_ok(data)
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/rh/conges/<cid>/valider", methods=["PUT"])
@token_requis
def valider(cid):
    try:
        data = get_json()
        eid = data.get("entreprise_id")
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

@business.route("/rh/pointages", methods=["POST"])
@token_requis
def add_pointage():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        ptg = pointer_heures(eid, data)
        return reponse_ok(ptg, "Pointage enregistré", 201)
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/rh/pointages", methods=["GET"])
@token_requis
def list_pointages():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        data = get_pointages(eid, request.args.get("employe_id"), request.args.get("mois"))
        return reponse_ok(data)
    except Exception as e:
        return reponse_erreur(str(e), 500)


# ─────────────────────────────────────────────
# RH — ÉVALUATIONS
# ─────────────────────────────────────────────

@business.route("/rh/evaluations", methods=["POST"])
@token_requis
def add_evaluation():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        eval_ = creer_evaluation(eid, data)
        return reponse_ok(eval_, "Évaluation créée", 201)
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


@business.route("/rh/evaluations", methods=["GET"])
@token_requis
def list_evaluations():
    try:
        eid = request.args.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)
        data = get_evaluations(eid, request.args.get("employe_id"))
        return reponse_ok(data)
    except Exception as e:
        return reponse_erreur(str(e), 500)


# ─────────────────────────────────────────────
# ANALYTICS IA
# ─────────────────────────────────────────────

@business.route("/analytics/analyser", methods=["POST"])
@token_requis
def analyser_business():
    try:
        data = get_json()
        eid = data.get("entreprise_id")
        if not eid or not _check_acces(eid, request.user_id):
            return reponse_erreur("Accès refusé", 403)

        # Collecter les données
        dashboard = get_dashboard_financier(eid, "annee")
        masse_sal = get_masse_salariale(eid)

        donnees = {
            "ca_annuel": dashboard.get("revenus", 0),
            "depenses_annuelles": dashboard.get("depenses", 0),
            "marge_nette": dashboard.get("marge_nette", 0),
            "taux_marge": dashboard.get("taux_marge", 0),
            "nb_employes": masse_sal.get("nb_employes_actifs", 0),
            "cout_masse_salariale_mensuel": masse_sal.get("cout_total_mensuel", 0),
            "part_salaires_depenses": round(
                masse_sal.get("cout_total_mensuel", 0) * 12 / max(dashboard.get("depenses", 1), 1) * 100, 1
            ),
            "depenses_par_categorie": dashboard.get("depenses_par_categorie", []),
            "evolution_12_mois": dashboard.get("evolution_mensuelle", [])
        }

        from agent import analyser_activite
        analyse = analyser_activite(donnees, "dirigeant de PME")
        return reponse_ok(analyse, "Analyse générée")
    except Exception as e:
        return reponse_erreur(str(e), 500)


