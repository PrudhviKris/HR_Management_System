from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from jinja2 import TemplateError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import RequestContext, get_request_context, require_permissions
from app.core.permissions import P
from app.core.timeutils import today_local
from app.exceptions import ValidationError
from app.models import AuditLog, EmailLog, EmailTemplate
from app.models.enums import EmailStatus
from app.repositories.base import escape_like, get_or_404, paginate
from app.schemas.admin import (
    AuditLogOut,
    EmailLogDetail,
    EmailLogOut,
    EmailTemplateIn,
    EmailTemplateOut,
    PermissionOut,
    RoleIn,
    RoleOut,
    TemplatePreviewIn,
    UserOut,
    UserRoleIn,
)
from app.schemas.common import Message, Page
from app.services import audit_service, notification_service, role_service, settings_service
from app.utils.exporters import to_csv

router = APIRouter(tags=["Administration"])
roles_perm = Depends(require_permissions(P.ROLE_MANAGE))
audit_perm = Depends(require_permissions(P.AUDIT_VIEW))
notif_perm = Depends(require_permissions(P.NOTIFICATION_MANAGE))


# roles & permissions ------------------------------------------------------------------
@router.get("/permissions", response_model=list[PermissionOut], dependencies=[roles_perm])
def list_permissions(db: Session = Depends(get_db)):
    return role_service.list_permissions(db)


