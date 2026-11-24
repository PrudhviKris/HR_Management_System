import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutils import month_bounds, today_local
from app.exceptions import ValidationError
from app.models import Attendance, Department, Employee, LeaveRequest, LeaveType, PayrollRun, Payslip
from app.models.enums import LeaveStatus, PayrollStatus
from app.services import attendance_service

ZERO = Decimal("0")
NON_WORK = {"weekend", "holiday", "not_employed"}


def _dept_name(db: Session, department_id: int | None) -> str | None:
    if not department_id:
        return None
    d = db.get(Department, department_id)
    return d.name if d else None


def _check_range(date_from: date, date_to: date, max_days: int = 366) -> None:
    if date_to < date_from:
        raise ValidationError("date_to must be on or after date_from")
    if (date_to - date_from).days > max_days:
        raise ValidationError(f"Date range cannot exceed {max_days} days")


def _months(date_from: date, date_to: date):
    y, m = date_from.year, date_from.month
    while (y, m) <= (date_to.year, date_to.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


# ------------------------------------------------------------------ attendance
def attendance_summary(db: Session, date_from: date, date_to: date, department_id: int | None = None) -> dict:
    _check_range(date_from, date_to)
    cutoff = min(date_to, today_local())
    stmt = select(Employee).where(
        Employee.date_of_joining <= date_to, (Employee.exit_date.is_(None)) | (Employee.exit_date >= date_from)
    ).order_by(Employee.employee_code)
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    employees = list(db.scalars(stmt).unique())
    agg = {e.id: {"working": 0, "present": ZERO, "half": 0, "absent": ZERO, "paid_leave": ZERO, "lop": ZERO, "late": 0, "minutes": 0} for e in employees}
    for y, m in _months(date_from, date_to):
        stats = attendance_service.compute_month(db, employees, y, m, cutoff=cutoff)
        for emp_id, st in stats.items():
            a = agg[emp_id]
            for d in st.days:
                if not (date_from <= d.date <= cutoff):
                    continue
                if d.attendance and d.attendance.work_minutes:
                    a["minutes"] += d.attendance.work_minutes
                if d.kind in NON_WORK or d.kind == "future":
                    continue
                a["working"] += 1
                att = min(d.att_credit, Decimal(1))
                a["present"] += att
                a["half"] += 1 if att == Decimal("0.5") else 0
                a["paid_leave"] += min(d.leave_paid, 1 - att)
                a["lop"] += d.lop
                if d.kind == "absent" and not d.attendance:
                    a["absent"] += 1
                if d.attendance and d.attendance.is_late:
                    a["late"] += 1
    rows = []
    for e in employees:
        a = agg[e.id]
        rows.append({
            "employee_code": e.employee_code, "employee_name": e.full_name,
            "department": e.department.name if e.department else "", "working_days": a["working"],
            "present_days": a["present"], "half_days": a["half"], "paid_leave_days": a["paid_leave"],
            "absent_days": a["absent"], "lop_days": a["lop"], "late_days": a["late"],
            "total_hours": round(a["minutes"] / 60, 1),
            "attendance_pct": round(float(a["present"] + a["paid_leave"]) / a["working"] * 100, 1) if a["working"] else 0,
        })
    totals = {k: sum((r[k] for r in rows), ZERO if k.endswith("days") else 0) for k in
              ["working_days", "present_days", "half_days", "paid_leave_days", "absent_days", "lop_days", "late_days"]}
    totals["employee_code"] = "Total"
    totals["total_hours"] = round(sum(r["total_hours"] for r in rows), 1)
    return {
        "title": "Attendance Summary Report",
        "filters": {"From": date_from.isoformat(), "To": date_to.isoformat(), "Department": _dept_name(db, department_id)},
        "columns": [
            {"key": "employee_code", "label": "Emp ID"}, {"key": "employee_name", "label": "Name"},
            {"key": "department", "label": "Department"}, {"key": "working_days", "label": "Working Days"},
            {"key": "present_days", "label": "Present"}, {"key": "half_days", "label": "Half Days"},
            {"key": "paid_leave_days", "label": "Paid Leave"}, {"key": "absent_days", "label": "Absent"},
            {"key": "lop_days", "label": "LOP Days"}, {"key": "late_days", "label": "Late"},
            {"key": "total_hours", "label": "Hours"}, {"key": "attendance_pct", "label": "Attendance %"},
        ],
        "rows": rows, "totals": totals,
    }


def attendance_daily(db: Session, date_from: date, date_to: date, department_id: int | None = None) -> dict:
    _check_range(date_from, date_to, 92)
    stmt = (
        select(Attendance).join(Employee, Attendance.employee_id == Employee.id)
        .where(Attendance.work_date.between(date_from, date_to))
        .order_by(Attendance.work_date.desc(), Employee.employee_code)
    )
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    rows = [
        {
            "work_date": a.work_date, "employee_code": a.employee.employee_code, "employee_name": a.employee.full_name,
            "department": a.employee.department.name if a.employee.department else "",
            "check_in": a.check_in.strftime("%H:%M") if a.check_in else "", "check_out": a.check_out.strftime("%H:%M") if a.check_out else "",
            "work_hours": a.work_hours, "status": a.status.value, "late": a.is_late, "overridden": a.is_overridden,
        }
        for a in db.scalars(stmt).unique()
    ]
    return {
        "title": "Daily Attendance Log",
        "filters": {"From": date_from.isoformat(), "To": date_to.isoformat(), "Department": _dept_name(db, department_id)},
        "columns": [
            {"key": "work_date", "label": "Date"}, {"key": "employee_code", "label": "Emp ID"},
            {"key": "employee_name", "label": "Name"}, {"key": "department", "label": "Department"},
            {"key": "check_in", "label": "In"}, {"key": "check_out", "label": "Out"},
            {"key": "work_hours", "label": "Hours"}, {"key": "status", "label": "Status"},
            {"key": "late", "label": "Late"}, {"key": "overridden", "label": "Corrected"},
        ],
        "rows": rows, "totals": None,
    }


# ------------------------------------------------------------------ leave
def leave_report(
    db: Session, date_from: date, date_to: date, department_id: int | None = None,
    status: LeaveStatus | None = None, leave_type_id: int | None = None,
) -> dict:
    _check_range(date_from, date_to)
    stmt = (
        select(LeaveRequest).join(Employee, LeaveRequest.employee_id == Employee.id)
        .where(LeaveRequest.start_date <= date_to, LeaveRequest.end_date >= date_from)
        .order_by(LeaveRequest.start_date.desc())
    )
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    if leave_type_id:
        stmt = stmt.where(LeaveRequest.leave_type_id == leave_type_id)
    reqs = db.scalars(stmt).unique().all()
    rows = [
        {
            "employee_code": r.employee.employee_code, "employee_name": r.employee.full_name,
            "department": r.employee.department.name if r.employee.department else "", "leave_type": r.leave_type.name,
            "start_date": r.start_date, "end_date": r.end_date, "total_days": r.total_days, "paid_days": r.paid_days,
            "lop_days": r.lop_days, "status": r.status.value, "applied_at": r.applied_at,
            "reviewed_by": r.reviewed_by.full_name if r.reviewed_by else "",
        }
        for r in reqs
    ]
    by_type: dict[str, dict] = {}
    for r in reqs:
        t = by_type.setdefault(r.leave_type.name, {"leave_type": r.leave_type.name, "requests": 0, "approved_days": ZERO, "pending_days": ZERO, "rejected": 0, "lop_days": ZERO})
        t["requests"] += 1
        if r.status == LeaveStatus.APPROVED:
            t["approved_days"] += r.total_days
            t["lop_days"] += r.lop_days
        elif r.status == LeaveStatus.PENDING:
            t["pending_days"] += r.total_days
        elif r.status == LeaveStatus.REJECTED:
            t["rejected"] += 1
    approved = [r for r in rows if r["status"] == "approved"]
    return {
        "title": "Leave Report",
        "filters": {
            "From": date_from.isoformat(), "To": date_to.isoformat(), "Department": _dept_name(db, department_id),
            "Status": status.value if status else None,
            "Leave type": (db.get(LeaveType, leave_type_id).name if leave_type_id and db.get(LeaveType, leave_type_id) else None),
        },
        "columns": [
            {"key": "employee_code", "label": "Emp ID"}, {"key": "employee_name", "label": "Name"},
            {"key": "department", "label": "Department"}, {"key": "leave_type", "label": "Type"},
            {"key": "start_date", "label": "From"}, {"key": "end_date", "label": "To"},
            {"key": "total_days", "label": "Days"}, {"key": "paid_days", "label": "Paid"},
            {"key": "lop_days", "label": "LOP"}, {"key": "status", "label": "Status"},
            {"key": "reviewed_by", "label": "Reviewed By"},
        ],
        "rows": rows,
        "totals": {
            "employee_code": "Total (approved)", "total_days": sum((r["total_days"] for r in approved), ZERO),
            "paid_days": sum((r["paid_days"] for r in approved), ZERO), "lop_days": sum((r["lop_days"] for r in approved), ZERO),
        },
        "summary": list(by_type.values()),
    }


# ------------------------------------------------------------------ payroll
def payroll_report(db: Session, from_year: int, from_month: int, to_year: int, to_month: int, department_id: int | None = None) -> dict:
    if (to_year, to_month) < (from_year, from_month):
        raise ValidationError("End period must be on or after start period")
    if (to_year - from_year) * 12 + to_month - from_month > 24:
        raise ValidationError("Period range cannot exceed 24 months")
    start, _ = month_bounds(from_year, from_month)
    _, end = month_bounds(to_year, to_month)
    stmt = (
        select(Payslip).join(PayrollRun, Payslip.payroll_run_id == PayrollRun.id)
        .where(
            (PayrollRun.year * 100 + PayrollRun.month).between(from_year * 100 + from_month, to_year * 100 + to_month),
            PayrollRun.status != PayrollStatus.DRAFT,
        )
        .order_by(PayrollRun.year, PayrollRun.month, Payslip.employee_code)
    )
    dept = _dept_name(db, department_id)
    if department_id:
        stmt = stmt.join(Employee, Payslip.employee_id == Employee.id).where(Employee.department_id == department_id)
    slips = db.scalars(stmt).unique().all()
    rows = [
        {
            "period": f"{calendar.month_abbr[s.payroll_run.month]} {s.payroll_run.year}", "employee_code": s.employee_code,
            "employee_name": s.employee_name, "department": s.department_name or "", "paid_days": s.paid_days,
            "lop_days": s.lop_days, "gross_earnings": s.gross_earnings, "lop_deduction": s.lop_deduction,
            "provident_fund": s.provident_fund, "professional_tax": s.professional_tax, "income_tax": s.income_tax,
            "total_deductions": s.total_deductions, "net_salary": s.net_salary, "payment_status": s.payment_status.value,
        }
        for s in slips
    ]
    money = ["gross_earnings", "lop_deduction", "provident_fund", "professional_tax", "income_tax", "total_deductions", "net_salary", "lop_days"]
    totals = {k: sum((r[k] for r in rows), ZERO) for k in money}
    totals["employee_code"] = "Total"
    return {
        "title": "Payroll Summary Report",
        "filters": {"From": f"{calendar.month_abbr[from_month]} {from_year}", "To": f"{calendar.month_abbr[to_month]} {to_year}", "Department": dept},
        "columns": [
            {"key": "period", "label": "Period"}, {"key": "employee_code", "label": "Emp ID"},
            {"key": "employee_name", "label": "Name"}, {"key": "department", "label": "Department"},
            {"key": "paid_days", "label": "Paid Days"}, {"key": "lop_days", "label": "LOP Days"},
            {"key": "gross_earnings", "label": "Gross"}, {"key": "lop_deduction", "label": "LOP Ded."},
            {"key": "provident_fund", "label": "PF"}, {"key": "professional_tax", "label": "PT"},
            {"key": "income_tax", "label": "TDS"}, {"key": "total_deductions", "label": "Deductions"},
            {"key": "net_salary", "label": "Net Pay"}, {"key": "payment_status", "label": "Payment"},
        ],
        "rows": rows, "totals": totals,
    }
