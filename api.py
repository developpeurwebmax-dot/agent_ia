"""
api.py — API Flask pour connecter Bubble à l'agent IA
Toutes les routes HTTP que Bubble appellera via l'API Connector

Pour lancer : python api.py
L'API sera disponible sur http://localhost:5000
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback

# Import des modules locaux
from agent import (
    generer_plan_journalier,
    generer_email_prospect,
    generer_message_linkedin,
    generer_relance,
    generer_post_linkedin,
    generer_offre_commerciale,
    analyser_activite,
    analyser_prix
)
from crm import (
    ajouter_prospect,
    modifier_prospect,
    changer_statut,
    supprimer_prospect,
    lister_prospects,
    obtenir_prospect,
    prospects_a_relancer,
    rechercher_prospects,
    enregistrer_interaction,
    historique_prospect,
    statistiques_crm
)
from tasks import (
    creer_tache,
    modifier_tache,
    terminer_tache,
    supprimer_tache,
    taches_du_jour,
    taches_en_retard,
    lister_taches,
    taches_semaine,
    creer_routine,
    routines_du_jour,
    executer_routine,
    definir_objectif,
    mettre_a_jour_objectif,
    statistiques_productivite
)

app = Flask(__name__)
CORS(app)  # Autorise les appels depuis Bubble


# ─────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────

def reponse_ok(data, message="Succès"):
    return jsonify({"statut": "ok", "message": message, "data": data}), 200

def reponse_erreur(message, code=400):
    return jsonify({"statut": "erreur", "message": message}), code

def get_json():
    """Récupère le body JSON de la requête."""
    return request.get_json() or {}


# ─────────────────────────────────────────────
# ROUTE DE TEST
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def accueil():
    """Route de test pour vérifier que l'API est en ligne."""
    return reponse_ok({
        "nom": "Agent IA pour Indépendants",
        "version": "1.0",
        "statut": "en ligne",
        "routes_disponibles": [
            "GET  /",
            "POST /agent/plan-journalier",
            "POST /agent/email",
            "POST /agent/message-linkedin",
            "POST /agent/relance",
            "POST /agent/post-linkedin",
            "POST /agent/offre-commerciale",
            "POST /agent/analyser-activite",
            "POST /agent/analyser-prix",
            "POST /crm/prospects",
            "GET  /crm/prospects",
            "GET  /crm/prospects/<id>",
            "PUT  /crm/prospects/<id>",
            "DELETE /crm/prospects/<id>",
            "PUT  /crm/prospects/<id>/statut",
            "GET  /crm/prospects/relancer",
            "GET  /crm/prospects/rechercher",
            "POST /crm/interactions",
            "GET  /crm/prospects/<id>/historique",
            "GET  /crm/stats",
            "POST /tasks/taches",
            "GET  /tasks/taches",
            "GET  /tasks/taches/jour",
            "GET  /tasks/taches/semaine",
            "PUT  /tasks/taches/<id>",
            "POST /tasks/taches/<id>/terminer",
            "DELETE /tasks/taches/<id>",
            "POST /tasks/routines",
            "GET  /tasks/routines/jour",
            "POST /tasks/routines/<id>/executer",
            "POST /tasks/objectifs",
            "PUT  /tasks/objectifs/<id>/progression",
            "GET  /tasks/stats"
        ]
    })


# ═══════════════════════════════════════════════
# ROUTES AGENT IA
# ═══════════════════════════════════════════════

@app.route("/agent/plan-journalier", methods=["POST"])
def plan_journalier():
    """
    Génère le plan d'action du matin.
    
    Body JSON:
    {
        "metier": "consultant RH",
        "prospects": [...],
        "taches_en_cours": [...]
    }
    """
    try:
        data = get_json()
        metier = data.get("metier", "indépendant")
        prospects = data.get("prospects", [])
        taches = data.get("taches_en_cours", [])
        
        # Si pas de données fournies, récupérer automatiquement
        if not prospects:
            prospects = lister_prospects(statut="contacte") + lister_prospects(statut="en_discussion")
        if not taches:
            taches = taches_du_jour()
        
        plan = generer_plan_journalier(prospects, taches, metier)
        return reponse_ok(plan, "Plan journalier généré")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/agent/email", methods=["POST"])
def generer_email():
    """
    Génère un email de prospection ou relance.
    
    Body JSON:
    {
        "prospect": {"nom": "...", "entreprise": "...", "besoin": "..."},
        "contexte": "premier contact",
        "metier": "consultant",
        "style": "professionnel"
    }
    """
    try:
        data = get_json()
        prospect = data.get("prospect", {})
        contexte = data.get("contexte", "premier contact")
        metier = data.get("metier", "indépendant")
        style = data.get("style", "professionnel")
        
        # Si prospect_id fourni, récupérer depuis CRM
        if "prospect_id" in data:
            prospect = obtenir_prospect(data["prospect_id"]) or prospect
        
        email = generer_email_prospect(prospect, contexte, metier, style)
        return reponse_ok(email, "Email généré")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/agent/message-linkedin", methods=["POST"])
