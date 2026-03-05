"""
crm.py — Gestion CRM des prospects et clients
Stockage JSON local (compatible avec une base de données Bubble via API)
"""

import json
import os
from datetime import datetime
from typing import Optional

CRM_FILE = "crm_data.json"


# ─────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────

def _charger_crm() -> dict:
    """Charge les données CRM depuis le fichier JSON."""
    if not os.path.exists(CRM_FILE):
        donnees_vides = {"prospects": [], "clients": [], "interactions": []}
        _sauvegarder_crm(donnees_vides)
        return donnees_vides
    with open(CRM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _sauvegarder_crm(data: dict):
    """Sauvegarde les données CRM."""
    with open(CRM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _generer_id(prefix: str) -> str:
    """Génère un ID unique."""
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


# ─────────────────────────────────────────────
# STATUTS DISPONIBLES
# ─────────────────────────────────────────────

STATUTS_PROSPECT = [
    "nouveau",        # Vient d'être ajouté
    "contacte",       # Premier contact effectué
    "en_discussion",  # Échange en cours
    "devis_envoye",   # Devis transmis
    "relance",        # En attente de réponse
    "gagne",          # Converti en client
    "perdu",          # Ne donnera pas suite
    "en_pause"        # À recontacter plus tard
]


# ─────────────────────────────────────────────
# GESTION DES PROSPECTS
# ─────────────────────────────────────────────

def ajouter_prospect(
    nom: str,
    entreprise: str = "",
    email: str = "",
    telephone: str = "",
    linkedin: str = "",
    secteur: str = "",
    besoin: str = "",
    source: str = "",
    notes: str = ""
) -> dict:
    """
    Ajoute un nouveau prospect au CRM.
    
    Returns:
        Le prospect créé avec son ID
    """
    crm = _charger_crm()
    
    prospect = {
        "id": _generer_id("PRO"),
        "nom": nom,
        "entreprise": entreprise,
        "email": email,
        "telephone": telephone,
        "linkedin": linkedin,
        "secteur": secteur,
        "besoin": besoin,
        "source": source,  # ex: "LinkedIn", "recommandation", "site web"
        "notes": notes,
        "statut": "nouveau",
        "score": 0,  # Score de priorité 0-100
        "date_ajout": datetime.now().isoformat(),
        "dernier_contact": None,
        "prochain_contact": None,
        "nb_interactions": 0,
        "valeur_estimee": 0  # CA potentiel estimé
    }
    
    crm["prospects"].append(prospect)
    _sauvegarder_crm(crm)
    return prospect


def modifier_prospect(prospect_id: str, modifications: dict) -> Optional[dict]:
    """
    Modifie un prospect existant.
    
    Args:
        prospect_id: ID du prospect
        modifications: dict des champs à modifier
    
    Returns:
        Prospect mis à jour ou None si non trouvé
    """
    crm = _charger_crm()
    
    for i, p in enumerate(crm["prospects"]):
        if p["id"] == prospect_id:
            crm["prospects"][i].update(modifications)
            crm["prospects"][i]["date_modification"] = datetime.now().isoformat()
            _sauvegarder_crm(crm)
            return crm["prospects"][i]
    
    return None


def changer_statut(prospect_id: str, nouveau_statut: str, note: str = "") -> Optional[dict]:
    """Change le statut d'un prospect."""
    if nouveau_statut not in STATUTS_PROSPECT:
        return {"erreur": f"Statut invalide. Options: {STATUTS_PROSPECT}"}
    
    modifications = {"statut": nouveau_statut}
    if note:
        modifications["notes"] = note
    
    # Si converti en client, déplacer vers clients
    if nouveau_statut == "gagne":
        _convertir_en_client(prospect_id)
    
    return modifier_prospect(prospect_id, modifications)


def _convertir_en_client(prospect_id: str):
    """Convertit un prospect en client."""
    crm = _charger_crm()
    
    prospect = next((p for p in crm["prospects"] if p["id"] == prospect_id), None)
    if not prospect:
        return
    
    client = {
        **prospect,
        "id": _generer_id("CLI"),
        "prospect_id_origine": prospect_id,
        "date_conversion": datetime.now().isoformat(),
        "ca_total": 0,
        "projets": [],
        "satisfaction": None
    }
    
    crm["clients"].append(client)
    _sauvegarder_crm(crm)


def supprimer_prospect(prospect_id: str) -> bool:
    """Supprime un prospect."""
    crm = _charger_crm()
    avant = len(crm["prospects"])
    crm["prospects"] = [p for p in crm["prospects"] if p["id"] != prospect_id]
    _sauvegarder_crm(crm)
    return len(crm["prospects"]) < avant


# ─────────────────────────────────────────────
# CONSULTATION DES PROSPECTS
# ─────────────────────────────────────────────

def lister_prospects(statut: str = None, trier_par: str = "date_ajout") -> list:
    """
    Liste tous les prospects, avec filtrage optionnel.
    
    Args:
        statut: filtrer par statut (None = tous)
        trier_par: "date_ajout" | "dernier_contact" | "score" | "valeur_estimee"
    """
    crm = _charger_crm()
    prospects = crm["prospects"]
    
    if statut:
        prospects = [p for p in prospects if p["statut"] == statut]
    
    # Tri
    reverse = trier_par in ["score", "valeur_estimee"]
    prospects = sorted(
        prospects,
        key=lambda x: x.get(trier_par) or "",
        reverse=reverse
    )
    
    return prospects


def obtenir_prospect(prospect_id: str) -> Optional[dict]:
    """Récupère un prospect par son ID."""
    crm = _charger_crm()
    return next((p for p in crm["prospects"] if p["id"] == prospect_id), None)


def prospects_a_relancer(jours_max: int = 7) -> list:
    """
    Retourne les prospects qui n'ont pas été contactés depuis X jours.
    
    Args:
        jours_max: nombre de jours sans contact
    """
    from datetime import timedelta
    
    crm = _charger_crm()
    seuil = datetime.now() - timedelta(days=jours_max)
    
    a_relancer = []
    for p in crm["prospects"]:
        if p["statut"] in ["perdu", "gagne"]:
            continue
        
        dernier = p.get("dernier_contact")
        if not dernier or datetime.fromisoformat(dernier) < seuil:
            p["jours_sans_contact"] = (datetime.now() - datetime.fromisoformat(dernier)).days if dernier else 999
            a_relancer.append(p)
    
    return sorted(a_relancer, key=lambda x: x["jours_sans_contact"], reverse=True)


def rechercher_prospects(terme: str) -> list:
    """Recherche dans les prospects (nom, entreprise, secteur, notes)."""
    crm = _charger_crm()
    terme = terme.lower()
    
    return [
        p for p in crm["prospects"]
        if terme in p.get("nom", "").lower()
        or terme in p.get("entreprise", "").lower()
        or terme in p.get("secteur", "").lower()
        or terme in p.get("notes", "").lower()
        or terme in p.get("besoin", "").lower()
    ]


# ─────────────────────────────────────────────
# HISTORIQUE DES INTERACTIONS
# ─────────────────────────────────────────────

def enregistrer_interaction(
    prospect_id: str,
    type_interaction: str,
    contenu: str,
    resultat: str = "",
    prochain_contact: str = None
) -> dict:
    """
    Enregistre une interaction avec un prospect.
    
    Args:
        type_interaction: "email_envoye" | "appel" | "linkedin" | "reunion" | "devis"
        contenu: description ou contenu de l'interaction
        resultat: résultat / réponse obtenu
        prochain_contact: date ISO du prochain contact prévu
    """
    crm = _charger_crm()
    
    interaction = {
        "id": _generer_id("INT"),
        "prospect_id": prospect_id,
        "type": type_interaction,
        "contenu": contenu,
        "resultat": resultat,
        "date": datetime.now().isoformat(),
        "prochain_contact": prochain_contact
    }
    
    crm["interactions"].append(interaction)
    
    # Mettre à jour le dernier contact du prospect
    modifier_prospect(prospect_id, {
        "dernier_contact": datetime.now().isoformat(),
        "nb_interactions": obtenir_prospect(prospect_id).get("nb_interactions", 0) + 1,
        "prochain_contact": prochain_contact
    })
    
    _sauvegarder_crm(crm)
    return interaction


def historique_prospect(prospect_id: str) -> list:
    """Retourne toutes les interactions d'un prospect."""
    crm = _charger_crm()
    interactions = [i for i in crm["interactions"] if i["prospect_id"] == prospect_id]
    return sorted(interactions, key=lambda x: x["date"], reverse=True)


# ─────────────────────────────────────────────
# STATISTIQUES CRM
# ─────────────────────────────────────────────

def statistiques_crm() -> dict:
    """Retourne les statistiques globales du CRM."""
    crm = _charger_crm()
    prospects = crm["prospects"]
    
    stats_par_statut = {}
    for statut in STATUTS_PROSPECT:
        stats_par_statut[statut] = len([p for p in prospects if p["statut"] == statut])
    
    total = len(prospects)
    gagnes = stats_par_statut.get("gagne", 0)
    
    return {
        "total_prospects": total,
        "total_clients": len(crm["clients"]),
        "total_interactions": len(crm["interactions"]),
        "repartition_statuts": stats_par_statut,
        "taux_conversion": round((gagnes / total * 100), 1) if total > 0 else 0,
        "valeur_pipeline": sum(p.get("valeur_estimee", 0) for p in prospects if p["statut"] not in ["perdu", "gagne"]),
        "prospects_chauds": len([p for p in prospects if p.get("score", 0) >= 70]),
        "a_relancer_urgence": len(prospects_a_relancer(3))
    }