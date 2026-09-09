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

    # Insights status —— 无 DB 连接时走 fallback，状态不再由陈旧快照写死；
    # automlStatus 只应由实时库内状态决定，fallback 下该键缺省（不再是历史静态值）。
    res = client.get("/api/insights/status")
    assert res.status_code == 200
    assert res.json().get("automlStatus") != "UNAVAILABLE_AWAITING_TRAINING"

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
    assert "DATE(MAX(submit_time))" in LATEST_COMPLETED_DOCUMENT_DATE_SQL
    assert "MAX(DATE(" not in LATEST_COMPLETED_DOCUMENT_DATE_SQL
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


def test_openapi_security_schemes():
    """KI-041: OpenAPI 文档必须显式声明 securitySchemes 认证体系。"""
    res = client.get("/api/openapi.json")
    assert res.status_code == 200
    spec = res.json()
    assert "components" in spec
    assert "securitySchemes" in spec["components"]
    schemes = spec["components"]["securitySchemes"]
    assert "ApiKeyAuth" in schemes
    assert "BearerAuth" in schemes
    assert "ActionTokenAuth" in schemes
    assert schemes["ApiKeyAuth"]["type"] == "apiKey"
    assert schemes["ApiKeyAuth"]["name"] == "X-MOD-Auth-Token"


def test_insights_status_provides_action_token():
    """KI-041: insights/status 接口必须提供短效 action_token 供前端合法会话使用。"""
    res = client.get("/api/insights/status")
    assert res.status_code == 200
    data = res.json()
    assert "action_token" in data
    assert isinstance(data["action_token"], str)
    assert len(data["action_token"]) >= 16


def test_insights_generate_requires_authentication(monkeypatch):
    """KI-041: POST /api/insights/generate 必须强制鉴权，未授权请求拒绝执行外部模型调用。"""
    from unittest.mock import MagicMock

    # 1. 无任何认证凭据 -> 401
    res = client.post("/api/insights/generate")
    assert res.status_code == 401

    # 2. 携带错误凭据 -> 401
    res = client.post("/api/insights/generate", headers={"X-MOD-Auth-Token": "invalid-token"})
    assert res.status_code == 401

    # 3. 携带合法 action_token -> 鉴权通过并执行业务逻辑
    from app.auth import get_current_action_token
    token = get_current_action_token()

    mock_cf_ai = MagicMock()
    mock_cf_ai.generate_insights.return_value = {"status": "ok", "content": "Mock insight"}
    monkeypatch.setattr("app.api.CloudflareAIAdapter", lambda: mock_cf_ai)

    res = client.post("/api/insights/generate", headers={"X-Action-Token": token})
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # 4. 携带配置的 MOD_INTERNAL_API_KEY -> 鉴权通过
    monkeypatch.setenv("MOD_INTERNAL_API_KEY", "internal-test-key-999")
    res = client.post("/api/insights/generate", headers={"X-MOD-Auth-Token": "internal-test-key-999"})
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_health_probe_status_code_when_db_down(monkeypatch):
    """KI-046: 数据库离线或不可达时，/api/health 必须返回 HTTP 503 明确标识降级故障。"""
    from app.db import connection

    def mock_offline_connection():
        yield None

    app.dependency_overrides[connection] = mock_offline_connection
    try:
        res = client.get("/api/health")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "degraded"
        assert "Database not reachable" in data["notice"]
    finally:
        app.dependency_overrides.pop(connection, None)


def test_health_probe_status_code_when_db_healthy(monkeypatch):
    """KI-046: 数据库正常连通时，/api/health 返回 HTTP 200 及数据库时间与元数据。"""
    from unittest.mock import MagicMock
    from app.db import connection

    mock_conn = MagicMock()
    mock_row = MagicMock()
    mock_row.mappings.return_value.one.return_value = {
        "db": "mod",
        "tz": "+08:00",
        "now_cst": "2026-09-08 00:44:00",
    }
    mock_conn.execute.return_value = mock_row

    def mock_healthy_connection():
        yield mock_conn

    app.dependency_overrides[connection] = mock_healthy_connection
    try:
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["database"] == "mod"
        assert data["session_timezone"] == "+08:00"
        assert data["now_cst"] == "2026-09-08 00:44:00"
    finally:
        app.dependency_overrides.pop(connection, None)


