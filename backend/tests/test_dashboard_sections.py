from decimal import Decimal

from app.services.dashboard_sections import compose_issue_sections


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
