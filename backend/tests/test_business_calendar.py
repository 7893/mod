from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.business_calendar import OFFICIAL_SCHEDULES, SCHEDULES, day_type
from app.live_projection.simulation_engine import HongKongDiurnalEngine
from simulation.governance_state_machine import compute_rhythm_factor

CHINA_TZ = timezone(timedelta(hours=8))


@pytest.mark.parametrize(
    ("year", "holiday", "makeup_workday", "holiday_count", "makeup_count"),
    [
        (2022, date(2022, 2, 1), date(2022, 1, 29), 31, 7),
        (2023, date(2023, 1, 23), date(2023, 1, 28), 26, 7),
        (2024, date(2024, 2, 12), date(2024, 2, 18), 30, 8),
        (2025, date(2025, 1, 29), date(2025, 1, 26), 28, 5),
        (2026, date(2026, 2, 16), date(2026, 2, 14), 33, 6),
    ],
)
def test_official_schedules_cover_holidays_and_makeup_days(
    year: int,
    holiday: date,
    makeup_workday: date,
    holiday_count: int,
    makeup_count: int,
) -> None:
    schedule = OFFICIAL_SCHEDULES[year]
    assert len(schedule.holidays) == holiday_count
    assert len(schedule.makeup_workdays) == makeup_count
    assert day_type(holiday) == "holiday"
    assert day_type(makeup_workday) == "makeup_workday"
    assert not schedule.provisional


def test_2026_schedule_matches_state_council_notice() -> None:
    expected_makeup_days = {
        date(2026, 1, 4),
        date(2026, 2, 14),
        date(2026, 2, 28),
        date(2026, 5, 9),
        date(2026, 9, 20),
        date(2026, 10, 10),
    }
    assert OFFICIAL_SCHEDULES[2026].makeup_workdays == expected_makeup_days
    assert day_type(date(2026, 1, 1)) == "holiday"
    assert day_type(date(2026, 2, 23)) == "holiday"
    assert day_type(date(2026, 10, 7)) == "holiday"


@pytest.mark.parametrize("year", range(2027, 2031))
def test_future_years_repeat_2026_month_day_template(year: int) -> None:
    schedule = SCHEDULES[year]
    assert schedule.provisional_template_year == 2026
    assert {(value.month, value.day) for value in schedule.holidays} == {
        (value.month, value.day) for value in OFFICIAL_SCHEDULES[2026].holidays
    }
    assert {(value.month, value.day) for value in schedule.makeup_workdays} == {
        (value.month, value.day) for value in OFFICIAL_SCHEDULES[2026].makeup_workdays
    }


def test_unknown_year_falls_back_to_normal_week_pattern() -> None:
    assert day_type(date(2031, 1, 6)) == "workday"
    assert day_type(date(2031, 1, 5)) == "weekend"


def test_diurnal_engine_damps_holiday_and_restores_makeup_workday() -> None:
    holiday = datetime(2026, 2, 16, 10, tzinfo=CHINA_TZ)
    makeup_workday = datetime(2026, 2, 14, 10, tzinfo=CHINA_TZ)
    normal_weekend = datetime(2026, 2, 7, 10, tzinfo=CHINA_TZ)

    assert HongKongDiurnalEngine.get_intensity(makeup_workday) > HongKongDiurnalEngine.get_intensity(holiday)
    assert HongKongDiurnalEngine.get_intensity(makeup_workday) > HongKongDiurnalEngine.get_intensity(normal_weekend)


def test_governance_rhythm_uses_same_calendar_overrides() -> None:
    holiday = datetime(2026, 2, 16, 10, tzinfo=CHINA_TZ)
    makeup_workday = datetime(2026, 2, 14, 10, tzinfo=CHINA_TZ)

    assert compute_rhythm_factor(holiday) == pytest.approx(0.18)
    assert compute_rhythm_factor(makeup_workday) == pytest.approx(1.8)
