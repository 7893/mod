"""Coordination contracts for the HeatWave AutoML retraining pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.agy import train_and_evaluate_models as training


def _engine_with_lock_result(lock_result: int):
    conn = MagicMock()

    def execute(statement, params=None):
        result = MagicMock()
        result.scalar.return_value = lock_result if "GET_LOCK" in str(statement) else 1
        return result

    conn.execute.side_effect = execute
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    return engine, conn


def test_full_pipeline_holds_and_releases_retrain_lock(monkeypatch):
    engine, conn = _engine_with_lock_result(1)
    monkeypatch.setattr(training, "load_environment", MagicMock())
    monkeypatch.setattr(training, "get_engine", lambda: engine)
    monkeypatch.setattr(training, "ensure_metadata_tables", MagicMock())
    monkeypatch.setattr(training, "rebuild_feature_tables", MagicMock(return_value={}))
    monkeypatch.setattr(training, "check_feature_integrity", MagicMock())
    monkeypatch.setattr(training, "split_datasets", MagicMock(return_value={}))
    monkeypatch.setattr(training, "train_heatwave_models", MagicMock())
    monkeypatch.setattr(training, "evaluate_classifier", MagicMock(return_value={}))
    monkeypatch.setattr(training, "evaluate_regression", MagicMock(return_value={}))
    monkeypatch.setattr(training, "execute_full_batch_scoring", MagicMock())
    monkeypatch.setattr(training, "persist_metadata_and_audit", MagicMock())
    monkeypatch.setattr(training, "print_comparison_report", MagicMock())

    assert training.run_full_pipeline()["status"] == "success"
    statements = [str(call.args[0]) for call in conn.execute.call_args_list]
    assert any("GET_LOCK" in statement for statement in statements)
    assert any("RELEASE_LOCK" in statement for statement in statements)


def test_full_pipeline_rejects_overlapping_retrain(monkeypatch):
    engine, conn = _engine_with_lock_result(0)
    rebuild = MagicMock()
    monkeypatch.setattr(training, "load_environment", MagicMock())
    monkeypatch.setattr(training, "get_engine", lambda: engine)
    monkeypatch.setattr(training, "rebuild_feature_tables", rebuild)

    with pytest.raises(RuntimeError, match="already active"):
        training.run_full_pipeline()

    rebuild.assert_not_called()
    statements = [str(call.args[0]) for call in conn.execute.call_args_list]
    assert any("GET_LOCK" in statement for statement in statements)
    assert not any("RELEASE_LOCK" in statement for statement in statements)
