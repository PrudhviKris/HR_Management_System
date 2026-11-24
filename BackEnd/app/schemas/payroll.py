from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.models.enums import AdjustmentKind, PaymentStatus, PayrollStatus
from app.schemas.common import Days, Money, ORMModel, StrictInput


class PayrollGenerate(StrictInput):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    notes: str | None = Field(None, max_length=1000)


class AdjustmentIn(StrictInput):
    kind: AdjustmentKind
    label: str = Field(min_length=2, max_length=100)
    amount: Decimal = Field(gt=0, le=10_000_000, decimal_places=2)
    reason: str = Field(min_length=5, max_length=255)


class AdjustmentOut(ORMModel):
    id: int
    kind: AdjustmentKind
    label: str
    amount: Money
    reason: str
    created_at: datetime
    created_by_name: str | None = None


class PayslipOut(ORMModel):
    id: int
    payroll_run_id: int
    employee_id: int
    year: int
    month: int
    period: str
    run_status: PayrollStatus
    employee_code: str
    employee_name: str
    department_name: str | None
    designation_title: str | None
    date_of_joining: date | None
    bank_name: str | None
    bank_account_masked: str | None
    pan_number: str | None
    working_days: int
    eligible_days: int
    present_days: Days
    paid_leave_days: Days
    lop_days: Days
    paid_days: Days
    monthly_gross: Money
    basic: Money
    hra: Money
    conveyance_allowance: Money
    medical_allowance: Money
    special_allowance: Money
    adjustment_earnings: Money
    gross_earnings: Money
    lop_deduction: Money
    provident_fund: Money
    professional_tax: Money
    income_tax: Money
    adjustment_deductions: Money
    total_deductions: Money
    net_salary: Money
    payment_status: PaymentStatus
    transaction_ref: str | None
    credited_at: datetime | None
    has_pdf: bool
    adjustments: list[AdjustmentOut] = []


class PayrollRunOut(ORMModel):
    id: int
    year: int
    month: int
    period: str
    status: PayrollStatus
    working_days: int
    employee_count: int
    total_gross: Money
    total_deductions: Money
    total_net: Money
    notes: str | None
    generated_at: datetime | None
    generated_by_name: str | None
    locked_at: datetime | None
    locked_by_name: str | None
    paid_at: datetime | None
    paid_by_name: str | None


class PayrollRunDetail(PayrollRunOut):
    payslips: list[PayslipOut]
    payment_summary: dict[str, int]


class GenerateResult(ORMModel):
    run: PayrollRunDetail
    warnings: list[str]


class CreditResult(ORMModel):
    run: PayrollRunDetail
    credited: int
    failed: list[str]
