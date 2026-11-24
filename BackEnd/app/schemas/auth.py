from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import PASSWORD_RULES, is_strong_password
from app.schemas.common import ORMModel, StrictInput


def _strong(v: str) -> str:
    if not is_strong_password(v):
        raise ValueError(PASSWORD_RULES)
    return v


class LoginRequest(StrictInput):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(StrictInput):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(max_length=128)

    _v = field_validator("new_password")(_strong)


class ForgotPasswordRequest(StrictInput):
    email: EmailStr


class ResetPasswordRequest(StrictInput):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(max_length=128)

    _v = field_validator("new_password")(_strong)


class EmployeeBrief(ORMModel):
    id: int
    employee_code: str
    full_name: str
    department_id: int | None = None
    designation_id: int | None = None


class CurrentUser(ORMModel):
    id: int
    email: str
    full_name: str
    role: str
    permissions: list[str]
    must_change_password: bool
    last_login_at: datetime | None = None
    employee: EmployeeBrief | None = None

    @classmethod
    def from_user(cls, user) -> "CurrentUser":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            permissions=sorted(user.permissions),
            must_change_password=user.must_change_password,
            last_login_at=user.last_login_at,
            employee=EmployeeBrief.model_validate(user.employee) if user.employee else None,
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: CurrentUser
