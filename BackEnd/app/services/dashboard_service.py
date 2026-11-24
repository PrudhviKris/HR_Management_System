from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutils import month_bounds, today_local
from app.models import Attendance, AuditLog, Department, Employee, Holiday, LeaveRequest, LeaveType, PayrollRun, Payslip
from app.models.enums import AttendanceStatus, EmployeeStatus, LeaveStatus, PayrollStatus
from app.services import attendance_service, leave_service, payroll_service
from app.services.calendar_service import WorkCalendar


def _upcoming_holidays(db: Session, limit: int = 5) -> list[dict]:
    rows = db.scalars(select(Holiday).where(Holiday.holiday_date >= today_local()).order_by(Holiday.holiday_date).limit(limit))
    return [{"date": h.holiday_date, "name": h.name, "is_optional": h.is_optional} for h in rows]


def admin_dashboard(db: Session) -> dict:
    today = today_local()
    m_start, m_end = month_bounds(today.year, today.month)

    status_counts = dict(db.execute(select(Employee.status, func.count(Employee.id)).group_by(Employee.status)).all())
    active = status_counts.get(EmployeeStatus.ACTIVE, 0)
    by_dept = db.execute(
        select(func.coalesce(Department.name, "Unassigned"), func.count(Employee.id))
        .select_from(Employee).outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.status == EmployeeStatus.ACTIVE)
        .group_by(Department.name).order_by(func.count(Employee.id).desc())
    ).all()
    new_joiners = db.scalars(
        select(Employee).where(Employee.date_of_joining.between(m_start, m_end)).order_by(Employee.date_of_joining.desc()).limit(5)
    ).unique().all()

    board = attendance_service.daily_board(db, today)
    c = board["counts"]
    present_now = c.get("present", 0) + c.get("half_day", 0) + c.get("checked_in", 0)

    # attendance trend: last 14 calendar days, working days only
    start = today - timedelta(days=20)
    cal = WorkCalendar(db, start, today)
    trend_rows = dict(db.execute(
        select(Attendance.work_date, func.count(Attendance.id))
        .where(Attendance.work_date.between(start, today), Attendance.status != AttendanceStatus.ABSENT)
        .group_by(Attendance.work_date)
    ).all())
    leave_map = leave_service.leave_day_map(db, [e for e in db.scalars(select(Employee.id).where(Employee.status == EmployeeStatus.ACTIVE))], start, today)
    leave_counts: dict = {}
    for (_, d), (p, lop) in leave_map.items():
        leave_counts[d] = leave_counts.get(d, 0) + 1
    attendance_trend = [
        {"date": d, "present": trend_rows.get(d, 0), "on_leave": leave_counts.get(d, 0)}
        for d in cal.working_days()
    ][-10:]

    pending = db.scalar(select(func.count(LeaveRequest.id)).where(LeaveRequest.status == LeaveStatus.PENDING)) or 0
    leave_by_type = db.execute(
        select(LeaveType.name, LeaveType.color, func.coalesce(func.sum(LeaveRequest.total_days), 0))
        .join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id)
        .where(LeaveRequest.status == LeaveStatus.APPROVED, LeaveRequest.start_date <= m_end, LeaveRequest.end_date >= m_start)
        .group_by(LeaveType.name, LeaveType.color)
    ).all()
    recent_pending = db.scalars(
        select(LeaveRequest).where(LeaveRequest.status == LeaveStatus.PENDING).order_by(LeaveRequest.applied_at.desc()).limit(5)
    ).unique().all()

    last_run = db.scalar(select(PayrollRun).order_by(PayrollRun.year.desc(), PayrollRun.month.desc()).limit(1))
    recent_audit = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(8)).all()

    return {
        "employees": {
            "total": sum(status_counts.values()), "active": active, "inactive": status_counts.get(EmployeeStatus.INACTIVE, 0),
            "new_this_month": len(new_joiners),
            "by_department": [{"department": n, "count": cnt} for n, cnt in by_dept],
            "new_joiners": [{"id": e.id, "name": e.full_name, "code": e.employee_code, "date_of_joining": e.date_of_joining,
                             "designation": e.designation.title if e.designation else None} for e in new_joiners],
        },
        "attendance_today": {
            "date": today, "is_working_day": board["is_working_day"], "present": present_now,
            "on_leave": c.get("on_leave", 0), "not_checked_in": c.get("not_checked_in", 0) + c.get("absent", 0),
            "late": c.get("late", 0), "total": len(board["rows"]),
            "rate": round(present_now / len(board["rows"]) * 100, 1) if board["rows"] else 0,
        },
        "attendance_trend": attendance_trend,
        "leave": {
            "pending": pending,
            "approved_days_this_month": float(sum(float(x[2]) for x in leave_by_type)),
            "by_type_this_month": [{"leave_type": n, "color": col, "days": float(d)} for n, col, d in leave_by_type],
            "recent_pending": [leave_service.to_out(r) for r in recent_pending],
        },
        "payroll": {
            "last_run": {
                "id": last_run.id, "period": payroll_service.period_label(last_run.year, last_run.month),
                "status": last_run.status.value, "employee_count": last_run.employee_count,
                "total_gross": float(last_run.total_gross), "total_net": float(last_run.total_net),
                "total_deductions": float(last_run.total_deductions),
            } if last_run else None,
            "trend": [{**t, "total_gross": float(t["total_gross"]), "total_net": float(t["total_net"]),
                       "total_deductions": float(t["total_deductions"])} for t in payroll_service.payroll_trend(db, 6)],
        },
        "recent_activity": [
            {"id": a.id, "action": a.action, "description": a.description, "actor": a.actor_email, "created_at": a.created_at}
            for a in recent_audit
        ],
        "upcoming_holidays": _upcoming_holidays(db),
    }


def employee_dashboard(db: Session, emp: Employee) -> dict:
    today = today_local()
    rec = attendance_service.today_record(db, emp)
    month = attendance_service.calendar_for(db, emp, today.year, today.month)["summary"]
    balances = leave_service.get_balances(db, emp, today.year)
    recent = db.scalars(
        select(LeaveRequest).where(LeaveRequest.employee_id == emp.id).order_by(LeaveRequest.applied_at.desc()).limit(5)
    ).unique().all()
    latest = db.scalar(
        select(Payslip).join(PayrollRun).where(Payslip.employee_id == emp.id, PayrollRun.status != PayrollStatus.DRAFT)
        .order_by(PayrollRun.year.desc(), PayrollRun.month.desc()).limit(1)
    )
    on_leave = leave_service.leave_day_map(db, [emp.id], today, today).get((emp.id, today))
    return {
        "today": {
            "date": today, "is_working_day": WorkCalendar(db, today, today).is_working_day(today),
            "attendance": attendance_service.to_out(rec) if rec else None, "on_leave": bool(on_leave),
        },
        "month_summary": month,
        "leave_balances": balances,
        "recent_leaves": [leave_service.to_out(r) for r in recent],
        "latest_payslip": {
            "id": latest.id, "period": payroll_service.period_label(latest.payroll_run.year, latest.payroll_run.month),
            "net_salary": float(latest.net_salary), "gross_earnings": float(latest.gross_earnings),
            "total_deductions": float(latest.total_deductions), "payment_status": latest.payment_status.value,
        } if latest else None,
        "upcoming_holidays": _upcoming_holidays(db),
        "year_to_date_net": float(payroll_service.employee_payroll_total(db, emp.id, today.year)),
    }
