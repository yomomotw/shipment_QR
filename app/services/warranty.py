"""Warranty dates (FR-04). Expiry day itself counts as in warranty (docs/08 Q-02, provisional)."""
import calendar
from datetime import date


def add_months(d: date, months: int) -> date:
    idx = d.year * 12 + (d.month - 1) + months
    year, month = divmod(idx, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def warranty_end(start: date, months: int) -> date:
    return add_months(start, months)


def in_warranty(end: date, today: date | None = None) -> bool:
    return (today or date.today()) <= end
