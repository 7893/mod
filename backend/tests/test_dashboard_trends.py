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
