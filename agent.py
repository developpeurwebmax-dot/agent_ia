"""
agent.py — Le cerveau de l'agent IA pour indépendants
Connexion OpenAI + génération de contenu intelligent
"""
import openai
import json
import os
from datetime import datetime

openai.api_key = os.environ.get("OPENAI_API_KEY")

MODEL = "gpt-4"


def _appeler_gpt(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """Fonction de base pour appeler GPT."""
    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=temperature
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────────────
# 1. PLAN D'ACTION DU MATIN
# ─────────────────────────────────────────────

def generer_plan_journalier(prospects: list, taches_en_cours: list, metier: str) -> dict:
    """
    Génère le plan d'action du matin pour l'indépendant.
    
    Args:
        prospects: liste de dicts [{nom, statut, dernier_contact, notes}]
        taches_en_cours: liste de tâches ouvertes
        metier: ex "consultant RH", "graphiste freelance"
    
    Returns:
        dict avec plan structuré
    """
    system = f"""Tu es un coach business expert pour les indépendants {metier}.
Tu analyses leur situation et génères un plan d'action concret, motivant et réaliste pour la journée.
Réponds UNIQUEMENT en JSON valide."""

    user = f"""
Aujourd'hui : {datetime.now().strftime('%A %d %B %Y')}

Prospects à gérer :
{json.dumps(prospects, ensure_ascii=False, indent=2)}

Tâches en cours :
{json.dumps(taches_en_cours, ensure_ascii=False, indent=2)}

Génère un plan JSON avec cette structure exacte :
{{
  "message_motivation": "phrase motivante pour bien démarrer",
  "priorites_du_jour": ["priorité 1", "priorité 2", "priorité 3"],
  "prospects_a_contacter": [
    {{"nom": "...", "raison": "...", "action": "email|appel|linkedin"}}
  ],
  "taches_du_jour": [
    {{"titre": "...", "duree_estimee": "...", "priorite": "haute|moyenne|basse"}}
  ],
  "conseil_du_jour": "un conseil business personnalisé"
}}
"""
    resultat = _appeler_gpt(system, user, temperature=0.6)
    try:
        return json.loads(resultat)
    except json.JSONDecodeError:
        return {"erreur": "Impossible de parser la réponse", "raw": resultat}


# ─────────────────────────────────────────────
# 2. GÉNÉRATION DE MESSAGES
# ─────────────────────────────────────────────

def generer_email_prospect(prospect: dict, contexte: str, metier: str, style: str = "professionnel") -> dict:
    """
    Génère un email de prospection ou de relance.
    
    Args:
        prospect: {nom, entreprise, besoin, dernier_contact}
        contexte: "premier contact" | "relance" | "suivi devis" | "remerciement"
        metier: métier de l'indépendant
        style: "professionnel" | "chaleureux" | "direct"
    
    Returns:
        dict {sujet, corps, call_to_action}
    """
    system = f"""Tu es un expert en copywriting B2B pour les {metier} freelances.
Tu rédiges des emails courts, percutants et personnalisés qui génèrent des réponses.
Réponds UNIQUEMENT en JSON valide."""

    user = f"""
Contexte : {contexte}
Prospect : {json.dumps(prospect, ensure_ascii=False)}
Style demandé : {style}
Mon métier : {metier}

Génère un email JSON :
{{
  "sujet": "objet de l'email accrocheur",
  "corps": "corps de l'email complet avec \\n pour les sauts de ligne",
  "call_to_action": "action attendue du prospect",
  "conseil": "pourquoi cet email devrait fonctionner"
}}
"""
    resultat = _appeler_gpt(system, user)
    try:
        return json.loads(resultat)
    except json.JSONDecodeError:
        return {"erreur": "Parsing échoué", "raw": resultat}


def generer_message_linkedin(prospect: dict, metier: str) -> dict:
    """Génère un message de connexion LinkedIn personnalisé."""
    system = f"""Tu es un expert en prospection LinkedIn pour les {metier}.
Tu rédiges des messages courts (max 300 caractères), humains, sans spam.
Réponds UNIQUEMENT en JSON valide."""

    user = f"""
Prospect : {json.dumps(prospect, ensure_ascii=False)}
Mon métier : {metier}

Génère un message LinkedIn JSON :
{{
  "message": "le message court et percutant",
  "note_de_connexion": "note optionnelle pour la demande de connexion (max 200 car.)",
  "conseil": "pourquoi cette approche fonctionne"
}}
"""
    resultat = _appeler_gpt(system, user)
    try:
        return json.loads(resultat)
    except json.JSONDecodeError:
        return {"erreur": "Parsing échoué", "raw": resultat}


def generer_relance(prospect: dict, nb_jours_sans_reponse: int, metier: str) -> dict:
    """Génère un message de relance adapté."""
    system = f"""Tu es un coach commercial pour les {metier} freelances.
Tu génères des relances efficaces, non intrusives et créatives.
Réponds UNIQUEMENT en JSON valide."""

    user = f"""
Prospect : {json.dumps(prospect, ensure_ascii=False)}
Jours sans réponse : {nb_jours_sans_reponse}
Mon métier : {metier}

Génère une relance JSON :
{{
  "canal_recommande": "email|linkedin|telephone",
  "message": "le message de relance complet",
  "sujet_email": "sujet si email",
  "ton": "description du ton utilisé",
  "conseil": "stratégie de relance conseillée"
}}
"""
    resultat = _appeler_gpt(system, user)
    try:
        return json.loads(resultat)
    except json.JSONDecodeError:
        return {"erreur": "Parsing échoué", "raw": resultat}


# ─────────────────────────────────────────────
# 3. CONTENU MARKETING
# ─────────────────────────────────────────────

def generer_post_linkedin(sujet: str, metier: str, objectif: str = "notoriété") -> dict:
    """
    Génère un post LinkedIn engageant.
    
    Args:
        sujet: sujet du post
        metier: métier de l'indépendant
        objectif: "notoriété" | "prospection" | "expertise" | "engagement"
    """
    system = f"""Tu es un expert en personal branding LinkedIn pour les {metier}.
Tu crées des posts qui génèrent de l'engagement et attirent des clients.
Format : accroche forte, contenu valeur, call to action.
Réponds UNIQUEMENT en JSON valide."""

    user = f"""
Sujet : {sujet}
Objectif : {objectif}
Mon métier : {metier}

Génère un post JSON :
{{
  "accroche": "première ligne qui donne envie de lire",
  "corps": "contenu complet du post avec \\n pour les sauts de ligne",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3"],
  "call_to_action": "question ou action finale",
  "score_potentiel": "estimation engagement 1-10",
  "meilleur_moment_publication": "jour et heure idéaux"
}}
"""
    resultat = _appeler_gpt(system, user)
    try:
        return json.loads(resultat)
    except json.JSONDecodeError:
        return {"erreur": "Parsing échoué", "raw": resultat}


def generer_offre_commerciale(service: dict, cible: dict, metier: str) -> dict:
    """
    Génère une offre commerciale structurée.
    
    Args:
        service: {nom, description, livrables, duree}
        cible: {secteur, taille_entreprise, probleme_principal}
        metier: métier de l'indépendant
    """
    system = f"""Tu es un expert en structuration d'offres commerciales pour les {metier} freelances.
Tu crées des offres claires, valorisantes et orientées résultats clients.
Réponds UNIQUEMENT en JSON valide."""

    user = f"""
Service proposé : {json.dumps(service, ensure_ascii=False)}
Cible client : {json.dumps(cible, ensure_ascii=False)}
Mon métier : {metier}

Génère une offre commerciale JSON :
{{
  "titre_offre": "nom accrocheur de l'offre",
  "promesse": "bénéfice principal en une phrase",
  "probleme_resolu": "problème client adressé",
  "solution": "description de la solution",
  "livrables": ["livrable 1", "livrable 2", "livrable 3"],
  "benefices": ["bénéfice 1", "bénéfice 2", "bénéfice 3"],
  "tarif_suggere": {{"fourchette_basse": 0, "fourchette_haute": 0, "logique_tarifaire": "..."}},
  "objections_reponses": [{{"objection": "...", "reponse": "..."}}],
  "call_to_action": "prochaine étape proposée au client"
}}
"""
    resultat = _appeler_gpt(system, user)
    try:
        return json.loads(resultat)
    except json.JSONDecodeError:
        return {"erreur": "Parsing échoué", "raw": resultat}


# ─────────────────────────────────────────────
# 4. ANALYSE & STRATÉGIE
# ─────────────────────────────────────────────

def analyser_activite(donnees_activite: dict, metier: str) -> dict:
    """
    Analyse l'activité de l'indépendant et propose une stratégie.
    
    Args:
        donnees_activite: {
            ca_mois: float,
            nb_clients_actifs: int,
            nb_prospects_pipeline: int,
            taux_conversion: float,
            services_vendus: list,
            charges_estimees: float
        }
    """
    system = f"""Tu es un coach business et financier pour les {metier} freelances.
Tu analyses les données et fournis des recommandations stratégiques concrètes.
Réponds UNIQUEMENT en JSON valide."""

    user = f"""
Données d'activité :
{json.dumps(donnees_activite, ensure_ascii=False, indent=2)}

Génère une analyse JSON :
{{
  "score_sante_business": {{"note": 0, "interpretation": "..."}},
  "points_forts": ["point 1", "point 2"],
  "points_amelioration": ["point 1", "point 2"],
  "alertes": ["alerte critique si applicable"],
  "recommandations": [
    {{"action": "...", "impact": "fort|moyen|faible", "delai": "cette semaine|ce mois|long terme"}}
  ],
  "objectif_ca_suggere": {{"montant": 0, "strategie": "comment y arriver"}},
  "conseil_pricing": "analyse et conseil sur les tarifs"
}}
"""
    resultat = _appeler_gpt(system, user, temperature=0.4)
    try:
        return json.loads(resultat)
    except json.JSONDecodeError:
        return {"erreur": "Parsing échoué", "raw": resultat}


def analyser_prix(tarifs_actuels: dict, metier: str, localisation: str = "France") -> dict:
    """Analyse les tarifs et propose des ajustements."""
    system = f"""Tu es un expert en pricing pour les {metier} freelances en {localisation}.
Tu analyses les tarifs par rapport au marché et conseilles des optimisations.
Réponds UNIQUEMENT en JSON valide."""

    user = f"""
Tarifs actuels : {json.dumps(tarifs_actuels, ensure_ascii=False)}
Métier : {metier}
Localisation : {localisation}

Génère une analyse tarifaire JSON :
{{
  "evaluation": "sous-tarifé|dans la moyenne|bien positionné|premium",
  "tarif_journalier_marche": {{"bas": 0, "moyen": 0, "haut": 0}},
  "recommandation_ajustement": "...",
  "strategie_augmentation": "comment augmenter ses tarifs sans perdre clients",
  "services_a_valoriser": ["service 1", "service 2"],
  "conseil_packaging": "comment packager ses offres pour maximiser la valeur perçue"
}}
"""
    resultat = _appeler_gpt(system, user, temperature=0.3)
    try:
        return json.loads(resultat)
    except json.JSONDecodeError:

        return {"erreur": "Parsing échoué", "raw": resultat}
