import re
from datetime import date

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import RequestContext
from app.core.permissions import ROLE_EMPLOYEE
from app.core.security import generate_temp_password, hash_password
from app.core.timeutils import today_local, utcnow
from app.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.models import Employee, EmployeeDocument, LeaveRequest, Role, SalaryStructure, User
from app.models.enums import EmployeeStatus, LeaveStatus, TokenPurpose
from app.repositories.base import escape_like, get_or_404, paginate
from app.services import audit_service, auth_service, leave_service, notification_service, organization_service
from app.utils import files

PROFILE_FIELDS = [
    "first_name", "last_name", "phone", "date_of_birth", "gender", "address", "emergency_contact_name",
    "emergency_contact_phone", "department_id", "designation_id", "manager_id", "date_of_joining",
    "employment_type", "work_location", "bank_name", "bank_account_number", "ifsc_code", "pan_number",
]
SALARY_FIELDS = [
    "effective_from", "basic", "hra", "conveyance_allowance", "medical_allowance", "special_allowance",
    "pf_applicable", "professional_tax_applicable", "tds_monthly", "remarks",
]
SORTABLE = {
    "employee_code": Employee.employee_code,
    "name": Employee.first_name,
    "date_of_joining": Employee.date_of_joining,
    "created_at": Employee.created_at,
}


# ------------------------------------------------------------------ serialisation helpers
def to_list_item(e: Employee) -> dict:
    return {
        "id": e.id, "employee_code": e.employee_code, "full_name": e.full_name, "first_name": e.first_name,
        "last_name": e.last_name, "email": e.email, "phone": e.phone, "department_id": e.department_id,
        "department_name": e.department.name if e.department else None, "designation_id": e.designation_id,
        "designation_title": e.designation.title if e.designation else None, "date_of_joining": e.date_of_joining,
        "employment_type": e.employment_type, "status": e.status, "role": e.user.role.name if e.user else None,
    }


def to_detail(e: Employee) -> dict:
    return {
        **to_list_item(e),
        **{f: getattr(e, f) for f in PROFILE_FIELDS},
        "user_id": e.user_id, "manager_name": e.manager.full_name if e.manager else None,
        "exit_date": e.exit_date, "exit_reason": e.exit_reason, "role_id": e.user.role_id,
        "is_user_active": e.user.is_active, "last_login_at": e.user.last_login_at, "created_at": e.created_at,
    }


# ------------------------------------------------------------------ queries
def list_employees(
    db: Session, *, page: int, page_size: int, search: str | None = None, department_id: int | None = None,
    designation_id: int | None = None, status: EmployeeStatus | None = None, employment_type=None,
    sort: str = "employee_code", order: str = "asc",
) -> dict:
    stmt = select(Employee).join(User, Employee.user_id == User.id)
    if search:
        term = f"%{escape_like(search.strip())}%"
        full = Employee.first_name + " " + Employee.last_name  # compiled to CONCAT() on MySQL
        stmt = stmt.where(
            or_(
                Employee.employee_code.ilike(term, escape="\\"), User.email.ilike(term, escape="\\"),
                full.ilike(term, escape="\\"), Employee.phone.ilike(term, escape="\\"),
            )
        )
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if designation_id:
        stmt = stmt.where(Employee.designation_id == designation_id)
    if status:
        stmt = stmt.where(Employee.status == status)
    if employment_type:
        stmt = stmt.where(Employee.employment_type == employment_type)
    col = SORTABLE.get(sort, Employee.employee_code)
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc(), Employee.id)
    result = paginate(db, stmt, page, page_size)
    result["items"] = [to_list_item(e) for e in result["items"]]
    return result


def get_employee(db: Session, employee_id: int) -> Employee:
    return get_or_404(db, Employee, employee_id, "Employee")


def _next_code(db: Session) -> str:
    codes = db.scalars(select(Employee.employee_code)).all()
    nums = [int(m.group(1)) for c in codes if (m := re.fullmatch(r"EMP(\d+)", c))]
    return f"EMP{(max(nums) + 1) if nums else 1:04d}"


