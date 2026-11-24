from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.employee import Employee
from app.models.enums import LeaveStatus, enum_type
from app.models.user import User

DAYS = Numeric(5, 1)


class LeaveType(TimestampMixin, Base):
    __tablename__ = "leave_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    annual_quota: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    carry_forward: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_carry_forward: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)
    color: Mapped[str] = mapped_column(String(10), nullable=False, default="#6366f1")
    description: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LeaveBalance(TimestampMixin, Base):
    __tablename__ = "leave_balances"
    __table_args__ = (UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_leave_balance"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type_id: Mapped[int] = mapped_column(ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)
    carried_forward: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)
    used: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)

    leave_type: Mapped[LeaveType] = relationship(lazy="joined")

    @property
    def total(self) -> Decimal:
        return Decimal(self.allocated) + Decimal(self.carried_forward)

    @property
    def available(self) -> Decimal:
        return self.total - Decimal(self.used)


class LeaveRequest(TimestampMixin, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="date_order"),
        Index("ix_leave_employee_dates", "employee_id", "start_date", "end_date"),
        Index("ix_leave_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type_id: Mapped[int] = mapped_column(ForeignKey("leave_types.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_half_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_days: Mapped[Decimal] = mapped_column(DAYS, nullable=False)
    paid_days: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)
    lop_days: Mapped[Decimal] = mapped_column(DAYS, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaveStatus] = mapped_column(
        enum_type(LeaveStatus, "leave_status"), nullable=False, default=LeaveStatus.PENDING
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(255))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    applied_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    employee: Mapped[Employee] = relationship(lazy="joined")
    leave_type: Mapped[LeaveType] = relationship(lazy="joined")
    reviewed_by: Mapped[User | None] = relationship(lazy="joined")
