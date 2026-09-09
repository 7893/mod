"""Unit and integration tests for QuotaWatchdog, CloudflareAIClient, and TrickleBackfiller.

Ensures:
1. Daily neuron limit of 3,000 is strictly enforced.
2. Fused state blocks further calls and triggers seamless local fallback.
3. Network failures/exceptions gracefully degrade to LocalNarrativeLibrary.
4. Backfill pipeline processes in conservative batches (<= 3 issues).
5. FastApi endpoints /api/governance/ai-quota and /api/governance/issues/{id}/enrich function correctly.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch
import os


from simulation.cf_ai_client import CloudflareAIClient
from simulation.quota_watchdog import QuotaWatchdog
from simulation.trickle_backfill import TrickleBackfiller


class MockLedgerCursor:
    def __init__(self, ledger: dict):
        self.ledger = ledger
        self._last_row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql: str, params: tuple = ()):
        sql_upper = sql.upper()
        if "SELECT" in sql_upper and "SIM_AI_QUOTA_LEDGER" in sql_upper:
            check_date = params[0]
            entry = self.ledger.get(check_date)
            if not entry:
                self._last_row = None
            elif "CALL_COUNT" in sql_upper:
                # SELECT call_count, neurons_used, status
                self._last_row = (entry["call_count"], entry["neurons_used"], entry["status"])
            else:
                # SELECT neurons_used, status
                self._last_row = (entry["neurons_used"], entry["status"])
        elif "INSERT" in sql_upper and "SIM_AI_QUOTA_LEDGER" in sql_upper:
            check_date = params[0]
            if "INSERT IGNORE" in sql_upper:
                self.ledger.setdefault(check_date, {
                    "call_count": 0,
                    "neurons_used": 0.0,
                    "status": "ACTIVE",
                    "updated_at": params[1],
                })
                return
            if len(params) == 3:
                self.ledger[check_date] = {
                    "call_count": 0,
                    "neurons_used": params[1],
                    "status": "ACTIVE",
                    "updated_at": params[2],
                }
                return
            calls = params[1]
            neurons = params[2]
            limit = params[4]
            now = params[5]
            entry = self.ledger.get(check_date, {"call_count": 0, "neurons_used": 0.0, "status": "ACTIVE"})
            entry["call_count"] += calls
            entry["neurons_used"] += neurons
            entry["status"] = "FUSED" if entry["neurons_used"] >= limit else "ACTIVE"
            entry["updated_at"] = now
            self.ledger[check_date] = entry
        elif "UPDATE SIM_AI_QUOTA_LEDGER" in sql_upper:
            check_date = params[-1]
            entry = self.ledger[check_date]
            if "CALL_COUNT" in sql_upper:
                entry.update(call_count=params[0], neurons_used=params[1], status=params[2], updated_at=params[3])
            else:
                entry.update(neurons_used=params[0], status="ACTIVE", updated_at=params[1])

    def fetchone(self):
        return self._last_row

    def fetchall(self):
        return [self._last_row] if self._last_row else []


class MockLedgerConnection:
    def __init__(self):
        self.ledger: dict = {}
        self.autocommit = True

    def cursor(self):
        return MockLedgerCursor(self.ledger)

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


def test_quota_watchdog_atomic_ledger_and_hard_fuse():
    """Verify QuotaWatchdog accurately tracks neurons and trips fuse at 3,000 neurons."""
    conn = MockLedgerConnection()
    test_date = date(2099, 12, 31)

    watchdog = QuotaWatchdog(conn=conn, daily_limit=3000.0)

    # Initial state on clean date
    status = watchdog.get_status(target_date=test_date)
    assert status.neurons_used == 0.0
    assert status.remaining_neurons == 3000.0
    assert status.status == "ACTIVE"

    # Check consumption permission
    can_run, msg = watchdog.can_consume(estimated_neurons=50.0, target_date=test_date)
    assert can_run is True

    # Consume 2,900 neurons
    st1 = watchdog.record_consumption(neurons_used=2900.0, target_date=test_date)
    assert st1.neurons_used == 2900.0
    assert st1.remaining_neurons == 100.0
    assert st1.status == "ACTIVE"

    # Can we consume 150 neurons? (2900 + 150 > 3000) -> Should be denied!
    can_run, reason = watchdog.can_consume(estimated_neurons=150.0, target_date=test_date)
    assert can_run is False
    assert "Quota exhausted" in reason

    # Consume 120 more neurons -> total 3020 -> Should flip to FUSED
    st2 = watchdog.record_consumption(neurons_used=120.0, target_date=test_date)
    assert st2.neurons_used == 3020.0
    assert st2.status == "FUSED"
    assert st2.remaining_neurons == 0.0

    # Further consume check must fail
    can_run_after, _ = watchdog.can_consume(estimated_neurons=1.0, target_date=test_date)
    assert can_run_after is False


def test_quota_watchdog_reserves_before_call_and_reconciles_actual_usage():
    conn = MockLedgerConnection()
    test_date = date(2099, 12, 31)
    watchdog = QuotaWatchdog(conn=conn, daily_limit=3000.0)

    reserved, _ = watchdog.try_reserve(300.0, target_date=test_date)
    assert reserved is True
    assert watchdog.get_status(test_date).neurons_used == 300.0

    watchdog.reconcile_reservation(300.0, 42.0, 1, target_date=test_date)
    status = watchdog.get_status(test_date)
    assert status.neurons_used == 42.0
    assert status.call_count == 1


def test_cf_ai_client_quota_fuse_fallback():
    """Verify CloudflareAIClient immediately falls back to LocalNarrativeLibrary when quota is full."""
    mock_watchdog = MagicMock(spec=QuotaWatchdog)
    mock_watchdog.try_reserve.return_value = (False, "Quota exhausted: 3000.0/3000.0")

    client = CloudflareAIClient(watchdog=mock_watchdog)
    res = client.enrich_issue(
        issue_id="ISS-TEST-001",
        issue_type="期初数据校验失败",
        unit_name="太原重工股份有限公司",
        province="山西",
        current_description="期初应付账款对账差异",
    )

    assert "LOCAL_FALLBACK" in res.source
    assert res.neurons_used == 0.0
    assert len(res.summary) > 0
    assert len(res.root_cause) > 0
    assert len(res.suggested_action) > 0
    assert "太原重工股份有限公司" in res.summary or "重工" in res.summary or "制造" in res.root_cause


def test_cf_ai_client_quota_ledger_error_fails_closed_to_local():
    mock_watchdog = MagicMock(spec=QuotaWatchdog)
    mock_watchdog.try_reserve.side_effect = RuntimeError("ledger unavailable")
    # CI 环境无凭据；注入虚拟环境变量使客户端认为已配置，从而走到 watchdog 逻辑
    with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "test_acc", "CLOUDFLARE_API_TOKEN": "test_tok"}):
        client = CloudflareAIClient(watchdog=mock_watchdog)
        result = client.enrich_issue(
            issue_id="ISS-TEST-QUOTA",
            issue_type="数据校验失败",
            unit_name="测试单位",
            province="北京",
        )

        assert "QUOTA_UNAVAILABLE" in result.source
        assert result.neurons_used == 0.0


def test_cf_ai_client_network_error_resilience():
    """Verify CloudflareAIClient swallows network errors and safely falls back."""
    mock_watchdog = MagicMock(spec=QuotaWatchdog)
    mock_watchdog.try_reserve.return_value = (True, "Quota reserved")

    client = CloudflareAIClient(watchdog=mock_watchdog, timeout=0.001)
    # Point to unreachable URL to induce network timeout
    client.gateway = ""
    client.account_id = "test_acc"
    client.api_token = "dummy_token"
    client.model = "test_model"

    with patch("urllib.request.urlopen", side_effect=TimeoutError("Connection timed out")):
        res = client.enrich_issue(
            issue_id="ISS-TEST-002",
            issue_type="超期挂账",
            unit_name="国能神东煤炭集团",
            province="陕西",
        )

    assert "LOCAL_FALLBACK" in res.source
    assert "EXCEPTION" in res.source
    assert res.neurons_used == 0.0
    assert "煤炭" in res.root_cause or "神东" in res.summary


def test_trickle_backfiller_execution():
    """Verify TrickleBackfiller processes issues in controlled batches and writes audits."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Mock un-enriched issue row: (id, issue_type, unit_name, province, description, rework_count)
    mock_cur.fetchall.return_value = [
        ("ISS-TEST-001", "超期挂账", "测试单位A", "北京", "原始问题描述", 0)
    ]

    mock_watchdog = MagicMock(spec=QuotaWatchdog)
    mock_watchdog.can_consume.return_value = (True, "Quota available")
    mock_watchdog.record_consumption.return_value = MagicMock(neurons_used=10.0, status="ACTIVE")

    mock_client = MagicMock(spec=CloudflareAIClient)
    from simulation.cf_ai_client import EnrichmentResult
    mock_client.enrich_issue.return_value = EnrichmentResult(
        source="LOCAL_FALLBACK",
        model="local-narrative-v1",
        neurons_used=10.0,
        summary="【专家深度研判】完成治理排查",
        root_cause="期初往来款对账不符",
        suggested_action="重新梳理科目借贷",
    )

    backfiller = TrickleBackfiller(conn=mock_conn, client=mock_client, watchdog=mock_watchdog)
    report = backfiller.run_cycle(batch_size=1, auto_commit=False)

    assert report.status == "COMPLETED"
    assert report.issues_processed == 1
    assert "ISS-TEST-001" in report.enriched_ids
    assert mock_cur.execute.called, "Must execute SQL updates for issue and timeline"
    assert mock_watchdog.can_consume.called
    mock_conn.commit.assert_not_called()


