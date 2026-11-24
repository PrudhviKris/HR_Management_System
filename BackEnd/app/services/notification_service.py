"""Template-based email with logging, plus in-app notifications.

Flow: a service calls `send_email(...)` inside its transaction. The template is rendered (sandboxed
Jinja2), an EmailLog row is written with secrets redacted, and the real message is parked in the
session's outbox. Only when the transaction commits is the message handed to a background worker that
delivers it over SMTP (if configured) and updates the log. A rolled-back action therefore never emails.
"""

import logging
import queue
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.timeutils import utcnow
from app.models import EmailLog, EmailTemplate, Notification, User
from app.models.enums import EmailStatus
from app.services import settings_service
from app.utils.email_templates import DEFAULT_TEMPLATES, LAYOUT

log = logging.getLogger("hrms.email")

_lenient_env = SandboxedEnvironment(autoescape=True)  # missing vars render empty
_strict_env = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)

REDACTED = "[link redacted]"


def render(subject_tpl: str, body_tpl: str, context: dict) -> tuple[str, str]:
    subject = _lenient_env.from_string(subject_tpl).render(**context).strip()
    content = _lenient_env.from_string(body_tpl).render(**context)  # variables auto-escaped
    body = LAYOUT.replace("{{ company_name }}", _escape(context.get("company_name", ""))).replace(
        "{{ content }}", content
    )
    return subject.replace("\n", " ")[:255], body


def _escape(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def validate_template(subject: str, body: str) -> None:
    """Syntax-check an edited template (raises TemplateError)."""
    _strict_env.parse(subject)
    _strict_env.parse(body)


def _get_template(db: Session, code: str) -> EmailTemplate | None:
    tpl = db.scalar(select(EmailTemplate).where(EmailTemplate.code == code))
    if tpl is None:
        default = next((t for t in DEFAULT_TEMPLATES if t["code"] == code), None)
        if default:
            tpl = EmailTemplate(**default)
    return tpl


def send_email(
    db: Session,
    template_code: str,
    to: str,
    context: dict,
    *,
    secrets: list[str] | None = None,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
) -> EmailLog | None:
    tpl = _get_template(db, template_code)
    if tpl is None or not tpl.is_active:
        log.info("Template %s missing or disabled; email to %s skipped", template_code, to)
        return None
    ctx = {"company_name": settings_service.get(db, "company_name"), "app_url": settings.FRONTEND_URL, **context}
    try:
        subject, body = render(tpl.subject, tpl.body_html, ctx)
    except TemplateError as exc:
        db.add(
            EmailLog(
                template_code=template_code, recipient=to, subject=f"[render error] {template_code}",
                body_html="", status=EmailStatus.FAILED, error_message=str(exc)[:500],
                entity_type=entity_type, entity_id=str(entity_id) if entity_id is not None else None,
            )
        )
        return None

    logged_body = body
    for s in secrets or []:
        if s:
            logged_body = logged_body.replace(s, REDACTED)

    entry = EmailLog(
        template_code=template_code,
        recipient=to,
        subject=subject,
        body_html=logged_body,
        status=EmailStatus.QUEUED if settings.smtp_enabled else EmailStatus.LOGGED,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
    )
    db.add(entry)
    db.flush()
    if settings.smtp_enabled:
        db.info.setdefault("email_outbox", []).append((entry.id, to, subject, body))
    elif settings.ENVIRONMENT == "development" and secrets:
        # No SMTP in local dev: surface action links in the server console so flows stay testable.
        log.warning("[dev email] to=%s subject=%r links=%s", to, subject, [s for s in secrets if s])
    return entry


def notify(db: Session, user_id: int, title: str, message: str, link: str | None = None) -> None:
    db.add(Notification(user_id=user_id, title=title[:150], message=message[:500], link=link))


def users_with_permission(db: Session, code: str) -> list[User]:
    users = db.scalars(select(User).where(User.is_active.is_(True))).unique().all()
    return [u for u in users if code in u.permissions]


# ---------------------------------------------------------------- outbox -> SMTP worker
_queue: "queue.Queue[tuple[int, str, str, str]]" = queue.Queue()
_worker: threading.Thread | None = None


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    for item in session.info.pop("email_outbox", []):
        _queue.put(item)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop("email_outbox", None)


def _smtp_send(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    name, addr = parseaddr(settings.MAIL_FROM)
    msg["From"] = formataddr((name, addr))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("This message requires an HTML capable email client.")
    msg.add_alternative(body, subtype="html")
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


def _work() -> None:
    while True:
        log_id, to, subject, body = _queue.get()
        status, error = EmailStatus.SENT, None
        try:
            _smtp_send(to, subject, body)
        except Exception as exc:  # noqa: BLE001
            status, error = EmailStatus.FAILED, str(exc)[:500]
            log.error("SMTP delivery to %s failed: %s", to, exc)
        with SessionLocal() as db:
            entry = db.get(EmailLog, log_id)
            if entry:
                entry.status = status
                entry.error_message = error
                entry.sent_at = utcnow() if status == EmailStatus.SENT else None
                db.commit()
        _queue.task_done()


def start_worker() -> None:
    global _worker
    if settings.smtp_enabled and _worker is None:
        _worker = threading.Thread(target=_work, name="email-worker", daemon=True)
        _worker.start()


def resend(db: Session, entry: EmailLog) -> EmailLog:
    """Re-deliver a logged email body (secrets stay redacted)."""
    entry.status = EmailStatus.QUEUED if settings.smtp_enabled else EmailStatus.LOGGED
    entry.error_message = None
    if settings.smtp_enabled:
        db.info.setdefault("email_outbox", []).append((entry.id, entry.recipient, entry.subject, entry.body_html))
    return entry
