import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings

TZ = ZoneInfo(settings.APP_TIMEZONE)


def now_local() -> datetime:
    """Current wall-clock time in the company time zone (naive, stored as-is)."""
    return datetime.now(TZ).replace(tzinfo=None, microsecond=0)


def today_local() -> date:
    return now_local().date()


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Saturday / Sunday
