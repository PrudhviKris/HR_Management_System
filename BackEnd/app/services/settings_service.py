from datetime import time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import RequestContext
from app.exceptions import ValidationError
from app.models import SystemSetting
from app.services import audit_service

# key -> (default, type, description)
DEFAULTS: dict[str, tuple[str, type, str]] = {
    "company_name": ("Acme Technologies Pvt. Ltd.", str, "Company name shown on payslips and emails"),
    "company_address": ("4th Floor, Tech Park, Hitec City, Hyderabad 500081", str, "Address printed on payslips"),
    "office_start_time": ("09:30", time, "Expected check-in time (HH:MM)"),
    "late_grace_minutes": ("15", int, "Minutes after start time before a check-in is marked late"),
    "full_day_hours": ("8", Decimal, "Minimum worked hours for a full day"),
    "half_day_hours": ("4", Decimal, "Minimum worked hours for a half day"),
    "pf_rate_percent": ("12", Decimal, "Employee provident fund contribution, % of earned basic"),
    "professional_tax_amount": ("200", Decimal, "Monthly professional tax"),
    "professional_tax_threshold": ("15000", Decimal, "Professional tax applies when earned gross exceeds this"),
}


def _parse(key: str, raw: str):
    _, typ, _ = DEFAULTS[key]
    try:
        if typ is time:
            hh, mm = raw.split(":")
            return time(int(hh), int(mm))
        if typ is int:
            return int(raw)
        if typ is Decimal:
            return Decimal(raw)
        return raw
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"Invalid value for {key}: {raw!r}") from exc


def get_all_raw(db: Session) -> dict[str, str]:
    stored = {s.key: s.value for s in db.scalars(select(SystemSetting))}
    return {k: stored.get(k, d[0]) for k, d in DEFAULTS.items()}


def get(db: Session, key: str):
    row = db.get(SystemSetting, key)
    return _parse(key, row.value if row else DEFAULTS[key][0])


def get_many(db: Session) -> dict:
    return {k: _parse(k, v) for k, v in get_all_raw(db).items()}


def describe(db: Session) -> list[dict]:
    raw = get_all_raw(db)
    return [
        {"key": k, "value": raw[k], "type": d[1].__name__, "description": d[2]} for k, d in DEFAULTS.items()
    ]


def update(db: Session, ctx: RequestContext, values: dict[str, str]) -> list[dict]:
    before = get_all_raw(db)
    for key, value in values.items():
        if key not in DEFAULTS:
            raise ValidationError(f"Unknown setting: {key}")
        value = str(value).strip()
        parsed = _parse(key, value)
        if isinstance(parsed, (int, Decimal)) and parsed < 0:
            raise ValidationError(f"{key} cannot be negative")
        row = db.get(SystemSetting, key)
        if row:
            row.value = value
        else:
            db.add(SystemSetting(key=key, value=value, description=DEFAULTS[key][2]))
    db.flush()
    after = get_all_raw(db)
    full, half = Decimal(after["full_day_hours"]), Decimal(after["half_day_hours"])
    if not (0 < half <= full <= 24):
        raise ValidationError("Require 0 < half_day_hours <= full_day_hours <= 24")
    audit_service.record(
        db, ctx, "settings.update", "Updated system settings", entity_type="settings",
        changes=audit_service.diff(before, after),
    )
    db.commit()
    return describe(db)
