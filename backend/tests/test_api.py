import os
import re
from fastapi.testclient import TestClient

os.environ.setdefault("MOD_DB_HOST", "127.0.0.1")
os.environ.setdefault("MOD_DB_PASSWORD", "test_password")

from app.main import app
from app.api import normalize_region, load_fallback_snapshot, normalize_operations_dict
from app.services.dashboard import LATEST_COMPLETED_DOCUMENT_DATE_SQL, REGION_SUMMARY_SQL

client = TestClient(app)


def test_normalize_region_34_provinces():
    test_cases = {
        "北京市": "北京",
        "天津市": "天津",
        "上海市": "上海",
        "重庆市": "重庆",
        "河北省": "河北",
        "山西省": "山西",
        "辽宁省": "辽宁",
        "吉林省": "吉林",
        "黑龙江省": "黑龙江",
        "江苏省": "江苏",
        "浙江省": "浙江",
        "安徽省": "安徽",
        "福建省": "福建",
        "江西省": "江西",
        "山东省": "山东",
        "河南省": "河南",
        "湖北省": "湖北",
        "湖南省": "湖南",
        "广东省": "广东",
        "海南省": "海南",
        "四川省": "四川",
        "贵州省": "贵州",
        "云南省": "云南",
        "陕西省": "陕西",
        "甘肃省": "甘肃",
        "青海省": "青海",
        "台湾省": "台湾",
        "内蒙古自治区": "内蒙古",
        "广西壮族自治区": "广西",
        "西藏自治区": "西藏",
        "宁夏回族自治区": "宁夏",
        "新疆维吾尔自治区": "新疆",
        "香港特别行政区": "香港",
        "澳门特别行政区": "澳门",
    }
    assert len(test_cases) == 34
    for full, expected in test_cases.items():
        assert normalize_region(full) == expected, f"Failed for {full}: expected {expected}, got {normalize_region(full)}"


def test_normalize_operations_dict():
    """Verify operations dict key normalization handles both snake_case and camelCase."""
    snake_input = {
        "business_document": 199612,
        "business_document_line": 498855,
        "accounting_voucher": 161270,
        "accounting_voucher_line": 322540,
        "document_voucher_link": 182201,
        "integration_result": 150233,
        "dual_run_result": 2859,
    }
    normalized = normalize_operations_dict(snake_input)
    assert normalized["businessDocument"] == 199612
    assert normalized["businessDocumentLine"] == 498855
    assert normalized["accountingVoucher"] == 161270
    assert normalized["accountingVoucherLine"] == 322540
    assert normalized["documentVoucherLink"] == 182201
    assert normalized["integrationResult"] == 150233
    assert normalized["dualRunResult"] == 2859
    assert "business_document" not in normalized

    # Idempotent on already camelCase input
    camel_input = {
        "businessDocument": 100,
        "accountingVoucher": 200,
    }
    normalized_camel = normalize_operations_dict(camel_input)
    assert normalized_camel["businessDocument"] == 100
    assert normalized_camel["accountingVoucher"] == 200


