"""Payroll processing.

Lifecycle: DRAFT (generate / regenerate / adjust) -> LOCKED (payslip PDFs + emails; attendance, leave,
holidays and salary for the month become immutable) -> PAID (simulated bank credit per payslip).

Calculation for an employee in a month (W = working days in the month, E = working days inside the
employment window, L = LOP days from the attendance/leave ledger):
  earned component     = component x E / W           (pro-rata for joiners / leavers)
  LOP deduction        = monthly gross / W x L
  paid days            = E - L
  provident fund       = pf_rate% x basic x paid days / W        (if applicable)
  professional tax     = flat amount when (earned gross - LOP) > threshold (if applicable)
  income tax (TDS)     = fixed monthly amount from the salary structure
  net                  = earned gross + adj. earnings - (LOP + PF + PT + TDS + adj. deductions), floored at 0
"""

import calendar
import secrets
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import RequestContext
from app.core.permissions import P
from app.core.timeutils import month_bounds, today_local, utcnow
from app.exceptions import ConflictError, LockedError, NotFoundError, ValidationError
from app.models import Employee, PayrollAdjustment, PayrollRun, Payslip
from app.models.enums import AdjustmentKind, PaymentStatus, PayrollStatus
from app.repositories.base import get_or_404, paginate
from app.services import attendance_service, audit_service, employee_service, notification_service, settings_service
from app.utils import files
from app.utils.money import fmt_inr, mask_account, q2
from app.utils.payslip_pdf import render_payslip

ZERO = Decimal("0")


def period_label(year: int, month: int) -> str:
    return f"{calendar.month_name[month]} {year}"


# ------------------------------------------------------------------ locking guards
def _locked_run(db: Session, year: int, month: int) -> PayrollRun | None:
    return db.scalar(
        select(PayrollRun).where(PayrollRun.year == year, PayrollRun.month == month, PayrollRun.status != PayrollStatus.DRAFT)
    )


def ensure_period_unlocked(db: Session, day: date, what: str = "This change") -> None:
    if _locked_run(db, day.year, day.month):
        raise LockedError(
            f"{what} is not allowed: payroll for {period_label(day.year, day.month)} is locked", code="payroll_locked"
        )


def ensure_range_unlocked(db: Session, start: date, end: date) -> None:
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        if _locked_run(db, y, m):
            raise LockedError(f"Payroll for {period_label(y, m)} is locked; dates in that month cannot be changed", code="payroll_locked")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


# ------------------------------------------------------------------ calculation
def _employees_for(db: Session, start: date, end: date) -> list[Employee]:
    return list(
        db.scalars(
            select(Employee)
            .where(Employee.date_of_joining <= end, (Employee.exit_date.is_(None)) | (Employee.exit_date >= start))
            .order_by(Employee.employee_code)
        ).unique()
    )


def _recalculate(slip: Payslip, cfg: dict, structure=None) -> None:
    """Recompute totals of a payslip from its stored earnings/day counts + adjustments."""
    adj_earn = sum((Decimal(a.amount) for a in slip.adjustments if a.kind == AdjustmentKind.EARNING), ZERO)
    adj_ded = sum((Decimal(a.amount) for a in slip.adjustments if a.kind == AdjustmentKind.DEDUCTION), ZERO)
    slip.adjustment_earnings = q2(adj_earn)
    slip.adjustment_deductions = q2(adj_ded)
    earned = sum(
        (Decimal(x) for x in (slip.basic, slip.hra, slip.conveyance_allowance, slip.medical_allowance, slip.special_allowance)),
        ZERO,
    )
    slip.gross_earnings = q2(earned + adj_earn)
    slip.total_deductions = q2(
        Decimal(slip.lop_deduction) + Decimal(slip.provident_fund) + Decimal(slip.professional_tax)
        + Decimal(slip.income_tax) + adj_ded
    )
    slip.net_salary = q2(max(ZERO, Decimal(slip.gross_earnings) - Decimal(slip.total_deductions)))


