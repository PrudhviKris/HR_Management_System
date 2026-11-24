from datetime import datetime

from pydantic import Field

from app.models.enums import EmailStatus
from app.schemas.common import ORMModel, StrictInput


class PermissionOut(ORMModel):
    id: int
    code: str
    module: str
    description: str


class RoleIn(StrictInput):
    name: str = Field(min_length=2, max_length=50)
    description: str = Field("", max_length=255)
    permissions: list[str] = Field(default_factory=list)


class RoleOut(ORMModel):
    id: int
    name: str
    description: str
    is_system: bool
    permissions: list[str]
    user_count: int


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role_id: int
    role: str
    is_active: bool
    last_login_at: datetime | None
    employee_code: str | None
    employee_id: int | None


class UserRoleIn(StrictInput):
    role_id: int


class AuditLogOut(ORMModel):
    id: int
    actor_id: int | None
    actor_email: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    description: str
    changes: dict | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class EmailTemplateOut(ORMModel):
    id: int
    code: str
    name: str
    subject: str
    body_html: str
    description: str | None
    variables: str | None
    is_active: bool
    updated_at: datetime


class EmailTemplateIn(StrictInput):
    subject: str = Field(min_length=3, max_length=255)
    body_html: str = Field(min_length=10, max_length=20000)
    is_active: bool = True


class TemplatePreviewIn(StrictInput):
    subject: str = Field(max_length=255)
    body_html: str = Field(max_length=20000)


class EmailLogOut(ORMModel):
    id: int
    template_code: str
    recipient: str
    subject: str
    status: EmailStatus
    error_message: str | None
    entity_type: str | None
    entity_id: str | None
    created_at: datetime
    sent_at: datetime | None


class EmailLogDetail(EmailLogOut):
    body_html: str


class NotificationOut(ORMModel):
    id: int
    title: str
    message: str
    link: str | None
    is_read: bool
    created_at: datetime
