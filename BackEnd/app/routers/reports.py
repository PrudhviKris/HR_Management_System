from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import RequestContext, get_request_context, require_permissions
from app.core.permissions import P
from app.core.timeutils import today_local
from app.models.enums import LeaveStatus
from app.services import audit_service, report_service, settings_service
from app.utils.exporters import to_csv, to_pdf

router = APIRouter(prefix="/reports", tags=["Reports"], dependencies=[Depends(require_permissions(P.REPORTS_VIEW))])

Format = Literal["json", "csv", "pdf"]


def _respond(db: Session, ctx: RequestContext, report: dict, fmt: str, slug: str):
    if fmt == "json":
        return report
    audit_service.record(
        db, ctx, "report.export", f"Exported {report['title']} as {fmt.upper()}", entity_type="report",
        changes={"filters": report.get("filters")},
    )
    db.commit()
    stamp = today_local().isoformat()
    if fmt == "csv":
        return Response(to_csv(report), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{slug}_{stamp}.csv"'})
    pdf = to_pdf(report, settings_service.get(db, "company_name"))
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{slug}_{stamp}.pdf"'})


def _default_from() -> date:
    return today_local().replace(day=1)


@router.get("/attendance", summary="Attendance summary per employee (json | csv | pdf)")
def attendance(
    date_from: date | None = None, date_to: date | None = None, department_id: int | None = None,
    format: Format = "json", ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db),
):
    rep = report_service.attendance_summary(db, date_from or _default_from(), date_to or today_local(), department_id)
    return _respond(db, ctx, rep, format, "attendance_summary")


@router.get("/attendance/daily", summary="Raw daily attendance log (max 92 days)")
def attendance_daily(
    date_from: date | None = None, date_to: date | None = None, department_id: int | None = None,
    format: Format = "json", ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db),
):
    rep = report_service.attendance_daily(db, date_from or _default_from(), date_to or today_local(), department_id)
    return _respond(db, ctx, rep, format, "attendance_daily")


@router.get("/leave", summary="Leave requests overlapping the date range")
def leave(
    date_from: date | None = None, date_to: date | None = None, department_id: int | None = None,
    status: LeaveStatus | None = None, leave_type_id: int | None = None,
    format: Format = "json", ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db),
):
    t = today_local()
    rep = report_service.leave_report(db, date_from or date(t.year, 1, 1), date_to or date(t.year, 12, 31), department_id, status, leave_type_id)
    return _respond(db, ctx, rep, format, "leave_report")


@router.get("/payroll", summary="Payslips of locked payroll runs within a month range")
def payroll(
    from_year: int = Query(..., ge=2000, le=2100), from_month: int = Query(..., ge=1, le=12),
    to_year: int = Query(..., ge=2000, le=2100), to_month: int = Query(..., ge=1, le=12),
    department_id: int | None = None, format: Format = "json",
    ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db),
):
    rep = report_service.payroll_report(db, from_year, from_month, to_year, to_month, department_id)
    return _respond(db, ctx, rep, format, "payroll_summary")
