"""
api.py — API Flask sécurisée avec SQLite/PostgreSQL
Authentification JWT + bcrypt pour les mots de passe
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import json
import traceback
from datetime import datetime, date, timedelta
import uuid

from database import get_db, row_to_dict, rows_to_list, init_db
from auth import (
    inscrire_user, connecter_user, get_user_by_id,
    modifier_user, changer_plan, supprimer_user, verifier_token,
    changer_mdp_initial
)
from agent import (
    generer_plan_journalier,
    generer_email_prospect,
    generer_message_linkedin,
    generer_offre_commerciale,
    generer_relance,
    analyser_activite,
    generer_post_linkedin,
)

app = Flask(__name__)

# ── MODULE BUSINESS (enregistrer AVANT CORS) ──
from api_business import business
app.register_blueprint(business)
from database_business import init_db_business
init_db_business()

# ── CORS — après register_blueprint pour couvrir TOUTES les routes ──
CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    "allow_headers": ["Content-Type", "Authorization", "Accept"],
    "supports_credentials": False
}})

# Initialiser la base de données au démarrage
init_db()


# ─────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────

def reponse_ok(data, message="Succès", code=200):
    return jsonify({"statut": "ok", "message": message, "data": data}), code

def reponse_erreur(message, code=400):
    return jsonify({"statut": "erreur", "message": message}), code

def get_json():
    return request.get_json() or {}

def generer_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


# ─────────────────────────────────────────────
# MIDDLEWARE JWT
# ─────────────────────────────────────────────

def token_requis(f):
    """Décorateur qui vérifie le token JWT."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "OPTIONS":
            return jsonify({}), 200
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            return reponse_erreur("Token manquant", 401)
        user_id = verifier_token(token)
        if not user_id:
            return reponse_erreur("Token invalide ou expiré", 401)
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# ROUTES AUTH
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def accueil():
    return reponse_ok({"nom": "Agent IA", "version": "2.0", "statut": "en ligne"})


@app.route("/auth/inscription", methods=["POST"])
def inscription():
    """Inscrit un nouvel utilisateur."""
    try:
        data = get_json()
        result = inscrire_user(data)
        return reponse_ok(result, "Compte créé avec succès", 201)
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(f"Erreur serveur: {str(e)}", 500)


@app.route("/auth/connexion", methods=["POST"])
def connexion():
    """Connecte un utilisateur."""
    try:
        data = get_json()
        email = data.get("email", "")
        password = data.get("password", "")
        if not email or not password:
            return reponse_erreur("Email et mot de passe requis")
        result = connecter_user(email, password)
        return reponse_ok(result, "Connexion réussie")
    except ValueError as e:
        return reponse_erreur(str(e), 401)
    except Exception as e:
        return reponse_erreur(f"Erreur serveur: {str(e)}", 500)


@app.route("/auth/profil", methods=["GET"])
@token_requis
def get_profil():
    """Récupère le profil de l'utilisateur connecté."""
    user = get_user_by_id(request.user_id)
    if not user:
        return reponse_erreur("Utilisateur non trouvé", 404)
    return reponse_ok(user)


@app.route("/auth/profil", methods=["PUT"])
@token_requis
def update_profil():
    """Modifie le profil."""
    try:
        data = get_json()
        user = modifier_user(request.user_id, data)
        return reponse_ok(user, "Profil mis à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/auth/plan", methods=["PUT"])
@token_requis
def update_plan():
    """Change le plan d'abonnement."""
    try:
        data = get_json()
        plan = data.get("plan")
        if plan not in ["starter", "pro", "premium", "business"]:
            return reponse_erreur("Plan invalide")
        user = changer_plan(request.user_id, plan)
        return reponse_ok(user, f"Plan changé en {plan}")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/auth/supprimer", methods=["DELETE"])
@token_requis
def delete_compte():
    """Supprime le compte et toutes les données."""
    supprimer_user(request.user_id)
    return reponse_ok({}, "Compte supprimé")


@app.route("/auth/changer-mdp-initial", methods=["POST", "OPTIONS"])
@token_requis
def changer_mdp_initial_route():
    """Change le mot de passe temporaire lors de la 1ère connexion."""
    if request.method == "OPTIONS":
        return jsonify({}), 200
    try:
        data           = get_json()
        ancien         = data.get("ancien_password", "")
        nouveau        = data.get("nouveau_password", "")
        if not ancien or not nouveau:
            return reponse_erreur("Les deux mots de passe sont requis")
        user = changer_mdp_initial(request.user_id, ancien, nouveau)
        return reponse_ok(user, "Mot de passe modifié")
    except ValueError as e:
        return reponse_erreur(str(e))
    except Exception as e:
        return reponse_erreur(str(e), 500)