def test_v2_snapshot_file_integrity():
    """
    Test fallback snapshot data integrity against V2 frozen baseline.
    Note: In local test environment, DB connection falls back to this verified snapshot.
    Online DB SQL path will be verified during USA read-only integration testing.
    """
    snap = load_fallback_snapshot()
    overview = snap["overview"]
    meta = snap["meta"]

    # Baseline core KPI — derive/structural assertions, no hardcoded volatile values
    assert isinstance(overview["orgTotal"], int) and overview["orgTotal"] > 0
    assert isinstance(overview["launched"], int) and 0 <= overview["launched"] <= overview["orgTotal"]
    assert isinstance(overview["dual"], int) and 0 <= overview["dual"] <= overview["orgTotal"]
    assert 0.0 <= overview["voucherSuccessPct"] <= 100.0
    assert 0.0 <= overview["integrationSuccessPct"] <= 100.0
    assert isinstance(meta["fullRows"], int) and meta["fullRows"] > 0
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["asOfDate"])

    # Cumulative and today added — structural, not fixed magnitudes
    assert isinstance(overview["contactsTotal"], int) and overview["contactsTotal"] >= 0
    assert isinstance(overview["contactsCoveredOrgs"], int)
    assert 0 <= overview["contactsCoveredOrgs"] <= overview["orgTotal"]
    assert 0.0 <= overview["contactsCoveragePct"] <= 100.0
    assert isinstance(overview["docsTotal"], int) and overview["docsTotal"] >= 0
    assert isinstance(overview["vouchersTotal"], int) and overview["vouchersTotal"] >= 0
    assert isinstance(overview["docsTodayAdded"], int) and overview["docsTodayAdded"] >= 0
    assert isinstance(overview["vouchersTodayAdded"], int) and overview["vouchersTodayAdded"] >= 0

    # 34 Provinces
    provinces = snap["provinces"]
    assert len(provinces) == 34
    prov_names = {p["name"] for p in provinces}
    assert "北京" in prov_names
    assert "辽宁" in prov_names
    assert "新疆" in prov_names
    assert "香港" in prov_names

    # Provincial todayAdded verification (R3)
    for p in provinces:
        assert "todayAdded" in p
        assert "docsTodayAdded" in p
        assert p["todayAdded"] == p["docsTodayAdded"]
        assert isinstance(p["todayAdded"], int)
        assert p["todayAdded"] >= 0
    assert sum(p["todayAdded"] for p in provinces) == overview["docsTodayAdded"]

    # Entities — count consistent with orgTotal, structural field checks
    entities = snap["entities"]
    assert len(entities) == overview["orgTotal"]
    for e in entities[:20]:
        assert isinstance(e["owner"], str) and e["owner"].strip()
        assert e["status"] in ("准备中", "建设中", "双轨运行", "已上线")
        # These metrics may be None ("未提供") for unlaunched units; if present, in range.
        for field in ("construction", "openingData", "voucherRate"):
            assert e[field] is None or 0.0 <= e[field] <= 100.0

    # Issues array compatibility
    issues = snap["issues"]
    assert isinstance(issues, list)
    assert len(issues) > 0
    for it in issues:
        assert "status" in it
        assert "level" in it
        assert "title" in it
        assert "owner" in it
        assert "due" in it
        assert "leadershipAttention" in it
        assert "orgName" in it

    # Issues summary — structural, cross-checked, no fixed magnitudes
    summary = snap["issuesSummary"]
    assert isinstance(summary["totalUnresolved"], int) and summary["totalUnresolved"] >= 0
    assert isinstance(summary["highRisk"], int) and summary["highRisk"] >= 0


def test_v2_api_routes():
    """
    Test FastAPI /api endpoints contract.
    Operates in fallback snapshot mode in local dev/test environment.
    """
    # Root
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.headers["x-robots-tag"] == "noindex, nofollow, noarchive, nosnippet, noimageindex"

    # Refresh Meta
    res = client.get("/api/dashboard/refresh-meta")
    assert res.status_code == 200
    data = res.json()
    assert data["data_version"] == "frozen"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["as_of_date"])

    # Overview
    res = client.get("/api/dashboard/overview")
    assert res.status_code == 200
    ov = res.json()
    assert isinstance(ov["orgTotal"], int) and ov["orgTotal"] > 0
    assert isinstance(ov["launched"], int) and 0 <= ov["launched"] <= ov["orgTotal"]
    assert isinstance(ov["dual"], int) and 0 <= ov["dual"] <= ov["orgTotal"]
    assert 0.0 <= ov["voucherSuccessPct"] <= 100.0

    # Snapshot
    res = client.get("/api/dashboard/snapshot")
    assert res.status_code == 200
    snap = res.json()
    assert "overview" in snap
    assert "rollout" in snap
    assert "trend" in snap
    assert "provinces" in snap
    assert "entities" in snap
    assert "issues" in snap
    assert "operations" in snap

    # Rollout
    res = client.get("/api/dashboard/rollout")
    assert res.status_code == 200
    assert len(res.json()) == 8

    # Regions (34 provinces with todayAdded)
    res = client.get("/api/dashboard/regions")
    assert res.status_code == 200
    reg_list = res.json()
    assert len(reg_list) == 34
    assert sum(r["todayAdded"] for r in reg_list) >= 0

    # Organizations (paginated)
    res = client.get("/api/organizations?page=1&page_size=10")
    assert res.status_code == 200
    pg = res.json()
    assert isinstance(pg["total"], int) and pg["total"] > 0
    assert len(pg["items"]) == 10

    # Issues summary
    res = client.get("/api/issues/summary")
    assert res.status_code == 200
    assert isinstance(res.json()["totalUnresolved"], int) and res.json()["totalUnresolved"] >= 0

    # Construction summary
    res = client.get("/api/construction/summary")
    assert res.status_code == 200
    assert isinstance(res.json()["totalTasks"], int) and res.json()["totalTasks"] >= 0

    # Insights status
    res = client.get("/api/insights/status")
    assert res.status_code == 200
    assert res.json()["automlStatus"] == "UNAVAILABLE_AWAITING_TRAINING"
    assert res.json()["trainingAuthorized"] is False

    # Operations summary (standardized camelCase keys)
    res = client.get("/api/operations/summary")
    assert res.status_code == 200
    ops = res.json()
    for key in (
        "businessDocument", "businessDocumentLine", "accountingVoucher",
        "accountingVoucherLine", "documentVoucherLink", "integrationResult",
        "dualRunResult",
    ):
        assert key in ops
        assert isinstance(ops[key], int) and ops[key] >= 0

    # Read-only presentation projection status
    res = client.get("/api/live-projection/status")
    assert res.status_code == 200
    projection = res.json()
    assert projection["mode"] == "display_projection"
    assert set(projection["cumulative"]) == {"documents", "vouchers", "integrations"}
    assert all(value >= 0 for value in projection["cumulative"].values())
    assert res.headers["x-robots-tag"] == "noindex, nofollow, noarchive, nosnippet, noimageindex"