def _compute_slip(slip: Payslip, emp: Employee, st, structure, cfg: dict) -> None:
    W = Decimal(st.working_days)
    E = Decimal(st.eligible_days)
    L = q2(st.lop_days)
    ratio = (E / W) if W else ZERO

    slip.employee_code = emp.employee_code
    slip.employee_name = emp.full_name
    slip.department_name = emp.department.name if emp.department else None
    slip.designation_title = emp.designation.title if emp.designation else None
    slip.date_of_joining = emp.date_of_joining
    slip.bank_name = emp.bank_name
    slip.bank_account_masked = mask_account(emp.bank_account_number)
    slip.pan_number = emp.pan_number

    slip.working_days = st.working_days
    slip.eligible_days = st.eligible_days
    slip.present_days = st.present_days
    slip.paid_leave_days = st.paid_leave_days
    slip.lop_days = L
    slip.paid_days = max(ZERO, E - L)

    gross = structure.gross_monthly
    slip.monthly_gross = q2(gross)
    slip.basic = q2(Decimal(structure.basic) * ratio)
    slip.hra = q2(Decimal(structure.hra) * ratio)
    slip.conveyance_allowance = q2(Decimal(structure.conveyance_allowance) * ratio)
    slip.medical_allowance = q2(Decimal(structure.medical_allowance) * ratio)
    slip.special_allowance = q2(Decimal(structure.special_allowance) * ratio)
    slip.lop_deduction = q2(gross / W * L) if W else ZERO

    paid_ratio = (Decimal(slip.paid_days) / W) if W else ZERO
    slip.provident_fund = q2(Decimal(structure.basic) * paid_ratio * cfg["pf_rate_percent"] / 100) if structure.pf_applicable else ZERO
    earned_after_lop = q2(gross * ratio) - Decimal(slip.lop_deduction)
    slip.professional_tax = (
        q2(cfg["professional_tax_amount"])
        if structure.professional_tax_applicable and earned_after_lop > cfg["professional_tax_threshold"]
        else ZERO
    )
    slip.income_tax = q2(structure.tds_monthly) if slip.paid_days > 0 else ZERO
    _recalculate(slip, cfg)


def _refresh_totals(run: PayrollRun) -> None:
    run.employee_count = len(run.payslips)
    run.total_gross = q2(sum((Decimal(s.gross_earnings) for s in run.payslips), ZERO))
    run.total_deductions = q2(sum((Decimal(s.total_deductions) for s in run.payslips), ZERO))
    run.total_net = q2(sum((Decimal(s.net_salary) for s in run.payslips), ZERO))


