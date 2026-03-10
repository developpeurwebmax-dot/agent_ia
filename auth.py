"""
auth.py — Authentification sécurisée
Bcrypt pour les mots de passe + JWT pour les sessions
"""

import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from database import get_db, row_to_dict, rows_to_list

SECRET_KEY = os.environ.get("JWT_SECRET", "agentia_secret_key_change_en_prod")
JWT_EXPIRE_DAYS = 30


def _generer_id():
    import time
    return "USR_" + str(int(time.time() * 1000000))


# ── MOT DE PASSE ──

def hasher_password(password: str) -> str:
    """Hash un mot de passe avec bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verifier_password(password: str, hash: str) -> bool:
    """Vérifie un mot de passe contre son hash."""
    try:
        return bcrypt.checkpw(password.encode(), hash.encode())
    except Exception:
        return False


# ── JWT ──

def generer_token(user_id: str) -> str:
    """Génère un token JWT."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verifier_token(token: str) -> str | None:
    """Vérifie un token JWT et retourne le user_id."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ── INSCRIPTION ──

def inscrire_user(data: dict) -> dict:
    """
    Inscrit un nouvel utilisateur.
    Retourne {user, token} ou lève une exception.
    """
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")

    if not email or not password:
        raise ValueError("Email et mot de passe requis")
    if len(password) < 8:
        raise ValueError("Mot de passe trop court (8 caractères minimum)")

    conn = get_db()
    try:
        # Vérifier si email déjà utilisé
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise ValueError("Cet email est déjà utilisé")

        # Déterminer les modules selon le plan
        plan = data.get("plan", "starter")
        modules = _modules_pour_plan(plan)

        user_id = _generer_id()
        password_hash = hasher_password(password)

        conn.execute("""
            INSERT INTO users (id, prenom, nom, email, password, metier, localisation,
                experience, secteurs, offre, tarif_type, tarif_journalier, tarif_horaire,
                objectif_ca, objectif_clients, charges, plan, modules, date_inscription)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data.get("prenom", ""),
            data.get("nom", ""),
            email,
            password_hash,
            data.get("metier", ""),
            data.get("localisation", ""),
            data.get("experience", ""),
            data.get("secteurs", ""),
            data.get("offre", ""),
            data.get("tarif_type", "jour"),
            data.get("tarif_journalier", 0),
            data.get("tarif_horaire", 0),
            data.get("objectif_ca", 0),
            data.get("objectif_clients", 0),
            data.get("charges", 0),
            plan,
            modules,
            datetime.now().isoformat()
        ))
        conn.commit()

        user = row_to_dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
        user.pop("password", None)  # Ne jamais renvoyer le mot de passe
        user["modules"] = user["modules"].split(",")

        token = generer_token(user_id)
        return {"user": user, "token": token}

    finally:
        conn.close()


# ── CONNEXION ──

def connecter_user(email: str, password: str) -> dict:
    """
    Connecte un utilisateur.
    Retourne {user, token} ou lève une exception.
    """
    email = email.lower().strip()
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            raise ValueError("Email ou mot de passe incorrect")

        user = dict(row)
        if not verifier_password(password, user["password"]):
            raise ValueError("Email ou mot de passe incorrect")

        user.pop("password", None)
        user["modules"] = user.get("modules", "dashboard,devis,factures,taches").split(",")
        try:
            import json
            user["profil_legal"] = json.loads(user.get("profil_legal") or "{}")
        except Exception:
            user["profil_legal"] = {}

        token = generer_token(user["id"])
        return {"user": user, "token": token}

    finally:
        conn.close()


# ── PROFIL ──

def get_user_by_id(user_id: str) -> dict | None:
    """Récupère un utilisateur par son ID."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return None
        user = dict(row)
        user.pop("password", None)
        user["modules"] = user.get("modules", "dashboard,devis,factures,taches").split(",")
        try:
            import json
            user["profil_legal"] = json.loads(user.get("profil_legal") or "{}")
        except Exception:
            user["profil_legal"] = {}
        return user
    finally:
        conn.close()


def modifier_user(user_id: str, data: dict) -> dict:
    """Modifie les infos d'un utilisateur."""
    import json
    conn = get_db()
    try:
        champs = []
        valeurs = []

        champs_autorises = ["prenom", "nom", "metier", "localisation", "profil_legal",
                           "tarif_journalier", "tarif_horaire", "objectif_ca", "charges"]

        for champ in champs_autorises:
            if champ in data:
                val = data[champ]
                if champ == "profil_legal" and isinstance(val, dict):
                    val = json.dumps(val, ensure_ascii=False)
                champs.append(f"{champ} = ?")
                valeurs.append(val)

        # Changement de mot de passe
        if "new_password" in data and len(data["new_password"]) >= 8:
            champs.append("password = ?")
            valeurs.append(hasher_password(data["new_password"]))

        if champs:
            valeurs.append(user_id)
            conn.execute(f"UPDATE users SET {', '.join(champs)} WHERE id = ?", valeurs)
            conn.commit()

        return get_user_by_id(user_id)
    finally:
        conn.close()


def changer_plan(user_id: str, nouveau_plan: str) -> dict:
    """Change le plan d'abonnement."""
    modules = _modules_pour_plan(nouveau_plan)
    conn = get_db()
    try:
        conn.execute("UPDATE users SET plan = ?, modules = ? WHERE id = ?",
                    (nouveau_plan, modules, user_id))
        conn.commit()
        return get_user_by_id(user_id)
    finally:
        conn.close()


def supprimer_user(user_id: str) -> bool:
    """Supprime un utilisateur et toutes ses données."""
    conn = get_db()
    try:
        tables = ["interactions", "prospects", "taches", "routines",
                 "objectifs", "devis", "factures"]
        for table in tables:
            conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def _modules_pour_plan(plan: str) -> str:
    """Retourne les modules selon le plan."""
    if plan == "premium":
        return "dashboard,devis,factures,taches,crm,analytics,plan_ia,contenu_ia"
    elif plan == "pro":
        return "dashboard,devis,factures,taches,crm,analytics,plan_ia"
    else:  # starter
        return "dashboard,devis,factures,taches"
