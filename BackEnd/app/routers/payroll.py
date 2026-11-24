from collections import Counter

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import RequestContext, get_current_employee, get_request_context, has_permission, require_permissions
from app.core.permissions import P
from app.exceptions import NotFoundError
from app.models import Employee, PayrollRun, Payslip
from app.models.enums import PayrollStatus
from app.repositories.base import get_or_404
from app.schemas.common import Page
from app.schemas.payroll import (
    AdjustmentIn,
    CreditResult,
    GenerateResult,
    PayrollGenerate,
    PayrollRunDetail,
    PayrollRunOut,
    PayslipOut,
)
from app.services import payroll_service as svc
from app.utils.payslip_pdf import render_payslip

router = APIRouter(prefix="/payroll", tags=["Payroll"])
view = Depends(require_permissions(P.PAYROLL_VIEW))
process = Depends(require_permissions(P.PAYROLL_PROCESS))


def run_out(r: PayrollRun) -> dict:
    return {
        "id": r.id, "year": r.year, "month": r.month, "period": svc.period_label(r.year, r.month), "status": r.status,
        "working_days": r.working_days, "employee_count": r.employee_count, "total_gross": r.total_gross,
        "total_deductions": r.total_deductions, "total_net": r.total_net, "notes": r.notes,
        "generated_at": r.generated_at, "generated_by_name": r.generated_by.full_name if r.generated_by else None,
        "locked_at": r.locked_at, "locked_by_name": r.locked_by.full_name if r.locked_by else None,
        "paid_at": r.paid_at, "paid_by_name": r.paid_by.full_name if r.paid_by else None,
    }


def slip_out(s: Payslip) -> dict:
    data = {c: getattr(s, c) for c in PayslipOut.model_fields if hasattr(s, c) and c not in ("adjustments",)}
    run = s.payroll_run
    data.update(
        year=run.year, month=run.month, period=svc.period_label(run.year, run.month), run_status=run.status,
        has_pdf=bool(s.pdf_filename),
        adjustments=[
            {"id": a.id, "kind": a.kind, "label": a.label, "amount": a.amount, "reason": a.reason,
             "created_at": a.created_at, "created_by_name": a.created_by.full_name if a.created_by else None}
            for a in s.adjustments
        ],
    )
    return data


def run_detail(r: PayrollRun) -> dict:
    return {
        **run_out(r),
        "payslips": [slip_out(s) for s in r.payslips],
        "payment_summary": dict(Counter(s.payment_status.value for s in r.payslips)),
    }


# runs -----------------------------------------------------------------------------
@router.get("/runs", response_model=Page[PayrollRunOut], dependencies=[view])
def list_runs(page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=100), year: int | None = None, db: Session = Depends(get_db)):
    res = svc.list_runs(db, page, page_size, year)
    res["items"] = [run_out(r) for r in res["items"]]
    return res


