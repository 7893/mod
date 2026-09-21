"""KI-080: output truthfulness, fully isolated from databases and model providers."""
from datetime import datetime
import json
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.integrations.heatwave_ml import HeatWaveMLAdapter
from app.services import daily_briefing


@pytest.mark.parametrize('probability, expected', [(0, 0), (1, 1), (0.37, 0.37),
                                                 (None, None), (True, None), ('bad', None),
                                                 (-0.1, None), (1.1, None), (float('nan'), None)])
def test_missing_or_invalid_probability_is_not_invented(probability, expected):
    conn = MagicMock()
    adapter = HeatWaveMLAdapter(conn)
    adapter._table_exists = lambda name: name == 'ml_score_risk'
    conn.execute.return_value.mappings.return_value.all.return_value = [{
        'org_id': 1, 'pred_value': 1,
        'prediction_json': json.dumps({'probabilities': {'1': probability}}),
    }]
    result = adapter.get_predictions()[0]
    assert result['riskScore'] == expected
    assert result['probabilitySource'] == ('UNAVAILABLE' if expected is None else 'MODEL')


def explanation(row, native=None):
    conn = MagicMock()
    adapter = HeatWaveMLAdapter(conn)
    adapter._safe_query = MagicMock(return_value=[row])
    conn.execute.return_value.scalar.return_value = json.dumps(native) if native else None
    return adapter.explain_risk(1), conn


def test_zero_success_rates_reach_model_and_rule_explanation():
    result, conn = explanation({'doc_success_pct': 0, 'integration_success_pct': 0})
    features = json.loads(conn.execute.call_args.args[1]['feats'])
    assert features['doc_success_pct'] == 0
    assert features['integration_success_pct'] == 0
    assert 'integration_success_pct' in [a['factor'] for a in result['topAttributions']]


@pytest.mark.parametrize('native', [None, {'ml_results': {'attributions': {'stagnant_days': -0.2}}}])
def test_no_positive_factors_do_not_create_a_hundred_percent_cause(native):
    result, _ = explanation({'construction_pct': 100, 'integration_success_pct': 100,
                             'progress_slope_14d': 3}, native)
    assert result['topAttributions'] == []


@pytest.mark.parametrize('briefing_date, stale', [('2026-09-12', False), ('2026-09-11', True)])
def test_briefing_freshness_uses_display_day(monkeypatch, briefing_date, stale):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 12, 17, tzinfo=ZoneInfo('UTC')).astimezone(tz)
    monkeypatch.setattr(daily_briefing, 'datetime', Clock)
    monkeypatch.setattr(daily_briefing, 'get_display_timezone', lambda: ZoneInfo('Asia/Singapore'))
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = [{
        'briefing_date': briefing_date, 'content': '摘要', 'model': 'model',
        'source': 'llm', 'generated_at': '2026-09-12 16:30:00',
    }]
    result = daily_briefing.get_latest(conn)
    assert result['status'] == 'ok'  # Additive API contract: old content is retained.
    assert result['isStale'] is stale
    assert result['generatedAt'] == '2026-09-12T16:30:00+00:00'
    assert str(conn.execute.call_args.args[1]['expected_date']) == '2026-09-12'


def test_legacy_same_day_briefing_is_not_presented_as_closed_day(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 21, 9, tzinfo=ZoneInfo('UTC')).astimezone(tz)

    monkeypatch.setattr(daily_briefing, 'datetime', Clock)
    monkeypatch.setattr(daily_briefing, 'get_display_timezone', lambda: ZoneInfo('Asia/Hong_Kong'))
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = [{
        'briefing_date': '2026-09-20',
        'content': '旧口径今日新增',
        'model': 'model',
        'source': 'llm',
        'generated_at': '2026-09-19 16:30:00',
    }]

    result = daily_briefing.get_latest(conn)

    assert result == {'status': 'no_briefing', 'message': '尚无上一完整自然日口径的日报'}


def test_briefing_uses_previous_complete_calendar_day(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 9, 20, 16, 30, tzinfo=ZoneInfo('UTC'))
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    monkeypatch.setattr(daily_briefing, 'datetime', Clock)
    conn = MagicMock()
    stats_result = MagicMock()
    stats_result.mappings.return_value.first.return_value = {
        'doc_today': 8200,
        'voucher_today': 7900,
    }
    conn.execute.side_effect = [MagicMock(), stats_result, MagicMock()]
    adapter = MagicMock()
    adapter.generate_insights.return_value = {
        'status': 'ok',
        'content': '上一完整自然日摘要',
        'model': 'model',
    }

    result = daily_briefing.generate_and_store(
        conn,
        {
            'docsTotal': 5_000_000,
            'docsTodayAdded': 12,
            'vouchersTodayAdded': 3,
        },
        adapter,
        display_tz='Asia/Hong_Kong',
    )

    payload = adapter.generate_insights.call_args.args[0]
    assert payload['docsClosedDayAdded'] == 8200
    assert payload['vouchersClosedDayAdded'] == 7900
    assert 'docsTodayAdded' not in payload
    assert 'vouchersTodayAdded' not in payload
    assert adapter.generate_insights.call_args.kwargs['reporting_date'] == '2026-09-20'
    assert result['briefingDate'] == '2026-09-20'
    write_params = conn.execute.call_args_list[2].args[1]
    assert str(write_params['d']) == '2026-09-20'


def test_fit_scores_do_not_certify_business_forecasts(monkeypatch):
    from app import api
    hw = MagicMock()
    hw.get_status.return_value = {'status': 'ready', 'models': {
        'regression': {'quality': 0.99}, 'classifier': {'quality': 0.9}}}
    hw.get_predictions.return_value = []
    monkeypatch.setattr(api, 'HeatWaveMLAdapter', lambda conn: hw)
    monkeypatch.setattr(api, 'dashboard_snapshot', lambda conn: {'insights': {}})
    result = api.insights_status(None)
    assert result['automlStatus'] == 'EXPERIMENTAL'
    assert result['businessValidated'] is False
    assert result['hw_ml']['models']['regression']['quality'] == 0.99