def message_linkedin():
    """
    Génère un message LinkedIn.
    
    Body JSON:
    {
        "prospect": {"nom": "...", "entreprise": "...", "poste": "..."},
        "metier": "graphiste freelance"
    }
    """
    try:
        data = get_json()
        prospect = data.get("prospect", {})
        metier = data.get("metier", "indépendant")
        
        if "prospect_id" in data:
            prospect = obtenir_prospect(data["prospect_id"]) or prospect
        
        message = generer_message_linkedin(prospect, metier)
        return reponse_ok(message, "Message LinkedIn généré")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/agent/relance", methods=["POST"])
def relance():
    """
    Génère un message de relance.
    
    Body JSON:
    {
        "prospect_id": "PRO_...",  OU "prospect": {...},
        "nb_jours_sans_reponse": 5,
        "metier": "..."
    }
    """
    try:
        data = get_json()
        metier = data.get("metier", "indépendant")
        nb_jours = data.get("nb_jours_sans_reponse", 5)
        
        prospect = data.get("prospect", {})
        if "prospect_id" in data:
            prospect = obtenir_prospect(data["prospect_id"]) or prospect
        
        msg = generer_relance(prospect, nb_jours, metier)
        return reponse_ok(msg, "Message de relance généré")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/agent/post-linkedin", methods=["POST"])
def post_linkedin():
    """
    Génère un post LinkedIn.
    
    Body JSON:
    {
        "sujet": "comment j'ai trouvé 3 clients en 1 semaine",
        "metier": "coach business",
        "objectif": "notoriété"
    }
    """
    try:
        data = get_json()
        sujet = data.get("sujet", "")
        metier = data.get("metier", "indépendant")
        objectif = data.get("objectif", "notoriété")
        
        if not sujet:
            return reponse_erreur("Le champ 'sujet' est requis")
        
        post = generer_post_linkedin(sujet, metier, objectif)
        return reponse_ok(post, "Post LinkedIn généré")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/agent/offre-commerciale", methods=["POST"])
def offre_commerciale():
    """
    Génère une offre commerciale.
    
    Body JSON:
    {
        "service": {"nom": "...", "description": "...", "livrables": [], "duree": "..."},
        "cible": {"secteur": "...", "taille_entreprise": "...", "probleme_principal": "..."},
        "metier": "..."
    }
    """
    try:
        data = get_json()
        service = data.get("service", {})
        cible = data.get("cible", {})
        metier = data.get("metier", "indépendant")
        
        offre = generer_offre_commerciale(service, cible, metier)
        return reponse_ok(offre, "Offre commerciale générée")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/agent/analyser-activite", methods=["POST"])
def analyser_activite_route():
    """
    Analyse l'activité et propose une stratégie.
    
    Body JSON:
    {
        "metier": "...",
        "ca_mois": 4500,
        "nb_clients_actifs": 3,
        "nb_prospects_pipeline": 8,
        "taux_conversion": 0.25,
        "services_vendus": ["coaching", "formation"],
        "charges_estimees": 800
    }
    """
    try:
        data = get_json()
        metier = data.pop("metier", "indépendant")
        analyse = analyser_activite(data, metier)
        return reponse_ok(analyse, "Analyse générée")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/agent/analyser-prix", methods=["POST"])
def analyser_prix_route():
    """
    Analyse les tarifs.
    
    Body JSON:
    {
        "metier": "développeur freelance",
        "localisation": "Paris",
        "tarif_journalier": 500,
        "tarif_horaire": 75,
        "forfaits": {"petit": 1500, "moyen": 3000}
    }
    """
    try:
        data = get_json()
        metier = data.pop("metier", "indépendant")
        localisation = data.pop("localisation", "France")
        analyse = analyser_prix(data, metier, localisation)
        return reponse_ok(analyse, "Analyse tarifaire générée")
    except Exception as e:
        return reponse_erreur(str(e))


# ═══════════════════════════════════════════════
# ROUTES CRM
# ═══════════════════════════════════════════════

