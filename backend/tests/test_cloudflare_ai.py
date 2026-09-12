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


def _enabled_adapter(monkeypatch):
    from app.integrations import cloudflare_ai as module
    monkeypatch.setenv('MOD_CF_AI_ENABLED', 'true')
    monkeypatch.setenv('MOD_CF_AI_DAILY_LIMIT', '1')
    monkeypatch.setattr(CloudflareAIAdapter, '_read_credentials', lambda self: ('test', 'test'))
    monkeypatch.setattr(module, '_cf_daily_count', 0)
    monkeypatch.setattr(module, '_cf_daily_date', '')
    monkeypatch.setattr(module, '_cf_cached_result', None)
    return CloudflareAIAdapter()


def test_failed_attempt_consumes_quota_and_does_not_change_socket_default(monkeypatch):
    import socket
    import urllib.request
    from unittest.mock import Mock
    adapter = _enabled_adapter(monkeypatch)
    request = Mock(side_effect=OSError('offline'))
    monkeypatch.setattr(urllib.request, 'urlopen', request)
    before = socket.getdefaulttimeout()
    assert adapter.generate_insights({'orgTotal': 2})['status'] == 'unavailable'
    assert adapter.generate_insights({'orgTotal': 2})['status'] == 'rate_limited'
    assert request.call_count == 1
    assert adapter.get_status()['quota']['scope'] == 'process'
    assert socket.getdefaulttimeout() == before


def test_whitelist_drops_non_finite_values():
    from app.integrations.cloudflare_ai import _filter_to_whitelist
    assert _filter_to_whitelist({'orgTotal': float('nan'), 'launched': float('inf'),
                                 'dual': True, 'highRisk': 0, 'secret': 'no'}) == {'highRisk': 0}


def test_malformed_and_truncated_outputs_are_not_cached(monkeypatch):
    import json
    import urllib.request
    from unittest.mock import MagicMock
    for payload in [[], {'success': True, 'result': {'response': ['not text']}},
                    {'success': True, 'result': {'response': '   '}},
                    {'success': True, 'result': {'choices': [{'finish_reason': 'length',
                     'message': {'content': 'unfinished'}}]}}]:
        adapter = _enabled_adapter(monkeypatch)
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **kw: response)
        assert adapter.generate_insights({'orgTotal': 2})['status'] == 'unavailable'
        assert adapter.get_status()['cache']['has_cache'] is False
