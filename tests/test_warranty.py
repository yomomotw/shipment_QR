from datetime import date

from app.services.warranty import in_warranty, warranty_end


def test_twelve_months():
    assert warranty_end(date(2026, 11, 16), 12) == date(2027, 11, 16)


def test_month_end_clamps():
    assert warranty_end(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_leap_day():
    assert warranty_end(date(2028, 2, 29), 12) == date(2029, 2, 28)


def test_expiry_day_is_in_warranty():
    assert in_warranty(date(2027, 11, 16), today=date(2027, 11, 16))


def test_day_after_expiry_is_out():
    assert not in_warranty(date(2027, 11, 16), today=date(2027, 11, 17))
