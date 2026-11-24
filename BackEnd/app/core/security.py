import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,128}$")
PASSWORD_RULES = "Password must be 8-128 characters and include an uppercase letter, a lowercase letter and a digit."

ACCESS = "access"
REFRESH = "refresh"


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; pre-hash longer inputs so nothing is silently ignored
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raw = hashlib.sha256(raw).hexdigest().encode()
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raw = hashlib.sha256(raw).hexdigest().encode()
    try:
        return bcrypt.checkpw(raw, password_hash.encode())
    except ValueError:
        return False


# A real hash used to keep timing constant when the email does not exist
DUMMY_HASH = hash_password("dummy-Password-1")


def is_strong_password(password: str) -> bool:
    return bool(PASSWORD_RE.match(password))


def _encode(payload: dict, expires: timedelta) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    exp = now + expires
    payload = {**payload, "iat": now, "nbf": now, "exp": exp, "iss": settings.APP_NAME}
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, exp.replace(tzinfo=None)


def create_access_token(user_id: int, role: str, token_version: int) -> tuple[str, datetime]:
    return _encode(
        {"sub": str(user_id), "role": role, "ver": token_version, "type": ACCESS, "jti": uuid.uuid4().hex},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    jti = uuid.uuid4().hex
    token, exp = _encode(
        {"sub": str(user_id), "type": REFRESH, "jti": jti}, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    return token, jti, exp


def decode_token(token: str, expected_type: str) -> dict:
    """Raises jwt.PyJWTError on any problem (bad signature, expired, wrong type...)."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        issuer=settings.APP_NAME,
        options={"require": ["exp", "iat", "sub", "type", "jti"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


def generate_url_token() -> tuple[str, str]:
    """Returns (raw token for the link, sha256 digest to store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_url_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_temp_password() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(12))
        if is_strong_password(pwd):
            return pwd
