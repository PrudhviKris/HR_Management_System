from datetime import date

from pydantic import Field

from app.schemas.common import ORMModel, StrictInput


class DepartmentIn(StrictInput):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(None, max_length=255)
    is_active: bool = True


class DepartmentOut(ORMModel):
    id: int
    name: str
    code: str
    description: str | None
    is_active: bool
    employee_count: int = 0


class DesignationIn(StrictInput):
    title: str = Field(min_length=2, max_length=100)
    department_id: int | None = None
    description: str | None = Field(None, max_length=255)
    is_active: bool = True


class DesignationOut(ORMModel):
    id: int
    title: str
    department_id: int | None
    department_name: str | None = None
    description: str | None
    is_active: bool


class HolidayIn(StrictInput):
    holiday_date: date
    name: str = Field(min_length=2, max_length=100)
    is_optional: bool = False


class HolidayOut(ORMModel):
    id: int
    holiday_date: date
    name: str
    is_optional: bool


class SettingOut(ORMModel):
    key: str
    value: str
    type: str
    description: str


class SettingsUpdate(StrictInput):
    values: dict[str, str] = Field(min_length=1)
