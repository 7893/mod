"""Unit tests for realistic business simulation engine runtime service (Step 3)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from app.simulation.construction_models import (
    ConstructionTaskFootprint,
    DataReadinessEventFootprint,
    DataReadinessRecordFootprint,
)
from app.simulation.engine_context import (
    ConstructionBaseline,
    IdAllocator,
    SimulationBaseline,
)
from app.simulation.footprint_models import (
    DocumentFootprint,
    DocumentLineFootprint,
    EventFootprint,
    IntegrationFootprint,
    LinkFootprint,
    VoucherFootprint,
    VoucherLineFootprint,
)
from app.simulation.runtime_service import (
    FailClosedManager,
    PostCycleSelfChecker,
    RateLimitFuse,
    SimulatorRuntimeConfig,
    SimulatorRuntimeService,
)

HK_TZ = ZoneInfo("Asia/Hong_Kong")


def _create_sample_fast_event(
    amount: Decimal = Decimal("1500.50"),
    submit_time: datetime = datetime(2026, 9, 5, 9, 30, 0),
    approve_time: datetime = datetime(2026, 9, 5, 10, 15, 0),
    gen_time: datetime = datetime(2026, 9, 5, 10, 20, 0),
    int_time: datetime = datetime(2026, 9, 5, 10, 22, 0),
) -> EventFootprint:
    doc_lines = [
        DocumentLineFootprint(id=101, doc_id=1, item_name="差旅交通费", amount=Decimal("1000.00"), quantity=1),
        DocumentLineFootprint(id=102, doc_id=1, item_name="住宿费", amount=Decimal("500.50"), quantity=1),
    ]
    doc = DocumentFootprint(
        id=1,
        org_id=10,
        type="费用报销单",
        doc_no="DOC-TEST001",
        applicant="张三",
        nature="正式业务",
        amount=amount,
        submit_time=submit_time,
        approve_time=approve_time,
        status="处理完成",
        lines=doc_lines,
    )
    vch_lines = [
        VoucherLineFootprint(
            id=201, voucher_id=1, subject_code="1002", subject_name="银行存款",
            debit=amount, credit=Decimal("0.00")
        ),
        VoucherLineFootprint(
            id=202, voucher_id=1, subject_code="2202", subject_name="应付账款",
            debit=Decimal("0.00"), credit=amount
        ),
    ]
    vch = VoucherFootprint(
        id=1,
        org_id=10,
        voucher_no="V-TEST001",
        type="记账凭证",
        gen_time=gen_time,
        int_time=int_time,
        status="已集成",
        debit=amount,
        credit=amount,
        lines=vch_lines,
    )
    link = LinkFootprint(doc_id=1, voucher_id=1)
    integ = IntegrationFootprint(
        id=301,
        voucher_id=1,
        status="SUCCESS",
        retry_count=0,
        error_code="",
        error_message="成功",
        integration_time=int_time,
    )
    return EventFootprint(document=doc, voucher=vch, link=link, integration=integ)


def test_fail_closed_manager(tmp_path):
    flag_file = tmp_path / "fail_closed.flag"
    audit_file = tmp_path / "audit.log"
    mgr = FailClosedManager(flag_path=flag_file, audit_log_path=audit_file)

    assert not mgr.is_tripped()
    assert mgr.get_trip_info() is None

    mgr.trip("Test critical assertion failed", {"cycle": 42})
    assert mgr.is_tripped()
    info = mgr.get_trip_info()
    assert info is not None
    assert info["tripped"] is True
    assert "Test critical assertion" in info["reason"]
    assert info["details"]["cycle"] == 42
    assert audit_file.exists()

    cleared = mgr.clear()
    assert cleared is True
    assert not mgr.is_tripped()
    assert mgr.get_trip_info() is None


def test_rate_limit_fuse_minute_and_day():
    fuse = RateLimitFuse(max_per_minute=5, max_per_day=10)
    t0 = datetime(2026, 9, 5, 10, 0, 0)

    # Within minute limit
    ok, msg = fuse.can_produce(t0, count=3)
    assert ok is True
    fuse.record(t0, count=3)

    # Exceed minute limit
    ok, msg = fuse.can_produce(t0, count=3)
    assert ok is False
    assert "Minute hard cap reached" in msg

    # Next minute rollover
    t1 = datetime(2026, 9, 5, 10, 1, 0)
    ok, msg = fuse.can_produce(t1, count=4)
    assert ok is True
    fuse.record(t1, count=4)

    # Now daily total is 7 / 10
    ok, msg = fuse.can_produce(t1, count=4)
    assert ok is False
    assert "Daily hard cap reached" in msg or "Minute hard cap reached" in msg

    t2 = datetime(2026, 9, 5, 10, 2, 0)
    ok, msg = fuse.can_produce(t2, count=3)
    assert ok is True
    fuse.record(t2, count=3)
    # Total daily is 10 / 10

    t3 = datetime(2026, 9, 5, 10, 3, 0)
    ok, msg = fuse.can_produce(t3, count=1)
    assert ok is False
    assert "Daily hard cap reached" in msg

    # Next day rollover
    t_next_day = datetime(2026, 9, 6, 10, 0, 0)
    ok, msg = fuse.can_produce(t_next_day, count=5)
    assert ok is True


def test_post_cycle_self_checker_fast_movie():
    ev = _create_sample_fast_event()
    ok, msg = PostCycleSelfChecker.check_fast_movie_events(conn=None, events=[ev])
    assert ok is True
    assert msg == ""

    # Line sum mismatch
    ev_line_bad = _create_sample_fast_event()
    ev_line_bad.document.lines[0].amount = Decimal("9999.00")
    ok, msg = PostCycleSelfChecker.check_fast_movie_events(conn=None, events=[ev_line_bad])
    assert ok is False
    assert "Line sum mismatch" in msg

    # Voucher line unbalanced
    ev_vch_bad = _create_sample_fast_event()
    ev_vch_bad.voucher.lines[0].debit = Decimal("9999.00")
    ok, msg = PostCycleSelfChecker.check_fast_movie_events(conn=None, events=[ev_vch_bad])
    assert ok is False
    assert "unbalanced" in msg

    # Time inversion
    ev_time_bad = _create_sample_fast_event()
    ev_time_bad.document.approve_time = datetime(2026, 9, 5, 8, 0, 0)
    ev_time_bad.document.submit_time = datetime(2026, 9, 5, 9, 0, 0)
    ok, msg = PostCycleSelfChecker.check_fast_movie_events(conn=None, events=[ev_time_bad])
    assert ok is False
    assert "Time inversion" in msg


def test_post_cycle_self_checker_construction():
    readiness = DataReadinessRecordFootprint(
        org_id=10,
        batch_id=2,
        static_total=100,
        static_completed=85,
        static_rate="85.0%",
        opening_total=50,
        opening_completed=40,
        opening_rate="80.0%",
        opening_diff_amount=Decimal("0.00"),
        dynamic_total=200,
        dynamic_completed=180,
        dynamic_sync_success=170,
        dynamic_sync_fail=10,
        dynamic_sync_pending=20,
        dynamic_rate="85.0%",
        overall_status="收集中",
        last_sync_time="2026-09-05 10:00:00",
    )
    task = ConstructionTaskFootprint(
        id=101,
        org_id=10,
        name="存货与物料编码分类标准对齐",
        type="基础数据",
        owner="张三",
        plan_time=date(2026, 9, 10),
        actual_time=None,
        status="进行中",
        progress=85,
        update_time=date(2026, 9, 5),
    )
    ev = DataReadinessEventFootprint(
        org_id=10,
        batch_id=2,
        event_date=date(2026, 9, 5),
        readiness=readiness,
        associated_task=task,
    )
    ok, msg = PostCycleSelfChecker.check_construction_events(conn=None, events=[ev])
    assert ok is True
    assert msg == ""

    # Bad event
    bad_obj = "not an event object"
    ok, msg = PostCycleSelfChecker.check_construction_events(conn=None, events=[bad_obj])
    assert ok is False
    assert "validation error" in msg


def _mock_fast_baseline() -> SimulationBaseline:
    return SimulationBaseline(
        latest_business_date=datetime(2026, 9, 4, 18, 0, 0),
        online_org_ids=[1],
        org_users={1: [{"name": "张三", "role": "经办人"}]},
        next_ids={
            "business_document": 100,
            "business_document_line": 200,
            "accounting_voucher": 300,
            "accounting_voucher_line": 400,
            "integration_result": 500,
        },
    )


def _mock_construction_baseline() -> ConstructionBaseline:
    return ConstructionBaseline(
        latest_business_date=datetime(2026, 9, 4, 18, 0, 0),
        orgs={1: {"id": 1, "name": "测试单位", "batch_id": 1, "status": "双轨运行中"}},
        orgs_by_status={"双轨运行中": [1]},
        org_users={1: [{"name": "李四", "role": "项目经理"}]},
        next_ids={
            "construction_task": 100,
            "training_record": 200,
            "dual_run_result": 300,
            "data_readiness_record": 400,
            "interface_debug_record": 500,
            "transition_review_record": 600,
            "rollout_batch": 700,
        },
        batches={1: {"id": 1, "name": "第一批次", "status": "双轨运行中"}},
    )


def test_runtime_service_dry_run_cycle(tmp_path):
    config = SimulatorRuntimeConfig(
        max_events_per_minute=20,
        max_events_per_day=5000,
        fail_closed_flag_path=tmp_path / "flag.flag",
        status_file_path=tmp_path / "status.json",
        audit_log_path=tmp_path / "audit.log",
        dry_run=True,
    )
    mock_conn = MagicMock()
    service = SimulatorRuntimeService(config=config, conn=mock_conn, seed=42)
    service._fast_baseline = _mock_fast_baseline()
    service._fast_allocator = IdAllocator(service._fast_baseline.next_ids)
    service._construction_baseline = _mock_construction_baseline()
    service._construction_allocator = IdAllocator(service._construction_baseline.next_ids)

    # Step at Monday 10:00 HKT (intensity is active)
    now_hkt = datetime(2026, 9, 7, 10, 0, 0, tzinfo=HK_TZ)
    res = service.step_cycle(now=now_hkt)

    assert res.status == "DRY_RUN"
    assert res.events_written == 0
    assert res.intensity > 1.0
    assert config.status_file_path.exists()


def test_runtime_service_fail_closed_guard(tmp_path):
    flag = tmp_path / "flag.flag"
    flag.write_text("{\"tripped\": true, \"reason\": \"Manual intervention required\"}", encoding="utf-8")

    config = SimulatorRuntimeConfig(
        fail_closed_flag_path=flag,
        status_file_path=tmp_path / "status.json",
        audit_log_path=tmp_path / "audit.log",
    )
    service = SimulatorRuntimeService(config=config)
    res = service.step_cycle()

    assert res.status == "FAIL_CLOSED"
    assert "Manual clearance required" in res.error


def test_runtime_service_consecutive_failure_trips_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")
    flag = tmp_path / "flag.flag"

    config = SimulatorRuntimeConfig(
        consecutive_failure_threshold=3,
        fail_closed_flag_path=flag,
        status_file_path=tmp_path / "status.json",
        audit_log_path=tmp_path / "audit.log",
        dry_run=False,
    )
    mock_conn = MagicMock()
    service = SimulatorRuntimeService(config=config, conn=mock_conn, seed=42)
    service._fast_baseline = _mock_fast_baseline()
    service._fast_allocator = IdAllocator(service._fast_baseline.next_ids)

    # Force step_cycle to fail during execution by throwing error in check_fast_movie_events
    monkeypatch.setattr(
        PostCycleSelfChecker,
        "check_fast_movie_events",
        lambda conn, events: (False, "Injected critical consistency breach"),
    )

    now_hkt = datetime(2026, 9, 7, 10, 0, 0, tzinfo=HK_TZ)

    # Failure 1
    r1 = service.step_cycle(now=now_hkt)
    assert r1.status == "ERROR"
    assert service.consecutive_failures == 1
    assert not flag.exists()

    # Failure 2
    r2 = service.step_cycle(now=now_hkt)
    assert r2.status == "ERROR"
    assert service.consecutive_failures == 2
    assert not flag.exists()

    # Failure 3 -> Trips fail-closed!
    r3 = service.step_cycle(now=now_hkt)
    assert r3.status == "ERROR"
    assert service.consecutive_failures == 3
    assert flag.exists()

    # Failure 4 -> Service enters FAIL_CLOSED halted mode immediately
    r4 = service.step_cycle(now=now_hkt)
    assert r4.status == "FAIL_CLOSED"


def test_runtime_service_rate_limit_cycle(tmp_path):
    config = SimulatorRuntimeConfig(
        max_events_per_minute=0,  # Force immediate rate limit
        fail_closed_flag_path=tmp_path / "flag.flag",
        status_file_path=tmp_path / "status.json",
        audit_log_path=tmp_path / "audit.log",
    )
    service = SimulatorRuntimeService(config=config, seed=42)
    now_hkt = datetime(2026, 9, 7, 10, 0, 0, tzinfo=HK_TZ)
    res = service.step_cycle(now=now_hkt)

    assert res.status == "RATE_LIMITED"
    assert "Minute hard cap reached" in (res.error or "")
    assert config.status_file_path.exists()


def test_runtime_service_successful_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")

    config = SimulatorRuntimeConfig(
        slow_movie_interval_cycles=2,
        fail_closed_flag_path=tmp_path / "flag.flag",
        status_file_path=tmp_path / "status.json",
        audit_log_path=tmp_path / "audit.log",
        dry_run=False,
    )
    mock_conn = MagicMock()
    service = SimulatorRuntimeService(config=config, conn=mock_conn, seed=42)
    service._fast_baseline = _mock_fast_baseline()
    service._fast_allocator = IdAllocator(service._fast_baseline.next_ids)
    service._construction_baseline = _mock_construction_baseline()
    service._construction_allocator = IdAllocator(service._construction_baseline.next_ids)

    # Mock fast movie writer and check
    mock_res = MagicMock(success=True, written_count=1)
    monkeypatch.setattr("app.simulation.runtime_service.SimulationWriter.write_events", lambda self, evts: mock_res)
    monkeypatch.setattr(PostCycleSelfChecker, "check_fast_movie_events", lambda conn, evts: (True, ""))

    # Cycle 1: Fast movie
    now_hkt = datetime(2026, 9, 7, 10, 0, 0, tzinfo=HK_TZ)
    r1 = service.step_cycle(now=now_hkt)
    assert r1.status == "SUCCESS"
    assert r1.events_written > 0
    assert service.consecutive_failures == 0

    # Mock slow movie writer and check
    c_mock_res = MagicMock(success=True)
    monkeypatch.setattr(
        "app.simulation.runtime_service.ConstructionWriter.write_construction_events",
        lambda self, evts, execute=True: c_mock_res,
    )
    monkeypatch.setattr(PostCycleSelfChecker, "check_construction_events", lambda conn, evts: (True, ""))

    # Cycle 2: Slow movie (cycle_count % 2 == 0)
    r2 = service.step_cycle(now=now_hkt)
    assert r2.status == "SUCCESS"
    assert r2.events_written == 1


def test_runtime_service_run_forever_stop():
    config = SimulatorRuntimeConfig(dry_run=True)
    service = SimulatorRuntimeService(config=config)
    import threading
    stop_event = threading.Event()
    stop_event.set()  # Stop immediately
    service.run_forever(stop_event=stop_event)

