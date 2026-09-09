"""
backend/tests/test_heatwave_causality_and_shap.py
=================================================
Regression test suite for KI-034 Phase 1:
- Causal dynamics in simulator (initial data diff penalty in dual-run stage)
- Momentum features in HeatWave feature tables
- HeatWave native SHAP explainability (sys.ML_EXPLAIN_ROW) & deterministic fallback
- FastAPI /api/insights/risk-explanation/{org_id} endpoint contract
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db import connection  # noqa: E402
from app.integrations.heatwave_ml import HeatWaveMLAdapter  # noqa: E402
from app.integrations.heatwave_sql import (  # noqa: E402
    _DDL_FEAT_CLASSIFIER,
    _DDL_FEAT_REGRESSION,
)
from app.main import app  # noqa: E402
from simulation.engine_context import ConstructionBaseline  # noqa: E402
from simulation.lifecycle_advancer import (  # noqa: E402
    LifecycleAdvancer,
    LifecycleThresholds,
    OrgMetricsSnapshot,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_lifecycle_advancer_causal_diff_penalty():
    """If unit has opening diff amount > 0, dual-run requirement must increase by 7 days."""
    baseline = ConstructionBaseline(
        latest_business_date=datetime(2026, 9, 5, 18, 0, 0),
        orgs={
            20: {
                "id": 20,
                "name": "测试单位B",
                "batch_id": 1,
                "status": "双轨运行中",
                "start_date": date(2026, 8, 1),
                "end_date": date(2026, 12, 1),
            }
        },
        orgs_by_status={"双轨运行中": [20]},
        org_users={20: [{"name": "李四", "role": "经办人"}]},
        next_ids={"construction_task": 100, "training": 100, "dual_run_result": 100},
        batches={1: {"id": 1, "name": "第一批", "start_date": date(2026, 7, 1), "end_date": date(2026, 12, 31), "status": "双轨运行中"}},
    )
    thresholds = LifecycleThresholds(
        dual_run_days_min=14,
        dual_run_min_checks=5,
        dual_run_consistency_rate_min=98.0,
        dual_run_consecutive_days_min=1,
    )
    cur_date = date(2026, 9, 5)

    # Unit with 16 days in dual-run:
    # 16 >= 14, so clean unit is qualified to advance
    clean_metrics = OrgMetricsSnapshot(
        org_id=20,
        current_status="双轨运行中",
        batch_id=1,
        stage_entered_date=date(2026, 8, 20),  # 16 days
        dual_run_checks_total=10,
        dual_run_consistency_rate=99.5,
        dual_run_recent_matches=5,
        has_blocking_risk=False,
        opening_diff_amount=Decimal("0.00"),
    )
    advancer_clean = LifecycleAdvancer(baseline, thresholds=thresholds, seed=42)
    is_qual_clean, _, reasons_clean = advancer_clean.evaluate_qualification(clean_metrics, cur_date)
    assert is_qual_clean
    assert any("具备上线条件" in r for r in reasons_clean)

    # Flawed unit with opening diff amount > 0:
    # Requires 14 + 7 = 21 days, so 16 days must be rejected with penalty notice
    flawed_metrics = OrgMetricsSnapshot(
        org_id=20,
        current_status="双轨运行中",
        batch_id=1,
        stage_entered_date=date(2026, 8, 20),  # 16 days
        dual_run_checks_total=10,
        dual_run_consistency_rate=99.5,
        dual_run_recent_matches=5,
        has_blocking_risk=False,
        opening_diff_amount=Decimal("5000.00"),
    )
    advancer_flawed = LifecycleAdvancer(baseline, thresholds=thresholds, seed=42)
    is_qual_flawed, _, reasons_flawed = advancer_flawed.evaluate_qualification(flawed_metrics, cur_date)
    assert not is_qual_flawed
    assert any("含期初数据质量差异考核惩罚+7天" in r for r in reasons_flawed)
    assert any("21天" in r for r in reasons_flawed)


def test_heatwave_sql_momentum_features_contract():
    """Ensure the 4 momentum features exist in DDL definitions without leakage."""
    # 1. Check risk training table DDL
    assert "progress_slope_14d" in _DDL_FEAT_CLASSIFIER
    assert "stagnant_days" in _DDL_FEAT_CLASSIFIER
    assert "training_error_scissors" in _DDL_FEAT_CLASSIFIER
    assert "handler_concentration" in _DDL_FEAT_CLASSIFIER
    assert "risk_flag" in _DDL_FEAT_CLASSIFIER

    # Verify absence of target leakage in risk features
    assert "doc_count_prev30" not in _DDL_FEAT_CLASSIFIER
    assert "daily_doc_delta" not in _DDL_FEAT_CLASSIFIER

    # 2. Check doc volume training table DDL
    assert "avg_daily_doc_prev7" in _DDL_FEAT_REGRESSION
    assert "handler_count" in _DDL_FEAT_REGRESSION
    assert "handler_concentration" in _DDL_FEAT_REGRESSION
    assert "daily_doc_delta" in _DDL_FEAT_REGRESSION


def test_heatwave_ml_shap_explain_risk_native():
    """Verify sys.ML_EXPLAIN_ROW output parsing and Top 3 weight normalization."""
    conn = MagicMock()
    adapter = HeatWaveMLAdapter(conn)

    # Mock org info query via _safe_query
    mock_org_row = {
        "org_id": 88,
        "org_name": "天府创新示范基地",
        "region": "四川省",
        "batch_id": 3,
        "status": "建设中",
        "construction_pct": 72.0,
        "unresolved_issues": 8,
        "high_risk_issues": 3,
        "progress_slope_14d": 0.2,
        "stagnant_days": 18,
        "training_error_scissors": 24.5,
        "handler_concentration": 0.85,
    }
    adapter._safe_query = MagicMock(return_value=[mock_org_row])

    # Mock sys.ML_EXPLAIN_ROW returning native SHAP attributions via scalar
    shap_results = {
        "ml_results": {
            "attributions": {
                "stagnant_days_attribution": 0.45,
                "high_risk_issues_attribution": 0.30,
                "training_error_scissors_attribution": 0.15,
                "unresolved_issues_attribution": 0.05,
                "handler_concentration_attribution": 0.05,
            }
        }
    }
    conn.execute.return_value.scalar.return_value = json.dumps(shap_results)

    res = adapter.explain_risk(88)
    assert res["status"] == "ok"
    assert res["explanationSource"] == "HEATWAVE_SHAP"
    assert res["orgId"] == 88
    assert res["orgName"] == "天府创新示范基地"
    assert len(res["topAttributions"]) == 3

    top1 = res["topAttributions"][0]
    top2 = res["topAttributions"][1]
    top3 = res["topAttributions"][2]

    assert top1["factor"] == "stagnant_days"
    assert top1["factorName"] == "工期停滞过久"
    assert top2["factor"] == "high_risk_issues"
    assert top2["factorName"] == "高危风险阻断"
    assert top3["factor"] == "training_error_scissors"
    assert top3["factorName"] == "培训与上线报错剪刀差"

    # Total of Top 3 normalized weights should be 100% (45/90=50%, 30/90=33%, 15/90=17%)
    total_pct = top1["weightPct"] + top2["weightPct"] + top3["weightPct"]
    assert total_pct == 100


def test_heatwave_ml_shap_explain_risk_fallback_on_db_error():
    """If HeatWave native SHAP call fails, it must fallback to deterministic business rules gracefully."""
    conn = MagicMock()
    adapter = HeatWaveMLAdapter(conn)

    mock_org_row = {
        "org_id": 99,
        "org_name": "滨海储备研发中心",
        "region": "山东省",
        "batch_id": 8,
        "status": "准备中",
        "construction_pct": 50.0,
        "unresolved_issues": 10,
        "high_risk_issues": 2,
        "progress_slope_14d": 0.1,
        "stagnant_days": 25,
        "training_error_scissors": 18.0,
        "handler_concentration": 0.70,
    }
    adapter._safe_query = MagicMock(return_value=[mock_org_row])
    conn.execute.side_effect = Exception("HeatWave sys.ML_EXPLAIN_ROW unavailable in test mock")

    res = adapter.explain_risk(99)
    assert res["status"] == "ok"
    assert res["explanationSource"] == "RULE_BASED"
    assert res["orgId"] == 99
    assert len(res["topAttributions"]) == 3
    assert sum(a["weightPct"] for a in res["topAttributions"]) == 100
    valid_factors = {
        "unresolved_issues", "high_risk_issues", "stagnant_days",
        "progress_slope_14d", "training_error_scissors",
        "handler_concentration", "construction_pct", "integration_success_pct"
    }
    for a in res["topAttributions"]:
        assert a["factor"] in valid_factors
        assert a["weightPct"] > 0


def test_insights_risk_explanation_api_endpoint(client):
    """GET /api/insights/risk-explanation/{org_id} should return valid explanation structure."""
    # 1. Disconnected state returns graceful unavailable response
    response = client.get("/api/insights/risk-explanation/1")
    assert response.status_code == 200
    data = response.json()
    assert data["orgId"] == 1
    assert data["status"] in ("unavailable", "ok")
    assert data["explanationSource"] in ("UNAVAILABLE", "RULE_BASED", "HEATWAVE_SHAP")

    # 2. When mock connection is injected
    mock_conn = MagicMock()
    app.dependency_overrides[connection] = lambda: mock_conn
    try:
        mock_org_row = {
            "org_id": 1,
            "org_name": "总部机关",
            "region": "北京",
            "batch_id": 1,
            "construction_pct": 92.0,
            "unresolved_issues": 2,
            "high_risk_issues": 0,
            "progress_slope_14d": 0.5,
            "stagnant_days": 1,
            "training_error_scissors": 5.0,
            "handler_concentration": 0.55,
        }
        mock_conn.execute.return_value.mappings.return_value.all.return_value = [mock_org_row]
        mock_conn.execute.return_value.scalar.return_value = None  # fallback rule

        resp = client.get("/api/insights/risk-explanation/1")
        assert resp.status_code == 200
        d = resp.json()
        assert d["orgId"] == 1
        assert d["orgName"] == "总部机关"
        assert d["status"] == "ok"
        assert d["explanationSource"] == "RULE_BASED"
        assert len(d["topAttributions"]) >= 1
    finally:
        app.dependency_overrides.clear()
