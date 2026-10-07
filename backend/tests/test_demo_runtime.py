"""Demo mode cannot inherit source connections, writes, or external AI opt-ins."""
from unittest.mock import MagicMock
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url
from app.config import get_settings
from app.db import _on_connect
from app.integrations.cloudflare_ai import CloudflareAIAdapter
from app.integrations.heatwave_ml import HeatWaveMLAdapter
from simulation.cf_ai_client import CloudflareAIClient
from simulation.construction_writer import is_construction_writer_enabled
from simulation.simulation_writer import is_simulation_engine_enabled


def test_demo_requires_explicit_database(monkeypatch):
    monkeypatch.setenv('MOD_DEMO_MODE', 'true')
    monkeypatch.setenv('MOD_DB_HOST', 'source.example.test')
    monkeypatch.delenv('MOD_DEMO_DATABASE_URL', raising=False)
    with pytest.raises(ValueError, match='required'):
        _ = get_settings().database_url
    monkeypatch.setenv('MOD_DEMO_DATABASE_URL', 'mysql+pymysql://127.0.0.1/independent_demo')
    assert get_settings().database_url == 'mysql+pymysql://127.0.0.1/independent_demo'


def test_demo_sql_sessions_are_read_only_and_skip_heatwave(monkeypatch):
    monkeypatch.setenv('MOD_DEMO_MODE', 'true')
    monkeypatch.setenv('MOD_HW_ENABLED', 'true')
    connection = MagicMock()
    _on_connect(connection, MagicMock())
    statements = [call.args[0] for call in connection.cursor.return_value.execute.call_args_list]
    assert 'SET SESSION TRANSACTION READ ONLY' in statements
    assert not any('use_secondary_engine' in sql for sql in statements)


def test_demo_blocks_writers_even_with_explicit_write_flags(monkeypatch):
    monkeypatch.setenv('MOD_DEMO_MODE', 'true')
    monkeypatch.setenv('MOD_SIMULATION_ENGINE_ENABLED', 'true')
    assert not is_simulation_engine_enabled()
    assert not is_construction_writer_enabled()
    monkeypatch.setenv('MOD_HW_ML_ENABLED', 'true')
    connection = MagicMock()
    adapter = HeatWaveMLAdapter(conn=connection, execute=True)
    assert adapter.build_feature_tables()['status'] == 'plan'
    assert adapter.train_models()['status'] == 'plan'
    assert adapter.run_batch_scoring()['status'] == 'plan'
    connection.execute.assert_not_called()


def test_demo_blocks_both_external_ai_clients(monkeypatch):
    monkeypatch.setenv('MOD_DEMO_MODE', 'true')
    monkeypatch.setenv('MOD_CF_AI_ENABLED', 'true')
    monkeypatch.setenv('CLOUDFLARE_ACCOUNT_ID', 'fixture-account')
    monkeypatch.setenv('CLOUDFLARE_API_TOKEN', 'fixture-token')
    assert not CloudflareAIClient(watchdog=MagicMock()).is_configured()
    assert not CloudflareAIAdapter()._enabled


def test_container_target_escapes_password_without_source_fallback(monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'scripts/project/demo_container.py'
    spec = importlib.util.spec_from_file_location('demo_container', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('MOD_DEMO_DB_PASSWORD', 'test-only:%@/#')
    monkeypatch.setenv('MOD_DB_HOST', 'source.example.test')
    url = make_url(module.target_url())
    assert url.host == 'demo-db'
    assert url.password == 'test-only:%@/#'  # pragma: allowlist secret (synthetic fixture)
    monkeypatch.delenv('MOD_DEMO_DB_PASSWORD')
    with pytest.raises(ValueError):
        module.target_url()