def generate(db: Session, ctx: RequestContext, year: int, month: int, notes: str | None = None) -> dict:
    start, end = month_bounds(year, month)
    if end >= today_local():
        raise ValidationError(f"Payroll for {period_label(year, month)} can be generated only after the month ends")
    run = db.scalar(select(PayrollRun).where(PayrollRun.year == year, PayrollRun.month == month))
    if run and run.status != PayrollStatus.DRAFT:
        raise LockedError(f"Payroll for {period_label(year, month)} is already {run.status.value}", code="payroll_locked")

    cfg = settings_service.get_many(db)
    employees = _employees_for(db, start, end)
    stats = attendance_service.compute_month(db, employees, year, month)
    regenerated = run is not None
    if run is None:
        run = PayrollRun(year=year, month=month, working_days=0)
        db.add(run)
        db.flush()
    existing = {s.employee_id: s for s in run.payslips}
    warnings, kept = [], set()
    for emp in employees:
        structure = employee_service.salary_for_date(db, emp.id, end)
        if structure is None:
            warnings.append(f"{emp.employee_code} {emp.full_name}: no salary structure, skipped")
            continue
        st = stats[emp.id]
        if st.eligible_days == 0:
            continue
        slip = existing.get(emp.id)
        if slip is None:
            slip = Payslip(employee_id=emp.id, working_days=0, eligible_days=0, employee_code="", employee_name="")
            run.payslips.append(slip)
        _compute_slip(slip, emp, st, structure, cfg)
        kept.add(emp.id)
    for emp_id, slip in existing.items():
        if emp_id not in kept:
            run.payslips.remove(slip)

    run.working_days = next(iter(stats.values())).working_days if stats else len(attendance_service.WorkCalendar(db, start, end).working_days())
    run.generated_by_id = ctx.user_id
    run.generated_at = utcnow()
    if notes is not None:
        run.notes = notes
    db.flush()
    _refresh_totals(run)
    audit_service.record(
        db, ctx, "payroll.regenerate" if regenerated else "payroll.generate",
        f"{'Regenerated' if regenerated else 'Generated'} payroll for {period_label(year, month)}: "
        f"{run.employee_count} employees, net Rs. {fmt_inr(run.total_net)}",
        entity_type="payroll_run", entity_id=run.id,
        changes={"employee_count": run.employee_count, "total_net": run.total_net, "warnings": warnings},
    )
    db.commit()
    db.refresh(run)
    return {"run": run, "warnings": warnings}


# ------------------------------------------------------------------ adjustments
def add_adjustment(db: Session, ctx: RequestContext, payslip_id: int, data: dict) -> Payslip:
    slip = get_or_404(db, Payslip, payslip_id, "Payslip")
    if slip.payroll_run.status != PayrollStatus.DRAFT:
        raise LockedError("Payroll is locked; adjustments are no longer possible", code="payroll_locked")
    adj = PayrollAdjustment(**data, payslip_id=slip.id, created_by_id=ctx.user_id)
    slip.adjustments.append(adj)
    _recalculate(slip, settings_service.get_many(db))
    _refresh_totals(slip.payroll_run)
    db.flush()
    audit_service.record(
        db, ctx, "payroll.adjust",
        f"Added {data['kind'].value} adjustment '{data['label']}' Rs. {fmt_inr(data['amount'])} to {slip.employee_name} "
        f"({period_label(slip.payroll_run.year, slip.payroll_run.month)}): {data['reason']}",
        entity_type="payslip", entity_id=slip.id, changes={**data, "new_net": slip.net_salary},
    )
    db.commit()
    db.refresh(slip)
    return slip


def remove_adjustment(db: Session, ctx: RequestContext, payslip_id: int, adjustment_id: int) -> Payslip:
    slip = get_or_404(db, Payslip, payslip_id, "Payslip")
    if slip.payroll_run.status != PayrollStatus.DRAFT:
        raise LockedError("Payroll is locked; adjustments are no longer possible", code="payroll_locked")
    adj = next((a for a in slip.adjustments if a.id == adjustment_id), None)
    if adj is None:
        raise NotFoundError("Adjustment not found")
    slip.adjustments.remove(adj)
    _recalculate(slip, settings_service.get_many(db))
    _refresh_totals(slip.payroll_run)
    audit_service.record(
        db, ctx, "payroll.adjust_remove", f"Removed adjustment '{adj.label}' from {slip.employee_name}",
        entity_type="payslip", entity_id=slip.id, changes={"label": adj.label, "amount": adj.amount, "kind": adj.kind},
    )
    db.commit()
    db.refresh(slip)
    return slip


# ------------------------------------------------------------------ lock / credit / discard
def company_info(db: Session) -> dict:
    cfg = settings_service.get_many(db)
    return {"name": cfg["company_name"], "address": cfg["company_address"]}


def write_pdf(db: Session, slip: Payslip, company: dict | None = None) -> str:
    files.ensure_dirs()
    name = slip.pdf_filename or f"payslip_{slip.payroll_run.year}_{slip.payroll_run.month:02d}_{slip.employee_code}_{secrets.token_hex(6)}.pdf"
    (files.PAYSLIPS_DIR / name).write_bytes(render_payslip(slip, company or company_info(db)))
    slip.pdf_filename = name
    return name


