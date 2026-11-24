from datetime import date, datetime

from pydantic import Field, model_validator

from app.models.enums import AttendanceStatus
from app.schemas.common import Days, ORMModel, StrictInput


class CheckInOut(StrictInput):
    remarks: str | None = Field(None, max_length=255)


class AttendanceOut(ORMModel):
    id: int
    employee_id: int
    employee_name: str
    employee_code: str
    work_date: date
    check_in: datetime | None
    check_out: datetime | None
    work_minutes: int
    work_hours: float
    status: AttendanceStatus
    is_late: bool
    remarks: str | None
    is_overridden: bool
    override_reason: str | None
    overridden_at: datetime | None


class AttendanceOverride(StrictInput):
    employee_id: int
    work_date: date
    check_in: datetime | None = None
    check_out: datetime | None = None
    status: AttendanceStatus | None = Field(None, description="Leave empty to derive from worked hours")
    remarks: str | None = Field(None, max_length=255)
    reason: str = Field(min_length=5, max_length=255)

    @model_validator(mode="after")
    def _strip_tz(self):
        # times are wall-clock in the company time zone
        if self.check_in and self.check_in.tzinfo:
            self.check_in = self.check_in.replace(tzinfo=None)
        if self.check_out and self.check_out.tzinfo:
            self.check_out = self.check_out.replace(tzinfo=None)
        return self


class AttendanceDelete(StrictInput):
    reason: str = Field(min_length=5, max_length=255)


class MonthlySummary(ORMModel):
    employee_id: int
    employee_code: str
    employee_name: str
    department_name: str | None
    working_days: int
    eligible_days: int
    counted_days: int
    present_days: Days
    half_days: int
    absent_days: Days
    paid_leave_days: Days
    lop_leave_days: Days
    lop_days: Days
    late_days: int
    total_hours: float
    avg_hours: float
    attendance_pct: float | None


class CalendarDay(ORMModel):
    date: date
    kind: str
    leave_type: str | None
    check_in: datetime | None
    check_out: datetime | None
    work_hours: float
    is_late: bool
    is_overridden: bool
    attendance_id: int | None
    lop: Days | float


class AttendanceCalendar(ORMModel):
    summary: MonthlySummary
    days: list[CalendarDay]
