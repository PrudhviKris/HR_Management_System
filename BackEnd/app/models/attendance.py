from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.employee import Employee
from app.models.enums import AttendanceStatus, enum_type


class Attendance(TimestampMixin, Base):
    __tablename__ = "attendance"
    # one row per employee per day -> the DB itself rejects duplicate check-ins
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="uq_attendance_employee_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_in: Mapped[datetime | None] = mapped_column(DateTime)
    check_out: Mapped[datetime | None] = mapped_column(DateTime)
    work_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[AttendanceStatus] = mapped_column(
        enum_type(AttendanceStatus, "attendance_status"), nullable=False, default=AttendanceStatus.PRESENT
    )
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    check_in_ip: Mapped[str | None] = mapped_column(String(64))
    remarks: Mapped[str | None] = mapped_column(String(255))

    is_overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[str | None] = mapped_column(String(255))
    overridden_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime)

    employee: Mapped[Employee] = relationship(lazy="joined")

    @property
    def work_hours(self) -> float:
        return round(self.work_minutes / 60, 2)
