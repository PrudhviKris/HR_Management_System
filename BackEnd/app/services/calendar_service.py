"""Working-day calendar shared by attendance, leave and payroll (weekends + mandatory holidays off)."""

from datetime import date

from sqlalchemy.orm import Session

from app.core.timeutils import daterange, is_weekend
from app.services.organization_service import holiday_dates


class WorkCalendar:
    def __init__(self, db: Session, start: date, end: date):
        self.start, self.end = start, end
        self.holidays = holiday_dates(db, start, end) if start <= end else set()

    def is_working_day(self, d: date) -> bool:
        return not is_weekend(d) and d not in self.holidays

    def working_days(self, start: date | None = None, end: date | None = None) -> list[date]:
        s, e = max(start or self.start, self.start), min(end or self.end, self.end)
        return [d for d in daterange(s, e) if self.is_working_day(d)] if s <= e else []


def count_working_days(db: Session, start: date, end: date) -> int:
    return len(WorkCalendar(db, start, end).working_days())
