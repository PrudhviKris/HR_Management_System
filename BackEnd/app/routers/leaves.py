from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import RequestContext, get_current_employee, get_current_user, get_request_context, require_permissions
from app.core.permissions import P
from app.core.timeutils import today_local
from app.exceptions import ValidationError
from app.models import Employee, LeaveType
from app.models.enums import LeaveStatus
from app.repositories.base import get_or_404
from app.schemas.common import Page
from app.schemas.leave import (
    BalanceAdjust,
    LeaveApply,
    LeaveBalanceOut,
    LeaveDecision,
    LeavePreview,
    LeavePreviewIn,
    LeaveReject,
    LeaveRequestOut,
    LeaveTypeIn,
    LeaveTypeOut,
)
from app.services import leave_service as svc

router = APIRouter(prefix="/leaves", tags=["Leave"])
apply_perm = Depends(require_permissions(P.LEAVE_APPLY))
configure = Depends(require_permissions(P.LEAVE_CONFIGURE))


# leave types ---------------------------------------------------------------------
@router.get("/types", response_model=list[LeaveTypeOut], dependencies=[Depends(get_current_user)])
def list_types(active_only: bool = False, db: Session = Depends(get_db)):
    return svc.list_types(db, active_only)


@router.post("/types", response_model=LeaveTypeOut, status_code=status.HTTP_201_CREATED, dependencies=[configure])
def create_type(body: LeaveTypeIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.save_type(db, ctx, body.model_dump())


@router.put("/types/{type_id}", response_model=LeaveTypeOut, dependencies=[configure])
def update_type(type_id: int, body: LeaveTypeIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.save_type(db, ctx, body.model_dump(), type_id)


# balances ------------------------------------------------------------------------
@router.get("/balances/me", response_model=list[LeaveBalanceOut], dependencies=[apply_perm])
def my_balances(year: int | None = Query(None, ge=2000, le=2100), emp: Employee = Depends(get_current_employee), db: Session = Depends(get_db)):
    return svc.get_balances(db, emp, year or today_local().year)


@router.get("/balances/{employee_id}", response_model=list[LeaveBalanceOut], dependencies=[Depends(require_permissions(P.LEAVE_VIEW))])
def employee_balances(employee_id: int, year: int | None = Query(None, ge=2000, le=2100), db: Session = Depends(get_db)):
    emp = get_or_404(db, Employee, employee_id, "Employee")
    return svc.get_balances(db, emp, year or today_local().year)


@router.post("/balances/adjust", response_model=list[LeaveBalanceOut], dependencies=[configure])
def adjust_balance(body: BalanceAdjust, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    svc.adjust_balance(db, ctx, body.employee_id, body.leave_type_id, body.year, body.allocated, body.reason)
    return svc.get_balances(db, get_or_404(db, Employee, body.employee_id), body.year)


# requests ------------------------------------------------------------------------
@router.post("/preview", response_model=LeavePreview, dependencies=[apply_perm])
def preview(body: LeavePreviewIn, emp: Employee = Depends(get_current_employee), db: Session = Depends(get_db)):
    """Working days, balance and estimated LOP split for a prospective request."""
    lt = get_or_404(db, LeaveType, body.leave_type_id, "Leave type")
    if body.end_date < body.start_date:
        raise ValidationError("End date cannot be before start date")
    return svc.preview(db, emp, lt, body.start_date, body.end_date, body.is_half_day)


@router.post("", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED, dependencies=[apply_perm])
def apply_leave(body: LeaveApply, emp: Employee = Depends(get_current_employee), ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.to_out(svc.apply(db, ctx, emp, body.model_dump()))


@router.get("/me", response_model=Page[LeaveRequestOut], dependencies=[apply_perm])
def my_requests(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: LeaveStatus | None = None,
    year: int | None = Query(None, ge=2000, le=2100),
    emp: Employee = Depends(get_current_employee), db: Session = Depends(get_db),
):
    return svc.list_requests(
        db, page=page, page_size=page_size, employee_id=emp.id, status=status,
        date_from=date(year, 1, 1) if year else None, date_to=date(year, 12, 31) if year else None,
    )


@router.get("", response_model=Page[LeaveRequestOut], dependencies=[Depends(require_permissions(P.LEAVE_VIEW))])
def all_requests(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: LeaveStatus | None = None,
    employee_id: int | None = None, leave_type_id: int | None = None, department_id: int | None = None,
    date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db),
):
    return svc.list_requests(
        db, page=page, page_size=page_size, employee_id=employee_id, status=status, leave_type_id=leave_type_id,
        department_id=department_id, date_from=date_from, date_to=date_to,
    )


@router.get("/{request_id}", response_model=LeaveRequestOut)
def get_request(request_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.to_out(svc.get_request(db, ctx, request_id))


@router.post("/{request_id}/approve", response_model=LeaveRequestOut, dependencies=[Depends(require_permissions(P.LEAVE_APPROVE))])
def approve(request_id: int, body: LeaveDecision | None = None, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    """Deducts the balance; days beyond the available balance become Loss of Pay."""
    return svc.to_out(svc.approve(db, ctx, request_id, body.comment if body else None))


@router.post("/{request_id}/reject", response_model=LeaveRequestOut, dependencies=[Depends(require_permissions(P.LEAVE_APPROVE))])
def reject(request_id: int, body: LeaveReject, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.to_out(svc.reject(db, ctx, request_id, body.comment))


@router.post("/{request_id}/cancel", response_model=LeaveRequestOut)
def cancel(request_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    """Owner can cancel pending requests (or approved ones not yet started); HR can cancel any unlocked one."""
    return svc.to_out(svc.cancel(db, ctx, request_id))