# ─────────────────────────────────────────────
# ROUTES AGENT IA (freelance)
# ─────────────────────────────────────────────

@app.route("/agent/plan-journalier", methods=["POST"])
@token_requis
def agent_plan_journalier():
    try:
        data = get_json()
        prospects = data.get("prospects", [])
        taches = data.get("taches_en_cours", [])
        metier = data.get("metier") or (get_user_by_id(request.user_id) or {}).get("metier", "indépendant")
        plan = generer_plan_journalier(prospects, taches, metier)
        return reponse_ok(plan)
    except Exception as e:
        return reponse_erreur(f"Erreur génération plan: {e}", 500)


@app.route("/agent/email", methods=["POST"])
@token_requis
def agent_email():
    try:
        data = get_json()
        prospect = data.get("prospect") or {}
        contexte = data.get("contexte", "premier contact")
        metier = data.get("metier") or (get_user_by_id(request.user_id) or {}).get("metier", "indépendant")
        style = data.get("style", "professionnel")
        email = generer_email_prospect(prospect, contexte, metier, style)
        return reponse_ok(email)
    except Exception as e:
        return reponse_erreur(f"Erreur génération email: {e}", 500)


@app.route("/agent/post-linkedin", methods=["POST"])
@token_requis
def agent_post_linkedin():
    try:
        data = get_json()
        sujet = data.get("sujet", "")
        metier = data.get("metier") or (get_user_by_id(request.user_id) or {}).get("metier", "indépendant")
        objectif = data.get("objectif", "notoriété")
        post = generer_post_linkedin(sujet, metier, objectif)
        return reponse_ok(post)
    except Exception as e:
        return reponse_erreur(f"Erreur génération post LinkedIn: {e}", 500)


@app.route("/agent/offre-commerciale", methods=["POST"])
@token_requis
def agent_offre_commerciale():
    try:
        data = get_json()
        service = data.get("service") or {}
        cible = data.get("cible") or {}
        metier = data.get("metier") or (get_user_by_id(request.user_id) or {}).get("metier", "indépendant")
        offre = generer_offre_commerciale(service, cible, metier)
        return reponse_ok(offre)
    except Exception as e:
        return reponse_erreur(f"Erreur génération offre: {e}", 500)


@app.route("/agent/relance", methods=["POST"])
@token_requis
def agent_relance():
    try:
        data = get_json()
        prospect = data.get("prospect") or {}
        nb_jours = int(data.get("nb_jours_sans_reponse", 3))
        metier = data.get("metier") or (get_user_by_id(request.user_id) or {}).get("metier", "indépendant")
        relance = generer_relance(prospect, nb_jours, metier)
        return reponse_ok(relance)
    except Exception as e:
        return reponse_erreur(f"Erreur génération relance: {e}", 500)


@app.route("/agent/analyser-activite", methods=["POST"])
@token_requis
def agent_analyser_activite():
    try:
        data = get_json()
        metier = data.get("metier") or (get_user_by_id(request.user_id) or {}).get("metier", "indépendant")
        donnees = data.get("donnees_activite") or data
        analyse = analyser_activite(donnees, metier)
        return reponse_ok(analyse)
    except Exception as e:
        return reponse_erreur(f"Erreur analyse activité: {e}", 500)


# ─────────────────────────────────────────────
# ROUTES CRM
# ─────────────────────────────────────────────

