from datetime import date
from decimal import Decimal

from app.main import (
    health,
    months_until_target,
    next_month,
    next_occurrence_for_day,
    parse_optional_date,
    parse_optional_int,
    parse_planning_amount,
    parse_planning_target_date,
)
from app.security import hash_password, verify_password


def test_password_hash_argon2():
    password = "super-secure-password"
    hashed = hash_password(password)
    assert hashed.startswith("$argon2")
    assert verify_password(password, hashed)
    assert not verify_password("errada", hashed)


def test_next_month_rollover():
    assert next_month("2026-03") == "2026-04"
    assert next_month("2026-12") == "2027-01"


def test_health_endpoint():
    assert health() == {"status": "ok"}


def test_parse_optional_helpers():
    assert parse_optional_int(None) is None
    assert parse_optional_int("") is None
    assert parse_optional_int("12") == 12
    assert parse_optional_date(None) is None
    assert parse_optional_date("") is None
    assert str(parse_optional_date("2026-03-05")) == "2026-03-05"


def test_next_occurrence_for_day():
    assert next_occurrence_for_day(5, date(2026, 3, 1)) == date(2026, 3, 5)
    assert next_occurrence_for_day(5, date(2026, 3, 6)) == date(2026, 4, 5)
    assert next_occurrence_for_day(31, date(2026, 2, 27)) == date(2026, 2, 28)


def test_months_until_target():
    assert months_until_target(date(2026, 3, 5), date(2026, 3, 5)) == 1
    assert months_until_target(date(2026, 3, 5), date(2026, 12, 1)) == 10
    assert months_until_target(date(2026, 3, 5), date(2026, 2, 28)) == 0


def test_parse_planning_amount():
    assert parse_planning_amount("2800") == Decimal("2800")
    assert parse_planning_amount("2,800.50") == Decimal("2800.50")
    assert parse_planning_amount("2.800,50") == Decimal("2800.50")
    assert parse_planning_amount("2800,50") == Decimal("2800.50")


def test_parse_planning_target_date():
    assert str(parse_planning_target_date("2026-12-21")) == "2026-12-21"
    assert str(parse_planning_target_date("12/21/2026")) == "2026-12-21"
    assert str(parse_planning_target_date("21/12/2026")) == "2026-12-21"