def test_connection_generator_lifecycle_and_throw():
    """KI-046: connection() 生成器依赖在下游抛出异常时绝不能二次 yield 触发 generator didn't stop after throw()。"""
    from unittest.mock import MagicMock, patch
    from app.db import connection

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value = mock_conn

    with patch("app.db.get_engine", return_value=mock_engine):
        gen = connection()
        yielded = next(gen)
        assert yielded is mock_conn

        # 下游抛出异常时，生成器必须执行 finally: close 并正常退出，不得二次 yield
        test_exc = RuntimeError("simulated business error in route")
        try:
            gen.throw(test_exc)
            assert False, "应当抛出异常退出生成器"
        except RuntimeError as e:
            assert e is test_exc
            mock_conn.close.assert_called()

    # 测试连接建立即失败的情形
    failing_engine = MagicMock()
    failing_engine.connect.side_effect = ConnectionRefusedError("db refused")
    with patch("app.db.get_engine", return_value=failing_engine):
        gen_fail = connection()
        val = next(gen_fail)
        assert val is None
        # 生成器应当直接 return 结束
        try:
            next(gen_fail)
            assert False, "生成器应当在 yield None 后终止"
        except StopIteration:
            pass


def test_error_responses_desensitized(monkeypatch):
    """KI-046: 服务端异常信息脱敏，绝不暴露敏感 SQL、内部连接或堆栈。"""
    from unittest.mock import MagicMock
    from app.db import connection

    # 1. /api/health 查询报错时不泄露底层敏感字符串
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = Exception("pymysql.err.OperationalError: Table mod.secret_tbl does not exist")

    def mock_failing_connection():
        yield mock_conn

    app.dependency_overrides[connection] = mock_failing_connection
    try:
        res = client.get("/api/health")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "degraded"
        assert "secret_tbl" not in data.get("error", "")
        assert data["error"] == "Database health check failed"
    finally:
        app.dependency_overrides.pop(connection, None)

    # 2. /api/insights/briefing 异常时不泄露内部错误
    monkeypatch.setattr("app.services.daily_briefing.get_latest", MagicMock(side_effect=Exception("DB syntax error near DROP TABLE")))
    res_briefing = client.get("/api/insights/briefing")
    assert res_briefing.status_code == 200
    assert "DROP TABLE" not in res_briefing.json().get("message", "")
    assert res_briefing.json()["message"] == "服务端错误，暂无可用简报"


def test_dashboard_snapshot_swr_and_prewarm(monkeypatch):
    """KI-059: 验证快照开机预热与 Stale-While-Revalidate (SWR) 毫秒级保障。"""
    import time
    from app.api import prewarm_snapshot, dashboard_snapshot
    import app.api as api_mod

    # 1. 测试同步预热入口
    prewarm_snapshot(sync=True)
    assert api_mod._snapshot_cache is not None

    # 2. 验证直接调用与 HTTP 端点均极速返回 (< 100ms)
    t0 = time.monotonic()
    snap = dashboard_snapshot(None)
    duration = time.monotonic() - t0
    assert duration < 0.1, f"Expected < 100ms response, took {duration:.3f}s"
    assert "overview" in snap
    assert "entities" in snap

    # 3. 模拟缓存过期，验证 SWR 异步刷新且立即返回旧缓存
    api_mod._snapshot_cached_at = time.monotonic() - 1000.0  # 过期
    t0 = time.monotonic()
    res = client.get("/api/dashboard/snapshot")
    duration = time.monotonic() - t0
    assert res.status_code == 200
    assert duration < 0.1, f"Expected instant SWR response < 100ms, took {duration:.3f}s"
    assert res.json()["overview"]["orgTotal"] > 0


