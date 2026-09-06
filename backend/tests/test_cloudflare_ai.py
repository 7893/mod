"""CloudflareAIAdapter 的配置与端点行为测试（不发真实网络请求）。"""

from app.integrations.cloudflare_ai import (
    CloudflareAIAdapter,
    _CF_AI_ENDPOINT,
    _CF_AI_GATEWAY_ENDPOINT,
)


def test_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MOD_CF_AI_ENABLED", raising=False)
    adapter = CloudflareAIAdapter()
    status = adapter.get_status()
    assert status["status"] == "disabled"


def test_gateway_defaults_to_mod_gateway(monkeypatch) -> None:
    monkeypatch.delenv("MOD_CF_AI_GATEWAY", raising=False)
    adapter = CloudflareAIAdapter()
    assert adapter._gateway == "mod-gateway"
    assert adapter.get_status()["gateway"] == "mod-gateway"


def test_gateway_can_be_disabled_for_direct_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("MOD_CF_AI_GATEWAY", "")
    adapter = CloudflareAIAdapter()
    assert adapter._gateway == ""
    assert adapter.get_status()["gateway"] is None


def test_gateway_endpoint_template_shape() -> None:
    # 网关端点必须经过 gateway.ai.cloudflare.com，直连端点走 api.cloudflare.com
    gw = _CF_AI_GATEWAY_ENDPOINT.format(account_id="acct", gateway="mod-gateway", model="@cf/x")
    assert gw.startswith("https://gateway.ai.cloudflare.com/v1/acct/mod-gateway/workers-ai/")
    direct = _CF_AI_ENDPOINT.format(account_id="acct", model="@cf/x")
    assert direct.startswith("https://api.cloudflare.com/client/v4/accounts/acct/ai/run/")


def test_generate_insights_disabled_makes_no_request(monkeypatch) -> None:
    monkeypatch.delenv("MOD_CF_AI_ENABLED", raising=False)
    adapter = CloudflareAIAdapter()
    result = adapter.generate_insights({"orgTotal": 2000, "launched": 748})
    assert result["status"] == "disabled"
