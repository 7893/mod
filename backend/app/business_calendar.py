"""Mainland China work calendar used by simulator activity rhythms.

The 2022-2026 schedules are transcribed from State Council notices. 2027-2030
are deliberately provisional: they repeat the 2026 month/day flags until the
project owner replaces them with each year's official notice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Mapping

DayType = Literal["workday", "makeup_workday", "weekend", "holiday"]


@dataclass(frozen=True)
class YearSchedule:
    holidays: frozenset[date]
    makeup_workdays: frozenset[date]
    source_url: str
    provisional_template_year: int | None = None

    def __post_init__(self) -> None:
        overlap = self.holidays & self.makeup_workdays
        if overlap:
            raise ValueError(f"calendar dates cannot be both holiday and workday: {sorted(overlap)}")

    @property
    def provisional(self) -> bool:
        return self.provisional_template_year is not None


def _date(year: int, value: str) -> date:
    month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def _ranges(year: int, *ranges: tuple[str, str]) -> frozenset[date]:
    values: set[date] = set()
    for start_text, end_text in ranges:
        current = _date(year, start_text)
        end = _date(year, end_text)
        while current <= end:
            values.add(current)
            current += timedelta(days=1)
    return frozenset(values)


def _listed(year: int, *values: str) -> frozenset[date]:
    return frozenset(_date(year, value) for value in values)


# Official notices:
# 2022: https://app.www.gov.cn/govdata/gov/202110/25/477428/article.html
# 2023: https://app.www.gov.cn/govdata/gov/202212/08/495070/article.html
# 2024: https://www.gov.cn/zhengce/content/202310/content_6911527.htm
# 2025: https://big5.www.gov.cn/gate/big5/www.gov.cn/zhengce/zhengceku/202411/content_6986383.htm
# 2026: https://big5.www.gov.cn/gate/big5/www.gov.cn/gongbao/2025/issue_12406/202511/content_7048922.html
OFFICIAL_SCHEDULES: dict[int, YearSchedule] = {
    2022: YearSchedule(
        holidays=_ranges(
            2022,
            ("01-01", "01-03"),
            ("01-31", "02-06"),
            ("04-03", "04-05"),
            ("04-30", "05-04"),
            ("06-03", "06-05"),
            ("09-10", "09-12"),
            ("10-01", "10-07"),
        ),
        makeup_workdays=_listed(2022, "01-29", "01-30", "04-02", "04-24", "05-07", "10-08", "10-09"),
        source_url="https://app.www.gov.cn/govdata/gov/202110/25/477428/article.html",
    ),
    2023: YearSchedule(
        holidays=_ranges(
            2023,
            ("01-01", "01-02"),
            ("01-21", "01-27"),
            ("04-05", "04-05"),
            ("04-29", "05-03"),
            ("06-22", "06-24"),
            ("09-29", "10-06"),
        ),
        makeup_workdays=_listed(2023, "01-28", "01-29", "04-23", "05-06", "06-25", "10-07", "10-08"),
        source_url="https://app.www.gov.cn/govdata/gov/202212/08/495070/article.html",
    ),
    2024: YearSchedule(
        holidays=_ranges(
            2024,
            ("01-01", "01-01"),
            ("02-10", "02-17"),
            ("04-04", "04-06"),
            ("05-01", "05-05"),
            ("06-08", "06-10"),
            ("09-15", "09-17"),
            ("10-01", "10-07"),
        ),
        makeup_workdays=_listed(2024, "02-04", "02-18", "04-07", "04-28", "05-11", "09-14", "09-29", "10-12"),
        source_url="https://www.gov.cn/zhengce/content/202310/content_6911527.htm",
    ),
    2025: YearSchedule(
        holidays=_ranges(
            2025,
            ("01-01", "01-01"),
            ("01-28", "02-04"),
            ("04-04", "04-06"),
            ("05-01", "05-05"),
            ("05-31", "06-02"),
            ("10-01", "10-08"),
        ),
        makeup_workdays=_listed(2025, "01-26", "02-08", "04-27", "09-28", "10-11"),
        source_url="https://big5.www.gov.cn/gate/big5/www.gov.cn/zhengce/zhengceku/202411/content_6986383.htm",
    ),
    2026: YearSchedule(
        holidays=_ranges(
            2026,
            ("01-01", "01-03"),
            ("02-15", "02-23"),
            ("04-04", "04-06"),
            ("05-01", "05-05"),
            ("06-19", "06-21"),
            ("09-25", "09-27"),
            ("10-01", "10-07"),
        ),
        makeup_workdays=_listed(2026, "01-04", "02-14", "02-28", "05-09", "09-20", "10-10"),
        source_url="https://big5.www.gov.cn/gate/big5/www.gov.cn/gongbao/2025/issue_12406/202511/content_7048922.html",
    ),
}


def _copy_month_days(schedule: YearSchedule, year: int, template_year: int) -> YearSchedule:
    return YearSchedule(
        holidays=frozenset(date(year, value.month, value.day) for value in schedule.holidays),
        makeup_workdays=frozenset(date(year, value.month, value.day) for value in schedule.makeup_workdays),
        source_url=schedule.source_url,
        provisional_template_year=template_year,
    )


SCHEDULES = dict(OFFICIAL_SCHEDULES)
SCHEDULES.update({year: _copy_month_days(OFFICIAL_SCHEDULES[2026], year, 2026) for year in range(2027, 2031)})


def day_type(value: date) -> DayType:
    """Classify a local calendar date; unknown years fall back to weekdays."""
    schedule = SCHEDULES.get(value.year)
    if schedule is not None:
        if value in schedule.makeup_workdays:
            return "makeup_workday"
        if value in schedule.holidays:
            return "holiday"
    return "weekend" if value.weekday() >= 5 else "workday"


def activity_day_weight(
    value: date,
    weekday_weights: Mapping[int, float],
    *,
    holiday_weight: float,
    makeup_workday_weight: float = 1.0,
) -> float:
    """Return an activity multiplier with official overrides taking precedence."""
    kind = day_type(value)
    if kind == "holiday":
        return holiday_weight
    if kind == "makeup_workday":
        return makeup_workday_weight
    return weekday_weights.get(value.weekday(), 1.0)
