"""Leave management.

Balance rules
* Each paid leave type has an annual quota; balances are per employee per calendar year, created lazily.
  Joiners get a pro-rated allocation (rounded to 0.5 day); carry-forward types bring over up to the cap.
* Leave days count working days only (weekends and mandatory holidays are skipped). Half day = 0.5.
* On approval the paid portion is min(requested, available balance); the remainder becomes Loss of Pay
  (LOP). Unpaid leave types (e.g. "Loss of Pay") are 100% LOP. Cancelling an approved leave restores the
  balance. Payroll reads approved requests through `leave_day_map` to decide paid vs. LOP per day.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import RequestContext, has_permission
from app.core.permissions import P
from app.core.timeutils import today_local, utcnow
from app.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.models import Employee, LeaveBalance, LeaveRequest, LeaveType
from app.models.enums import EmployeeStatus, LeaveStatus
from app.repositories.base import get_or_404, paginate
from app.services import audit_service, notification_service
from app.services.calendar_service import WorkCalendar

ZERO = Decimal("0")
HALF = Decimal("0.5")
ONE = Decimal("1")
LEAVE_TYPE_FIELDS = ["name", "code", "annual_quota", "is_paid", "carry_forward", "max_carry_forward", "color", "description", "is_active"]


def _round_half(x: Decimal) -> Decimal:
    return (x * 2).quantize(ONE, rounding=ROUND_HALF_UP) / 2


# ------------------------------------------------------------------ balances
def ensure_balances(db: Session, emp: Employee, year: int) -> list[LeaveBalance]:
    types = db.scalars(select(LeaveType).where(LeaveType.is_active.is_(True), LeaveType.is_paid.is_(True))).all()
    existing = {
        b.leave_type_id: b
        for b in db.scalars(select(LeaveBalance).where(LeaveBalance.employee_id == emp.id, LeaveBalance.year == year))
    }
    created = False
    for lt in types:
        if lt.id in existing:
            continue
        quota = Decimal(lt.annual_quota)
        if emp.date_of_joining.year == year:
            months = 12 - emp.date_of_joining.month + 1
            quota = _round_half(quota * months / 12)
        elif emp.date_of_joining.year > year:
            quota = ZERO
        carried = ZERO
        if lt.carry_forward:
            prev = db.scalar(
                select(LeaveBalance).where(
                    LeaveBalance.employee_id == emp.id, LeaveBalance.leave_type_id == lt.id, LeaveBalance.year == year - 1
                )
            )
            if prev:
                carried = max(ZERO, min(prev.available, Decimal(lt.max_carry_forward)))
        bal = LeaveBalance(employee_id=emp.id, leave_type_id=lt.id, year=year, allocated=quota, carried_forward=carried, used=ZERO)
        db.add(bal)
        existing[lt.id] = bal
        created = True
    if created:
        db.flush()
    return sorted(existing.values(), key=lambda b: b.leave_type_id)


def _pending_days(db: Session, emp_id: int, type_id: int, year: int, exclude_id: int | None = None) -> Decimal:
    stmt = select(func.coalesce(func.sum(LeaveRequest.total_days), 0)).where(
        LeaveRequest.employee_id == emp_id, LeaveRequest.leave_type_id == type_id,
        LeaveRequest.status == LeaveStatus.PENDING,
        LeaveRequest.start_date.between(date(year, 1, 1), date(year, 12, 31)),
    )
    if exclude_id:
        stmt = stmt.where(LeaveRequest.id != exclude_id)
    return Decimal(str(db.scalar(stmt) or 0))


def get_balances(db: Session, emp: Employee, year: int) -> list[dict]:
    balances = ensure_balances(db, emp, year)
    db.commit()
    out = []
    for b in balances:
        pending = _pending_days(db, emp.id, b.leave_type_id, year)
        out.append({
            "leave_type_id": b.leave_type_id, "leave_type": b.leave_type.name, "code": b.leave_type.code,
            "color": b.leave_type.color, "year": year, "allocated": b.allocated, "carried_forward": b.carried_forward,
            "total": b.total, "used": b.used, "pending": pending, "available": b.available,
        })
    lop_used = db.scalar(
        select(func.coalesce(func.sum(LeaveRequest.lop_days), 0)).where(
            LeaveRequest.employee_id == emp.id, LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date.between(date(year, 1, 1), date(year, 12, 31)),
        )
    )
    out.append({
        "leave_type_id": None, "leave_type": "Loss of Pay (taken)", "code": "LOP", "color": "#ef4444", "year": year,
        "allocated": ZERO, "carried_forward": ZERO, "total": ZERO, "used": Decimal(str(lop_used or 0)),
        "pending": ZERO, "available": ZERO,
    })
    return out


def adjust_balance(db: Session, ctx: RequestContext, employee_id: int, leave_type_id: int, year: int, allocated: Decimal, reason: str) -> LeaveBalance:
    emp = get_or_404(db, Employee, employee_id, "Employee")
    ensure_balances(db, emp, year)
    bal = db.scalar(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id, LeaveBalance.leave_type_id == leave_type_id, LeaveBalance.year == year
        )
    )
    if bal is None:
        raise NotFoundError("No balance for this leave type (is it a paid, active type?)")
    if allocated + Decimal(bal.carried_forward) < Decimal(bal.used):
        raise ValidationError(f"Allocation cannot be below days already used ({bal.used})")
    old = bal.allocated
    bal.allocated = allocated
    audit_service.record(
        db, ctx, "leave.balance_adjust",
        f"Adjusted {bal.leave_type.code} allocation for {emp.full_name} ({year}) {old} -> {allocated}: {reason}",
        entity_type="employee", entity_id=emp.id, changes={"allocated": {"from": old, "to": allocated}, "reason": reason},
    )
    db.commit()
    return bal


# ------------------------------------------------------------------ day calculations
def request_days(cal: WorkCalendar, start: date, end: date, is_half_day: bool) -> list[tuple[date, Decimal]]:
    days = cal.working_days(start, end)
    weight = HALF if is_half_day else ONE
    return [(d, weight) for d in days]


def preview(db: Session, emp: Employee, leave_type: LeaveType, start: date, end: date, is_half_day: bool, exclude_id: int | None = None) -> dict:
    cal = WorkCalendar(db, start, end)
    days = request_days(cal, start, end, is_half_day)
    total = sum((w for _, w in days), ZERO)
    available = ZERO
    if leave_type.is_paid:
        bal = next((b for b in ensure_balances(db, emp, start.year) if b.leave_type_id == leave_type.id), None)
        available = max(ZERO, (bal.available if bal else ZERO) - _pending_days(db, emp.id, leave_type.id, start.year, exclude_id))
    paid = min(total, available) if leave_type.is_paid else ZERO
    return {
        "total_days": total, "available_balance": available, "paid_days": paid, "lop_days": total - paid,
        "working_dates": [d for d, _ in days],
    }


def leave_day_map(db: Session, employee_ids: list[int], start: date, end: date) -> dict[tuple[int, date], tuple[Decimal, Decimal]]:
    """(employee_id, date) -> (paid_fraction, lop_fraction) for approved leave overlapping [start, end].
    Within a request the paid portion is assigned to the earliest days, LOP to the last ones."""
    if not employee_ids:
        return {}
    reqs = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.employee_id.in_(employee_ids), LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date <= end, LeaveRequest.end_date >= start,
        )
    ).all()
    if not reqs:
        return {}
    cal = WorkCalendar(db, min(r.start_date for r in reqs), max(r.end_date for r in reqs))
    out: dict[tuple[int, date], tuple[Decimal, Decimal]] = {}
    for r in reqs:
        paid_left, lop_left = Decimal(r.paid_days), Decimal(r.lop_days)
        for d, w in request_days(cal, r.start_date, r.end_date, r.is_half_day):
            p = min(w, paid_left)
            paid_left -= p
            lop = min(w - p, lop_left)
            lop_left -= lop
            if start <= d <= end and (p or lop):
                prev = out.get((r.employee_id, d), (ZERO, ZERO))
                out[(r.employee_id, d)] = (prev[0] + p, prev[1] + lop)
    return out


# ------------------------------------------------------------------ requests
def _validate_dates(db: Session, emp: Employee, start: date, end: date, is_half_day: bool) -> None:
    from app.services import payroll_service

    if end < start:
        raise ValidationError("End date cannot be before start date")
    if is_half_day and start != end:
        raise ValidationError("A half-day leave must start and end on the same date")
    if start.year != end.year:
        raise ValidationError("A leave request cannot span two calendar years; please split it")
    if start < emp.date_of_joining:
        raise ValidationError("Leave cannot start before your joining date")
    today = today_local()
    if start < today - timedelta(days=60):
        raise ValidationError("Leave can be back-dated by at most 60 days")
    if end > today + timedelta(days=365):
        raise ValidationError("Leave can be applied at most one year in advance")
    payroll_service.ensure_range_unlocked(db, start, end)


def _check_overlap(db: Session, emp_id: int, start: date, end: date, exclude_id: int | None = None) -> None:
    stmt = select(LeaveRequest).where(
        LeaveRequest.employee_id == emp_id,
        LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
        LeaveRequest.start_date <= end, LeaveRequest.end_date >= start,
    )
    if exclude_id:
        stmt = stmt.where(LeaveRequest.id != exclude_id)
    clash = db.scalars(stmt).first()
    if clash:
        raise ConflictError(
            f"Overlaps with an existing {clash.status.value} request ({clash.start_date} to {clash.end_date})",
            code="leave_overlap",
        )


def to_out(r: LeaveRequest) -> dict:
    return {
        "id": r.id, "employee_id": r.employee_id, "employee_name": r.employee.full_name,
        "employee_code": r.employee.employee_code,
        "department_name": r.employee.department.name if r.employee.department else None,
        "leave_type_id": r.leave_type_id, "leave_type": r.leave_type.name, "leave_type_code": r.leave_type.code,
        "leave_type_color": r.leave_type.color, "is_paid_type": r.leave_type.is_paid,
        "start_date": r.start_date, "end_date": r.end_date, "is_half_day": r.is_half_day,
        "total_days": r.total_days, "paid_days": r.paid_days, "lop_days": r.lop_days, "reason": r.reason,
        "status": r.status, "applied_at": r.applied_at, "reviewed_by_name": r.reviewed_by.full_name if r.reviewed_by else None,
        "reviewed_at": r.reviewed_at, "review_comment": r.review_comment, "cancelled_at": r.cancelled_at,
    }


def _fmt(d: date) -> str:
    return d.strftime("%d %b %Y")


def apply(db: Session, ctx: RequestContext, emp: Employee, data: dict) -> LeaveRequest:
    if emp.status != EmployeeStatus.ACTIVE:
        raise PermissionDeniedError("Inactive employees cannot apply for leave")
    lt = get_or_404(db, LeaveType, data["leave_type_id"], "Leave type")
    if not lt.is_active:
        raise ValidationError("This leave type is not available")
    start, end, half = data["start_date"], data["end_date"], data.get("is_half_day", False)
    _validate_dates(db, emp, start, end, half)
    _check_overlap(db, emp.id, start, end)
    pv = preview(db, emp, lt, start, end, half)
    if pv["total_days"] <= 0:
        raise ValidationError("The selected dates contain no working days (weekends/holidays)")

    req = LeaveRequest(
        employee_id=emp.id, leave_type_id=lt.id, start_date=start, end_date=end, is_half_day=half,
        total_days=pv["total_days"], paid_days=pv["paid_days"], lop_days=pv["lop_days"], reason=data["reason"],
    )
    db.add(req)
    db.flush()

    common = {
        "employee_name": emp.full_name, "employee_code": emp.employee_code, "leave_type": lt.name,
        "start_date": _fmt(start), "end_date": _fmt(end), "days": float(pv["total_days"]), "lop_days": float(pv["lop_days"]),
        "reason": data["reason"],
    }
    notification_service.send_email(db, "leave_applied_confirmation", emp.email, common, entity_type="leave_request", entity_id=req.id)
    for approver in notification_service.users_with_permission(db, P.LEAVE_APPROVE):
        if approver.id == emp.user_id:
            continue
        notification_service.send_email(
            db, "leave_applied", approver.email,
            {**common, "approver_name": approver.full_name, "review_url": f"{settings.FRONTEND_URL}/leaves/approvals"},
            entity_type="leave_request", entity_id=req.id,
        )
        notification_service.notify(
            db, approver.id, "New leave request",
            f"{emp.full_name} applied for {lt.name}: {_fmt(start)} - {_fmt(end)} ({pv['total_days']} day(s))", "/leaves/approvals",
        )
    audit_service.record(
        db, ctx, "leave.apply", f"{emp.full_name} applied for {lt.code} {start} to {end} ({pv['total_days']} d)",
        entity_type="leave_request", entity_id=req.id,
        changes={"total_days": pv["total_days"], "estimated_lop": pv["lop_days"]},
    )
    db.commit()
    db.refresh(req)
    return req


def _review_common(db: Session, ctx: RequestContext, request_id: int) -> LeaveRequest:
    req = get_or_404(db, LeaveRequest, request_id, "Leave request")
    if req.status != LeaveStatus.PENDING:
        raise ConflictError(f"Request is already {req.status.value}")
    if req.employee.user_id == ctx.user_id:
        raise PermissionDeniedError("You cannot review your own leave request")
    return req


def _notify_decision(db: Session, req: LeaveRequest, ctx: RequestContext) -> None:
    emp = req.employee
    notification_service.send_email(
        db, "leave_status", emp.email,
        {
            "employee_name": emp.full_name, "leave_type": req.leave_type.name, "start_date": _fmt(req.start_date),
            "end_date": _fmt(req.end_date), "days": float(req.total_days), "status": req.status.value,
            "paid_days": float(req.paid_days), "lop_days": float(req.lop_days), "comment": req.review_comment,
            "reviewer_name": ctx.user.full_name,
        },
        entity_type="leave_request", entity_id=req.id,
    )
    notification_service.notify(
        db, emp.user_id, f"Leave {req.status.value}",
        f"Your {req.leave_type.name} ({_fmt(req.start_date)} - {_fmt(req.end_date)}) was {req.status.value}"
        + (f"; {req.lop_days} day(s) LOP" if req.status == LeaveStatus.APPROVED and req.lop_days else ""),
        "/my/leaves",
    )


def approve(db: Session, ctx: RequestContext, request_id: int, comment: str | None) -> LeaveRequest:
    from app.services import payroll_service

    req = _review_common(db, ctx, request_id)
    payroll_service.ensure_range_unlocked(db, req.start_date, req.end_date)
    _check_overlap(db, req.employee_id, req.start_date, req.end_date, exclude_id=req.id)

    # recompute against the live balance (other requests may have been approved meanwhile)
    cal = WorkCalendar(db, req.start_date, req.end_date)
    total = sum((w for _, w in request_days(cal, req.start_date, req.end_date, req.is_half_day)), ZERO)
    if total <= 0:
        raise ValidationError("The request no longer contains working days (holiday calendar changed); reject it instead")
    paid = ZERO
    if req.leave_type.is_paid:
        bal = next((b for b in ensure_balances(db, req.employee, req.start_date.year) if b.leave_type_id == req.leave_type_id), None)
        if bal is not None:
            paid = max(ZERO, min(total, bal.available))
            bal.used = Decimal(bal.used) + paid
    req.total_days, req.paid_days, req.lop_days = total, paid, total - paid
    req.status = LeaveStatus.APPROVED
    req.reviewed_by_id = ctx.user_id
    req.reviewed_at = utcnow()
    req.review_comment = comment
    _notify_decision(db, req, ctx)
    audit_service.record(
        db, ctx, "leave.approve",
        f"Approved {req.leave_type.code} for {req.employee.full_name} {req.start_date} to {req.end_date}: {paid} paid, {total - paid} LOP",
        entity_type="leave_request", entity_id=req.id, changes={"paid_days": paid, "lop_days": total - paid, "comment": comment},
    )
    db.commit()
    db.refresh(req)
    return req


def reject(db: Session, ctx: RequestContext, request_id: int, comment: str) -> LeaveRequest:
    req = _review_common(db, ctx, request_id)
    req.status = LeaveStatus.REJECTED
    req.reviewed_by_id = ctx.user_id
    req.reviewed_at = utcnow()
    req.review_comment = comment
    req.paid_days = ZERO
    req.lop_days = ZERO
    _notify_decision(db, req, ctx)
    audit_service.record(
        db, ctx, "leave.reject", f"Rejected {req.leave_type.code} for {req.employee.full_name} {req.start_date} to {req.end_date}",
        entity_type="leave_request", entity_id=req.id, changes={"comment": comment},
    )
    db.commit()
    db.refresh(req)
    return req


def cancel(db: Session, ctx: RequestContext, request_id: int) -> LeaveRequest:
    from app.services import payroll_service

    req = get_or_404(db, LeaveRequest, request_id, "Leave request")
    is_owner = req.employee.user_id == ctx.user_id
    is_approver = has_permission(ctx.user, P.LEAVE_APPROVE)
    if not (is_owner or is_approver):
        raise NotFoundError("Leave request not found")
    if req.status not in (LeaveStatus.PENDING, LeaveStatus.APPROVED):
        raise ConflictError(f"A {req.status.value} request cannot be cancelled")
    if req.status == LeaveStatus.APPROVED:
        if not is_approver and req.start_date <= today_local():
            raise ValidationError("Approved leave that has already started can only be cancelled by HR")
        payroll_service.ensure_range_unlocked(db, req.start_date, req.end_date)
        if req.leave_type.is_paid and req.paid_days:
            bal = db.scalar(
                select(LeaveBalance).where(
                    LeaveBalance.employee_id == req.employee_id, LeaveBalance.leave_type_id == req.leave_type_id,
                    LeaveBalance.year == req.start_date.year,
                )
            )
            if bal:
                bal.used = max(ZERO, Decimal(bal.used) - Decimal(req.paid_days))
    prev = req.status
    req.status = LeaveStatus.CANCELLED
    req.cancelled_at = utcnow()
    if not is_owner:
        notification_service.notify(db, req.employee.user_id, "Leave cancelled", f"Your {req.leave_type.name} from {_fmt(req.start_date)} was cancelled by HR", "/my/leaves")
    audit_service.record(
        db, ctx, "leave.cancel", f"Cancelled {prev.value} {req.leave_type.code} of {req.employee.full_name} {req.start_date} to {req.end_date}",
        entity_type="leave_request", entity_id=req.id, changes={"previous_status": prev.value, "restored_days": req.paid_days if prev == LeaveStatus.APPROVED else 0},
    )
    db.commit()
    db.refresh(req)
    return req


def list_requests(
    db: Session, *, page: int, page_size: int, employee_id: int | None = None, status: LeaveStatus | None = None,
    leave_type_id: int | None = None, department_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
) -> dict:
    stmt = select(LeaveRequest).join(Employee, LeaveRequest.employee_id == Employee.id)
    if employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    if leave_type_id:
        stmt = stmt.where(LeaveRequest.leave_type_id == leave_type_id)
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if date_from:
        stmt = stmt.where(LeaveRequest.end_date >= date_from)
    if date_to:
        stmt = stmt.where(LeaveRequest.start_date <= date_to)
    stmt = stmt.order_by(LeaveRequest.applied_at.desc(), LeaveRequest.id.desc())
    res = paginate(db, stmt, page, page_size)
    res["items"] = [to_out(r) for r in res["items"]]
    return res


def get_request(db: Session, ctx: RequestContext, request_id: int) -> LeaveRequest:
    req = get_or_404(db, LeaveRequest, request_id, "Leave request")
    if req.employee.user_id != ctx.user_id and not has_permission(ctx.user, P.LEAVE_VIEW):
        raise NotFoundError("Leave request not found")
    return req


def on_leave_today(db: Session, day: date) -> dict[int, LeaveRequest]:
    rows = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.status == LeaveStatus.APPROVED, LeaveRequest.start_date <= day, LeaveRequest.end_date >= day
        )
    ).all()
    return {r.employee_id: r for r in rows}


# ------------------------------------------------------------------ leave types
def list_types(db: Session, active_only: bool = False) -> list[LeaveType]:
    stmt = select(LeaveType).order_by(LeaveType.is_paid.desc(), LeaveType.name)
    if active_only:
        stmt = stmt.where(LeaveType.is_active.is_(True))
    return list(db.scalars(stmt))


def save_type(db: Session, ctx: RequestContext, data: dict, type_id: int | None = None) -> LeaveType:
    data["code"] = data["code"].upper()
    dup = select(LeaveType).where((func.lower(LeaveType.name) == data["name"].lower()) | (LeaveType.code == data["code"]))
    if type_id:
        dup = dup.where(LeaveType.id != type_id)
    if db.scalar(dup):
        raise ConflictError("A leave type with this name or code already exists")
    if not data["is_paid"]:
        data["annual_quota"] = ZERO
        data["carry_forward"] = False
    if type_id:
        lt = get_or_404(db, LeaveType, type_id, "Leave type")
        if lt.is_paid != data["is_paid"] and db.scalar(select(func.count(LeaveRequest.id)).where(LeaveRequest.leave_type_id == lt.id)):
            raise ConflictError("Cannot switch paid/unpaid on a leave type that already has requests")
        before = audit_service.snapshot(lt, LEAVE_TYPE_FIELDS)
        for k, v in data.items():
            setattr(lt, k, v)
        action, changes = "leave_type.update", audit_service.diff(before, audit_service.snapshot(lt, LEAVE_TYPE_FIELDS))
    else:
        lt = LeaveType(**data)
        db.add(lt)
        action, changes = "leave_type.create", audit_service.snapshot(lt, LEAVE_TYPE_FIELDS)
    db.flush()
    audit_service.record(db, ctx, action, f"Saved leave type {lt.name}", entity_type="leave_type", entity_id=lt.id, changes=changes)
    db.commit()
    return lt


def leave_summary_by_type(db: Session, start: date, end: date) -> dict:
    rows = db.execute(
        select(LeaveType.name, LeaveRequest.status, func.count(LeaveRequest.id), func.coalesce(func.sum(LeaveRequest.total_days), 0))
        .join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id)
        .where(LeaveRequest.start_date <= end, LeaveRequest.end_date >= start)
        .group_by(LeaveType.name, LeaveRequest.status)
    ).all()
    out: dict = defaultdict(lambda: defaultdict(float))
    for name, status, cnt, days in rows:
        out[name][status.value if hasattr(status, "value") else status] += float(days)
    return out
