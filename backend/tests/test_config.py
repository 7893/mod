import os

os.environ.setdefault("MOD_DB_HOST", "127.0.0.1")
os.environ.setdefault("MOD_DB_PASSWORD", "test password")

from app.config import DEFAULT_DISPLAY_TIMEZONE, get_display_timezone, get_settings


def test_database_url_escapes_password() -> None:
    get_settings.cache_clear()
    url = get_settings().database_url
    assert "test+password" in url
    assert "mod_s" in url


def test_database_defaults_do_not_target_remote_host(monkeypatch) -> None:
    for name in ("MOD_DB_HOST", "MOD_V2_DB_HOST", "MOD_DB_PASSWORD", "MOD_V2_DB_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.db_host == "127.0.0.1"
    assert settings.db_password == ""
    get_settings.cache_clear()


def test_display_timezone_defaults_to_hong_kong(monkeypatch) -> None:
    monkeypatch.delenv("MOD_DISPLAY_TIMEZONE", raising=False)
    get_settings.cache_clear()
    get_display_timezone.cache_clear()
    assert get_settings().display_timezone == DEFAULT_DISPLAY_TIMEZONE
    assert DEFAULT_DISPLAY_TIMEZONE == "Asia/Hong_Kong"
    assert str(get_display_timezone()) == "Asia/Hong_Kong"
    get_settings.cache_clear()
    get_display_timezone.cache_clear()


def test_display_timezone_is_the_single_source() -> None:
    """展示时区只有一个来源：投影与模拟内核必须引用同一个对象，不得各自写死。"""
    from app.live_projection.models import DISPLAY_TIMEZONE
    from app.live_projection.simulation_engine import HONG_KONG_TZ

    assert DISPLAY_TIMEZONE is get_display_timezone()
    assert HONG_KONG_TZ is DISPLAY_TIMEZONE


def test_display_timezone_honours_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("MOD_DISPLAY_TIMEZONE", "Australia/Sydney")
    get_settings.cache_clear()
    get_display_timezone.cache_clear()
    try:
        assert str(get_display_timezone()) == "Australia/Sydney"
    finally:
        monkeypatch.delenv("MOD_DISPLAY_TIMEZONE", raising=False)
        get_settings.cache_clear()
        get_display_timezone.cache_clear()
