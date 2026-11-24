from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ACCESS, decode_token
from app.exceptions import AuthenticationError, PermissionDeniedError
from app.models import Employee, User

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token from /auth/login")


@dataclass
class RequestContext:
    """Who is acting and from where; handed to services for auditing."""

    user: User | None
    ip: str | None
    user_agent: str | None

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user else None


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication required")
    try:
        payload = decode_token(creds.credentials, ACCESS)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Access token expired", code="token_expired")
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid access token", code="invalid_token")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("Account is inactive or no longer exists", code="inactive_account")
    if payload.get("ver") != user.token_version:
        raise AuthenticationError("Session has been revoked, please sign in again", code="token_revoked")
    return user


def get_request_context(request: Request, user: User = Depends(get_current_user)) -> RequestContext:
    return RequestContext(user=user, ip=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:255])


def require_permissions(*codes: str, any_of: bool = False):
    """Dependency factory: user must hold all (default) or any of the given permission codes."""

    def checker(user: User = Depends(get_current_user)) -> User:
        perms = user.permissions
        ok = any(c in perms for c in codes) if any_of else all(c in perms for c in codes)
        if not ok:
            raise PermissionDeniedError("You do not have permission to perform this action")
        return user

    return checker


def get_current_employee(user: User = Depends(get_current_user)) -> Employee:
    if user.employee is None:
        raise PermissionDeniedError("This account has no employee profile", code="no_employee_profile")
    return user.employee


def has_permission(user: User, code: str) -> bool:
    return code in user.permissions
