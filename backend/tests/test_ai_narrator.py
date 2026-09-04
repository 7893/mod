from app.ai_narrator import AINarrator


def test_narrator_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MOD_CF_AI_ENABLED", raising=False)
    monkeypatch.delenv("MOD_CF_AI_GATEWAY_URL", raising=False)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "global-token-must-not-enable-mod")

    narrator = AINarrator()

    assert narrator.enabled is False


def test_narrator_requires_url_and_token(monkeypatch) -> None:
    monkeypatch.setenv("MOD_CF_AI_ENABLED", "true")
    monkeypatch.delenv("MOD_CF_AI_GATEWAY_URL", raising=False)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    assert AINarrator().enabled is False

    monkeypatch.setenv("MOD_CF_AI_GATEWAY_URL", "https://example.invalid/ai")
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    assert AINarrator().enabled is False


def test_narrator_enables_only_with_explicit_complete_config(monkeypatch) -> None:
    monkeypatch.setenv("MOD_CF_AI_ENABLED", "true")
    monkeypatch.setenv("MOD_CF_AI_GATEWAY_URL", "https://example.invalid/ai")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")

    narrator = AINarrator()

    assert narrator.enabled is True