@app.route("/crm/prospects", methods=["POST"])
@token_requis
def creer_prospect():
    try:
        data = get_json()
        if not data.get("nom"):
            return reponse_erreur("Le champ 'nom' est requis")
        conn = get_db()
        pid = generer_id("PRO")
        conn.execute("""
            INSERT INTO prospects (id, user_id, nom, entreprise, email, telephone,
                linkedin, secteur, besoin, source, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pid, request.user_id, data["nom"], data.get("entreprise",""),
              data.get("email",""), data.get("telephone",""), data.get("linkedin",""),
              data.get("secteur",""), data.get("besoin",""), data.get("source",""),
              data.get("notes","")))
        conn.commit()
        row = conn.execute("SELECT * FROM prospects WHERE id=?", (pid,)).fetchone()
        conn.close()
        return reponse_ok(row_to_dict(row), "Prospect créé", 201)
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects", methods=["GET"])
@token_requis
def get_prospects():
    try:
        conn = get_db()
        statut = request.args.get("statut")
        if statut:
            rows = conn.execute(
                "SELECT * FROM prospects WHERE user_id=? AND statut=? ORDER BY date_ajout DESC",
                (request.user_id, statut)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM prospects WHERE user_id=? ORDER BY date_ajout DESC",
                (request.user_id,)
            ).fetchall()
        conn.close()
        return reponse_ok({"prospects": rows_to_list(rows), "total": len(rows)})
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects/<pid>", methods=["PUT"])
@token_requis
def update_prospect(pid):
    try:
        data = get_json()
        conn = get_db()
        champs = ["nom","entreprise","email","telephone","linkedin","secteur",
                  "besoin","source","notes","statut","valeur_estimee","dernier_contact"]
        sets = []
        vals = []
        for k in champs:
            if k in data:
                sets.append(f"{k}=?")
                vals.append(data[k])
        if sets:
            vals += [pid, request.user_id]
            conn.execute(f"UPDATE prospects SET {','.join(sets)} WHERE id=? AND user_id=?", vals)
            conn.commit()
        row = conn.execute("SELECT * FROM prospects WHERE id=?", (pid,)).fetchone()
        conn.close()
        return reponse_ok(row_to_dict(row), "Prospect mis à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects/<pid>/statut", methods=["PUT"])
@token_requis
def update_statut_prospect(pid):
    try:
        data = get_json()
        conn = get_db()
        statut = data.get("statut")
        if statut:
            conn.execute(
                "UPDATE prospects SET statut=?, dernier_contact=? WHERE id=? AND user_id=?",
                (statut, datetime.now().isoformat(), pid, request.user_id)
            )
            conn.commit()
        row = conn.execute("SELECT * FROM prospects WHERE id=?", (pid,)).fetchone()
        conn.close()
        return reponse_ok(row_to_dict(row), "Statut mis à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects/<pid>", methods=["DELETE"])
@token_requis
def delete_prospect(pid):
    conn = get_db()
    conn.execute("DELETE FROM prospects WHERE id=? AND user_id=?", (pid, request.user_id))
    conn.commit()
    conn.close()
    return reponse_ok({}, "Prospect supprimé")


@app.route("/crm/prospects/<pid>/interactions", methods=["POST"])
@token_requis
def ajouter_interaction(pid):
    try:
        data = get_json()
        conn = get_db()
        iid = generer_id("INT")
        conn.execute("""
            INSERT INTO interactions (id, user_id, prospect_id, type, contenu, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (iid, request.user_id, pid, data.get("type","note"),
              (data.get("contenu") or data.get("note") or ""),
              data.get("date", date.today().isoformat())))
        conn.execute(
            "UPDATE prospects SET dernier_contact=? WHERE id=? AND user_id=?",
            (date.today().isoformat(), pid, request.user_id)
        )
        conn.commit()
        conn.close()
        return reponse_ok({}, "Interaction ajoutée", 201)
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects/<pid>/interactions", methods=["GET"])
@token_requis
def get_interactions(pid):
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM interactions WHERE prospect_id=? AND user_id=? ORDER BY date DESC",
            (pid, request.user_id)
        ).fetchall()
        conn.close()
        return reponse_ok({"interactions": rows_to_list(rows)})
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/stats", methods=["GET"])
@token_requis
def crm_stats():
    try:
        conn = get_db()
        uid = request.user_id
        seuil = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")

        def scalar(row):
            if row is None:
                return 0
            if isinstance(row, dict):
                return list(row.values())[0]
            return row[0]

        total        = scalar(conn.execute("SELECT COUNT(*) as c FROM prospects WHERE user_id=?", (uid,)).fetchone())
        clients      = scalar(conn.execute("SELECT COUNT(*) as c FROM prospects WHERE user_id=? AND statut='gagne'", (uid,)).fetchone())
        interactions = scalar(conn.execute("SELECT COUNT(*) as c FROM interactions WHERE user_id=?", (uid,)).fetchone())
        pipeline     = scalar(conn.execute(
            "SELECT COALESCE(SUM(valeur_estimee),0) as c FROM prospects WHERE user_id=? AND statut NOT IN ('gagne','perdu')",
            (uid,)
        ).fetchone())
        a_relancer = scalar(conn.execute("""
            SELECT COUNT(*) as c FROM prospects WHERE user_id=? AND statut NOT IN ('gagne','perdu')
            AND (dernier_contact IS NULL OR dernier_contact < ? OR dernier_contact = '')
        """, (uid, seuil)).fetchone())

        rows = conn.execute(
            "SELECT statut, COUNT(*) as nb FROM prospects WHERE user_id=? GROUP BY statut",
            (uid,)
        ).fetchall()
        repartition = {r["statut"]: r["nb"] for r in rows_to_list(rows)}
        conn.close()

        taux = round((clients / total * 100), 1) if total > 0 else 0
        return reponse_ok({
            "total_prospects": total,
            "total_clients": clients,
            "total_interactions": interactions,
            "taux_conversion": taux,
            "valeur_pipeline": pipeline,
            "a_relancer_urgence": a_relancer,
            "repartition_statuts": repartition
        })
    except Exception as e:
        return reponse_erreur(str(e))


