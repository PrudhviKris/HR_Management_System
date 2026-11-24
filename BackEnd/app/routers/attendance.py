from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import RequestContext, get_current_employee, get_request_context, require_permissions
from app.core.permissions import P
from app.core.timeutils import today_local
from app.models import Employee
from app.repositories.base import get_or_404
from app.schemas.attendance import (
    AttendanceCalendar,
    AttendanceOut,
    AttendanceOverride,
    CheckInOut,
    MonthlySummary,
)
from app.services import attendance_service as svc

router = APIRouter(prefix="/attendance", tags=["Attendance"])
self_service = Depends(require_permissions(P.ATTENDANCE_SELF))


def _ym(year: int | None, month: int | None) -> tuple[int, int]:
    t = today_local()
    return year or t.year, month or t.month


# self service ------------------------------------------------------------------
@router.post("/check-in", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED, dependencies=[self_service])
def check_in(
    body: CheckInOut | None = None,
    emp: Employee = Depends(get_current_employee),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """One check-in per day; a second attempt returns 409 `duplicate_check_in`."""
    return svc.to_out(svc.check_in(db, ctx, emp, body.remarks if body else None))


@router.post("/check-out", response_model=AttendanceOut, dependencies=[self_service])
def check_out(
    body: CheckInOut | None = None,
    emp: Employee = Depends(get_current_employee),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return svc.to_out(svc.check_out(db, ctx, emp, body.remarks if body else None))


@router.get("/today", response_model=AttendanceOut | None, dependencies=[self_service])
def today(emp: Employee = Depends(get_current_employee), db: Session = Depends(get_db)):
    rec = svc.today_record(db, emp)
    return svc.to_out(rec) if rec else None


@router.get("/me", response_model=AttendanceCalendar, dependencies=[self_service])
def my_month(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    emp: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Day-by-day calendar with status, hours and the month summary."""
    return svc.calendar_for(db, emp, *_ym(year, month))


# administration ------------------------------------------------------------------
@router.get("/daily", dependencies=[Depends(require_permissions(P.ATTENDANCE_VIEW))])
def daily_board(day: date | None = None, department_id: int | None = None, db: Session = Depends(get_db)):
    """Everyone's status for one day (present, on leave, not checked in...)."""
    return svc.daily_board(db, day or today_local(), department_id)


@router.get("/summary", response_model=list[MonthlySummary], dependencies=[Depends(require_permissions(P.ATTENDANCE_VIEW))])
def monthly_summary(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    department_id: int | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
):
    return svc.monthly_summary(db, *_ym(year, month), department_id, employee_id)


@router.get("/employees/{employee_id}", response_model=AttendanceCalendar, dependencies=[Depends(require_permissions(P.ATTENDANCE_VIEW))])
def employee_month(
    employee_id: int,
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    emp = get_or_404(db, Employee, employee_id, "Employee")
    return svc.calendar_for(db, emp, *_ym(year, month))


@router.post("/override", response_model=AttendanceOut, dependencies=[Depends(require_permissions(P.ATTENDANCE_OVERRIDE))])
def override(body: AttendanceOverride, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    """Create or correct an attendance record. A reason is mandatory and the change is audited.
    Rejected with 423 if the month's payroll is locked."""
    return svc.to_out(svc.override(db, ctx, body.model_dump()))


@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permissions(P.ATTENDANCE_OVERRIDE))])
def delete_record(
    attendance_id: int,
    reason: str = Query(..., min_length=5, max_length=255),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    svc.delete_record(db, ctx, attendance_id, reason)