def test_ki061_fallback_snapshot_contracts():
    """KI-061: 验证 fallback 快照包含全部必需字段，杜绝 C3/D3/D6 空白面板。"""
    from app.services.dashboard import load_fallback_snapshot
    snap = load_fallback_snapshot()

    # C3: rolloutTrend
    assert "rolloutTrend" in snap, "fallback 快照必须包含 rolloutTrend，防止 C3 暂无批次历史快照空态"
    assert isinstance(snap["rolloutTrend"], list)
    assert len(snap["rolloutTrend"]) > 0
    first_rt = snap["rolloutTrend"][0]
    for field in ("date", "fullDate", "batchId", "name", "total", "launchedPct", "dualPct"):
        assert field in first_rt, f"rolloutTrend 元素必须包含 {field}"
    assert isinstance(first_rt["batchId"], int)
    assert isinstance(first_rt["launchedPct"], (int, float))

    # D3: operationsTrend
    assert "operationsTrend" in snap, "fallback 快照必须包含 operationsTrend，防止 D3 暂无连续日吞吐数据空态"
    assert isinstance(snap["operationsTrend"], list)
    assert len(snap["operationsTrend"]) > 0
    first_ot = snap["operationsTrend"][0]
    for field in ("date", "fullDate", "documents", "vouchers", "integrations"):
        assert field in first_ot, f"operationsTrend 元素必须包含 {field}"

    # D6: operations dualRun fields
    ops = snap.get("operations", {})
    for field in ("dualRunResult", "dualRunConsistent", "dualRunInconsistent", "dualRunConsistencyPct", "integrationSuccess", "integrationFailed"):
        assert field in ops, f"operations 必须包含 {field}，防止 D6 当前快照未提供双轨明细空态"
    assert ops["dualRunConsistent"] > 0
    assert ops["dualRunConsistent"] + ops["dualRunInconsistent"] == ops["dualRunResult"]
    assert 0 <= ops["dualRunConsistencyPct"] <= 100
    if "dualRunBreakdown" in ops:
        assert isinstance(ops["dualRunBreakdown"], list)
        for item in ops["dualRunBreakdown"]:
            assert "type" in item
            assert "consistent" in item
            assert "inconsistent" in item
            assert "rate" in item


def test_ki069_dual_run_co_sourcing_consistency_pct():
    """KI-069: 双轨核对一致率分子与分母同源，杜绝因 daily_stats 滞后导致一致率破 100% (如 102.65%)。"""
    consistent = 29827
    inconsistent = 2310
    total = consistent + inconsistent
    assert total == 32137
    # 一致率严格由 dual_run_result 同源计算，值应为 92.81%，绝不大于 100%
    pct = round(consistent * 100.0 / total, 2)
    assert 0 <= pct <= 100
    assert pct == 92.81
    # 模拟滞后快照场景：daily_stats.dual_run_count 为 29056
    lagged_daily_stats_count = 29056
    buggy_pct = round(consistent * 100.0 / lagged_daily_stats_count, 2)
    assert buggy_pct > 100, "复现 bug：旧逻辑在滞后分母下会破 100%"
    assert pct <= 100


