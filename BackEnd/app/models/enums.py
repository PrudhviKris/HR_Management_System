import enum

from sqlalchemy import Enum as SAEnum


def enum_type(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Store enum *values* (not names); native ENUM on MySQL, VARCHAR+CHECK on SQLite."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
        length=20,
    )


class StrEnum(str, enum.Enum):
    def __str__(self) -> str:
        return self.value


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"


class EmployeeStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    HALF_DAY = "half_day"
    ABSENT = "absent"


class LeaveStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PayrollStatus(StrEnum):
    DRAFT = "draft"
    LOCKED = "locked"
    PAID = "paid"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    CREDITED = "credited"
    FAILED = "failed"


class AdjustmentKind(StrEnum):
    EARNING = "earning"
    DEDUCTION = "deduction"


class EmailStatus(StrEnum):
    QUEUED = "queued"  # waiting for SMTP delivery
    SENT = "sent"
    LOGGED = "logged"  # SMTP not configured: rendered + stored only
    FAILED = "failed"


class TokenPurpose(StrEnum):
    ONBOARDING = "onboarding"
    RESET = "reset"
