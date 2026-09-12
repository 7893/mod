from app.services.dashboard import build_operations_trend


def test_build_operations_trend_derives_daily_integration_delta_and_rate():
    rows = [
        {
            "date": "09-03",
            "fullDate": "2026-09-03",
            "documents": 13,
            "vouchers": 12,
            "integrationTotal": 126,
            "integrationSuccess": 122,
        },
        {
            "date": "09-02",
            "fullDate": "2026-09-02",
            "documents": 10,
            "vouchers": 9,
            "integrationTotal": 114,
            "integrationSuccess": 112,
        },
        {
            "date": "09-01",
            "fullDate": "2026-09-01",
            "documents": 8,
            "vouchers": 8,
            "integrationTotal": 105,
            "integrationSuccess": 104,
        },
    ]

    trend = build_operations_trend(rows)

    assert [item["fullDate"] for item in trend] == ["2026-09-02", "2026-09-03"]
    assert trend[0] == {
        "date": "09-02",
        "fullDate": "2026-09-02",
        "documents": 10,
        "vouchers": 9,
        "integrations": 9,
        "integrationSuccessPct": 88.89,
    }
    assert trend[1]["integrations"] == 12
    assert trend[1]["integrationSuccessPct"] == 83.33


def test_build_operations_trend_keeps_missing_rate_honest():
    rows = [
        {
            "date": "09-01",
            "fullDate": "2026-09-01",
            "documents": 0,
            "vouchers": 0,
            "integrationTotal": 10,
            "integrationSuccess": 10,
        },
        {
            "date": "09-02",
            "fullDate": "2026-09-02",
            "documents": 0,
            "vouchers": 0,
            "integrationTotal": 10,
            "integrationSuccess": 10,
        },
    ]

    trend = build_operations_trend(rows)

    assert trend[0]["integrations"] == 0
    assert trend[0]["integrationSuccessPct"] is None


def test_build_operations_trend_spike_smoothing_and_rate_clamping():
    # KI-079: 累积计数器发生断档式存量回填跃迁时，平滑单日集成量并防止成功率溢出 100%
    rows = [
        {
            "date": "09-28",
            "fullDate": "2026-09-28",
            "documents": 1000,
            "vouchers": 1000,
            "integrationTotal": 10000,
            "integrationSuccess": 9500,
        },
        {
            "date": "09-29",
            "fullDate": "2026-09-29",
            "documents": 2,
            "vouchers": 2,
            "integrationTotal": 10002,
            "integrationSuccess": 9519,  # raw_succ = 19, raw_delta = 2
        },
        {
            "date": "09-30",
            "fullDate": "2026-09-30",
            "documents": 1800,
            "vouchers": 1800,
            "integrationTotal": 3551102,  # raw_delta = 3,541,100 (存量回填毛刺)
            "integrationSuccess": 3338500,
        },
    ]

    trend = build_operations_trend(rows)
    assert len(trend) == 2
    # 09-29: 成功率被上限控制在 <= 100.0%
    row_29 = trend[0]
    assert row_29["fullDate"] == "2026-09-29"
    assert row_29["integrations"] == 2
    assert row_29["integrationSuccessPct"] is not None
    assert row_29["integrationSuccessPct"] <= 100.0

    # 09-30: 350 万存量毛刺被平滑至当期单据/凭证规模 (1800)
    row_30 = trend[1]
    assert row_30["fullDate"] == "2026-09-30"
    assert row_30["integrations"] == 1800
    assert 0.0 <= row_30["integrationSuccessPct"] <= 100.0


def test_fallback_snapshot_trend_structure():
    from app.services.dashboard import load_fallback_snapshot
    snapshot = load_fallback_snapshot()
    assert "trend" in snapshot
    assert len(snapshot["trend"]) == 7
    for item in snapshot["trend"]:
        assert "date" in item
        assert "fullDate" in item
        assert "launched" in item


