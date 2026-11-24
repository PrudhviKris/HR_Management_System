from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import RequestContext
from app.exceptions import ConflictError, ValidationError
from app.models import Department, Designation, Employee, Holiday
from app.models.enums import EmployeeStatus
from app.repositories.base import get_or_404
from app.services import audit_service

DEPT_FIELDS = ["name", "code", "description", "is_active"]
DESIG_FIELDS = ["title", "department_id", "description", "is_active"]
HOLIDAY_FIELDS = ["holiday_date", "name", "is_optional"]


# ------------------------------------------------------------------ departments
def list_departments(db: Session, include_inactive: bool = True) -> list[dict]:
    counts = dict(
        db.execute(
            select(Employee.department_id, func.count(Employee.id))
            .where(Employee.status == EmployeeStatus.ACTIVE)
            .group_by(Employee.department_id)
        ).all()
    )
    stmt = select(Department).order_by(Department.name)
    if not include_inactive:
        stmt = stmt.where(Department.is_active.is_(True))
    return [
        {**{f: getattr(d, f) for f in ["id", *DEPT_FIELDS]}, "employee_count": counts.get(d.id, 0)}
        for d in db.scalars(stmt)
    ]


def _check_dept_unique(db: Session, name: str, code: str, exclude_id: int | None = None) -> None:
    stmt = select(Department).where((func.lower(Department.name) == name.lower()) | (func.upper(Department.code) == code.upper()))
    if exclude_id:
        stmt = stmt.where(Department.id != exclude_id)
    if db.scalar(stmt):
        raise ConflictError("A department with this name or code already exists")


def create_department(db: Session, ctx: RequestContext, data: dict) -> Department:
    data["code"] = data["code"].upper()
    _check_dept_unique(db, data["name"], data["code"])
    dept = Department(**data)
    db.add(dept)
    db.flush()
    audit_service.record(db, ctx, "department.create", f"Created department {dept.name}", entity_type="department", entity_id=dept.id)
    db.commit()
    return dept


def update_department(db: Session, ctx: RequestContext, dept_id: int, data: dict) -> Department:
    dept = get_or_404(db, Department, dept_id, "Department")
    data["code"] = data["code"].upper()
    _check_dept_unique(db, data["name"], data["code"], dept_id)
    before = audit_service.snapshot(dept, DEPT_FIELDS)
    for k, v in data.items():
        setattr(dept, k, v)
    audit_service.record(
        db, ctx, "department.update", f"Updated department {dept.name}", entity_type="department", entity_id=dept.id,
        changes=audit_service.diff(before, audit_service.snapshot(dept, DEPT_FIELDS)),
    )
    db.commit()
    return dept


def delete_department(db: Session, ctx: RequestContext, dept_id: int) -> None:
    dept = get_or_404(db, Department, dept_id, "Department")
    in_use = db.scalar(select(func.count(Employee.id)).where(Employee.department_id == dept_id))
    if in_use:
        raise ConflictError(f"Department has {in_use} employee(s). Reassign them or mark the department inactive instead.")
    audit_service.record(db, ctx, "department.delete", f"Deleted department {dept.name}", entity_type="department", entity_id=dept.id)
    db.delete(dept)
    db.commit()


# ------------------------------------------------------------------ designations
def list_designations(db: Session) -> list[dict]:
    rows = db.scalars(select(Designation).order_by(Designation.title)).all()
    return [
        {**{f: getattr(d, f) for f in ["id", *DESIG_FIELDS]}, "department_name": d.department.name if d.department else None}
        for d in rows
    ]


