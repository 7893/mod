from decimal import Decimal

from app.services.dashboard_sections import compose_issue_sections, compose_rule_based_alerts


def test_compose_issue_sections_uses_matching_aggregates():
    summary, issues = compose_issue_sections(
        totals={"latestDate": "2027-02-28", "totalIssues": 10, "totalResolved": 7, "totalUnresolved": 3},
        risks={"highRisk": 2, "mediumRisk": 4, "lowRisk": 1},
        by_stage=[{"stage": "上线后运行", "total": 10, "resolved": 7, "unresolved": 3}],
        issue_batches=[{"batchId": 1, "name": "第一批", "unresolved": 3}],
        risk_batches={1: {"batchId": 1, "high": 2, "medium": 4, "low": 1}},
    )

    assert summary["closeRate"] == 70.0
    assert summary["totalUnresolved"] == 3
    assert summary["highRisk"] == 2
    assert summary["byBatch"][0]["high"] == 2
    assert issues == [{
        "type": "风险预警",
        "level": "高",
        "title": "第一批·风险预警（高风险 2 项）",
        "area": "全国跨省",
        "owner": "项目质量组",
        "due": "",
        "status": "待处置",
        "leadershipAttention": True,
        "orgName": "第一批",
    }]


def test_compose_issue_sections_handles_empty_snapshot():
    summary, issues = compose_issue_sections(
        totals={"totalIssues": 0, "totalResolved": 0, "totalUnresolved": 0},
        risks={"highRisk": 0, "mediumRisk": 0, "lowRisk": 0},
        by_stage=[],
        issue_batches=[],
        risk_batches={},
    )

    assert summary["closeRate"] == 0
    assert summary["byBatch"] == []
    assert issues == []


def test_compose_issue_sections_normalizes_database_decimals():
    summary, _ = compose_issue_sections(
        totals={"totalIssues": Decimal("10"), "totalResolved": Decimal("7"), "totalUnresolved": Decimal("3")},
        risks={"highRisk": Decimal("2"), "mediumRisk": Decimal("4"), "lowRisk": Decimal("1")},
        by_stage=[],
        issue_batches=[],
        risk_batches={},
    )

    assert summary["totalUnresolved"] == 3
    assert isinstance(summary["totalUnresolved"], int)
    assert summary["closeRate"] == 70


def _batch(batch_id, total, launched=0, dual=0, construction=0.0):
    return {
        "batchId": batch_id, "name": f"第{batch_id}批", "total": total,
        "launched": launched, "dual": dual, "constructionPct": construction,
    }


def test_compose_rule_based_alerts_derives_numbers_from_rollout_rows():
    rows = [
        _batch(1, 100, launched=60, construction=50.0),
        _batch(5, 100, launched=40, construction=40.0),
        _batch(6, 300, dual=300, construction=Decimal("87.3")),
        _batch(7, 400, construction=62.7),
        _batch(8, 466),
    ]
    alerts = compose_rule_based_alerts(rows, 96.5)

    assert [a["level"] for a in alerts] == ["INFO", "SUCCESS", "WARNING"]
    assert "300 家单位处于双轨运行期" in alerts[0]["title"]
    assert "87.3%" in alerts[0]["detail"]
    assert "100 家单位已上线" in alerts[1]["title"]
    assert "共 200 家单位，其中 100 家已上线（50.0%）" in alerts[1]["detail"]
    assert "96.5%" in alerts[1]["detail"]
    assert "第7批 400 家在建单位平均进度 62.7%" in alerts[2]["detail"]
    assert "第8批 466 家储备单位" in alerts[2]["detail"]
    assert "全量投产" not in " ".join(a["detail"] for a in alerts)


def test_compose_rule_based_alerts_handles_empty_rollout():
    assert compose_rule_based_alerts([], None) == []

