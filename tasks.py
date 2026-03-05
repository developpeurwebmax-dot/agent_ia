"""
tasks.py — Gestion des tâches et planification
Système de tâches quotidiennes avec priorisation IA
"""

import json
import os
from datetime import datetime, date, timedelta
from typing import Optional

TASKS_FILE = "tasks_data.json"

PRIORITES = ["critique", "haute", "moyenne", "basse"]
CATEGORIES = ["prospection", "production", "admin", "marketing", "formation", "autre"]
STATUTS_TACHE = ["a_faire", "en_cours", "terminee", "annulee", "reportee"]


# ─────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────

def _charger_tasks() -> dict:
    if not os.path.exists(TASKS_FILE):
        vide = {"taches": [], "objectifs": [], "routines": []}
        _sauvegarder_tasks(vide)
        return vide
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _sauvegarder_tasks(data: dict):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _generer_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


# ─────────────────────────────────────────────
# GESTION DES TÂCHES
# ─────────────────────────────────────────────

def creer_tache(
    titre: str,
    description: str = "",
    priorite: str = "moyenne",
    categorie: str = "autre",
    date_echeance: str = None,
    duree_estimee_min: int = 30,
    prospect_id: str = None,
    tags: list = None
) -> dict:
    """
    Crée une nouvelle tâche.
    
    Args:
        titre: titre court de la tâche
        description: détails
        priorite: "critique" | "haute" | "moyenne" | "basse"
        categorie: "prospection" | "production" | "admin" | "marketing" | "formation" | "autre"
        date_echeance: date ISO (ex: "2024-12-31")
        duree_estimee_min: durée estimée en minutes
        prospect_id: lien vers un prospect CRM
        tags: liste de tags libres
    """
    tasks = _charger_tasks()
    
    tache = {
        "id": _generer_id("TSK"),
        "titre": titre,
        "description": description,
        "priorite": priorite if priorite in PRIORITES else "moyenne",
        "categorie": categorie if categorie in CATEGORIES else "autre",
        "statut": "a_faire",
        "date_creation": datetime.now().isoformat(),
        "date_echeance": date_echeance,
        "duree_estimee_min": duree_estimee_min,
        "duree_reelle_min": None,
        "prospect_id": prospect_id,
        "tags": tags or [],
        "notes": "",
        "completee_le": None
    }
    
    tasks["taches"].append(tache)
    _sauvegarder_tasks(tasks)
    return tache


def modifier_tache(tache_id: str, modifications: dict) -> Optional[dict]:
    """Modifie une tâche existante."""
    tasks = _charger_tasks()
    
    for i, t in enumerate(tasks["taches"]):
        if t["id"] == tache_id:
            tasks["taches"][i].update(modifications)
            _sauvegarder_tasks(tasks)
            return tasks["taches"][i]
    return None


def terminer_tache(tache_id: str, duree_reelle_min: int = None, notes: str = "") -> Optional[dict]:
    """Marque une tâche comme terminée."""
    modifications = {
        "statut": "terminee",
        "completee_le": datetime.now().isoformat(),
        "notes": notes
    }
    if duree_reelle_min:
        modifications["duree_reelle_min"] = duree_reelle_min
    
    return modifier_tache(tache_id, modifications)


def supprimer_tache(tache_id: str) -> bool:
    """Supprime une tâche."""
    tasks = _charger_tasks()
    avant = len(tasks["taches"])
    tasks["taches"] = [t for t in tasks["taches"] if t["id"] != tache_id]
    _sauvegarder_tasks(tasks)
    return len(tasks["taches"]) < avant


# ─────────────────────────────────────────────
# CONSULTATION DES TÂCHES
# ─────────────────────────────────────────────

def taches_du_jour() -> list:
    """Retourne les tâches à faire aujourd'hui (échéance = aujourd'hui ou en retard)."""
    tasks = _charger_tasks()
    aujourd_hui = date.today().isoformat()
    
    a_faire = []
    for t in tasks["taches"]:
        if t["statut"] not in ["a_faire", "en_cours"]:
            continue
        
        echeance = t.get("date_echeance")
        if not echeance or echeance <= aujourd_hui:
            t["en_retard"] = echeance and echeance < aujourd_hui
            a_faire.append(t)
    
    # Tri par priorité
    ordre_priorite = {"critique": 0, "haute": 1, "moyenne": 2, "basse": 3}
    return sorted(a_faire, key=lambda x: ordre_priorite.get(x["priorite"], 99))


def taches_en_retard() -> list:
    """Retourne les tâches en retard."""
    tasks = _charger_tasks()
    aujourd_hui = date.today().isoformat()
    
    return [
        t for t in tasks["taches"]
        if t["statut"] in ["a_faire", "en_cours"]
        and t.get("date_echeance")
        and t["date_echeance"] < aujourd_hui
    ]


def lister_taches(
    statut: str = None,
    categorie: str = None,
    priorite: str = None,
    prospect_id: str = None
) -> list:
    """Liste les tâches avec filtres optionnels."""
    tasks = _charger_tasks()
    taches = tasks["taches"]
    
    if statut:
        taches = [t for t in taches if t["statut"] == statut]
    if categorie:
        taches = [t for t in taches if t["categorie"] == categorie]
    if priorite:
        taches = [t for t in taches if t["priorite"] == priorite]
    if prospect_id:
        taches = [t for t in taches if t.get("prospect_id") == prospect_id]
    
    return taches


