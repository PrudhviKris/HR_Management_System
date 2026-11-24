from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import EmployeeStatus, EmploymentType, Gender, enum_type
from app.models.organization import Department, Designation
from app.models.user import User

MONEY = Numeric(12, 2)


class Employee(TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (Index("ix_employees_status_department", "status", "department_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(75), nullable=False)
    last_name: Mapped[str] = mapped_column(String(75), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[Gender | None] = mapped_column(enum_type(Gender, "gender"))
    address: Mapped[str | None] = mapped_column(Text)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20))

    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    designation_id: Mapped[int | None] = mapped_column(ForeignKey("designations.id", ondelete="SET NULL"), index=True)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    date_of_joining: Mapped[date] = mapped_column(Date, nullable=False)
    employment_type: Mapped[EmploymentType] = mapped_column(
        enum_type(EmploymentType, "employment_type"), nullable=False, default=EmploymentType.FULL_TIME
    )
    work_location: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[EmployeeStatus] = mapped_column(
        enum_type(EmployeeStatus, "employee_status"), nullable=False, default=EmployeeStatus.ACTIVE
    )
    exit_date: Mapped[date | None] = mapped_column(Date)
    exit_reason: Mapped[str | None] = mapped_column(String(255))

    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_account_number: Mapped[str | None] = mapped_column(String(30))
    ifsc_code: Mapped[str | None] = mapped_column(String(15))
    pan_number: Mapped[str | None] = mapped_column(String(10))

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    user: Mapped[User] = relationship(back_populates="employee", foreign_keys=[user_id], lazy="joined")
    department: Mapped[Department | None] = relationship(lazy="joined")
    designation: Mapped[Designation | None] = relationship(lazy="joined")
    manager: Mapped["Employee | None"] = relationship(remote_side=[id], lazy="select")
    salary_structures: Mapped[list["SalaryStructure"]] = relationship(
        back_populates="employee", order_by="desc(SalaryStructure.effective_from)", cascade="all, delete-orphan"
    )
    documents: Mapped[list["EmployeeDocument"]] = relationship(back_populates="employee", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def email(self) -> str:
        return self.user.email if self.user else ""

    @property
    def current_salary(self) -> "SalaryStructure | None":
        return self.salary_structures[0] if self.salary_structures else None


class SalaryStructure(Base):
    """Monthly salary components; a new row is added on each revision (history is preserved)."""

    __tablename__ = "salary_structures"
    __table_args__ = (Index("ix_salary_employee_effective", "employee_id", "effective_from"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    basic: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    hra: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    conveyance_allowance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    medical_allowance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    special_allowance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    pf_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    professional_tax_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tds_monthly: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    remarks: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="salary_structures")

    @property
    def gross_monthly(self) -> Decimal:
        return (
            Decimal(self.basic)
            + Decimal(self.hra)
            + Decimal(self.conveyance_allowance)
            + Decimal(self.medical_allowance)
            + Decimal(self.special_allowance)
        )

    @property
    def annual_ctc(self) -> Decimal:
        return self.gross_monthly * 12


class EmployeeDocument(Base):
    __tablename__ = "employee_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="documents")
    uploaded_by: Mapped[User | None] = relationship(lazy="joined")
