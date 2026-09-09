"""Contract tests for the single source of org-status vocabulary and thresholds."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import business_rules as br

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_LITERAL = re.compile(r"""['"](未启动|准备中|已具备双轨条件|双轨运行中|已上线|稳定运行)['"]""")
# 直接拼 SQL 的模块必须引用 business_rules，而不是散写状态字面量。
SQL_MODULES = (
    "backend/app/services/dashboard.py",
    "backend/app/services/dashboard_sections.py",
    "backend/app/integrations/heatwave_sql.py",
    "simulation/engine_context.py",
)


def test_lifecycle_stages_are_ordered_and_unique():
    assert len(set(br.ORG_LIFECYCLE_STAGES)) == len(br.ORG_LIFECYCLE_STAGES) == 6
    assert br.ORG_LIFECYCLE_STAGES[0] == br.ORG_STATUS_NOT_STARTED
    assert br.ORG_LIFECYCLE_STAGES[-1] == br.ORG_STATUS_STABLE
    assert set(br.BATCH_LIFECYCLE_STAGES) == set(br.ORG_LIFECYCLE_STAGES) - {br.ORG_STATUS_DUAL_READY}


def test_status_groups_are_subsets_of_lifecycle():
    stages = set(br.ORG_LIFECYCLE_STAGES)
    assert set(br.LAUNCHED_STATUSES) <= stages
    assert set(br.DISPLAY_STATUS_MAPPING) <= stages


def test_display_mapping_covers_every_db_status_into_five_public_states():
    public = {br.DISPLAY_STATUS_MAPPING.get(s, s) for s in br.ORG_LIFECYCLE_STAGES}
    # 数据库六态折叠为前端可见三态；「未启动」仅由蓄水池(batch 8)分支直接产出。
    assert public == {"准备中", "双轨运行", "已上线"}
    assert public <= {"未启动", "准备中", "建设中", "双轨运行", "已上线"}


def test_sql_helpers_render_in_lists():
    assert br.sql_status_list(("a", "b")) == "('a', 'b')"
    assert br.SQL_LAUNCHED_STATUSES == "('已上线', '稳定运行')"
    assert "'双轨运行中' THEN 6" in br.SQL_INFERRED_BATCH_ID
    assert "{" not in br.SQL_INFERRED_BATCH_ID


def test_public_business_rules_exposes_status_vocabulary():
    rules = br.public_business_rules()
    assert rules["lifecycle"]["orgStages"] == list(br.ORG_LIFECYCLE_STAGES)
    assert rules["lifecycle"]["launchedStatuses"] == list(br.LAUNCHED_STATUSES)
    assert rules["lifecycle"]["dualRunConsistencyRateMin"] == br.DUAL_RUN_CONSISTENCY_RATE_MIN


@pytest.mark.parametrize("rel_path", SQL_MODULES)
def test_sql_modules_do_not_hardcode_status_literals(rel_path: str):
    source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    hits = STATUS_LITERAL.findall(source)
    assert not hits, f"{rel_path} hardcodes org status literals {sorted(set(hits))}; use app.business_rules"