def _check_email_free(db: Session, email: str, exclude_user_id: int | None = None) -> None:
    stmt = select(User.id).where(func.lower(User.email) == email.lower())
    if exclude_user_id:
        stmt = stmt.where(User.id != exclude_user_id)
    if db.scalar(stmt):
        raise ConflictError("Another account already uses this email address", code="email_taken")


def _check_manager(db: Session, manager_id: int | None, employee_id: int | None = None) -> None:
    if not manager_id:
        return
    if manager_id == employee_id:
        raise ValidationError("An employee cannot be their own manager")
    mgr = get_or_404(db, Employee, manager_id, "Manager")
    if mgr.status != EmployeeStatus.ACTIVE:
        raise ValidationError("Manager must be an active employee")
    # prevent cycles: walk up the chain from the proposed manager
    seen, cur = set(), mgr
    while cur is not None and cur.id not in seen:
        if employee_id and cur.id == employee_id:
            raise ValidationError("This manager assignment would create a reporting cycle")
        seen.add(cur.id)
        cur = cur.manager


# ------------------------------------------------------------------ commands
def create_employee(db: Session, ctx: RequestContext, data: dict) -> Employee:
    salary = data.pop("salary")
    password = data.pop("password", None)
    role_id = data.pop("role_id", None)
    email = data.pop("email").lower()

    _check_email_free(db, email)
    organization_service.validate_refs(db, data.get("department_id"), data.get("designation_id"))
    _check_manager(db, data.get("manager_id"))
    role = db.get(Role, role_id) if role_id else db.scalar(select(Role).where(Role.name == ROLE_EMPLOYEE))
    if role is None:
        raise ValidationError("Role not found")
    if role.name == "Admin" and "role:manage" not in ctx.user.permissions:
        raise PermissionDeniedError("Only administrators can assign the Admin role")

    user = User(
        email=email,
        full_name=f"{data['first_name']} {data['last_name']}",
        password_hash=hash_password(password or generate_temp_password()),
        role_id=role.id,
        must_change_password=True,
    )
    db.add(user)
    db.flush()

    emp = Employee(**data, user_id=user.id, employee_code=_next_code(db), created_by_id=ctx.user_id)
    db.add(emp)
    db.flush()

    salary["effective_from"] = salary.get("effective_from") or emp.date_of_joining
    db.add(SalaryStructure(**salary, employee_id=emp.id, created_by_id=ctx.user_id))
    leave_service.ensure_balances(db, emp, emp.date_of_joining.year)
    if emp.date_of_joining.year != today_local().year:
        leave_service.ensure_balances(db, emp, today_local().year)

    link = None
    if not password:
        link = auth_service.password_link(auth_service.create_password_token(db, user, TokenPurpose.ONBOARDING))
    db.refresh(emp)
    notification_service.send_email(
        db, "employee_onboarding", user.email,
        {
            "employee_name": emp.full_name, "employee_code": emp.employee_code, "email": user.email,
            "designation": emp.designation.title if emp.designation else None,
            "department": emp.department.name if emp.department else None,
            "joining_date": emp.date_of_joining.strftime("%d %b %Y"),
            "login_url": f"{settings.FRONTEND_URL}/login", "set_password_url": link,
        },
        secrets=[link] if link else None, entity_type="employee", entity_id=emp.id,
    )
    notification_service.notify(db, user.id, "Welcome aboard!", f"Your employee ID is {emp.employee_code}.", "/profile")
    audit_service.record(
        db, ctx, "employee.create", f"Onboarded {emp.full_name} ({emp.employee_code}) as {role.name}",
        entity_type="employee", entity_id=emp.id,
        changes={"email": email, "role": role.name, **audit_service.snapshot(emp, PROFILE_FIELDS)},
    )
    db.commit()
    return emp