def test_governance_ai_quota_and_enrich_endpoints(monkeypatch):
    """Verify /api/governance/ai-quota and /api/governance/issues/{id}/enrich API endpoints."""
    from app.api import governance_ai_quota, governance_issue_enrich
    mock_conn = MagicMock()

    monkeypatch.setattr(
        "app.services.governance.get_ai_quota_status",
        lambda conn, **kwargs: {
            "statDate": "2026-09-09",
            "neuronsUsed": 150.0,
            "dailyLimit": 3000.0,
            "status": "ACTIVE",
            "callCount": 3,
            "remainingNeurons": 2850.0,
        },
    )
    monkeypatch.setattr(
        "app.services.governance.enrich_governance_issue",
        lambda conn, issue_id: {
            "id": issue_id,
            "aiEnriched": 1,
            "description": "【专家深度研判】整改完毕",
        },
    )

    quota_data = governance_ai_quota(conn=mock_conn)
    assert quota_data["statDate"] == "2026-09-09"
    assert quota_data["dailyLimit"] == 3000.0
    assert quota_data["status"] == "ACTIVE"

    enriched_data = governance_issue_enrich("ISS-TEST-001", conn=mock_conn)
    assert enriched_data["id"] == "ISS-TEST-001"
    assert enriched_data["aiEnriched"] == 1
