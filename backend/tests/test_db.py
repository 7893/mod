"""Database connection-mode contracts for ordinary MySQL and HeatWave."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.db import _on_connect


def test_on_connect_defaults_to_ordinary_mysql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOD_HW_ENABLED", raising=False)
    connection = MagicMock()

    _on_connect(connection, MagicMock())

    cursor = connection.cursor.return_value
    cursor.execute.assert_called_once_with("SET time_zone = '+08:00'")
    cursor.close.assert_called_once_with()


def test_on_connect_enables_heatwave_only_when_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOD_HW_ENABLED", "true")
    connection = MagicMock()

    _on_connect(connection, MagicMock())

    cursor = connection.cursor.return_value
    assert [call.args[0] for call in cursor.execute.call_args_list] == [
        "SET time_zone = '+08:00'",
        "SET use_secondary_engine = ON",
    ]
    cursor.close.assert_called_once_with()


def test_on_connect_does_not_hide_heatwave_configuration_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOD_HW_ENABLED", "true")
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.execute.side_effect = [None, RuntimeError("unsupported HeatWave setting")]

    with pytest.raises(RuntimeError, match="unsupported HeatWave setting"):
        _on_connect(connection, MagicMock())

    cursor.close.assert_called_once_with()