def update_employee(db: Session, ctx: RequestContext, employee_id: int, data: dict) -> Employee:
    emp = get_employee(db, employee_id)
    email = data.pop("email").lower()
    if data.get("department_id") != emp.department_id or data.get("designation_id") != emp.designation_id:
        organization_service.validate_refs(
            db,
            data.get("department_id") if data.get("department_id") != emp.department_id else None,
            data.get("designation_id") if data.get("designation_id") != emp.designation_id else None,
        )
    if data.get("manager_id") != emp.manager_id:
        _check_manager(db, data.get("manager_id"), emp.id)

    before = {**audit_service.snapshot(emp, PROFILE_FIELDS), "email": emp.user.email}
    if email != emp.user.email:
        _check_email_free(db, email, emp.user_id)
        emp.user.email = email
    for k, v in data.items():
        setattr(emp, k, v)
    emp.user.full_name = emp.full_name
    after = {**audit_service.snapshot(emp, PROFILE_FIELDS), "email": emp.user.email}
    changes = audit_service.diff(before, after)
    if changes:
        audit_service.record(
            db, ctx, "employee.update", f"Updated profile of {emp.full_name} ({emp.employee_code})",
            entity_type="employee", entity_id=emp.id, changes=changes,
        )
    db.commit()
    db.refresh(emp)
    return emp


def update_self(db: Session, ctx: RequestContext, emp: Employee, data: dict) -> Employee:
    fields = list(data.keys())
    before = audit_service.snapshot(emp, fields)
    for k, v in data.items():
        setattr(emp, k, v)
    audit_service.record(
        db, ctx, "employee.self_update", "Updated own contact details", entity_type="employee", entity_id=emp.id,
        changes=audit_service.diff(before, audit_service.snapshot(emp, fields)),
    )
    db.commit()
    return emp


def deactivate(db: Session, ctx: RequestContext, employee_id: int, exit_date: date | None, reason: str) -> Employee:
    emp = get_employee(db, employee_id)
    if emp.user_id == ctx.user_id:
        raise ValidationError("You cannot deactivate your own account")
    if emp.status == EmployeeStatus.INACTIVE:
        raise ConflictError("Employee is already inactive")
    exit_date = exit_date or today_local()
    if exit_date < emp.date_of_joining:
        raise ValidationError("Exit date cannot be before the joining date")
    emp.status = EmployeeStatus.INACTIVE
    emp.exit_date = exit_date
    emp.exit_reason = reason
    emp.user.is_active = False
    auth_service.revoke_all_sessions(db, emp.user)
    # pending requests can no longer be acted on
    pending = db.scalars(
        select(LeaveRequest).where(LeaveRequest.employee_id == emp.id, LeaveRequest.status == LeaveStatus.PENDING)
    ).all()
    for lr in pending:
        lr.status = LeaveStatus.CANCELLED
        lr.cancelled_at = utcnow()
        lr.review_comment = "Auto-cancelled: employee deactivated"
    audit_service.record(
        db, ctx, "employee.deactivate", f"Deactivated {emp.full_name} ({emp.employee_code}): {reason}",
        entity_type="employee", entity_id=emp.id,
        changes={"exit_date": exit_date.isoformat(), "reason": reason, "cancelled_leave_requests": len(pending)},
    )
    db.commit()
    return emp


def activate(db: Session, ctx: RequestContext, employee_id: int) -> Employee:
    emp = get_employee(db, employee_id)
    if emp.status == EmployeeStatus.ACTIVE:
        raise ConflictError("Employee is already active")
    old_exit = emp.exit_date
    emp.status = EmployeeStatus.ACTIVE
    emp.exit_date = None
    emp.exit_reason = None
    emp.user.is_active = True
    leave_service.ensure_balances(db, emp, today_local().year)
    audit_service.record(
        db, ctx, "employee.activate", f"Reactivated {emp.full_name} ({emp.employee_code})",
        entity_type="employee", entity_id=emp.id, changes={"previous_exit_date": old_exit},
    )
    db.commit()
    return emp


def reset_credentials(db: Session, ctx: RequestContext, employee_id: int) -> None:
    """HR-triggered: email the employee a fresh set-password link."""
    emp = get_employee(db, employee_id)
    if not emp.user.is_active:
        raise ValidationError("Employee account is inactive")
    link = auth_service.password_link(auth_service.create_password_token(db, emp.user, TokenPurpose.RESET))
    notification_service.send_email(
        db, "password_reset", emp.user.email,
        {"user_name": emp.full_name, "reset_url": link, "expires_hours": settings.PASSWORD_RESET_EXPIRE_HOURS},
        secrets=[link], entity_type="employee", entity_id=emp.id,
    )
    audit_service.record(db, ctx, "employee.password_reset_sent", f"Sent password reset link to {emp.full_name}", entity_type="employee", entity_id=emp.id)
    db.commit()