def _admins_notify(db: Session, ctx: RequestContext, run: PayrollRun, action: str) -> None:
    for u in notification_service.users_with_permission(db, P.PAYROLL_PROCESS):
        notification_service.send_email(
            db, "payroll_processed", u.email,
            {
                "recipient_name": u.full_name, "period": period_label(run.year, run.month), "action": action,
                "employee_count": run.employee_count, "total_gross": fmt_inr(run.total_gross),
                "total_net": fmt_inr(run.total_net), "actor_name": ctx.user.full_name,
            },
            entity_type="payroll_run", entity_id=run.id,
        )


def lock(db: Session, ctx: RequestContext, run_id: int) -> PayrollRun:
    run = get_or_404(db, PayrollRun, run_id, "Payroll run")
    if run.status != PayrollStatus.DRAFT:
        raise ConflictError(f"Payroll is already {run.status.value}")
    if not run.payslips:
        raise ValidationError("Payroll has no payslips")
    company = company_info(db)
    period = period_label(run.year, run.month)
    run.status = PayrollStatus.LOCKED
    run.locked_by_id = ctx.user_id
    run.locked_at = utcnow()
    for slip in run.payslips:
        write_pdf(db, slip, company)
        emp = slip.employee
        notification_service.send_email(
            db, "payslip_generated", emp.email,
            {
                "employee_name": slip.employee_name, "period": period, "net_salary": fmt_inr(slip.net_salary),
                "paid_days": float(slip.paid_days), "lop_days": float(slip.lop_days),
                "payslip_url": f"{settings.FRONTEND_URL}/my/payslips",
            },
            entity_type="payslip", entity_id=slip.id,
        )
        notification_service.notify(db, emp.user_id, "Salary slip available", f"Your salary slip for {period} is ready (net Rs. {fmt_inr(slip.net_salary)}).", "/my/payslips")
    _admins_notify(db, ctx, run, "locked")
    audit_service.record(
        db, ctx, "payroll.lock", f"Locked payroll for {period}; {len(run.payslips)} payslips generated",
        entity_type="payroll_run", entity_id=run.id, changes={"total_net": run.total_net},
    )
    db.commit()
    db.refresh(run)
    return run


def credit(db: Session, ctx: RequestContext, run_id: int) -> dict:
    """Simulated salary disbursement. Payslips without bank details fail and can be retried later."""
    run = get_or_404(db, PayrollRun, run_id, "Payroll run")
    if run.status == PayrollStatus.DRAFT:
        raise ValidationError("Lock the payroll before crediting salaries")
    if run.status == PayrollStatus.PAID:
        raise ConflictError("Salaries for this payroll have already been credited")
    period = period_label(run.year, run.month)
    credited, failed = 0, []
    now = utcnow()
    company = company_info(db)
    for slip in run.payslips:
        if slip.payment_status == PaymentStatus.CREDITED:
            continue
        emp = slip.employee
        if Decimal(slip.net_salary) > 0 and not emp.bank_account_number:
            slip.payment_status = PaymentStatus.FAILED
            failed.append(f"{slip.employee_code} {slip.employee_name}: no bank account on file")
            continue
        slip.bank_name = emp.bank_name
        slip.bank_account_masked = mask_account(emp.bank_account_number)
        slip.payment_status = PaymentStatus.CREDITED
        slip.transaction_ref = f"SIM{now:%Y%m%d}{secrets.token_hex(5).upper()}"
        slip.credited_at = now
        write_pdf(db, slip, company)  # PDF now shows payment reference
        credited += 1
        notification_service.send_email(
            db, "salary_credited", emp.email,
            {"employee_name": slip.employee_name, "period": period, "net_salary": fmt_inr(slip.net_salary),
             "transaction_ref": slip.transaction_ref, "bank_account": slip.bank_account_masked},
            entity_type="payslip", entity_id=slip.id,
        )
        notification_service.notify(db, emp.user_id, "Salary credited", f"Rs. {fmt_inr(slip.net_salary)} for {period} credited. Ref {slip.transaction_ref}", "/my/payslips")
    if not failed:
        run.status = PayrollStatus.PAID
        run.paid_at = now
        run.paid_by_id = ctx.user_id
        _admins_notify(db, ctx, run, "credited")
    audit_service.record(
        db, ctx, "payroll.credit", f"Salary credit simulation for {period}: {credited} credited, {len(failed)} failed",
        entity_type="payroll_run", entity_id=run.id, changes={"credited": credited, "failed": failed},
    )
    db.commit()
    db.refresh(run)
    return {"run": run, "credited": credited, "failed": failed}


