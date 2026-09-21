"""Shared offline-test isolation for application lifespan side effects."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_external_startup_work(monkeypatch: pytest.MonkeyPatch):
    """Keep TestClient startup independent from a configured live database."""
    monkeypatch.setenv("MOD_STARTUP_DB_PROBE_ENABLED", "false")
    monkeypatch.setenv("MOD_SNAPSHOT_PREWARM_ENABLED", "false")
