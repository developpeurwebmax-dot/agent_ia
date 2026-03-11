"""
users.py — Gestion multi-utilisateurs et entreprises
Rôles : admin, rh, comptable, commercial, employe (lecture seule)
"""

import json
from datetime import datetime, date
from database import get_db, row_to_dict, rows_to_list
from auth import verifier_token, get_user_by_id


def _generer_id(prefix="ENT"):
    import time
    return f"{prefix}_{int(time.time() * 1000000)}"


# ─────────────────────────────────────────────
# RÔLES ET PERMISSIONS
# ─────────────────────────────────────────────

ROLES = {
    "admin":      ["*"],  # Tout
    "rh":         ["employes.*", "conges.*", "pointages.*", "evaluations.*", "dashboard.read"],
    "comptable":  ["finances.*", "factures.*", "devis.*", "dashboard.read"],
    "commercial": ["crm.*", "devis.*", "factures.read", "dashboard.read"],
    "employe":    ["conges.create", "pointages.create", "profil.read"]
}

ROLE_LABELS = {
    "admin": "Administrateur",
    "rh": "Responsable RH",
    "comptable": "Comptable",
    "commercial": "Commercial",
    "employe": "Employé"
}


def a_permission(role: str, action: str) -> bool:
    """Vérifie si un rôle a une permission donnée."""
    perms = ROLES.get(role, [])
    if "*" in perms:
        return True
    module, op = (action.split(".", 1) + ["*"])[:2]
    return (f"{module}.*" in perms or action in perms or f"*.{op}" in perms)


# ─────────────────────────────────────────────
# ENTREPRISES
# ─────────────────────────────────────────────

