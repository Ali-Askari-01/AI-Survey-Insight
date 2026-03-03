"""
Notifications & Alerts API Routes — Feature 5 (Continuous Improvement)
Handles notifications, alerts, engagement tracking, and email invitations.
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from ..database import get_db
from ..models import NotificationCreate
from ..auth import get_current_user
from ..services.email_service import send_survey_invites, is_smtp_configured
from typing import Optional

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/")
def get_notifications(
    survey_id: Optional[int] = Query(None),
    is_read: Optional[int] = Query(None),
    severity: Optional[str] = Query(None)
):
    """Get notifications with optional filters."""
    conn = get_db()
    query = "SELECT * FROM notifications WHERE 1=1"
    params = []
    if survey_id:
        query += " AND survey_id = ?"
        params.append(survey_id)
    if is_read is not None:
        query += " AND is_read = ?"
        params.append(is_read)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    query += " ORDER BY created_at DESC"

    notifs = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(n) for n in notifs]


@router.get("/unread-count")
def get_unread_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) as c FROM notifications WHERE is_read = 0").fetchone()
    conn.close()
    return {"count": dict(count)["c"]}


@router.post("/")
def create_notification(notif: NotificationCreate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notifications (survey_id, type, title, message, severity)
        VALUES (?, ?, ?, ?, ?)
    """, (notif.survey_id, notif.type, notif.title, notif.message, notif.severity))
    conn.commit()
    notif_id = cursor.lastrowid
    conn.close()
    return {"id": notif_id, "message": "Notification created"}


@router.put("/{notif_id}/read")
def mark_read(notif_id: int):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()
    return {"message": "Marked as read"}


@router.put("/read-all")
def mark_all_read():
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1")
    conn.commit()
    conn.close()
    return {"message": "All marked as read"}


@router.delete("/{notif_id}")
def delete_notification(notif_id: int):
    conn = get_db()
    conn.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()
    return {"message": "Notification deleted"}


# ═══════════════════════════════════════════════════
# EMAIL INVITATIONS
# ═══════════════════════════════════════════════════
@router.get("/email-status")
def email_status(current_user: dict = Depends(get_current_user)):
    """Check if SMTP email is configured."""
    return {"smtp_configured": is_smtp_configured()}


@router.post("/send-invites")
def send_invites(data: dict, request: Request, current_user: dict = Depends(get_current_user)):
    """
    Send survey invitations via email.
    Body: { survey_id, emails: ["a@b.com", ...], message?: "optional custom note" }
    If SMTP is configured, sends real emails. Otherwise returns a mailto: link.
    """
    survey_id = data.get("survey_id")
    emails = data.get("emails", [])

    if not survey_id or not emails:
        raise HTTPException(status_code=400, detail="survey_id and emails are required")
    if not isinstance(emails, list) or len(emails) > 50:
        raise HTTPException(status_code=400, detail="Provide 1-50 email addresses")

    conn = get_db()
    try:
        # Get survey info + share code
        survey = conn.execute("SELECT title FROM surveys WHERE id = ?", (survey_id,)).fetchone()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")
        survey_title = dict(survey)["title"]

        share_row = conn.execute(
            "SELECT share_code FROM published_surveys WHERE survey_id = ? AND status = 'active'",
            (survey_id,)
        ).fetchone()
        if not share_row:
            raise HTTPException(status_code=400, detail="Survey must be published and active first")
        share_code = dict(share_row)["share_code"]

        # Build share URL from request origin
        base = str(request.base_url).rstrip("/")
        share_url = f"{base}/interview/{share_code}"

        sender_name = current_user.get("name", "")

        result = send_survey_invites(emails, survey_title, share_url, sender_name)

        # Create in-app notification for tracking
        sent = result.get("sent", 0) if result["method"] == "smtp" else len(emails)
        conn.execute(
            "INSERT INTO notifications (survey_id, type, title, message, severity) VALUES (?, ?, ?, ?, ?)",
            (survey_id, "email_invite",
             f"Invitations sent to {len(emails)} recipient(s)",
             f"Survey '{survey_title}' invite sent via {result['method']}",
             "info")
        )
        conn.commit()

        return result
    finally:
        conn.close()
