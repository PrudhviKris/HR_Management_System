from datetime import date, datetime
from decimal import Decimal

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.security import PASSWORD_RULES, is_strong_password
from app.core.timeutils import today_local
from app.models.enums import EmployeeStatus, EmploymentType, Gender
from app.schemas.common import Money, ORMModel, StrictInput

PHONE = r"^\+?[0-9][0-9 \-]{6,18}$"
IFSC = r"^[A-Z]{4}0[A-Z0-9]{6}$"
PAN = r"^[A-Z]{5}[0-9]{4}[A-Z]$"


class SalaryIn(StrictInput):
    effective_from: date | None = None  # defaults to joining date / today
    basic: Decimal = Field(gt=0, le=10_000_000, decimal_places=2)
    hra: Decimal = Field(Decimal(0), ge=0, le=10_000_000, decimal_places=2)
    conveyance_allowance: Decimal = Field(Decimal(0), ge=0, le=10_000_000, decimal_places=2)
    medical_allowance: Decimal = Field(Decimal(0), ge=0, le=10_000_000, decimal_places=2)
    special_allowance: Decimal = Field(Decimal(0), ge=0, le=10_000_000, decimal_places=2)
    pf_applicable: bool = True
    professional_tax_applicable: bool = True
    tds_monthly: Decimal = Field(Decimal(0), ge=0, le=10_000_000, decimal_places=2)
    remarks: str | None = Field(None, max_length=255)


class SalaryOut(ORMModel):
    id: int
    effective_from: date
    basic: Money
    hra: Money
    conveyance_allowance: Money
    medical_allowance: Money
    special_allowance: Money
    pf_applicable: bool
    professional_tax_applicable: bool
    tds_monthly: Money
    gross_monthly: Money
    annual_ctc: Money
    remarks: str | None
    created_at: datetime


class _EmployeeFields(StrictInput):
    first_name: str = Field(min_length=1, max_length=75)
    last_name: str = Field(min_length=1, max_length=75)
    email: EmailStr
    phone: str | None = Field(None, pattern=PHONE)
    date_of_birth: date | None = None
    gender: Gender | None = None
    address: str | None = Field(None, max_length=500)
    emergency_contact_name: str | None = Field(None, max_length=150)
    emergency_contact_phone: str | None = Field(None, pattern=PHONE)
    department_id: int | None = None
    designation_id: int | None = None
    manager_id: int | None = None
    date_of_joining: date
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    work_location: str | None = Field(None, max_length=100)
    bank_name: str | None = Field(None, max_length=100)
    bank_account_number: str | None = Field(None, pattern=r"^[0-9]{6,20}$")
    ifsc_code: str | None = Field(None, pattern=IFSC)
    pan_number: str | None = Field(None, pattern=PAN)

    @field_validator("ifsc_code", "pan_number", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.strip().upper() if isinstance(v, str) and v.strip() else (None if v == "" else v)

    @field_validator("phone", "emergency_contact_phone", "bank_account_number", "address", "work_location",
                     "bank_name", "emergency_contact_name", mode="before")
    @classmethod
    def _empty_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @model_validator(mode="after")
    def _dates(self):
        today = today_local()
        if self.date_of_birth:
            age = (today - self.date_of_birth).days / 365.25
            if age < 18 or age > 80:
                raise ValueError("date_of_birth: employee must be between 18 and 80 years old")
            if self.date_of_joining <= self.date_of_birth:
                raise ValueError("date_of_joining must be after date_of_birth")
        if (self.date_of_joining - today).days > 180:
            raise ValueError("date_of_joining cannot be more than 6 months in the future")
        return self


class EmployeeCreate(_EmployeeFields):
    role_id: int | None = None  # defaults to the Employee role
    password: str | None = Field(None, max_length=128, description="Optional initial password; otherwise an emailed set-password link is used")
    salary: SalaryIn

    @field_validator("password")
    @classmethod
    def _pwd(cls, v):
        if v and not is_strong_password(v):
            raise ValueError(PASSWORD_RULES)
        return v or None


class EmployeeUpdate(_EmployeeFields):
    pass


class EmployeeSelfUpdate(StrictInput):
    phone: str | None = Field(None, pattern=PHONE)
    address: str | None = Field(None, max_length=500)
    emergency_contact_name: str | None = Field(None, max_length=150)
    emergency_contact_phone: str | None = Field(None, pattern=PHONE)

    @field_validator("*", mode="before")
    @classmethod
    def _empty_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


class DeactivateIn(StrictInput):
    exit_date: date | None = None
    reason: str = Field(min_length=3, max_length=255)


class EmployeeListItem(ORMModel):
    id: int
    employee_code: str
    full_name: str
    first_name: str
    last_name: str
    email: str
    phone: str | None
    department_id: int | None
    department_name: str | None = None
    designation_id: int | None
    designation_title: str | None = None
    date_of_joining: date
    employment_type: EmploymentType
    status: EmployeeStatus
    role: str | None = None


class EmployeeDetail(EmployeeListItem):
    user_id: int
    date_of_birth: date | None
    gender: Gender | None
    address: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    manager_id: int | None
    manager_name: str | None = None
    work_location: str | None
    exit_date: date | None
    exit_reason: str | None
    bank_name: str | None
    bank_account_number: str | None
    ifsc_code: str | None
    pan_number: str | None
    role_id: int | None = None
    is_user_active: bool = True
    last_login_at: datetime | None = None
    created_at: datetime


class DocumentOut(ORMModel):
    id: int
    employee_id: int
    document_type: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    uploaded_by_name: str | None = None
