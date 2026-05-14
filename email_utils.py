"""
email_utils.py — Envoi d'emails SMTP pour devis et factures
Variables d'environnement requises : SMTP_USER, SMTP_PASSWORD
Optionnelles : SMTP_HOST (défaut smtp.gmail.com), SMTP_PORT (défaut 587), SMTP_FROM
"""

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST     = os.environ.get("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER",     "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM     = os.environ.get("SMTP_FROM",     "") or SMTP_USER


def smtp_disponible() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)


def _envoyer(destinataire: str, sujet: str, corps_html: str) -> None:
    if not smtp_disponible():
        raise RuntimeError(
            "Envoi impossible : configurez SMTP_USER et SMTP_PASSWORD dans les variables d'environnement."
        )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = SMTP_FROM
    msg["To"]      = destinataire
    msg.attach(MIMEText(corps_html, "html", "utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as srv:
        srv.ehlo()
        srv.starttls()
        srv.login(SMTP_USER, SMTP_PASSWORD)
        srv.sendmail(SMTP_FROM, [destinataire], msg.as_string())


def _fmt(v) -> str:
    try:
        s = f"{float(v):,.2f}".replace(",", " ").replace(".", ",")
        return f"{s} €"
    except Exception:
        return "0,00 €"


def _lignes_html(lignes: list) -> str:
    rows = ""
    for l in lignes:
        if not l.get("desc") and not l.get("prix"):
            continue
        qte   = l.get("qte") or 1
        prix  = l.get("prix") or 0
        total = qte * prix
        rows += (
            f'<tr>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#374151">{l.get("desc","")}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:center;color:#374151">{qte}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right;color:#374151">{_fmt(prix)}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:600;color:#111827">{_fmt(total)}</td>'
            f'</tr>'
        )
    return rows


def _html_email(
    titre: str, numero: str, emetteur: dict,
    client: str, adresse_client: str, objet: str, date_doc: str,
    lignes: list, montant_ht: float, montant_ttc: float, tva: float,
    mention_tva: str, extra_info: str, message_perso: str,
) -> str:
    ht  = montant_ht or sum((l.get("qte") or 1) * (l.get("prix") or 0) for l in lignes)
    tva_pct = tva or 0
    tva_amt = ht * tva_pct / 100
    ttc     = montant_ttc or ht + tva_amt
    nom     = emetteur.get("nom", "")

    tva_row = (
        f'<tr><td style="padding:4px 12px;color:#6b7280">TVA ({tva_pct:.0f}%)</td>'
        f'<td style="padding:4px 12px;text-align:right;color:#6b7280">{_fmt(tva_amt)}</td></tr>'
        if not mention_tva else
        f'<tr><td colspan="2" style="padding:4px 12px;color:#f59e0b;font-size:13px">{mention_tva}</td></tr>'
    )
    montant_final = ht if mention_tva else ttc
    libelle_total = "TOTAL HT" if mention_tva else "TOTAL TTC"

    msg_block = ""
    if message_perso:
        msg_block = (
            '<div style="margin:20px 0;padding:16px 20px;background:#f0fdf4;'
            'border-left:4px solid #10b981;border-radius:0 8px 8px 0">'
            f'<p style="margin:0;color:#065f46;font-size:14px;line-height:1.6">{message_perso}</p></div>'
        )

    siret_row  = f'<p style="margin:2px 0;font-size:12px;color:#9ca3af">SIRET : {emetteur["siret"]}</p>' if emetteur.get("siret") else ""
    email_row  = f'<p style="margin:2px 0;font-size:12px;color:#9ca3af">{emetteur["email"]}</p>'             if emetteur.get("email") else ""
    tel_row    = f'<p style="margin:2px 0;font-size:12px;color:#9ca3af">{emetteur["tel"]}</p>'               if emetteur.get("tel")   else ""
    extra_row  = f'<p style="margin:16px 0 0;font-size:12px;color:#9ca3af">{extra_info}</p>'                 if extra_info            else ""
    adr_client = f'<p style="margin:4px 0 0;font-size:13px;color:#6b7280;white-space:pre-line">{adresse_client}</p>' if adresse_client else ""

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"/></head>
<body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;background:#f8fafc">
<div style="max-width:680px;margin:32px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

  <div style="background:linear-gradient(135deg,#6366f1,#818cf8);padding:32px 40px;color:#ffffff">
    <h1 style="margin:0;font-size:26px;font-weight:700">{titre}</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:15px">N° {numero}</p>
  </div>

  <div style="padding:32px 40px">

    <table style="width:100%;border-collapse:collapse;margin-bottom:28px"><tr>
      <td style="width:50%;vertical-align:top;padding-right:12px">
        <div style="background:#f8fafc;border-radius:8px;padding:16px">
          <p style="margin:0 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#9ca3af">De</p>
          <p style="margin:0;font-weight:700;color:#111827">{nom}</p>
          <p style="margin:4px 0 0;font-size:13px;color:#6b7280;white-space:pre-line">{emetteur.get("adresse","")}</p>
          {siret_row}{email_row}{tel_row}
        </div>
      </td>
      <td style="width:50%;vertical-align:top;padding-left:12px">
        <div style="background:#f8fafc;border-radius:8px;padding:16px">
          <p style="margin:0 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#9ca3af">À</p>
          <p style="margin:0;font-weight:700;color:#111827">{client}</p>
          {adr_client}
        </div>
      </td>
    </tr></table>

    <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
      <tr>
        <td style="padding:10px 14px;background:#f1f5f9;border-radius:6px 0 0 6px;font-size:13px;color:#64748b">Objet</td>
        <td style="padding:10px 14px;background:#f1f5f9;font-weight:600;color:#111827">{objet}</td>
        <td style="padding:10px 14px;background:#f1f5f9;font-size:13px;color:#64748b;text-align:right">Date</td>
        <td style="padding:10px 14px;background:#f1f5f9;border-radius:0 6px 6px 0;font-weight:600;color:#111827;text-align:right">{date_doc or ""}</td>
      </tr>
    </table>

    {msg_block}

    <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
      <thead>
        <tr style="background:#f1f5f9">
          <th style="padding:10px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#64748b">Description</th>
          <th style="padding:10px 12px;text-align:center;font-size:11px;text-transform:uppercase;color:#64748b">Qté</th>
          <th style="padding:10px 12px;text-align:right;font-size:11px;text-transform:uppercase;color:#64748b">Prix HT</th>
          <th style="padding:10px 12px;text-align:right;font-size:11px;text-transform:uppercase;color:#64748b">Total HT</th>
        </tr>
      </thead>
      <tbody>{_lignes_html(lignes)}</tbody>
    </table>

    <table style="width:240px;margin-left:auto;border-collapse:collapse">
      <tr><td style="padding:4px 12px;color:#6b7280">Sous-total HT</td><td style="padding:4px 12px;text-align:right;color:#374151">{_fmt(ht)}</td></tr>
      {tva_row}
      <tr style="border-top:2px solid #e2e8f0">
        <td style="padding:10px 12px;font-weight:700;color:#111827;font-size:15px">{libelle_total}</td>
        <td style="padding:10px 12px;text-align:right;font-weight:700;color:#6366f1;font-size:15px">{_fmt(montant_final)}</td>
      </tr>
    </table>
    {extra_row}

  </div>

  <div style="padding:20px 40px;background:#f8fafc;border-top:1px solid #e2e8f0;text-align:center">
    <p style="margin:0;font-size:12px;color:#9ca3af">Généré via Agent IA · {nom}</p>
  </div>
</div>
</body></html>"""


def envoyer_devis(devis: dict, profil: dict, email_dest: str, message_perso: str = "") -> None:
    lignes = devis.get("lignes") or []
    if isinstance(lignes, str):
        try:
            lignes = json.loads(lignes)
        except Exception:
            lignes = []
    extra = f"Ce devis est valable jusqu'au {devis.get('validite','')}" if devis.get("validite") else ""
    corps = _html_email(
        titre="DEVIS",
        numero=devis.get("numero", ""),
        emetteur=profil,
        client=devis.get("client", ""),
        adresse_client=devis.get("adresse_client", ""),
        objet=devis.get("objet", ""),
        date_doc=devis.get("date", ""),
        lignes=lignes,
        montant_ht=devis.get("montant_ht", 0),
        montant_ttc=devis.get("montant_ttc", 0),
        tva=devis.get("tva", 20),
        mention_tva=profil.get("mention_tva", ""),
        extra_info=extra,
        message_perso=message_perso,
    )
    sujet = f"Devis {devis.get('numero','')} — {profil.get('nom','')}"
    _envoyer(email_dest, sujet, corps)


def envoyer_facture(facture: dict, profil: dict, email_dest: str, message_perso: str = "") -> None:
    lignes = facture.get("lignes") or []
    if isinstance(lignes, str):
        try:
            lignes = json.loads(lignes)
        except Exception:
            lignes = []
    extra = f"Date d'échéance : {facture.get('date_echeance','')}" if facture.get("date_echeance") else ""
    corps = _html_email(
        titre="FACTURE",
        numero=facture.get("numero", ""),
        emetteur=profil,
        client=facture.get("client", ""),
        adresse_client=facture.get("adresse_client", ""),
        objet=facture.get("objet", ""),
        date_doc=facture.get("date", ""),
        lignes=lignes,
        montant_ht=facture.get("montant_ht", 0),
        montant_ttc=facture.get("montant_ttc", 0),
        tva=facture.get("tva", 20),
        mention_tva=profil.get("mention_tva", ""),
        extra_info=extra,
        message_perso=message_perso,
    )
    sujet = f"Facture {facture.get('numero','')} — {profil.get('nom','')}"
    _envoyer(email_dest, sujet, corps)