# ─────────────────────────────────────────────
# ROUTES DEVIS
# ─────────────────────────────────────────────

@app.route("/devis", methods=["POST"])
@token_requis
def creer_devis():
    try:
        data = get_json()
        if not data.get("client"):
            return reponse_erreur("Le champ 'client' est requis")
        conn = get_db()
        did = generer_id("DEV")
        lignes = json.dumps(data.get("lignes", []), ensure_ascii=False)
        commercial_id = data.get("commercial_id")
        conn.execute("""
            INSERT INTO devis (id, user_id, numero, client, adresse_client, objet,
                lignes, montant_ht, montant_ttc, tva, statut, date, validite, delai, conditions, commercial_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (did, request.user_id, data.get("numero",""), data["client"],
              data.get("adresse",""), data.get("objet",""), lignes,
              data.get("montant_ht",0), data.get("montant_ttc",0), data.get("tva",20),
              data.get("statut","brouillon"), data.get("date",""), data.get("validite",""),
              data.get("delai",""), data.get("conditions",""), commercial_id))
        conn.commit()
        row = conn.execute("SELECT * FROM devis WHERE id=?", (did,)).fetchone()
        conn.close()
        d = row_to_dict(row)
        d["lignes"] = json.loads(d.get("lignes") or "[]")
        return reponse_ok(d, "Devis créé", 201)
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/devis", methods=["GET"])
@token_requis
def get_devis():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM devis WHERE user_id=? ORDER BY date_creation DESC",
            (request.user_id,)
        ).fetchall()
        conn.close()
        devis = []
        for r in rows_to_list(rows):
            r["lignes"] = json.loads(r.get("lignes") or "[]")
            devis.append(r)
        return reponse_ok({"devis": devis, "total": len(devis)})
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/devis/<did>", methods=["PUT"])
@token_requis
def update_devis(did):
    try:
        data = get_json()
        conn = get_db()
        champs = ["numero","client","adresse_client","objet","lignes","montant_ht",
                  "montant_ttc","tva","statut","date","validite","delai","conditions","commercial_id"]
        sets = []
        vals = []
        for k in champs:
            if k in data:
                val = data[k]
                if k == "lignes" and isinstance(val, list):
                    val = json.dumps(val, ensure_ascii=False)
                sets.append(f"{k}=?")
                vals.append(val)
        if sets:
            vals += [did, request.user_id]
            conn.execute(f"UPDATE devis SET {','.join(sets)} WHERE id=? AND user_id=?", vals)
            conn.commit()
        row = conn.execute("SELECT * FROM devis WHERE id=?", (did,)).fetchone()
        conn.close()
        d = row_to_dict(row)
        d["lignes"] = json.loads(d.get("lignes") or "[]")
        return reponse_ok(d, "Devis mis à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/devis/<did>", methods=["DELETE"])
@token_requis
def delete_devis(did):
    conn = get_db()
    conn.execute("DELETE FROM devis WHERE id=? AND user_id=?", (did, request.user_id))
    conn.commit()
    conn.close()
    return reponse_ok({}, "Devis supprimé")


@app.route("/devis/<did>/convertir", methods=["POST"])
@token_requis
def convertir_devis(did):
    try:
        conn = get_db()
        devis_row = conn.execute(
            "SELECT * FROM devis WHERE id=? AND user_id=?",
            (did, request.user_id)
        ).fetchone()
        if not devis_row:
            conn.close()
            return reponse_erreur("Devis non trouvé", 404)

        d = dict(devis_row)
        nb_row = conn.execute(
            "SELECT COUNT(*) as c FROM factures WHERE user_id=?",
            (request.user_id,)
        ).fetchone()
        nb = list(nb_row.values())[0] if isinstance(nb_row, dict) else nb_row[0]
        annee = datetime.now().year
        num = f"FAC-{annee}-{str(nb+1).zfill(3)}"
        echeance = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        fid = generer_id("FAC")
        conn.execute("""
            INSERT INTO factures (id, user_id, numero, client, adresse_client, objet,
                lignes, montant_ht, montant_ttc, tva, statut, date, date_echeance,
                paiement, conditions, devis_id, commercial_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fid, request.user_id, num, d["client"], d.get("adresse_client",""),
              d.get("objet",""), d.get("lignes","[]"), d.get("montant_ht",0),
              d.get("montant_ttc",0), d.get("tva",20), "non_payee",
              datetime.now().strftime("%Y-%m-%d"), echeance,
              "Virement bancaire", d.get("conditions",""), did,
              d.get("commercial_id")))

        conn.execute("UPDATE devis SET statut='accepte' WHERE id=?", (did,))
        conn.commit()

        facture = row_to_dict(conn.execute("SELECT * FROM factures WHERE id=?", (fid,)).fetchone())
        conn.close()
        facture["lignes"] = json.loads(facture.get("lignes") or "[]")
        return reponse_ok({"facture": facture, "numero": num}, "Facture créée")
    except Exception as e:
        return reponse_erreur(str(e))


