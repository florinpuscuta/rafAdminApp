"""
Abstracție pentru trimiterea emailurilor.

Dacă `SMTP_HOST` e setat în env → trimite real via aiosmtplib (multipart: text + HTML).
Altfel → loghează varianta text în stderr (vizibil în `docker logs backend`).

Toate funcțiile sunt async — apelul se face cu `await`.
"""
from __future__ import annotations

import html
import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

log = logging.getLogger("adeplast.email")


def _render_html(*, title: str, intro: str, cta_label: str, cta_url: str, footer: str) -> str:
    """
    Template minimalist, inline CSS — pentru compatibilitate maximă cu
    Gmail/Outlook/Apple Mail. Nu folosim <style>, totul merge pe atribute.
    """
    safe_intro = html.escape(intro).replace("\n", "<br>")
    safe_footer = html.escape(footer).replace("\n", "<br>")
    safe_label = html.escape(cta_label)
    safe_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="ro">
<head><meta charset="utf-8"><title>{safe_title}</title></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,Segoe UI,Roboto,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f5f5f5;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" border="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.05);">
        <tr><td style="background:#1e3a8a;padding:20px 32px;">
          <div style="color:#ffffff;font-size:18px;font-weight:600;letter-spacing:0.3px;">Adeplast SaaS</div>
        </td></tr>
        <tr><td style="padding:32px;">
          <h1 style="margin:0 0 16px;font-size:20px;color:#111827;">{safe_title}</h1>
          <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:#374151;">{safe_intro}</p>
          <table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td style="border-radius:6px;background:#2563eb;">
            <a href="{html.escape(cta_url, quote=True)}" style="display:inline-block;padding:12px 24px;color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;border-radius:6px;">{safe_label}</a>
          </td></tr></table>
          <p style="margin:28px 0 0;font-size:12px;color:#6b7280;line-height:1.5;">
            Dacă butonul nu funcționează, copiază și deschide acest link în browser:<br>
            <a href="{html.escape(cta_url, quote=True)}" style="color:#2563eb;word-break:break-all;">{html.escape(cta_url)}</a>
          </p>
          <p style="margin:24px 0 0;font-size:12px;color:#9ca3af;line-height:1.5;">{safe_footer}</p>
        </td></tr>
        <tr><td style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb;">
          <p style="margin:0;font-size:11px;color:#9ca3af;text-align:center;">
            Acest email a fost trimis automat. Dacă nu te aștepți la el, poți să-l ignori.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""


async def _send(*, to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    if not settings.smtp_host:
        log.warning("[EMAIL-DEV] to=%s subject=%s\n%s", to_email, subject, text_body)
        return

    msg = EmailMessage()
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            start_tls=settings.smtp_use_starttls and not settings.smtp_use_tls,
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        # Nu blocăm flow-ul userului din cauza unei erori SMTP. Logăm și mergem mai departe.
        log.error("[EMAIL-FAIL] to=%s subject=%s err=%s", to_email, subject, exc)


async def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    subject = "Resetare parolă — Adeplast SaaS"
    text = (
        "Ai cerut resetarea parolei pentru contul tău.\n\n"
        f"Deschide acest link (valabil 30 minute) pentru a continua:\n{reset_url}\n\n"
        "Dacă nu tu ai cerut resetarea, ignoră acest email."
    )
    html_body = _render_html(
        title="Resetare parolă",
        intro="Ai cerut resetarea parolei pentru contul tău. Apasă butonul de mai jos pentru a continua.",
        cta_label="Setează parolă nouă",
        cta_url=reset_url,
        footer="Linkul expiră în 30 de minute. Dacă nu tu ai cerut resetarea, ignoră acest email.",
    )
    await _send(to_email=to_email, subject=subject, text_body=text, html_body=html_body)


async def send_email_verification_email(*, to_email: str, verify_url: str) -> None:
    subject = "Verifică adresa de email — Adeplast SaaS"
    text = (
        "Bun venit!\n\n"
        f"Confirmă adresa de email deschizând acest link:\n{verify_url}\n\n"
        "Linkul expiră în 48 de ore."
    )
    html_body = _render_html(
        title="Bun venit!",
        intro="Îți mulțumim că te-ai alăturat. Confirmă adresa de email pentru a-ți activa complet contul.",
        cta_label="Confirmă email-ul",
        cta_url=verify_url,
        footer="Linkul expiră în 48 de ore.",
    )
    await _send(to_email=to_email, subject=subject, text_body=text, html_body=html_body)


async def send_invitation_email(*, to_email: str, invite_url: str, inviter_email: str) -> None:
    subject = "Ai fost invitat pe Adeplast SaaS"
    text = (
        f"{inviter_email} te-a invitat să te alături organizației pe Adeplast SaaS.\n\n"
        f"Acceptă invitația (valabilă 7 zile):\n{invite_url}\n"
    )
    html_body = _render_html(
        title="Ai fost invitat",
        intro=f"{inviter_email} te-a invitat să te alături organizației pe Adeplast SaaS. Acceptă invitația pentru a-ți crea contul.",
        cta_label="Acceptă invitația",
        cta_url=invite_url,
        footer="Invitația e valabilă 7 zile.",
    )
    await _send(to_email=to_email, subject=subject, text_body=text, html_body=html_body)
