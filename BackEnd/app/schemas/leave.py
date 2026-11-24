from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.models.enums import LeaveStatus
from app.schemas.common import Days, ORMModel, StrictInput


class LeaveApply(StrictInput):
    leave_type_id: int
    start_date: date
    end_date: date
    is_half_day: bool = False
    reason: str = Field(min_length=5, max_length=1000)


class LeavePreviewIn(StrictInput):
    leave_type_id: int
    start_date: date
    end_date: date
    is_half_day: bool = False


class LeavePreview(ORMModel):
    total_days: Days
    available_balance: Days
    paid_days: Days
    lop_days: Days
    working_dates: list[date]


class LeaveDecision(StrictInput):
    comment: str | None = Field(None, max_length=255)


class LeaveReject(StrictInput):
    comment: str = Field(min_length=3, max_length=255)


class LeaveRequestOut(ORMModel):
    id: int
    employee_id: int
    employee_name: str
    employee_code: str
    department_name: str | None
    leave_type_id: int
    leave_type: str
    leave_type_code: str
    leave_type_color: str
    is_paid_type: bool
    start_date: date
    end_date: date
    is_half_day: bool
    total_days: Days
    paid_days: Days
    lop_days: Days
    reason: str
    status: LeaveStatus
    applied_at: datetime
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    review_comment: str | None
    cancelled_at: datetime | None


class LeaveBalanceOut(ORMModel):
    leave_type_id: int | None
    leave_type: str
    code: str
    color: str
    year: int
    allocated: Days
    carried_forward: Days
    total: Days
    used: Days
    pending: Days
    available: Days


class BalanceAdjust(StrictInput):
    employee_id: int
    leave_type_id: int
    year: int = Field(ge=2000, le=2100)
    allocated: Decimal = Field(ge=0, le=365, decimal_places=1)
    reason: str = Field(min_length=5, max_length=255)


class LeaveTypeIn(StrictInput):
    name: str = Field(min_length=2, max_length=50)
    code: str = Field(min_length=2, max_length=10, pattern=r"^[A-Za-z0-9_]+$")
    annual_quota: Decimal = Field(Decimal(0), ge=0, le=365, decimal_places=1)
    is_paid: bool = True
    carry_forward: bool = False
    max_carry_forward: Decimal = Field(Decimal(0), ge=0, le=365, decimal_places=1)
    color: str = Field("#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    description: str | None = Field(None, max_length=255)
    is_active: bool = True


class LeaveTypeOut(ORMModel):
    id: int
    name: str
    code: str
    annual_quota: Days
    is_paid: bool
    carry_forward: bool
    max_carry_forward: Days
    color: str
    description: str | None
    is_active: bool