@app.route("/crm/prospects", methods=["POST"])
def creer_prospect():
    """Ajoute un prospect. Body JSON: champs du prospect."""
    try:
        data = get_json()
        if not data.get("nom"):
            return reponse_erreur("Le champ 'nom' est requis")
        prospect = ajouter_prospect(**{k: v for k, v in data.items() if k in [
            "nom", "entreprise", "email", "telephone", "linkedin",
            "secteur", "besoin", "source", "notes"
        ]})
        return reponse_ok(prospect, "Prospect ajouté"), 201
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects", methods=["GET"])
def get_prospects():
    """Liste les prospects. Query params: statut, trier_par"""
    try:
        statut = request.args.get("statut")
        trier_par = request.args.get("trier_par", "date_ajout")
        prospects = lister_prospects(statut=statut, trier_par=trier_par)
        return reponse_ok({"prospects": prospects, "total": len(prospects)})
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects/<prospect_id>", methods=["GET"])
def get_prospect(prospect_id):
    """Récupère un prospect par ID."""
    prospect = obtenir_prospect(prospect_id)
    if not prospect:
        return reponse_erreur("Prospect non trouvé", 404)
    return reponse_ok(prospect)


@app.route("/crm/prospects/<prospect_id>", methods=["PUT"])
def update_prospect(prospect_id):
    """Modifie un prospect. Body JSON: champs à modifier."""
    try:
        data = get_json()
        prospect = modifier_prospect(prospect_id, data)
        if not prospect:
            return reponse_erreur("Prospect non trouvé", 404)
        return reponse_ok(prospect, "Prospect mis à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects/<prospect_id>", methods=["DELETE"])
def delete_prospect(prospect_id):
    """Supprime un prospect."""
    if supprimer_prospect(prospect_id):
        return reponse_ok({}, "Prospect supprimé")
    return reponse_erreur("Prospect non trouvé", 404)


@app.route("/crm/prospects/<prospect_id>/statut", methods=["PUT"])
def update_statut(prospect_id):
    """Change le statut. Body JSON: {statut, note}"""
    try:
        data = get_json()
        statut = data.get("statut")
        if not statut:
            return reponse_erreur("Le champ 'statut' est requis")
        prospect = changer_statut(prospect_id, statut, data.get("note", ""))
        if not prospect:
            return reponse_erreur("Prospect non trouvé", 404)
        return reponse_ok(prospect, f"Statut changé en '{statut}'")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects/relancer", methods=["GET"])
def get_a_relancer():
    """Prospects à relancer. Query param: jours (défaut: 7)"""
    jours = int(request.args.get("jours", 7))
    prospects = prospects_a_relancer(jours)
    return reponse_ok({"prospects": prospects, "total": len(prospects)})


@app.route("/crm/prospects/rechercher", methods=["GET"])
def rechercher():
    """Recherche dans les prospects. Query param: q"""
    terme = request.args.get("q", "")
    if not terme:
        return reponse_erreur("Paramètre 'q' requis")
    resultats = rechercher_prospects(terme)
    return reponse_ok({"resultats": resultats, "total": len(resultats)})


@app.route("/crm/interactions", methods=["POST"])
def creer_interaction():
    """
    Enregistre une interaction.
    
    Body JSON:
    {
        "prospect_id": "...",
        "type_interaction": "email_envoye",
        "contenu": "...",
        "resultat": "...",
        "prochain_contact": "2024-12-31T10:00:00"
    }
    """
    try:
        data = get_json()
        if not data.get("prospect_id") or not data.get("type_interaction"):
            return reponse_erreur("prospect_id et type_interaction requis")
        
        interaction = enregistrer_interaction(
            data["prospect_id"],
            data["type_interaction"],
            data.get("contenu", ""),
            data.get("resultat", ""),
            data.get("prochain_contact")
        )
        return reponse_ok(interaction, "Interaction enregistrée"), 201
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/crm/prospects/<prospect_id>/historique", methods=["GET"])
def get_historique(prospect_id):
    """Historique des interactions d'un prospect."""
    historique = historique_prospect(prospect_id)
    return reponse_ok({"interactions": historique, "total": len(historique)})


@app.route("/crm/stats", methods=["GET"])
def get_stats_crm():
    """Statistiques globales du CRM."""
    stats = statistiques_crm()
    return reponse_ok(stats)


# ═══════════════════════════════════════════════
# ROUTES TÂCHES
# ═══════════════════════════════════════════════

@app.route("/tasks/taches", methods=["POST"])
def creer_tache_route():
    """Crée une tâche. Body JSON: champs de la tâche."""
    try:
        data = get_json()
        if not data.get("titre"):
            return reponse_erreur("Le champ 'titre' est requis")
        tache = creer_tache(**{k: v for k, v in data.items() if k in [
            "titre", "description", "priorite", "categorie",
            "date_echeance", "duree_estimee_min", "prospect_id", "tags"
        ]})
        return reponse_ok(tache, "Tâche créée"), 201
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/tasks/taches", methods=["GET"])
def get_taches():
    """Liste les tâches. Query params: statut, categorie, priorite, prospect_id"""
    taches = lister_taches(
        statut=request.args.get("statut"),
        categorie=request.args.get("categorie"),
        priorite=request.args.get("priorite"),
        prospect_id=request.args.get("prospect_id")
    )
    return reponse_ok({"taches": taches, "total": len(taches)})


