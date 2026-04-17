"""
agent.py — Le cerveau de l'agent IA pour indépendants
Connexion OpenAI + génération de contenu intelligent
"""

import json
import os
from datetime import datetime

try:
    from openai import OpenAI
except Exception as e:
    raise RuntimeError(
        "Le package 'openai' est requis. Installe-le via requirements.txt."
    ) from e

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    OPENAI_API_KEY = ""

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Modèle configurable par variable d'environnement
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def _appeler_gpt(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """Fonction de base pour appeler GPT."""
    if client is None:
        raise RuntimeError("OPENAI_API_KEY manquante (variable d'environnement).")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        timeout=30,
    )
    content = response.choices[0].message.content
    return (content or "").strip()


# ─────────────────────────────────────────────
# 1. PLAN D'ACTION DU MATIN
# ─────────────────────────────────────────────

def generer_plan_journalier(prospects: list, taches_en_cours: list, metier: str) -> dict:
    """
    Génère le plan d'action du matin pour l'indépendant.
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
        # Tentative de nettoyage du JSON
        try:
            import re
            match = re.search(r'\{.*\}', resultat, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return {"erreur": "Impossible de parser la réponse", "raw": resultat}


# ─────────────────────────────────────────────
# 2. GÉNÉRATION DE MESSAGES
# ─────────────────────────────────────────────

def generer_email_prospect(prospect: dict, contexte: str, metier: str, style: str = "professionnel") -> dict:
    """
    Génère un email de prospection ou de relance.
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
        try:
            import re
            match = re.search(r'\{.*\}', resultat, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
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
        try:
            import re
            match = re.search(r'\{.*\}', resultat, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return {"erreur": "Parsing échoué", "raw": resultat}


def generer_offre_commerciale(service: dict, cible: dict, metier: str) -> dict:
    """
    Génère une offre commerciale structurée.
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
    Analyse l'activité de l'indépendant ou du dirigeant et propose une stratégie.
    """
    system = f"""Tu es un coach business et financier pour les {metier}.
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
        try:
            import re
            match = re.search(r'\{.*\}', resultat, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
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