def test_v2_overview_r5_r6_contract():
    """
    R5 & R6 contract tests:
    - R5: All 4 metrics (org, contacts, docs, vouchers) must provide cumulative values.
          Contacts retain traceability metadata and provide calculated organization coverage.
    - R6: Document additions date (2026-08-29) must not be confused with global snapshot date (2026-08-30).
          Both API and snapshot must return addedAsOfDate per metric and for all 34 provinces.
    """
    res = client.get("/api/dashboard/overview")
    assert res.status_code == 200
    ov = res.json()

    # 1. Four A2 cards presence & correct types
    # Card 1: Org
    assert isinstance(ov["orgTotal"], int) and ov["orgTotal"] > 0
    assert isinstance(ov["orgTodayAdded"], int) and ov["orgTodayAdded"] >= 0
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ov["orgAddedAsOfDate"])
    assert "无可追溯" in ov["orgAddedNote"]

    # Card 2: Contacts (R5) — structural, retains traceability metadata contract
    assert isinstance(ov["contactsTotal"], int) and ov["contactsTotal"] >= 0
    assert isinstance(ov["contactsCoveredOrgs"], int)
    assert 0 <= ov["contactsCoveredOrgs"] <= ov["orgTotal"]
    assert 0.0 <= ov["contactsCoveragePct"] <= 100.0
    assert isinstance(ov["contactsTodayAdded"], int) and ov["contactsTodayAdded"] >= 0
    assert ov["contactsAddedAsOfDate"] == "无可追溯"
    assert ov["contactsAddedNote"] == "当前封版无可追溯新增人员"

    # Card 3: Docs (R6)
    assert isinstance(ov["docsTotal"], int) and ov["docsTotal"] >= 0
    assert isinstance(ov["docsTodayAdded"], int) and ov["docsTodayAdded"] >= 0
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ov["docsAddedAsOfDate"])

    # Card 4: Vouchers (R6)
    assert isinstance(ov["vouchersTotal"], int) and ov["vouchersTotal"] >= 0
    assert isinstance(ov["vouchersTodayAdded"], int) and ov["vouchersTodayAdded"] >= 0
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ov["vouchersAddedAsOfDate"])

    # Total snapshot date vs Document additions date differentiation (R6)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ov["asOfDate"])
    assert ov["docsAddedAsOfDate"] != ov["asOfDate"]

    # 2. Provincial additions date contract
    reg_res = client.get("/api/dashboard/regions")
    assert reg_res.status_code == 200
    regions = reg_res.json()
    assert len(regions) == 34
    for r in regions:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["docsAddedAsOfDate"])
        assert r["todayAdded"] == r["docsTodayAdded"]
        assert isinstance(r["todayAdded"], int)


def test_v2_snapshot_internal_consistency_contract():
    """R3 and R6 remain enforced in the checked-in fallback snapshot."""
    snap = load_fallback_snapshot()
    overview = snap["overview"]
    provinces = snap["provinces"]

    # R3: province-level todayAdded must reconcile with the overview total.
    total_prov_docs_today = sum(p["todayAdded"] for p in provinces)
    assert total_prov_docs_today == overview["docsTodayAdded"]

    # R6: document additions date must remain distinct from the total baseline date.
    api_ov = client.get("/api/dashboard/overview").json()
    assert api_ov["docsAddedAsOfDate"] != api_ov["asOfDate"]


def test_v2_region_query_derives_document_additions():
    assert "submit_time < :anchor_date" in LATEST_COMPLETED_DOCUMENT_DATE_SQL
    assert "0 AS todayAdded" not in REGION_SUMMARY_SQL
    assert "COUNT(*) AS docs_today_added" in REGION_SUMMARY_SQL
    assert "submit_time >= :docs_as_of_date" in REGION_SUMMARY_SQL


def test_v2_refresh_meta_total_rows():
    """
    Ensure that /dashboard/refresh-meta returns total_rows matching snapshot.fullRows,
    even in fallback mode.
    """
    res = client.get("/api/dashboard/refresh-meta")
    assert res.status_code == 200
    data = res.json()
    assert "total_rows" in data
    # Cross-check against the fallback snapshot rather than a hardcoded magnitude
    snap = load_fallback_snapshot()
    assert data["total_rows"] == snap["meta"]["fullRows"]
    assert data["status"] == "fallback"
    assert data["data_version"] == "frozen"