def creer_entreprise(user_id: str, data: dict) -> dict:
    """Crée une entreprise et associe le créateur comme admin."""
    if not data.get("nom"):
        raise ValueError("Nom de l'entreprise requis")

    conn = get_db()
    try:
        eid = _generer_id("ENT")
        conn.execute("""
            INSERT INTO entreprises
                (id, nom, siren, secteur, adresse, telephone, email,
                 tva_intracommunautaire, forme_juridique, date_creation_entreprise,
                 nb_employes_max, plan, owner_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eid,
            data["nom"],
            data.get("siren", ""),
            data.get("secteur", ""),
            data.get("adresse", ""),
            data.get("telephone", ""),
            data.get("email", ""),
            data.get("tva_intracommunautaire", ""),
            data.get("forme_juridique", "SAS"),
            data.get("date_creation_entreprise", ""),
            int(data.get("nb_employes_max", 50)),
            data.get("plan", "business"),
            user_id
        ))

        # Associer le créateur comme admin
        mid = _generer_id("MBR")
        conn.execute("""
            INSERT INTO membres_entreprise (id, entreprise_id, user_id, role, actif)
            VALUES (?, ?, ?, ?, ?)
        """, (mid, eid, user_id, "admin", 1))

        conn.commit()
        return row_to_dict(conn.execute("SELECT * FROM entreprises WHERE id=?", (eid,)).fetchone())
    finally:
        conn.close()


def get_entreprises_user(user_id: str) -> list:
    """Retourne toutes les entreprises auxquelles appartient un user."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT e.*, m.role, m.actif as membre_actif
            FROM entreprises e
            INNER JOIN membres_entreprise m ON e.id = m.entreprise_id
            WHERE m.user_id=? AND m.actif=1
            ORDER BY e.nom
        """, (user_id,)).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def get_entreprise(eid: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM entreprises WHERE id=?", (eid,)).fetchone()
        return row_to_dict(row) if row else None
    finally:
        conn.close()


def modifier_entreprise(eid: str, user_id: str, data: dict) -> dict:
    """Modifie une entreprise (admin seulement)."""
    if not _verifier_role(eid, user_id, "admin"):
        raise PermissionError("Accès refusé — rôle admin requis")

    conn = get_db()
    try:
        champs_ok = ["nom", "siren", "secteur", "adresse", "telephone", "email",
                     "tva_intracommunautaire", "forme_juridique", "nb_employes_max"]
        sets, vals = [], []
        for k in champs_ok:
            if k in data:
                sets.append(f"{k}=?")
                vals.append(data[k])
        if sets:
            vals.append(eid)
            conn.execute(f"UPDATE entreprises SET {','.join(sets)} WHERE id=?", vals)
            conn.commit()
        return get_entreprise(eid)
    finally:
        conn.close()


# ─────────────────────────────────────────────
# MEMBRES / INVITATIONS
# ─────────────────────────────────────────────

def inviter_membre(entreprise_id: str, inviteur_id: str, email_invite: str, role: str) -> dict:
    """Invite un utilisateur existant dans l'entreprise."""
    if not _verifier_role(entreprise_id, inviteur_id, "admin"):
        raise PermissionError("Seul l'admin peut inviter des membres")
    if role not in ROLES:
        raise ValueError(f"Rôle invalide. Valeurs: {list(ROLES.keys())}")

    conn = get_db()
    try:
        # Trouver l'utilisateur par email
        user_row = conn.execute("SELECT id, prenom, nom, email FROM users WHERE email=?",
                                (email_invite.lower(),)).fetchone()
        if not user_row:
            raise ValueError(f"Aucun compte trouvé pour {email_invite}")

        user = row_to_dict(user_row)

        # Vérifier si déjà membre
        existant = conn.execute(
            "SELECT id FROM membres_entreprise WHERE entreprise_id=? AND user_id=?",
            (entreprise_id, user["id"])
        ).fetchone()
        if existant:
            raise ValueError("Cet utilisateur est déjà membre de l'entreprise")

        mid = _generer_id("MBR")
        conn.execute("""
            INSERT INTO membres_entreprise (id, entreprise_id, user_id, role, actif)
            VALUES (?, ?, ?, ?, ?)
        """, (mid, entreprise_id, user["id"], role, 1))
        conn.commit()

        return {
            "membre_id": mid,
            "user": user,
            "role": role,
            "role_label": ROLE_LABELS[role]
        }
    finally:
        conn.close()


def get_membres(entreprise_id: str) -> list:
    """Liste tous les membres d'une entreprise."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT m.id as membre_id, m.role, m.actif, m.date_ajout,
                   u.id as user_id, u.prenom, u.nom, u.email
            FROM membres_entreprise m
            INNER JOIN users u ON m.user_id = u.id
            WHERE m.entreprise_id=?
            ORDER BY m.role, u.nom
        """, (entreprise_id,)).fetchall()
        membres = rows_to_list(rows)
        for m in membres:
            m["role_label"] = ROLE_LABELS.get(m["role"], m["role"])
        return membres
    finally:
        conn.close()


def modifier_role_membre(entreprise_id: str, admin_id: str, user_id: str, nouveau_role: str) -> bool:
    if not _verifier_role(entreprise_id, admin_id, "admin"):
        raise PermissionError("Accès refusé")
    if nouveau_role not in ROLES:
        raise ValueError("Rôle invalide")

    conn = get_db()
    try:
        conn.execute(
            "UPDATE membres_entreprise SET role=? WHERE entreprise_id=? AND user_id=?",
            (nouveau_role, entreprise_id, user_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def retirer_membre(entreprise_id: str, admin_id: str, user_id: str) -> bool:
    if not _verifier_role(entreprise_id, admin_id, "admin"):
        raise PermissionError("Accès refusé")

    conn = get_db()
    try:
        conn.execute(
            "UPDATE membres_entreprise SET actif=0 WHERE entreprise_id=? AND user_id=?",
            (entreprise_id, user_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_role_user(entreprise_id: str, user_id: str) -> str | None:
    """Retourne le rôle d'un utilisateur dans une entreprise."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT role FROM membres_entreprise WHERE entreprise_id=? AND user_id=? AND actif=1",
            (entreprise_id, user_id)
        ).fetchone()
        if not row:
            return None
        return row["role"] if isinstance(row, dict) else row[0]
    finally:
        conn.close()


def _verifier_role(entreprise_id: str, user_id: str, role_requis: str) -> bool:
    role = get_role_user(entreprise_id, user_id)
    if not role:
        return False
    if role == "admin":
        return True
    return role == role_requis