def taches_semaine() -> dict:
    """Retourne les tâches organisées par jour pour la semaine."""
    tasks = _charger_tasks()
    aujourd_hui = date.today()
    
    semaine = {}
    for i in range(7):
        jour = (aujourd_hui + timedelta(days=i)).isoformat()
        semaine[jour] = [
            t for t in tasks["taches"]
            if t.get("date_echeance") == jour
            and t["statut"] in ["a_faire", "en_cours"]
        ]
    
    return semaine


# ─────────────────────────────────────────────
# ROUTINES QUOTIDIENNES
# ─────────────────────────────────────────────

def creer_routine(
    titre: str,
    description: str,
    frequence: str,
    heure_ideale: str,
    duree_min: int,
    categorie: str = "autre"
) -> dict:
    """
    Crée une routine récurrente.
    
    Args:
        frequence: "quotidien" | "hebdomadaire" | "mensuel"
        heure_ideale: "matin" | "midi" | "apres-midi" | "soir"
    """
    tasks = _charger_tasks()
    
    routine = {
        "id": _generer_id("ROU"),
        "titre": titre,
        "description": description,
        "frequence": frequence,
        "heure_ideale": heure_ideale,
        "duree_min": duree_min,
        "categorie": categorie,
        "active": True,
        "date_creation": datetime.now().isoformat(),
        "derniere_execution": None,
        "nb_executions": 0
    }
    
    tasks["routines"].append(routine)
    _sauvegarder_tasks(tasks)
    return routine


def routines_du_jour() -> list:
    """Retourne les routines à effectuer aujourd'hui."""
    tasks = _charger_tasks()
    aujourd_hui = date.today()
    
    routines_actives = []
    for r in tasks["routines"]:
        if not r.get("active"):
            continue
        
        derniere = r.get("derniere_execution")
        
        if r["frequence"] == "quotidien":
            if not derniere or datetime.fromisoformat(derniere).date() < aujourd_hui:
                routines_actives.append(r)
        
        elif r["frequence"] == "hebdomadaire":
            if not derniere or (aujourd_hui - datetime.fromisoformat(derniere).date()).days >= 7:
                routines_actives.append(r)
        
        elif r["frequence"] == "mensuel":
            if not derniere or (aujourd_hui - datetime.fromisoformat(derniere).date()).days >= 30:
                routines_actives.append(r)
    
    return routines_actives


def executer_routine(routine_id: str) -> Optional[dict]:
    """Marque une routine comme exécutée aujourd'hui."""
    tasks = _charger_tasks()
    
    for i, r in enumerate(tasks["routines"]):
        if r["id"] == routine_id:
            tasks["routines"][i]["derniere_execution"] = datetime.now().isoformat()
            tasks["routines"][i]["nb_executions"] += 1
            _sauvegarder_tasks(tasks)
            return tasks["routines"][i]
    return None


# ─────────────────────────────────────────────
# OBJECTIFS
# ─────────────────────────────────────────────

def definir_objectif(
    titre: str,
    description: str,
    valeur_cible: float,
    unite: str,
    date_limite: str,
    categorie: str = "autre"
) -> dict:
    """
    Définit un objectif mesurable.
    
    Exemple: CA de 5000€ ce mois, 10 nouveaux contacts cette semaine
    """
    tasks = _charger_tasks()
    
    objectif = {
        "id": _generer_id("OBJ"),
        "titre": titre,
        "description": description,
        "valeur_cible": valeur_cible,
        "valeur_actuelle": 0,
        "unite": unite,
        "date_limite": date_limite,
        "categorie": categorie,
        "date_creation": datetime.now().isoformat(),
        "atteint": False,
        "historique": []
    }
    
    tasks["objectifs"].append(objectif)
    _sauvegarder_tasks(tasks)
    return objectif


def mettre_a_jour_objectif(objectif_id: str, nouvelle_valeur: float, note: str = "") -> Optional[dict]:
    """Met à jour la progression d'un objectif."""
    tasks = _charger_tasks()
    
    for i, o in enumerate(tasks["objectifs"]):
        if o["id"] == objectif_id:
            tasks["objectifs"][i]["valeur_actuelle"] = nouvelle_valeur
            tasks["objectifs"][i]["historique"].append({
                "date": datetime.now().isoformat(),
                "valeur": nouvelle_valeur,
                "note": note
            })
            
            if nouvelle_valeur >= o["valeur_cible"]:
                tasks["objectifs"][i]["atteint"] = True
            
            _sauvegarder_tasks(tasks)
            return tasks["objectifs"][i]
    return None


# ─────────────────────────────────────────────
# STATISTIQUES
# ─────────────────────────────────────────────

def statistiques_productivite(nb_jours: int = 7) -> dict:
    """Statistiques de productivité sur les X derniers jours."""
    tasks = _charger_tasks()
    
    date_debut = (date.today() - timedelta(days=nb_jours)).isoformat()
    
    taches_periode = [
        t for t in tasks["taches"]
        if t.get("completee_le") and t["completee_le"][:10] >= date_debut
    ]
    
    temps_total = sum(t.get("duree_reelle_min") or t.get("duree_estimee_min", 0) for t in taches_periode)
    
    par_categorie = {}
    for cat in CATEGORIES:
        par_categorie[cat] = len([t for t in taches_periode if t["categorie"] == cat])
    
    return {
        "taches_completees": len(taches_periode),
        "taches_en_retard": len(taches_en_retard()),
        "taches_a_faire": len(lister_taches(statut="a_faire")),
        "temps_total_heures": round(temps_total / 60, 1),
        "repartition_categories": par_categorie,
        "objectifs_actifs": len([o for o in tasks["objectifs"] if not o["atteint"]]),
        "objectifs_atteints": len([o for o in tasks["objectifs"] if o["atteint"]]),
        "routines_actives": len([r for r in tasks["routines"] if r.get("active")])
    }