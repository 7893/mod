"""KI-052 附带：工作时间节律回归测试。

验证 ExpensePlaybook._sample_worktime：
- 提交时刻主要落在核心工作时段（8-17 点为主）
- 分钟不集中在整点（非机械打卡）
- 月末加班（18 点后）概率显著高于普通工作日（财务周期性）
"""
from __future__ import annotations

from datetime import datetime

from simulation.expense_playbook import ExpensePlaybook
from simulation.engine_context import IdAllocator, SimulationBaseline


def _make_pb():
    baseline = SimulationBaseline(
        latest_business_date=datetime(2024, 3, 1),
        online_org_ids=[1],
        org_users={1: [{"name": "张三", "role": "经办人"}]},
        next_ids={
            "business_document": 1, "business_document_line": 1,
            "accounting_voucher": 1, "accounting_voucher_line": 1,
            "integration_result": 1,
        },
    )
    return ExpensePlaybook(baseline, IdAllocator(baseline.next_ids), seed=42)


def _sample_hours(pb, day, n=2000):
    hours, minutes = [], []
    for _ in range(n):
        t = pb._sample_worktime(datetime(day.year, day.month, day.day))
        hours.append(t.hour)
        minutes.append(t.minute)
    return hours, minutes


def test_core_worktime_dominates():
    pb = _make_pb()
    hours, _ = _sample_hours(pb, datetime(2024, 3, 13))  # 普通工作日(周三)
    core = sum(1 for h in hours if 8 <= h <= 17)
    assert core / len(hours) > 0.8, "核心工作时段应占绝大多数"


def test_minutes_not_clustered_on_zero():
    pb = _make_pb()
    _, minutes = _sample_hours(pb, datetime(2024, 3, 13))
    zero_ratio = minutes.count(0) / len(minutes)
    assert zero_ratio < 0.05, "分钟不应集中在整点(非机械打卡)"


def test_month_end_overtime_higher():
    pb = _make_pb()
    normal_hours, _ = _sample_hours(pb, datetime(2024, 3, 13))   # 普通日
    monthend_hours, _ = _sample_hours(pb, datetime(2024, 3, 29))  # 月末
    ot_normal = sum(1 for h in normal_hours if h >= 18) / len(normal_hours)
    ot_monthend = sum(1 for h in monthend_hours if h >= 18) / len(monthend_hours)
    assert ot_monthend > ot_normal, "月末加班概率应高于普通工作日(财务周期性)"