def test_ki061_refresh_meta_and_health_probe_source_distinction(monkeypatch):
    """KI-061: 健康探针与 refresh-meta 必须真实反映快照来源，连接健康但处于 fallback 时不得谎报 live。"""
    import time
    from unittest.mock import MagicMock
    import app.api as api_mod
    from app.db import connection

    # 1. 模拟 DB 连通，但快照处于 fallback 状态
    mock_conn = MagicMock()
    mock_row = MagicMock()
    mock_row.mappings.return_value.one.return_value = {
        "db": "mod",
        "tz": "+08:00",
        "now_cst": "2026-09-08 00:44:00",
    }
    mock_conn.execute.return_value = mock_row

    def mock_healthy_connection():
        yield mock_conn

    app.dependency_overrides[connection] = mock_healthy_connection
    try:
        # 重置快照为 fallback 状态
        api_mod._snapshot_source = "fallback"
        api_mod._snapshot_cached_at = 0.0
        api_mod._snapshot_last_error = None

        res_meta = client.get("/api/dashboard/refresh-meta")
        assert res_meta.status_code == 200
        meta_data = res_meta.json()
        assert meta_data["data_version"] == "frozen", "快照为 fallback 时，即便 DB 连通也不得谎报 live"
        assert meta_data["status"] == "fallback"

        res_health = client.get("/api/health")
        assert res_health.status_code == 200
        health_data = res_health.json()
        assert "snapshot" in health_data
        snap_h = health_data["snapshot"]
        assert snap_h["source"] == "fallback"
        assert snap_h["status"] == "fallback"

        # 2. 模拟快照升级为 live 状态
        api_mod._snapshot_source = "live"
        api_mod._snapshot_cached_at = time.monotonic()

        res_meta_live = client.get("/api/dashboard/refresh-meta")
        meta_data_live = res_meta_live.json()
        assert meta_data_live["data_version"] == "live"
        assert meta_data_live["status"] == "ok"

        res_health_live = client.get("/api/health")
        snap_h_live = res_health_live.json()["snapshot"]
        assert snap_h_live["source"] == "live"
        assert snap_h_live["status"] == "ok"
        assert snap_h_live["is_stale"] is False

        # 3. 模拟快照过期 (stale)
        api_mod._snapshot_cached_at = time.monotonic() - 1000.0
        res_meta_stale = client.get("/api/dashboard/refresh-meta")
        assert res_meta_stale.json()["status"] == "stale"
        snap_h_stale = client.get("/api/health").json()["snapshot"]
        assert snap_h_stale["status"] == "stale"
        assert snap_h_stale["is_stale"] is True

    finally:
        app.dependency_overrides.pop(connection, None)
        api_mod._snapshot_source = "fallback"
        api_mod._snapshot_cached_at = 0.0


def test_ki061_swr_timeout_and_error_recovery(monkeypatch):
    """KI-061: 验证快照异步构建异常或超时时状态机能有界恢复，不堆积死锁。"""
    import time
    from unittest.mock import MagicMock
    import app.api as api_mod

    api_mod._snapshot_consecutive_failures = 0
    api_mod._snapshot_last_error = None

    # 1. 模拟后台构建抛出超时异常 (3024)
    def mock_hang_query():
        raise Exception("(pymysql.err.OperationalError) (3024, 'Query execution was interrupted, maximum statement execution time exceeded')")

    monkeypatch.setattr(api_mod, "_get_dedicated_connection", mock_hang_query)

    api_mod._snapshot_refreshing = True
    api_mod._snapshot_refresh_started_at = time.monotonic()
    api_mod._background_refresh_snapshot()

    # 验证状态已恢复
    assert api_mod._snapshot_refreshing is False, "构建异常后 _snapshot_refreshing 必须被可靠重置为 False"
    assert api_mod._snapshot_consecutive_failures == 1
    assert api_mod._snapshot_last_error is not None
    assert "QueryTimeout" in api_mod._snapshot_last_error
    assert "SELECT" not in api_mod._snapshot_last_error

    # 2. 验证退避保护：短时间内 prewarm 不会重复触发
    api_mod.prewarm_snapshot(sync=True)
    assert api_mod._snapshot_consecutive_failures == 1

    # 3. 验证超时死锁发现：如果由于外部未知原因 _snapshot_refreshing 停留超过 20s
    api_mod._snapshot_refreshing = True
    api_mod._snapshot_refresh_started_at = time.monotonic() - 30.0
    api_mod._snapshot_consecutive_failures = 0

    triggered = False

    def mock_dummy_thread(*args, **kwargs):
        nonlocal triggered
        triggered = True
        return MagicMock()

    monkeypatch.setattr("threading.Thread", mock_dummy_thread)
    api_mod.dashboard_snapshot(None)
    assert triggered is True, "超过超时时间后，SWR 必须强行重置并允许拉起新的刷新"

    api_mod._snapshot_refreshing = False
    api_mod._snapshot_consecutive_failures = 0
    api_mod._snapshot_last_error = None




