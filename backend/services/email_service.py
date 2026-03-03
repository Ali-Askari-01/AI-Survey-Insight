"""
Email Notification Service
Sends survey invitations and completion alerts via SMTP (if configured)
or returns mailto: links as a fallback.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote
from ..config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM_EMAIL, SMTP_FROM_NAME, SMTP_USE_TLS,
)


def is_smtp_configured() -> bool:
    """Check if SMTP credentials are available."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM_EMAIL)


def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> dict:
    """
    Send an email via SMTP.
    Returns {"sent": True} on success, or {"sent": False, "error": "..."} on failure.
    """
    if not is_smtp_configured():
        return {"sent": False, "error": "SMTP not configured"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "error": str(e)}


def build_invite_html(survey_title: str, share_url: str, sender_name: str = "") -> str:
    """Build a styled HTML email body for a survey invitation."""
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:560px;margin:0 auto;padding:24px">
        <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:32px;border-radius:16px 16px 0 0;text-align:center">
            <h1 style="color:#fff;margin:0;font-size:22px">You're Invited!</h1>
            <p style="color:#e0e7ff;margin:8px 0 0;font-size:14px">Share your thoughts in a quick AI-powered interview</p>
        </div>
        <div style="background:#fff;padding:28px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 16px 16px">
            <h2 style="margin:0 0 8px;font-size:18px;color:#1f2937">{survey_title}</h2>
            {f'<p style="color:#6b7280;font-size:14px;margin:0 0 20px">{sender_name} has invited you to participate.</p>' if sender_name else '<p style="color:#6b7280;font-size:14px;margin:0 0 20px">You have been invited to participate in this survey.</p>'}
            <div style="text-align:center;margin:24px 0">
                <a href="{share_url}" style="display:inline-block;padding:14px 36px;background:#6366f1;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px">
                    Start Interview &rarr;
                </a>
            </div>
            <p style="color:#9ca3af;font-size:12px;text-align:center;margin:16px 0 0">
                This interview is conducted by an AI assistant. Your responses are confidential.<br>
                Typically takes 5-10 minutes.
            </p>
        </div>
    </div>
    """


def build_invite_text(survey_title: str, share_url: str, sender_name: str = "") -> str:
    """Plain-text fallback."""
    intro = f"{sender_name} has invited you" if sender_name else "You have been invited"
    return (
        f"You're Invited: {survey_title}\n\n"
        f"{intro} to participate in a quick AI-powered interview.\n\n"
        f"Click here to start: {share_url}\n\n"
        f"This interview typically takes 5-10 minutes. Your responses are confidential."
    )


def build_mailto_link(to_emails: list, subject: str, body: str) -> str:
    """Build a mailto: link for fallback (when SMTP is not configured)."""
    to_str = ",".join(to_emails) if to_emails else ""
    return f"mailto:{to_str}?subject={quote(subject)}&body={quote(body)}"


def send_survey_invites(
    to_emails: list,
    survey_title: str,
    share_url: str,
    sender_name: str = "",
) -> dict:
    """
    Send survey invitations to a list of emails.
    If SMTP is configured, sends real emails.
    Otherwise returns a mailto: link the frontend can open.
    """
    subject = f"You're invited: {survey_title}"
    html_body = build_invite_html(survey_title, share_url, sender_name)
    text_body = build_invite_text(survey_title, share_url, sender_name)

    if is_smtp_configured():
        results = []
        for email in to_emails:
            result = send_email(email, subject, html_body, text_body)
            results.append({"email": email, **result})
        sent_count = sum(1 for r in results if r.get("sent"))
        return {
            "method": "smtp",
            "total": len(to_emails),
            "sent": sent_count,
            "failed": len(to_emails) - sent_count,
            "results": results,
        }
    else:
        # Fallback: return a mailto link for the frontend to open
        mailto = build_mailto_link(to_emails, subject, text_body)
        return {
            "method": "mailto",
            "total": len(to_emails),
            "mailto_link": mailto,
            "subject": subject,
            "body": text_body,
        }
