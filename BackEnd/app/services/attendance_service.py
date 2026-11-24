"""Attendance: self check-in/out, admin overrides and the per-day ledger shared with payroll.

Day classification (thresholds in system settings):
* worked >= full_day_hours -> present (1.0), >= half_day_hours -> half day (0.5), less -> absent (0)
* checked in but never checked out (past day) -> half day
* a working day with no attendance and no approved leave -> absent, which payroll treats as LOP
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import RequestContext
from app.core.timeutils import daterange, is_weekend, month_bounds, now_local, today_local, utcnow
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import Attendance, Employee
from app.models.enums import AttendanceStatus, EmployeeStatus
from app.repositories.base import get_or_404
from app.services import audit_service, leave_service, settings_service
from app.services.calendar_service import WorkCalendar

ZERO, HALF, ONE = Decimal("0"), Decimal("0.5"), Decimal("1")
CREDIT = {AttendanceStatus.PRESENT: ONE, AttendanceStatus.HALF_DAY: HALF, AttendanceStatus.ABSENT: ZERO}
AUDIT_FIELDS = ["work_date", "check_in", "check_out", "work_minutes", "status", "is_late", "remarks"]


def classify(db: Session, minutes: int, cfg: dict | None = None) -> AttendanceStatus:
    cfg = cfg or settings_service.get_many(db)
    hours = Decimal(minutes) / 60
    if hours >= cfg["full_day_hours"]:
        return AttendanceStatus.PRESENT
    if hours >= cfg["half_day_hours"]:
        return AttendanceStatus.HALF_DAY
    return AttendanceStatus.ABSENT


def _is_late(check_in: datetime, cfg: dict) -> bool:
    start = datetime.combine(check_in.date(), cfg["office_start_time"]) + timedelta(minutes=cfg["late_grace_minutes"])
    return check_in > start


def to_out(a: Attendance) -> dict:
    return {
        "id": a.id, "employee_id": a.employee_id, "employee_name": a.employee.full_name,
        "employee_code": a.employee.employee_code, "work_date": a.work_date, "check_in": a.check_in,
        "check_out": a.check_out, "work_minutes": a.work_minutes, "work_hours": a.work_hours, "status": a.status,
        "is_late": a.is_late, "remarks": a.remarks, "is_overridden": a.is_overridden,
        "override_reason": a.override_reason, "overridden_at": a.overridden_at,
    }


# ------------------------------------------------------------------ self service
def today_record(db: Session, emp: Employee) -> Attendance | None:
    return db.scalar(select(Attendance).where(Attendance.employee_id == emp.id, Attendance.work_date == today_local()))


def check_in(db: Session, ctx: RequestContext, emp: Employee, remarks: str | None = None) -> Attendance:
    if emp.status != EmployeeStatus.ACTIVE:
        raise ValidationError("Inactive employees cannot check in")
    now = now_local()
    today = now.date()
    existing = today_record(db, emp)
    if existing:
        raise ConflictError(
            f"You have already checked in today at {existing.check_in:%H:%M}" if existing.check_in else "Attendance for today is already recorded",
            code="duplicate_check_in",
        )
    leave = leave_service.leave_day_map(db, [emp.id], today, today).get((emp.id, today))
    if leave and sum(leave) >= ONE:
        raise ValidationError("You are on approved full-day leave today", code="on_leave")
    cfg = settings_service.get_many(db)
    rec = Attendance(
        employee_id=emp.id, work_date=today, check_in=now, status=AttendanceStatus.HALF_DAY,
        is_late=_is_late(now, cfg), check_in_ip=ctx.ip, remarks=remarks,
    )
    db.add(rec)
    try:
        db.flush()
    except IntegrityError:  # concurrent double click: unique (employee_id, work_date) wins
        db.rollback()
        raise ConflictError("You have already checked in today", code="duplicate_check_in")
    audit_service.record(db, ctx, "attendance.check_in", f"Checked in at {now:%H:%M}", entity_type="attendance", entity_id=rec.id)
    db.commit()
    db.refresh(rec)
    return rec


def check_out(db: Session, ctx: RequestContext, emp: Employee, remarks: str | None = None) -> Attendance:
    rec = today_record(db, emp)
    if rec is None or rec.check_in is None:
        raise ValidationError("You have not checked in today", code="not_checked_in")
    if rec.check_out is not None:
        raise ConflictError(f"You have already checked out today at {rec.check_out:%H:%M}", code="duplicate_check_out")
    now = now_local()
    rec.check_out = max(now, rec.check_in)
    rec.work_minutes = int((rec.check_out - rec.check_in).total_seconds() // 60)
    rec.status = classify(db, rec.work_minutes)
    if remarks:
        rec.remarks = remarks
    audit_service.record(
        db, ctx, "attendance.check_out", f"Checked out at {now:%H:%M} ({rec.work_hours} h)", entity_type="attendance", entity_id=rec.id
    )
    db.commit()
    db.refresh(rec)
    return rec


# ------------------------------------------------------------------ month ledger
@dataclass
class DayEntry:
    date: date
    kind: str  # weekend | holiday | not_employed | future | present | half_day | absent | leave | missed_checkout
    attendance: Attendance | None = None
    att_credit: Decimal = ZERO
    leave_paid: Decimal = ZERO
    leave_lop: Decimal = ZERO
    leave_type: str | None = None

    @property
    def paid_credit(self) -> Decimal:
        return min(ONE, self.att_credit + self.leave_paid)

    @property
    def lop(self) -> Decimal:
        return ONE - self.paid_credit


@dataclass
class MonthStats:
    employee: Employee
    working_days: int = 0  # working days in the month
    eligible_days: int = 0  # working days within the employment window
    counted_days: int = 0  # eligible days up to the cut-off (today for running month)
    present_days: Decimal = ZERO
    half_days: int = 0
    absent_days: Decimal = ZERO  # no attendance & no leave
    paid_leave_days: Decimal = ZERO
    lop_leave_days: Decimal = ZERO
    lop_days: Decimal = ZERO  # total unpaid (absent + LOP leave + short days)
    late_days: int = 0
    work_minutes: int = 0
    days: list[DayEntry] = field(default_factory=list)


def compute_month(db: Session, employees: list[Employee], year: int, month: int, cutoff: date | None = None) -> dict[int, MonthStats]:
    start, end = month_bounds(year, month)
    cutoff = min(end, cutoff or end)
    cal = WorkCalendar(db, start, end)
    working = cal.working_days()
    ids = [e.id for e in employees]
    records = {
        (a.employee_id, a.work_date): a
        for a in db.scalars(select(Attendance).where(Attendance.employee_id.in_(ids), Attendance.work_date.between(start, end)))
    } if ids else {}
    leaves = leave_service.leave_day_map(db, ids, start, end)
    leave_names = _leave_names(db, ids, start, end)
    today = today_local()

    out: dict[int, MonthStats] = {}
    for emp in employees:
        st = MonthStats(employee=emp, working_days=len(working))
        emp_start = max(start, emp.date_of_joining)
        emp_end = min(end, emp.exit_date) if emp.exit_date else end
        for d in daterange(start, end):
            rec = records.get((emp.id, d))
            if rec and rec.work_minutes:
                st.work_minutes += rec.work_minutes
            if is_weekend(d) or d in cal.holidays:
                st.days.append(DayEntry(d, "weekend" if is_weekend(d) else "holiday", rec))
                continue
            if d < emp_start or d > emp_end:
                st.days.append(DayEntry(d, "not_employed", rec))
                continue
            st.eligible_days += 1
            paid, lop = leaves.get((emp.id, d), (ZERO, ZERO))
            # today is still in progress: don't count it as absent before the employee checks in
            if d > cutoff or (d == today and rec is None and not (paid or lop)):
                st.days.append(DayEntry(d, "future", rec))
                continue
            st.counted_days += 1
            entry = DayEntry(d, "absent", rec, leave_paid=min(paid, ONE), leave_lop=min(lop, ONE), leave_type=leave_names.get((emp.id, d)))
            if rec:
                if rec.check_in and rec.check_out is None and d < today:
                    entry.kind, entry.att_credit = "missed_checkout", HALF
                elif rec.check_in and rec.check_out is None:
                    entry.kind, entry.att_credit = "checked_in", ONE  # today, still at work
                else:
                    entry.kind, entry.att_credit = rec.status.value, CREDIT[rec.status]
                if rec.is_late:
                    st.late_days += 1
            if entry.att_credit < ONE and (paid or lop) and entry.kind in ("absent",):
                entry.kind = "leave"
            att = min(entry.att_credit, ONE)
            st.present_days += att
            if att == HALF:
                st.half_days += 1
            st.paid_leave_days += min(entry.leave_paid, ONE - att)
            st.lop_leave_days += min(entry.leave_lop, ONE - att - min(entry.leave_paid, ONE - att))
            if not rec and not (paid or lop):
                st.absent_days += ONE
            st.lop_days += entry.lop
            st.days.append(entry)
        out[emp.id] = st
    return out


def _leave_names(db: Session, ids: list[int], start: date, end: date) -> dict[tuple[int, date], str]:
    from app.models import LeaveRequest
    from app.models.enums import LeaveStatus

    if not ids:
        return {}
    out = {}
    for r in db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.employee_id.in_(ids), LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date <= end, LeaveRequest.end_date >= start,
        )
    ):
        for d in daterange(max(r.start_date, start), min(r.end_date, end)):
            out[(r.employee_id, d)] = r.leave_type.code + (" (½)" if r.is_half_day else "")
    return out


def stats_to_summary(st: MonthStats) -> dict:
    e = st.employee
    return {
        "employee_id": e.id, "employee_code": e.employee_code, "employee_name": e.full_name,
        "department_name": e.department.name if e.department else None,
        "working_days": st.working_days, "eligible_days": st.eligible_days, "counted_days": st.counted_days,
        "present_days": st.present_days, "half_days": st.half_days, "absent_days": st.absent_days,
        "paid_leave_days": st.paid_leave_days, "lop_leave_days": st.lop_leave_days, "lop_days": st.lop_days,
        "late_days": st.late_days, "total_hours": round(st.work_minutes / 60, 2),
        "avg_hours": round(st.work_minutes / 60 / float(st.present_days), 2) if st.present_days else 0,
        "attendance_pct": round(float(st.present_days + st.paid_leave_days) / st.counted_days * 100, 1) if st.counted_days else None,
    }


def calendar_for(db: Session, emp: Employee, year: int, month: int) -> dict:
    st = compute_month(db, [emp], year, month, cutoff=today_local())[emp.id]
    days = []
    for d in st.days:
        a = d.attendance
        days.append({
            "date": d.date, "kind": d.kind, "leave_type": d.leave_type,
            "check_in": a.check_in if a else None, "check_out": a.check_out if a else None,
            "work_hours": a.work_hours if a else 0, "is_late": a.is_late if a else False,
            "is_overridden": a.is_overridden if a else False, "attendance_id": a.id if a else None,
            "lop": d.lop if d.kind not in ("weekend", "holiday", "not_employed", "future") else 0,
        })
    return {"summary": stats_to_summary(st), "days": days}


def monthly_summary(db: Session, year: int, month: int, department_id: int | None = None, employee_id: int | None = None) -> list[dict]:
    start, end = month_bounds(year, month)
    stmt = select(Employee).where(Employee.date_of_joining <= end).where(
        (Employee.exit_date.is_(None)) | (Employee.exit_date >= start)
    ).order_by(Employee.employee_code)
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if employee_id:
        stmt = stmt.where(Employee.id == employee_id)
    employees = list(db.scalars(stmt).unique())
    stats = compute_month(db, employees, year, month, cutoff=today_local())
    return [stats_to_summary(stats[e.id]) for e in employees]


def daily_board(db: Session, day: date, department_id: int | None = None) -> dict:
    stmt = select(Employee).where(
        Employee.date_of_joining <= day, (Employee.exit_date.is_(None)) | (Employee.exit_date >= day),
        (Employee.status == EmployeeStatus.ACTIVE) | (Employee.exit_date >= day),
    ).order_by(Employee.employee_code)
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    employees = list(db.scalars(stmt).unique())
    ids = [e.id for e in employees]
    recs = {a.employee_id: a for a in db.scalars(select(Attendance).where(Attendance.work_date == day, Attendance.employee_id.in_(ids)))} if ids else {}
    leaves = leave_service.leave_day_map(db, ids, day, day)
    cal = WorkCalendar(db, day, day)
    rows, counts = [], {"present": 0, "half_day": 0, "absent": 0, "on_leave": 0, "not_checked_in": 0, "checked_in": 0, "late": 0}
    for e in employees:
        a = recs.get(e.id)
        lv = leaves.get((e.id, day))
        if a:
            if a.check_out is None:
                state = "checked_in" if day == today_local() else "missed_checkout"
            else:
                state = a.status.value
            if a.is_late:
                counts["late"] += 1
        elif lv:
            state = "on_leave"
        elif not cal.is_working_day(day):
            state = "off"
        else:
            state = "not_checked_in" if day >= today_local() else "absent"
        counts[state] = counts.get(state, 0) + 1
        rows.append({
            "employee_id": e.id, "employee_code": e.employee_code, "employee_name": e.full_name,
            "department_name": e.department.name if e.department else None, "state": state,
            "attendance": to_out(a) if a else None,
        })
    return {"date": day, "is_working_day": cal.is_working_day(day), "counts": counts, "rows": rows}


# ------------------------------------------------------------------ admin override
def override(db: Session, ctx: RequestContext, data: dict) -> Attendance:
    from app.services import payroll_service

    emp = get_or_404(db, Employee, data["employee_id"], "Employee")
    day: date = data["work_date"]
    if day > today_local():
        raise ValidationError("Cannot record attendance for a future date")
    if day < emp.date_of_joining or (emp.exit_date and day > emp.exit_date):
        raise ValidationError("Date is outside the employee's employment period")
    payroll_service.ensure_period_unlocked(db, day, what="Attendance correction")

    cin, cout = data.get("check_in"), data.get("check_out")
    for label, t in (("check_in", cin), ("check_out", cout)):
        if t and t.date() != day and not (label == "check_out" and t.date() == day + timedelta(days=1)):
            raise ValidationError(f"{label} must fall on the attendance date")
    if cin and cout and cout <= cin:
        raise ValidationError("check_out must be after check_in")
    if cout and not cin:
        raise ValidationError("check_out requires check_in")

    rec = db.scalar(select(Attendance).where(Attendance.employee_id == emp.id, Attendance.work_date == day))
    before = audit_service.snapshot(rec, AUDIT_FIELDS) if rec else {}
    cfg = settings_service.get_many(db)
    if rec is None:
        rec = Attendance(employee_id=emp.id, work_date=day)
        db.add(rec)
    rec.check_in, rec.check_out = cin, cout
    rec.work_minutes = int((cout - cin).total_seconds() // 60) if cin and cout else 0
    rec.is_late = _is_late(cin, cfg) if cin else False
    status = data.get("status")
    if status is None:
        status = classify(db, rec.work_minutes, cfg) if cout else (AttendanceStatus.HALF_DAY if cin else AttendanceStatus.ABSENT)
    rec.status = status
    rec.remarks = data.get("remarks") or rec.remarks
    rec.is_overridden = True
    rec.override_reason = data["reason"]
    rec.overridden_by_id = ctx.user_id
    rec.overridden_at = utcnow()
    db.flush()
    audit_service.record(
        db, ctx, "attendance.override", f"Corrected attendance of {emp.full_name} for {day}: {data['reason']}",
        entity_type="attendance", entity_id=rec.id,
        changes=audit_service.diff(before, audit_service.snapshot(rec, AUDIT_FIELDS)),
    )
    db.commit()
    db.refresh(rec)
    return rec


def delete_record(db: Session, ctx: RequestContext, attendance_id: int, reason: str) -> None:
    from app.services import payroll_service

    rec = db.get(Attendance, attendance_id)
    if rec is None:
        raise NotFoundError("Attendance record not found")
    payroll_service.ensure_period_unlocked(db, rec.work_date, what="Attendance correction")
    audit_service.record(
        db, ctx, "attendance.delete", f"Removed attendance of {rec.employee.full_name} for {rec.work_date}: {reason}",
        entity_type="attendance", entity_id=rec.id, changes=audit_service.snapshot(rec, AUDIT_FIELDS),
    )
    db.delete(rec)
    db.commit()


def history(db: Session, employee_id: int, date_from: date, date_to: date) -> list[Attendance]:
    return list(
        db.scalars(
            select(Attendance)
            .where(Attendance.employee_id == employee_id, Attendance.work_date.between(date_from, date_to))
            .order_by(Attendance.work_date.desc())
        )
    )
