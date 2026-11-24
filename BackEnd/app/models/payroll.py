from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.employee import Employee
from app.models.enums import AdjustmentKind, PaymentStatus, PayrollStatus, enum_type
from app.models.user import User

MONEY = Numeric(12, 2)
DAYS = Numeric(5, 1)


class PayrollRun(TimestampMixin, Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (UniqueConstraint("year", "month", name="uq_payroll_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PayrollStatus] = mapped_column(
        enum_type(PayrollStatus, "payroll_status"), nullable=False, default=PayrollStatus.DRAFT
    )
    working_days: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_gross: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    total_deductions: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    total_net: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    generated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    paid_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)

    payslips: Mapped[list["Payslip"]] = relationship(
        back_populates="payroll_run", cascade="all, delete-orphan", order_by="Payslip.employee_code"
    )
    generated_by: Mapped[User | None] = relationship(foreign_keys=[generated_by_id], lazy="joined")
    locked_by: Mapped[User | None] = relationship(foreign_keys=[locked_by_id], lazy="joined")
    paid_by: Mapped[User | None] = relationship(foreign_keys=[paid_by_id], lazy="joined")

    @property
    def is_locked(self) -> bool:
        return self.status != PayrollStatus.DRAFT


class Payslip(TimestampMixin, Base):
    """One employee's salary for one payroll run. Employee details are snapshotted at generation."""

    __tablename__ = "payslips"
    __table_args__ = (UniqueConstraint("payroll_run_id", "employee_id", name="uq_payslip_run_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    payroll_run_id: Mapped[int] = mapped_column(ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)

    # snapshot
    employee_code: Mapped[str] = mapped_column(String(20), nullable=False)
    employee_name: Mapped[str] = mapped_column(String(150), nullable=False)
    department_name: Mapped[str | None] = mapped_column(String(100))
    designation_title: Mapped[str | None] = mapped_column(String(100))
    date_of_joining: Mapped[date | None] = mapped_column(Date)
    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_account_masked: Mapped[str | None] = mapped_column(String(30))
    pan_number: Mapped[str | None] = mapped_column(String(10))

    # day counts
    working_days: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_days: Mapped[int] = mapped_column(Integer, nullable=False)
    present_days: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)
    paid_leave_days: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)
    lop_days: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)
    paid_days: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)

    # monthly rate (from salary structure)
    monthly_gross: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)

    # earnings (pro-rated to employment window within the month)
    basic: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    hra: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    conveyance_allowance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    medical_allowance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    special_allowance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    adjustment_earnings: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    gross_earnings: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)

    # deductions
    lop_deduction: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    provident_fund: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    professional_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    income_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    adjustment_deductions: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    total_deductions: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)

    net_salary: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)

    payment_status: Mapped[PaymentStatus] = mapped_column(
        enum_type(PaymentStatus, "payment_status"), nullable=False, default=PaymentStatus.PENDING
    )
    transaction_ref: Mapped[str | None] = mapped_column(String(40))
    credited_at: Mapped[datetime | None] = mapped_column(DateTime)
    pdf_filename: Mapped[str | None] = mapped_column(String(100))

    payroll_run: Mapped[PayrollRun] = relationship(back_populates="payslips", lazy="joined")
    employee: Mapped[Employee] = relationship(lazy="select")
    adjustments: Mapped[list["PayrollAdjustment"]] = relationship(
        back_populates="payslip", cascade="all, delete-orphan", lazy="selectin", order_by="PayrollAdjustment.id"
    )


class PayrollAdjustment(Base):
    __tablename__ = "payroll_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    payslip_id: Mapped[int] = mapped_column(ForeignKey("payslips.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[AdjustmentKind] = mapped_column(enum_type(AdjustmentKind, "adjustment_kind"), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    payslip: Mapped[Payslip] = relationship(back_populates="adjustments")
    created_by: Mapped[User | None] = relationship(lazy="joined")