def save_designation(db: Session, ctx: RequestContext, data: dict, desig_id: int | None = None) -> Designation:
    if data.get("department_id"):
        get_or_404(db, Department, data["department_id"], "Department")
    dup = select(Designation).where(func.lower(Designation.title) == data["title"].lower())
    if desig_id:
        dup = dup.where(Designation.id != desig_id)
    if db.scalar(dup):
        raise ConflictError("A designation with this title already exists")
    if desig_id:
        desig = get_or_404(db, Designation, desig_id, "Designation")
        before = audit_service.snapshot(desig, DESIG_FIELDS)
        for k, v in data.items():
            setattr(desig, k, v)
        action, changes = "designation.update", audit_service.diff(before, audit_service.snapshot(desig, DESIG_FIELDS))
    else:
        desig = Designation(**data)
        db.add(desig)
        action, changes = "designation.create", None
    db.flush()
    audit_service.record(db, ctx, action, f"Saved designation {desig.title}", entity_type="designation", entity_id=desig.id, changes=changes)
    db.commit()
    db.refresh(desig)
    return desig


def delete_designation(db: Session, ctx: RequestContext, desig_id: int) -> None:
    desig = get_or_404(db, Designation, desig_id, "Designation")
    if db.scalar(select(func.count(Employee.id)).where(Employee.designation_id == desig_id)):
        raise ConflictError("Designation is assigned to employees; mark it inactive instead.")
    audit_service.record(db, ctx, "designation.delete", f"Deleted designation {desig.title}", entity_type="designation", entity_id=desig.id)
    db.delete(desig)
    db.commit()


# ------------------------------------------------------------------ holidays
def list_holidays(db: Session, year: int | None) -> list[Holiday]:
    stmt = select(Holiday).order_by(Holiday.holiday_date)
    if year:
        stmt = stmt.where(Holiday.holiday_date.between(date(year, 1, 1), date(year, 12, 31)))
    return list(db.scalars(stmt))


def holiday_dates(db: Session, start: date, end: date) -> set[date]:
    """Mandatory (non-optional) holidays in range; these are non-working days."""
    return set(
        db.scalars(
            select(Holiday.holiday_date).where(Holiday.holiday_date.between(start, end), Holiday.is_optional.is_(False))
        )
    )


def save_holiday(db: Session, ctx: RequestContext, data: dict, holiday_id: int | None = None) -> Holiday:
    from app.services import payroll_service  # local import: payroll depends on organization

    payroll_service.ensure_period_unlocked(db, data["holiday_date"])
    dup = select(Holiday).where(Holiday.holiday_date == data["holiday_date"])
    if holiday_id:
        dup = dup.where(Holiday.id != holiday_id)
    if db.scalar(dup):
        raise ConflictError("A holiday already exists on this date")
    if holiday_id:
        hol = get_or_404(db, Holiday, holiday_id, "Holiday")
        payroll_service.ensure_period_unlocked(db, hol.holiday_date)
        before = audit_service.snapshot(hol, HOLIDAY_FIELDS)
        for k, v in data.items():
            setattr(hol, k, v)
        action, changes = "holiday.update", audit_service.diff(before, audit_service.snapshot(hol, HOLIDAY_FIELDS))
    else:
        hol = Holiday(**data)
        db.add(hol)
        action, changes = "holiday.create", None
    db.flush()
    audit_service.record(db, ctx, action, f"Saved holiday {hol.name} on {hol.holiday_date}", entity_type="holiday", entity_id=hol.id, changes=changes)
    db.commit()
    return hol


def delete_holiday(db: Session, ctx: RequestContext, holiday_id: int) -> None:
    from app.services import payroll_service

    hol = get_or_404(db, Holiday, holiday_id, "Holiday")
    payroll_service.ensure_period_unlocked(db, hol.holiday_date)
    audit_service.record(db, ctx, "holiday.delete", f"Deleted holiday {hol.name} ({hol.holiday_date})", entity_type="holiday", entity_id=hol.id)
    db.delete(hol)
    db.commit()


def validate_refs(db: Session, department_id: int | None, designation_id: int | None) -> None:
    if department_id:
        d = get_or_404(db, Department, department_id, "Department")
        if not d.is_active:
            raise ValidationError("Department is inactive")
    if designation_id:
        g = get_or_404(db, Designation, designation_id, "Designation")
        if not g.is_active:
            raise ValidationError("Designation is inactive")