@router.get("/roles", response_model=list[RoleOut], dependencies=[Depends(require_permissions(P.ROLE_MANAGE, P.EMPLOYEE_CREATE, any_of=True))])
def list_roles(db: Session = Depends(get_db)):
    return role_service.list_roles(db)


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED, dependencies=[roles_perm])
def create_role(body: RoleIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return role_service.create_role(db, ctx, body.name, body.description, body.permissions)


@router.put("/roles/{role_id}", response_model=RoleOut, dependencies=[roles_perm])
def update_role(role_id: int, body: RoleIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return role_service.update_role(db, ctx, role_id, body.name, body.description, body.permissions)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[roles_perm])
def delete_role(role_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    role_service.delete_role(db, ctx, role_id)


@router.get("/users", response_model=Page[UserOut], dependencies=[roles_perm])
def list_users(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str | None = Query(None, max_length=100),
    role_id: int | None = None, db: Session = Depends(get_db),
):
    return role_service.list_users(db, page, page_size, search, role_id)


@router.put("/users/{user_id}/role", response_model=Message, dependencies=[roles_perm])
def change_role(user_id: int, body: UserRoleIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    user = role_service.change_user_role(db, ctx, user_id, body.role_id)
    return Message(message=f"{user.full_name} is now {user.role.name}")


# audit logs (read-only: there are deliberately no write endpoints) ------------------------
def _audit_query(action, actor, entity_type, entity_id, date_from, date_to, search):
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{escape_like(action)}%", escape="\\"))
    if actor:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{escape_like(actor)}%", escape="\\"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= datetime.combine(date_to, time.max))
    if search:
        stmt = stmt.where(AuditLog.description.ilike(f"%{escape_like(search)}%", escape="\\"))
    return stmt


@router.get("/audit-logs", response_model=Page[AuditLogOut], dependencies=[audit_perm])
def audit_logs(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    action: str | None = Query(None, max_length=64), actor: str | None = Query(None, max_length=100),
    entity_type: str | None = Query(None, max_length=50), entity_id: str | None = Query(None, max_length=50),
    date_from: date | None = None, date_to: date | None = None, search: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    """Timestamps are stored in UTC."""
    return paginate(db, _audit_query(action, actor, entity_type, entity_id, date_from, date_to, search), page, page_size)


@router.get("/audit-logs/actions", response_model=list[str], dependencies=[audit_perm])
def audit_actions(db: Session = Depends(get_db)):
    return sorted(db.scalars(select(AuditLog.action).distinct()))


@router.get("/audit-logs/export", dependencies=[audit_perm])
def export_audit_logs(
    action: str | None = None, actor: str | None = None, entity_type: str | None = None, date_from: date | None = None,
    date_to: date | None = None, search: str | None = None, db: Session = Depends(get_db),
):
    rows = db.scalars(_audit_query(action, actor, entity_type, None, date_from, date_to, search).limit(10000)).all()
    report = {
        "columns": [{"key": k, "label": k.replace("_", " ").title()} for k in
                    ["created_at", "actor_email", "action", "entity_type", "entity_id", "description", "ip_address"]],
        "rows": [{k: getattr(r, k) for k in ["created_at", "actor_email", "action", "entity_type", "entity_id", "description", "ip_address"]} for r in rows],
    }
    return Response(to_csv(report), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="audit_logs_{today_local()}.csv"'})


# email templates & logs --------------------------------------------------------------------
@router.get("/email-templates", response_model=list[EmailTemplateOut], dependencies=[notif_perm])
def list_templates(db: Session = Depends(get_db)):
    return list(db.scalars(select(EmailTemplate).order_by(EmailTemplate.name)))


@router.put("/email-templates/{template_id}", response_model=EmailTemplateOut, dependencies=[notif_perm])
def update_template(template_id: int, body: EmailTemplateIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    tpl = get_or_404(db, EmailTemplate, template_id, "Template")
    try:
        notification_service.validate_template(body.subject, body.body_html)
    except TemplateError as exc:
        raise ValidationError(f"Template syntax error: {exc}")
    before = audit_service.snapshot(tpl, ["subject", "body_html", "is_active"])
    tpl.subject, tpl.body_html, tpl.is_active = body.subject, body.body_html, body.is_active
    tpl.updated_by_id = ctx.user_id
    audit_service.record(
        db, ctx, "email_template.update", f"Edited email template '{tpl.name}'", entity_type="email_template", entity_id=tpl.id,
        changes=audit_service.diff(before, audit_service.snapshot(tpl, ["subject", "body_html", "is_active"])),
    )
    db.commit()
    return tpl


@router.post("/email-templates/{template_id}/preview", dependencies=[notif_perm])
def preview_template(template_id: int, body: TemplatePreviewIn, db: Session = Depends(get_db)):
    tpl = get_or_404(db, EmailTemplate, template_id, "Template")
    sample = {v.strip(): f"[{v.strip()}]" for v in (tpl.variables or "").split(",") if v.strip()}
    sample.update(company_name=settings_service.get(db, "company_name"), days=2, lop_days=0, status="approved")
    try:
        subject, html = notification_service.render(body.subject, body.body_html, sample)
    except TemplateError as exc:
        raise ValidationError(f"Template error: {exc}")
    return {"subject": subject, "html": html}


@router.get("/email-logs", response_model=Page[EmailLogOut], dependencies=[notif_perm])
def email_logs(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), status: EmailStatus | None = None,
    template_code: str | None = None, recipient: str | None = Query(None, max_length=100), db: Session = Depends(get_db),
):
    stmt = select(EmailLog).order_by(EmailLog.id.desc())
    if status:
        stmt = stmt.where(EmailLog.status == status)
    if template_code:
        stmt = stmt.where(EmailLog.template_code == template_code)
    if recipient:
        stmt = stmt.where(EmailLog.recipient.ilike(f"%{escape_like(recipient)}%", escape="\\"))
    return paginate(db, stmt, page, page_size)


@router.get("/email-logs/{log_id}", response_model=EmailLogDetail, dependencies=[notif_perm])
def email_log(log_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, EmailLog, log_id, "Email log")


@router.post("/email-logs/{log_id}/resend", response_model=EmailLogOut, dependencies=[notif_perm])
def resend_email(log_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    entry = get_or_404(db, EmailLog, log_id, "Email log")
    notification_service.resend(db, entry)
    audit_service.record(db, ctx, "email.resend", f"Re-sent email '{entry.subject}' to {entry.recipient}", entity_type="email_log", entity_id=entry.id)
    db.commit()
    return entry