@app.route("/tasks/taches/jour", methods=["GET"])
def get_taches_jour():
    """Tâches du jour + routines."""
    taches = taches_du_jour()
    routines = routines_du_jour()
    return reponse_ok({
        "taches": taches,
        "routines": routines,
        "total_taches": len(taches),
        "total_routines": len(routines)
    })


@app.route("/tasks/taches/semaine", methods=["GET"])
def get_taches_semaine():
    """Tâches de la semaine organisées par jour."""
    semaine = taches_semaine()
    return reponse_ok(semaine)


@app.route("/tasks/taches/<tache_id>", methods=["PUT"])
def update_tache(tache_id):
    """Modifie une tâche."""
    try:
        data = get_json()
        tache = modifier_tache(tache_id, data)
        if not tache:
            return reponse_erreur("Tâche non trouvée", 404)
        return reponse_ok(tache, "Tâche mise à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/tasks/taches/<tache_id>/terminer", methods=["POST"])
def terminer_tache_route(tache_id):
    """Marque une tâche comme terminée. Body JSON: {duree_reelle_min, notes}"""
    try:
        data = get_json()
        tache = terminer_tache(tache_id, data.get("duree_reelle_min"), data.get("notes", ""))
        if not tache:
            return reponse_erreur("Tâche non trouvée", 404)
        return reponse_ok(tache, "Tâche terminée ✅")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/tasks/taches/<tache_id>", methods=["DELETE"])
def delete_tache(tache_id):
    """Supprime une tâche."""
    if supprimer_tache(tache_id):
        return reponse_ok({}, "Tâche supprimée")
    return reponse_erreur("Tâche non trouvée", 404)


@app.route("/tasks/routines", methods=["POST"])
def creer_routine_route():
    """Crée une routine. Body JSON: champs de la routine."""
    try:
        data = get_json()
        routine = creer_routine(**{k: v for k, v in data.items() if k in [
            "titre", "description", "frequence", "heure_ideale", "duree_min", "categorie"
        ]})
        return reponse_ok(routine, "Routine créée"), 201
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/tasks/routines/jour", methods=["GET"])
def get_routines_jour():
    """Routines à effectuer aujourd'hui."""
    routines = routines_du_jour()
    return reponse_ok({"routines": routines, "total": len(routines)})


@app.route("/tasks/routines/<routine_id>/executer", methods=["POST"])
def executer_routine_route(routine_id):
    """Marque une routine comme exécutée."""
    routine = executer_routine(routine_id)
    if not routine:
        return reponse_erreur("Routine non trouvée", 404)
    return reponse_ok(routine, "Routine exécutée ✅")


@app.route("/tasks/objectifs", methods=["POST"])
def creer_objectif_route():
    """Crée un objectif. Body JSON: champs de l'objectif."""
    try:
        data = get_json()
        objectif = definir_objectif(**{k: v for k, v in data.items() if k in [
            "titre", "description", "valeur_cible", "unite", "date_limite", "categorie"
        ]})
        return reponse_ok(objectif, "Objectif créé"), 201
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/tasks/objectifs/<objectif_id>/progression", methods=["PUT"])
def update_objectif(objectif_id):
    """Met à jour la progression. Body JSON: {valeur_actuelle, note}"""
    try:
        data = get_json()
        valeur = data.get("valeur_actuelle")
        if valeur is None:
            return reponse_erreur("Le champ 'valeur_actuelle' est requis")
        objectif = mettre_a_jour_objectif(objectif_id, valeur, data.get("note", ""))
        if not objectif:
            return reponse_erreur("Objectif non trouvé", 404)
        return reponse_ok(objectif, "Progression mise à jour")
    except Exception as e:
        return reponse_erreur(str(e))


@app.route("/tasks/stats", methods=["GET"])
def get_stats_tasks():
    """Statistiques de productivité. Query param: jours (défaut: 7)"""
    nb_jours = int(request.args.get("jours", 7))
    stats = statistiques_productivite(nb_jours)
    return reponse_ok(stats)


# ─────────────────────────────────────────────
# LANCEMENT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 Agent IA pour Indépendants — API démarrée")
    print("📡 Disponible sur http://localhost:5000")
    print("📖 Routes: GET http://localhost:5000/")
    app.run(debug=True, host="0.0.0.0", port=5000)