# ─────────────────────────────────────────────
# ROUTES FACTURES
# ─────────────────────────────────────────────

@app.route("/factures", methods=["POST"])
@token_requis
def creer_facture():
    try:
        data = get_json()
        if not data.get("client"):
            return reponse_erreur("Le champ 'client' est requis")
        conn = get_db()
        fid = generer_id("FAC")
        lignes = json.dumps(data.get("lignes", []), ensure_ascii=False)
        conn.execute("""
            INSERT INTO factures (id, user_id, numero, client, adresse_client, objet,
                lignes, montant_ht, montant_ttc, tva, statut, date, date_echeance,
                paiement, conditions, mentions, commercial_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fid, request.user_id, data.get("numero",""), data["client"],
              data.get("adresse",""), data.get("objet",""), lignes,
              data.get("montant_ht",0), data.get("montant_ttc",0), data.get("tva",20),
              data.get("statut","non_payee"), data.get("date",""), data.get("date_echeance",""),
              data.get("paiement","Virement bancaire"), data.get("conditions",""),
              data.get("mentions",""), data.get("commercial_id")))
        conn.commit()
        row = conn.execute("SELECT * FROM factures WHERE id=?", (fid,)).fetchone()
        conn.close()
        f = row_to_dict(row)
        f["lignes"] = json.loads(f.get("lignes") or "[]")
        return reponse_ok(f, "Facture créée", 201)
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/factures", methods=["GET"])
@token_requis
def get_factures():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM factures WHERE user_id=? ORDER BY date_creation DESC",
            (request.user_id,)
        ).fetchall()
        conn.close()
        factures = []
        for r in rows_to_list(rows):
            r["lignes"] = json.loads(r.get("lignes") or "[]")
            factures.append(r)
        return reponse_ok({"factures": factures, "total": len(factures)})
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/factures/<fid>", methods=["PUT"])
@token_requis
def update_facture(fid):
    try:
        data = get_json()
        conn = get_db()
        champs = ["numero","client","adresse_client","objet","lignes","montant_ht",
                 "montant_ttc","tva","statut","date","date_echeance","paiement",
                 "conditions","mentions","commercial_id"]
        sets = []
        vals = []
        for k in champs:
            if k in data:
                val = data[k]
                if k == "lignes" and isinstance(val, list):
                    val = json.dumps(val, ensure_ascii=False)
                sets.append(f"{k}=?")
                vals.append(val)
        if sets:
            vals += [fid, request.user_id]
            conn.execute(f"UPDATE factures SET {','.join(sets)} WHERE id=? AND user_id=?", vals)
            conn.commit()
        row = conn.execute("SELECT * FROM factures WHERE id=?", (fid,)).fetchone()
        conn.close()
        f = row_to_dict(row)
        f["lignes"] = json.loads(f.get("lignes") or "[]")
        return reponse_ok(f, "Facture mise à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/factures/<fid>", methods=["DELETE"])
@token_requis
def delete_facture(fid):
    conn = get_db()
    conn.execute("DELETE FROM factures WHERE id=? AND user_id=?", (fid, request.user_id))
    conn.commit()
    conn.close()
    return reponse_ok({}, "Facture supprimée")


@app.route("/factures/<fid>/statut", methods=["PUT"])
@token_requis
def update_statut_facture(fid):
    try:
        data = get_json()
        statut = data.get("statut")
        if statut not in ["non_payee", "payee", "en_retard", "annulee"]:
            return reponse_erreur("Statut invalide")
        conn = get_db()
        conn.execute(
            "UPDATE factures SET statut=? WHERE id=? AND user_id=?",
            (statut, fid, request.user_id)
        )
        conn.commit()
        conn.close()
        return reponse_ok({}, "Statut mis à jour")
    except Exception as e:
        return reponse_erreur(str(e))


# ─────────────────────────────────────────────
# ENVOI PAR EMAIL
# ─────────────────────────────────────────────

@app.route("/devis/<did>/envoyer", methods=["POST", "OPTIONS"])
@token_requis
def envoyer_devis_route(did):
    if request.method == "OPTIONS":
        return "", 204
    try:
        from email_utils import envoyer_devis, smtp_disponible
        data = get_json()
        email_dest   = (data.get("email") or "").strip()
        message_perso = data.get("message", "")
        if not email_dest:
            return reponse_erreur("Email destinataire requis")
        if not smtp_disponible():
            return reponse_erreur("SMTP non configuré sur le serveur (SMTP_USER / SMTP_PASSWORD)", 503)
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM devis WHERE id=? AND user_id=?", (did, request.user_id)
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return reponse_erreur("Devis non trouvé", 404)
        devis = dict(row)
        devis["lignes"] = json.loads(devis.get("lignes") or "[]")
        user  = get_user_by_id(request.user_id) or {}
        profil = user.get("profil_legal") or {}
        if not profil.get("nom"):
            profil["nom"] = f"{user.get('prenom','')} {user.get('nom','')}".strip()
        if not profil.get("email"):
            profil["email"] = user.get("email", "")
        envoyer_devis(devis, profil, email_dest, message_perso)
        now_iso = datetime.utcnow().isoformat(timespec="seconds")
        conn2 = get_db()
        try:
            conn2.execute(
                "UPDATE devis SET envoye_le=?, statut=CASE WHEN statut='brouillon' THEN 'envoye' ELSE statut END "
                "WHERE id=? AND user_id=?",
                (now_iso, did, request.user_id),
            )
            conn2.commit()
        finally:
            conn2.close()
        return reponse_ok({}, f"Devis envoyé à {email_dest}")
    except RuntimeError as e:
        return reponse_erreur(str(e), 503)
    except Exception as e:
        return reponse_erreur(str(e), 500)


@app.route("/factures/<fid>/envoyer", methods=["POST", "OPTIONS"])
@token_requis
def envoyer_facture_route(fid):
    if request.method == "OPTIONS":
        return "", 204
    try:
        from email_utils import envoyer_facture, smtp_disponible
        data = get_json()
        email_dest    = (data.get("email") or "").strip()
        message_perso = data.get("message", "")
        if not email_dest:
            return reponse_erreur("Email destinataire requis")
        if not smtp_disponible():
            return reponse_erreur("SMTP non configuré sur le serveur (SMTP_USER / SMTP_PASSWORD)", 503)
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM factures WHERE id=? AND user_id=?", (fid, request.user_id)
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return reponse_erreur("Facture non trouvée", 404)
        facture = dict(row)
        facture["lignes"] = json.loads(facture.get("lignes") or "[]")
        user   = get_user_by_id(request.user_id) or {}
        profil = user.get("profil_legal") or {}
        if not profil.get("nom"):
            profil["nom"] = f"{user.get('prenom','')} {user.get('nom','')}".strip()
        if not profil.get("email"):
            profil["email"] = user.get("email", "")
        envoyer_facture(facture, profil, email_dest, message_perso)
        now_iso = datetime.utcnow().isoformat(timespec="seconds")
        conn2 = get_db()
        try:
            conn2.execute(
                "UPDATE factures SET envoye_le=? WHERE id=? AND user_id=?",
                (now_iso, fid, request.user_id),
            )
            conn2.commit()
        finally:
            conn2.close()
        return reponse_ok({}, f"Facture envoyée à {email_dest}")
    except RuntimeError as e:
        return reponse_erreur(str(e), 503)
    except Exception as e:
        return reponse_erreur(str(e), 500)


# ─────────────────────────────────────────────
# LANCEMENT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)