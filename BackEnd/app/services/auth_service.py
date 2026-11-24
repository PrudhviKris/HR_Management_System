from datetime import timedelta

import jwt
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import RequestContext
from app.core.security import (
    DUMMY_HASH,
    REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_url_token,
    hash_password,
    hash_url_token,
    verify_password,
)
from app.core.timeutils import utcnow
from app.exceptions import AuthenticationError, ValidationError
from app.models import PasswordResetToken, RefreshToken, User
from app.models.enums import TokenPurpose
from app.services import audit_service, notification_service


class IssuedTokens:
    def __init__(self, access: str, access_exp, refresh: str, refresh_exp, refresh_jti: str):
        self.refresh_jti = refresh_jti
        self.access_token = access
        self.access_expires_at = access_exp
        self.refresh_token = refresh
        self.refresh_expires_at = refresh_exp


def _issue(db: Session, user: User, ip: str | None, ua: str | None) -> IssuedTokens:
    access, access_exp = create_access_token(user.id, user.role.name, user.token_version)
    refresh, jti, refresh_exp = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, jti=jti, expires_at=refresh_exp, ip_address=ip, user_agent=ua))
    return IssuedTokens(access, access_exp, refresh, refresh_exp, jti)


def revoke_all_sessions(db: Session, user: User) -> None:
    """Invalidate every refresh token and (via token_version) every access token of the user."""
    user.token_version += 1
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def login(db: Session, email: str, password: str, ip: str | None, ua: str | None) -> tuple[User, IssuedTokens]:
    ctx = RequestContext(user=None, ip=ip, user_agent=ua)
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    generic = AuthenticationError("Invalid email or password", code="invalid_credentials")

    if user is None:
        verify_password(password, DUMMY_HASH)  # equalise timing to avoid user enumeration
        audit_service.record(db, ctx, "auth.login_failed", f"Failed login for unknown email {email}", actor_email=email)
        db.commit()
        raise generic

    now = utcnow()
    if user.locked_until and user.locked_until > now:
        mins = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise AuthenticationError(
            f"Account temporarily locked after repeated failed logins. Try again in {mins} minute(s).",
            code="account_locked",
        )

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        desc = f"Failed login ({user.failed_login_attempts}/{settings.MAX_FAILED_LOGINS})"
        if user.failed_login_attempts >= settings.MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
            desc = f"Account locked for {settings.LOCKOUT_MINUTES} minutes after repeated failed logins"
        audit_service.record(
            db, ctx, "auth.login_failed", desc, entity_type="user", entity_id=user.id, actor_email=user.email
        )
        db.commit()
        raise generic

    if not user.is_active:
        raise AuthenticationError("Your account has been deactivated. Contact HR.", code="inactive_account")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    tokens = _issue(db, user, ip, ua)
    audit_service.record(
        db, RequestContext(user=user, ip=ip, user_agent=ua), "auth.login", "Signed in",
        entity_type="user", entity_id=user.id,
    )
    db.commit()
    return user, tokens


def refresh(db: Session, raw_token: str | None, ip: str | None, ua: str | None) -> tuple[User, IssuedTokens]:
    if not raw_token:
        raise AuthenticationError("No refresh token", code="no_refresh_token")
    try:
        payload = decode_token(raw_token, REFRESH)
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid or expired refresh token", code="invalid_refresh_token")

    row = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    user = db.get(User, int(payload["sub"]))
    if row is None or user is None or row.user_id != user.id:
        raise AuthenticationError("Invalid refresh token", code="invalid_refresh_token")

    if row.revoked_at is not None:
        # A rotated/revoked token was replayed: assume theft and kill every session of this user.
        revoke_all_sessions(db, user)
        audit_service.record(
            db, RequestContext(user=user, ip=ip, user_agent=ua), "auth.token_reuse",
            "Refresh token reuse detected; all sessions revoked", entity_type="user", entity_id=user.id,
        )
        db.commit()
        raise AuthenticationError("Session expired, please sign in again", code="token_reuse")

    if row.expires_at < utcnow() or not user.is_active:
        raise AuthenticationError("Session expired, please sign in again", code="invalid_refresh_token")

    tokens = _issue(db, user, ip, ua)
    row.revoked_at = utcnow()
    row.replaced_by_jti = tokens.refresh_jti
    db.commit()
    return user, tokens


def logout(db: Session, ctx: RequestContext, raw_token: str | None) -> None:
    if raw_token:
        try:
            payload = decode_token(raw_token, REFRESH)
            row = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
            if row and row.user_id == ctx.user_id and row.revoked_at is None:
                row.revoked_at = utcnow()
        except jwt.PyJWTError:
            pass
    # the current access token stays valid until expiry unless we bump token_version; do it so
    # logout is immediate across the API (this signs out other devices too, acceptable for HRMS)
    ctx.user.token_version += 1
    audit_service.record(db, ctx, "auth.logout", "Signed out", entity_type="user", entity_id=ctx.user_id)
    db.commit()


def change_password(db: Session, ctx: RequestContext, current: str, new: str) -> IssuedTokens:
    user = ctx.user
    if not verify_password(current, user.password_hash):
        raise ValidationError("Current password is incorrect", code="invalid_password")
    if verify_password(new, user.password_hash):
        raise ValidationError("New password must be different from the current password")
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    revoke_all_sessions(db, user)
    tokens = _issue(db, user, ctx.ip, ctx.user_agent)
    audit_service.record(db, ctx, "auth.password_changed", "Changed password", entity_type="user", entity_id=user.id)
    db.commit()
    return tokens


def create_password_token(db: Session, user: User, purpose: TokenPurpose) -> str:
    # invalidate earlier unused tokens of the same purpose
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.purpose == purpose,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    raw, digest = generate_url_token()
    db.add(
        PasswordResetToken(
            user_id=user.id, token_hash=digest, purpose=purpose,
            expires_at=utcnow() + timedelta(hours=settings.PASSWORD_RESET_EXPIRE_HOURS),
        )
    )
    return raw


def password_link(raw_token: str) -> str:
    return f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"


def forgot_password(db: Session, email: str, ip: str | None, ua: str | None) -> None:
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None or not user.is_active:
        return  # never reveal whether the account exists
    raw = create_password_token(db, user, TokenPurpose.RESET)
    link = password_link(raw)
    notification_service.send_email(
        db, "password_reset", user.email,
        {"user_name": user.full_name, "reset_url": link, "expires_hours": settings.PASSWORD_RESET_EXPIRE_HOURS},
        secrets=[link], entity_type="user", entity_id=user.id,
    )
    audit_service.record(
        db, RequestContext(user=None, ip=ip, user_agent=ua), "auth.password_reset_requested",
        "Password reset requested", entity_type="user", entity_id=user.id, actor_email=user.email,
    )
    db.commit()


def reset_password(db: Session, raw_token: str, new_password: str, ip: str | None, ua: str | None) -> None:
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_url_token(raw_token)))
    if row is None or row.used_at is not None or row.expires_at < utcnow():
        raise ValidationError("This link is invalid or has expired. Please request a new one.", code="invalid_token")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise ValidationError("This account is not active", code="inactive_account")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    user.failed_login_attempts = 0
    user.locked_until = None
    row.used_at = utcnow()
    revoke_all_sessions(db, user)
    audit_service.record(
        db, RequestContext(user=None, ip=ip, user_agent=ua), "auth.password_reset",
        f"Password set via {row.purpose.value} link", entity_type="user", entity_id=user.id, actor_email=user.email,
    )
    db.commit()