@router.post("/runs", response_model=GenerateResult, status_code=status.HTTP_201_CREATED, dependencies=[process])
def generate(body: PayrollGenerate, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    """Calculates salaries for a completed month from attendance + approved leave. Re-running for a
    DRAFT month recalculates it (manual adjustments are kept)."""
    res = svc.generate(db, ctx, body.year, body.month, body.notes)
    return {"run": run_detail(res["run"]), "warnings": res["warnings"]}


@router.get("/runs/{run_id}", response_model=PayrollRunDetail, dependencies=[view])
def get_run(run_id: int, db: Session = Depends(get_db)):
    return run_detail(get_or_404(db, PayrollRun, run_id, "Payroll run"))


@router.post("/runs/{run_id}/regenerate", response_model=GenerateResult, dependencies=[process])
def regenerate(run_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    run = get_or_404(db, PayrollRun, run_id, "Payroll run")
    res = svc.generate(db, ctx, run.year, run.month)
    return {"run": run_detail(res["run"]), "warnings": res["warnings"]}


@router.post("/runs/{run_id}/lock", response_model=PayrollRunDetail, dependencies=[process])
def lock(run_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    """Freezes the payroll, generates payslip PDFs and emails every employee."""
    return run_detail(svc.lock(db, ctx, run_id))


@router.post("/runs/{run_id}/credit", response_model=CreditResult, dependencies=[process])
def credit(run_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    """Simulated bank transfer: assigns a transaction reference to each payslip (no real payment)."""
    res = svc.credit(db, ctx, run_id)
    return {"run": run_detail(res["run"]), "credited": res["credited"], "failed": res["failed"]}


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[process])
def discard(run_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    svc.discard(db, ctx, run_id)


# adjustments -------------------------------------------------------------------------
@router.post("/payslips/{payslip_id}/adjustments", response_model=PayslipOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permissions(P.PAYROLL_ADJUST))])
def add_adjustment(payslip_id: int, body: AdjustmentIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return slip_out(svc.add_adjustment(db, ctx, payslip_id, body.model_dump()))


@router.delete("/payslips/{payslip_id}/adjustments/{adjustment_id}", response_model=PayslipOut,
               dependencies=[Depends(require_permissions(P.PAYROLL_ADJUST))])
def remove_adjustment(payslip_id: int, adjustment_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return slip_out(svc.remove_adjustment(db, ctx, payslip_id, adjustment_id))


# payslips -------------------------------------------------------------------------------
@router.get("/payslips", response_model=Page[PayslipOut], dependencies=[view])
def all_payslips(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), employee_id: int | None = None,
    run_id: int | None = None, year: int | None = None, month: int | None = Query(None, ge=1, le=12),
    department: str | None = None, db: Session = Depends(get_db),
):
    res = svc.list_payslips(db, page=page, page_size=page_size, employee_id=employee_id, run_id=run_id, year=year,
                            month=month, department=department)
    res["items"] = [slip_out(s) for s in res["items"]]
    return res


@router.get("/payslips/me", response_model=Page[PayslipOut], dependencies=[Depends(require_permissions(P.PAYSLIP_SELF))])
def my_payslips(
    page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=100), year: int | None = None,
    emp: Employee = Depends(get_current_employee), db: Session = Depends(get_db),
):
    """Only payslips of locked (released) payroll runs are visible to employees."""
    res = svc.list_payslips(db, page=page, page_size=page_size, employee_id=emp.id, year=year, only_released=True)
    res["items"] = [slip_out(s) for s in res["items"]]
    return res


def _authorised_slip(db: Session, ctx: RequestContext, payslip_id: int) -> Payslip:
    slip = db.get(Payslip, payslip_id)
    if slip is None:
        raise NotFoundError("Payslip not found")
    if has_permission(ctx.user, P.PAYROLL_VIEW):
        return slip
    owner = ctx.user.employee and ctx.user.employee.id == slip.employee_id
    if owner and has_permission(ctx.user, P.PAYSLIP_SELF) and slip.payroll_run.status != PayrollStatus.DRAFT:
        return slip
    raise NotFoundError("Payslip not found")  # don't reveal existence


@router.get("/payslips/{payslip_id}", response_model=PayslipOut)
def get_payslip(payslip_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return slip_out(_authorised_slip(db, ctx, payslip_id))


@router.get("/payslips/{payslip_id}/pdf", response_class=FileResponse, summary="Download salary slip PDF")
def download_pdf(payslip_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    slip = _authorised_slip(db, ctx, payslip_id)
    run = slip.payroll_run
    filename = f"Payslip_{slip.employee_code}_{run.year}-{run.month:02d}.pdf"
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if run.status == PayrollStatus.DRAFT:  # preview: render fresh, never persist a draft PDF
        headers["Content-Disposition"] = f'attachment; filename="DRAFT_{filename}"'
        return Response(render_payslip(slip, svc.company_info(db)), media_type="application/pdf", headers=headers)
    return FileResponse(svc.pdf_bytes_path(db, slip), media_type="application/pdf", filename=filename, headers=headers)