# ------------------------------------------------------------------ salary
def salary_history(db: Session, employee_id: int) -> list[SalaryStructure]:
    get_employee(db, employee_id)
    return list(
        db.scalars(
            select(SalaryStructure)
            .where(SalaryStructure.employee_id == employee_id)
            .order_by(SalaryStructure.effective_from.desc(), SalaryStructure.id.desc())
        )
    )


def salary_for_date(db: Session, employee_id: int, on: date) -> SalaryStructure | None:
    return db.scalar(
        select(SalaryStructure)
        .where(SalaryStructure.employee_id == employee_id, SalaryStructure.effective_from <= on)
        .order_by(SalaryStructure.effective_from.desc(), SalaryStructure.id.desc())
        .limit(1)
    )


def add_salary(db: Session, ctx: RequestContext, employee_id: int, data: dict) -> SalaryStructure:
    emp = get_employee(db, employee_id)
    data["effective_from"] = data.get("effective_from") or today_local()
    if data["effective_from"] < emp.date_of_joining:
        raise ValidationError("Salary cannot be effective before the joining date")
    from app.services import payroll_service

    payroll_service.ensure_period_unlocked(db, data["effective_from"], what="Salary revision")
    previous = salary_for_date(db, employee_id, data["effective_from"])
    row = SalaryStructure(**data, employee_id=emp.id, created_by_id=ctx.user_id)
    db.add(row)
    db.flush()
    audit_service.record(
        db, ctx, "salary.revise", f"Salary revised for {emp.full_name} effective {data['effective_from']}",
        entity_type="employee", entity_id=emp.id,
        changes=audit_service.diff(
            audit_service.snapshot(previous, SALARY_FIELDS) if previous else {}, audit_service.snapshot(row, SALARY_FIELDS)
        ),
    )
    db.commit()
    return row


# ------------------------------------------------------------------ documents
def list_documents(db: Session, employee_id: int) -> list[dict]:
    docs = db.scalars(
        select(EmployeeDocument).where(EmployeeDocument.employee_id == employee_id).order_by(EmployeeDocument.uploaded_at.desc())
    ).all()
    return [
        {
            "id": d.id, "employee_id": d.employee_id, "document_type": d.document_type,
            "original_filename": d.original_filename, "content_type": d.content_type, "size_bytes": d.size_bytes,
            "uploaded_at": d.uploaded_at, "uploaded_by_name": d.uploaded_by.full_name if d.uploaded_by else None,
        }
        for d in docs
    ]


async def upload_document(db: Session, ctx: RequestContext, employee_id: int, document_type: str, upload: UploadFile) -> EmployeeDocument:
    emp = get_employee(db, employee_id)
    document_type = (document_type or "").strip()
    if not (2 <= len(document_type) <= 50):
        raise ValidationError("document_type must be 2-50 characters")
    meta = await files.save_upload(upload)
    doc = EmployeeDocument(**meta, employee_id=emp.id, document_type=document_type, uploaded_by_id=ctx.user_id)
    db.add(doc)
    db.flush()
    audit_service.record(
        db, ctx, "document.upload", f"Uploaded {document_type} '{meta['original_filename']}' for {emp.full_name}",
        entity_type="employee", entity_id=emp.id, changes={"document_id": doc.id, "size": meta["size_bytes"], "sha256": meta["sha256"]},
    )
    try:
        db.commit()
    except Exception:
        files.document_path(meta["stored_filename"]).unlink(missing_ok=True)
        raise
    return doc


def get_document(db: Session, employee_id: int, document_id: int) -> EmployeeDocument:
    doc = db.get(EmployeeDocument, document_id)
    if doc is None or doc.employee_id != employee_id:
        raise NotFoundError("Document not found")
    return doc


def delete_document(db: Session, ctx: RequestContext, employee_id: int, document_id: int) -> None:
    doc = get_document(db, employee_id, document_id)
    path = files.document_path(doc.stored_filename)
    audit_service.record(
        db, ctx, "document.delete", f"Deleted document '{doc.original_filename}' ({doc.document_type})",
        entity_type="employee", entity_id=employee_id, changes={"document_id": doc.id},
    )
    db.delete(doc)
    db.commit()
    path.unlink(missing_ok=True)
