from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import RequestContext, get_current_user, get_request_context, require_permissions
from app.core.permissions import P
from app.schemas.organization import (
    DepartmentIn,
    DepartmentOut,
    DesignationIn,
    DesignationOut,
    HolidayIn,
    HolidayOut,
    SettingOut,
    SettingsUpdate,
)
from app.services import organization_service as svc
from app.services import settings_service

router = APIRouter(tags=["Organization"])
manage = Depends(require_permissions(P.ORG_MANAGE))


# departments ---------------------------------------------------------------
@router.get("/departments", response_model=list[DepartmentOut], dependencies=[Depends(get_current_user)])
def list_departments(include_inactive: bool = True, db: Session = Depends(get_db)):
    return svc.list_departments(db, include_inactive)


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED, dependencies=[manage])
def create_department(body: DepartmentIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.create_department(db, ctx, body.model_dump())


@router.put("/departments/{dept_id}", response_model=DepartmentOut, dependencies=[manage])
def update_department(dept_id: int, body: DepartmentIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.update_department(db, ctx, dept_id, body.model_dump())


@router.delete("/departments/{dept_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage])
def delete_department(dept_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    svc.delete_department(db, ctx, dept_id)


# designations --------------------------------------------------------------
@router.get("/designations", response_model=list[DesignationOut], dependencies=[Depends(get_current_user)])
def list_designations(db: Session = Depends(get_db)):
    return svc.list_designations(db)


@router.post("/designations", response_model=DesignationOut, status_code=status.HTTP_201_CREATED, dependencies=[manage])
def create_designation(body: DesignationIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.save_designation(db, ctx, body.model_dump())


@router.put("/designations/{desig_id}", response_model=DesignationOut, dependencies=[manage])
def update_designation(desig_id: int, body: DesignationIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.save_designation(db, ctx, body.model_dump(), desig_id)


@router.delete("/designations/{desig_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage])
def delete_designation(desig_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    svc.delete_designation(db, ctx, desig_id)


# holidays ------------------------------------------------------------------
@router.get("/holidays", response_model=list[HolidayOut], dependencies=[Depends(get_current_user)])
def list_holidays(year: int | None = Query(None, ge=2000, le=2100), db: Session = Depends(get_db)):
    return svc.list_holidays(db, year)


@router.post("/holidays", response_model=HolidayOut, status_code=status.HTTP_201_CREATED, dependencies=[manage])
def create_holiday(body: HolidayIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.save_holiday(db, ctx, body.model_dump())


@router.put("/holidays/{holiday_id}", response_model=HolidayOut, dependencies=[manage])
def update_holiday(holiday_id: int, body: HolidayIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.save_holiday(db, ctx, body.model_dump(), holiday_id)


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage])
def delete_holiday(holiday_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    svc.delete_holiday(db, ctx, holiday_id)


# settings ------------------------------------------------------------------
@router.get("/settings", response_model=list[SettingOut], dependencies=[Depends(require_permissions(P.SETTINGS_MANAGE))])
def get_settings(db: Session = Depends(get_db)):
    return settings_service.describe(db)


@router.put("/settings", response_model=list[SettingOut], dependencies=[Depends(require_permissions(P.SETTINGS_MANAGE))])
def update_settings(body: SettingsUpdate, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return settings_service.update(db, ctx, body.values)


@router.get("/settings/public", dependencies=[Depends(get_current_user)])
def public_settings(db: Session = Depends(get_db)):
    raw = settings_service.get_all_raw(db)
    keys = ["company_name", "office_start_time", "full_day_hours", "half_day_hours"]
    return {k: raw[k] for k in keys}