def discard(db: Session, ctx: RequestContext, run_id: int) -> None:
    run = get_or_404(db, PayrollRun, run_id, "Payroll run")
    if run.status != PayrollStatus.DRAFT:
        raise LockedError("Locked payroll cannot be deleted", code="payroll_locked")
    audit_service.record(db, ctx, "payroll.discard", f"Discarded draft payroll for {period_label(run.year, run.month)}", entity_type="payroll_run", entity_id=run.id)
    db.delete(run)
    db.commit()


# ------------------------------------------------------------------ queries
def list_runs(db: Session, page: int, page_size: int, year: int | None = None) -> dict:
    stmt = select(PayrollRun).order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
    if year:
        stmt = stmt.where(PayrollRun.year == year)
    return paginate(db, stmt, page, page_size)


def list_payslips(
    db: Session, *, page: int, page_size: int, employee_id: int | None = None, run_id: int | None = None,
    year: int | None = None, month: int | None = None, only_released: bool = False, department: str | None = None,
) -> dict:
    stmt = select(Payslip).join(PayrollRun, Payslip.payroll_run_id == PayrollRun.id)
    if employee_id:
        stmt = stmt.where(Payslip.employee_id == employee_id)
    if run_id:
        stmt = stmt.where(Payslip.payroll_run_id == run_id)
    if year:
        stmt = stmt.where(PayrollRun.year == year)
    if month:
        stmt = stmt.where(PayrollRun.month == month)
    if only_released:
        stmt = stmt.where(PayrollRun.status != PayrollStatus.DRAFT)
    if department:
        stmt = stmt.where(Payslip.department_name == department)
    stmt = stmt.order_by(PayrollRun.year.desc(), PayrollRun.month.desc(), Payslip.employee_code)
    return paginate(db, stmt, page, page_size)


def pdf_bytes_path(db: Session, slip: Payslip):
    if not slip.pdf_filename or not (files.PAYSLIPS_DIR / slip.pdf_filename).exists():
        write_pdf(db, slip)
        db.commit()
    return files.PAYSLIPS_DIR / slip.pdf_filename


def payroll_trend(db: Session, months: int = 6) -> list[dict]:
    runs = db.scalars(select(PayrollRun).order_by(PayrollRun.year.desc(), PayrollRun.month.desc()).limit(months)).all()
    return [
        {"period": f"{calendar.month_abbr[r.month]} {r.year}", "year": r.year, "month": r.month, "status": r.status.value,
         "total_gross": r.total_gross, "total_net": r.total_net, "total_deductions": r.total_deductions, "employees": r.employee_count}
        for r in reversed(runs)
    ]


def employee_payroll_total(db: Session, employee_id: int, year: int) -> Decimal:
    return Decimal(str(db.scalar(
        select(func.coalesce(func.sum(Payslip.net_salary), 0)).join(PayrollRun).where(
            Payslip.employee_id == employee_id, PayrollRun.year == year, PayrollRun.status != PayrollStatus.DRAFT
        )
    ) or 0))
