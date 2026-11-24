import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy.orm import Session

from app.core.deps import RequestContext
from app.models import AuditLog


def _jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Enum):
        return v.value
    return v


def diff(before: dict, after: dict) -> dict:
    """{field: {"from": x, "to": y}} for changed fields only."""
    out = {}
    for k in sorted(set(before) | set(after)):
        b, a = _jsonable(before.get(k)), _jsonable(after.get(k))
        if b != a:
            out[k] = {"from": b, "to": a}
    return out


SENSITIVE = {"bank_account_number", "pan_number"}


def _mask(v):
    s = str(v)
    return "*" * max(0, len(s) - 4) + s[-4:]


def snapshot(obj, fields: list[str]) -> dict:
    """Field values for audit diffs; identifiers like bank account / PAN are masked."""
    out = {}
    for f in fields:
        v = _jsonable(getattr(obj, f, None))
        out[f] = _mask(v) if f in SENSITIVE and v else v
    return out


def record(
    db: Session,
    ctx: RequestContext | None,
    action: str,
    description: str,
    *,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    changes: dict | None = None,
    actor_email: str | None = None,
) -> AuditLog:
    """Adds an audit row to the current transaction (committed together with the change itself)."""
    if changes is not None:
        changes = json.loads(json.dumps(changes, default=_jsonable))
    entry = AuditLog(
        actor_id=ctx.user_id if ctx else None,
        actor_email=(ctx.user.email if ctx and ctx.user else actor_email),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        description=description[:500],
        changes=changes or None,
        ip_address=ctx.ip if ctx else None,
        user_agent=ctx.user_agent if ctx else None,
    )
    db.add(entry)
    return entry
