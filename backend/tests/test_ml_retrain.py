"""
backend/tests/test_ml_retrain.py
================================
Unit tests for KI-015 / KI-023 HeatWave AutoML Real Training, Verification,
Presentation layer truthfulness, and Retrain Pipeline integrity.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.integrations.heatwave_ml import HeatWaveMLAdapter  # noqa: E402
from app.integrations.heatwave_sql import (  # noqa: E402
    MODEL_CLASSIFIER,
    MODEL_REGRESSION,
)
from scripts.agy.train_and_evaluate_models import check_feature_integrity  # noqa: E402


def test_heatwave_adapter_unverified_model_fails_gracefully():
    """Unverified models without test set metrics must NOT report ready or false quality scores."""
    conn = MagicMock()
    # Mock _safe_query to return empty list (no row in ml_model_metadata)
    adapter = HeatWaveMLAdapter(conn)
    adapter._safe_query = MagicMock(return_value=[])

    # Case 1: Catalog returns model without verified=True
    meta_without_verified = json.dumps({
        "status": "Ready",
        "training_score": 1.0,
        "model_quality": 1.0,
    })
    mock_row = {
        "model_id": 1,
        "model_handle": MODEL_CLASSIFIER,
        "model_type": "DecisionTreeClassifier",
        "task": "classification",
        "model_metadata": meta_without_verified,
        "build_timestamp": 1788545764,
        "target_column_name": "risk_flag",
    }
    conn.execute.return_value.mappings.return_value.first.return_value = mock_row

    status = adapter.get_model_status(MODEL_CLASSIFIER)
    assert status["verified"] is False
    assert status["quality"] is None
    assert status["status"] == "not_evaluated"


def test_heatwave_adapter_verified_model_presents_real_test_score():
    """Verified models in ml_model_metadata must present the test set score, not self-score."""
    conn = MagicMock()
    adapter = HeatWaveMLAdapter(conn)

    verified_metadata_row = {
        "model_handle": MODEL_REGRESSION,
        "model_name": "业务单据日增量预测模型",
        "task_type": "regression",
        "target_column": "daily_doc_delta",
        "algorithm": "LinearRegression",
        "split_method": "temporal_80_20",
        "train_rows": 1600,
        "test_rows": 400,
        "train_score": 0.1630,
        "test_score": -0.0135,
        "train_metrics": json.dumps({"r2": 0.1630, "mae": 2.1384}),
        "test_metrics": json.dumps({"r2": -0.0135, "mae": 2.6367}),
        "verified": 1,
        "status": "ready",
        "trained_at": "2026-09-05 22:33:42",
        "verified_at": "2026-09-05 22:33:42",
    }
    adapter._safe_query = MagicMock(return_value=[verified_metadata_row])

    status = adapter.get_model_status(MODEL_REGRESSION)
    assert status["verified"] is True
    assert status["status"] == "ready"
    assert status["quality"] == -0.0135
    assert status["train_score"] == 0.1630
    assert status["test_score"] == -0.0135
    assert status["split_method"] == "temporal_80_20"


def test_heatwave_adapter_get_status_verified_flag():
    """get_status reports verified=True only when BOTH models are independently verified."""
    conn = MagicMock()
    adapter = HeatWaveMLAdapter(conn)

    # Mock get_model_status
    def mock_get_model_status(name: str):
        if name == MODEL_REGRESSION:
            return {"model": name, "status": "ready", "verified": True, "quality": -0.0135}
        return {"model": name, "status": "ready", "verified": True, "quality": 1.0}

    adapter.get_model_status = MagicMock(side_effect=mock_get_model_status)
    status = adapter.get_status()
    assert status["status"] == "ready"
    assert status["verified"] is True

    # If one model is unverified
    def mock_get_model_status_partial(name: str):
        if name == MODEL_REGRESSION:
            return {"model": name, "status": "ready", "verified": True, "quality": -0.0135}
        return {"model": name, "status": "not_evaluated", "verified": False, "quality": None}

    adapter.get_model_status = MagicMock(side_effect=mock_get_model_status_partial)
    status = adapter.get_status()
    assert status["verified"] is False


def test_heatwave_adapter_get_predictions_parses_posterior_probability():
    """Predictions should parse real probabilities from ml_results instead of static values."""
    conn = MagicMock()
    adapter = HeatWaveMLAdapter(conn)
    adapter._table_exists = MagicMock(side_effect=lambda t: t == "ml_score_risk")

    fake_row = {
        "org_id": 42,
        "org_name": "测试单位",
        "pred_value": 1,
        "prediction_json": json.dumps({
            "predictions": {"risk_flag": 1},
            "probabilities": {"0": 0.05, "1": 0.95},
        }),
        "region": "北京市",
        "batch_id": 1,
        "construction_pct": 88.5,
        "unresolved_issues": 3,
        "high_risk_issues": 1,
        "actual_flag": 1,
    }
    conn.execute.return_value.mappings.return_value.all.return_value = [fake_row]

    preds = adapter.get_predictions()
    assert len(preds) == 1
    assert preds[0]["riskFlag"] == 1
    assert preds[0]["riskScore"] == 0.95


def test_feature_integrity_blocks_time_series_leakage():
    """Risk model features must not include daily transaction or volume counters."""
    conn = MagicMock()
    mock_res_risk = MagicMock()
    mock_res_risk.fetchall.return_value = [("id",), ("org_id",), ("construction_pct",), ("doc_count_prev30",), ("risk_flag",)]
    mock_res_doc = MagicMock()
    mock_res_doc.fetchall.return_value = [("id",), ("org_id",), ("daily_doc_delta",)]
    conn.execute.side_effect = [mock_res_risk, mock_res_doc]

    try:
        check_feature_integrity(conn)
        assert False, "Expected ValueError due to time series leakage in risk features"
    except ValueError as exc:
        assert "Leakage detected in risk model features" in str(exc)
