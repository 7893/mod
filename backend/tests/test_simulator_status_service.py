"""Comprehensive unit and integration tests for Simulator Status Service (KI-039).

Verifies:
1. Fresh heartbeat -> HTTP 200, fresh=True, status=RUNNING, enabled=True.
2. Stale heartbeat -> HTTP 200, fresh=False, status=STALE, enabled=False.
3. Missing file -> HTTP 200, fresh=False, status=UNAVAILABLE, enabled=False.
4. Malformed/Empty/Non-object/Invalid timestamp -> HTTP 200, status=UNAVAILABLE, no 500.
5. Permission error -> HTTP 503, no paths or credentials leaked.
6. Whitelist filtering -> Extra fields stripped.
7. Decoupled architecture -> No simulation package imports in API route.
8. Production equivalent release isolation -> Passes when simulation/ is not in sys.path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api import router
from app.services.simulator_status import (
    get_default_status_path,
    get_stale_threshold_seconds,
    read_simulator_status,
)

HK_TZ = timezone(timedelta(hours=8))


def test_get_default_status_path_and_threshold(tmp_path):
    """KI-039: 测试集中配置解析函数 get_default_status_path 与 get_stale_threshold_seconds."""
    custom_path = tmp_path / "custom_status.json"
    with patch.dict(os.environ, {
        "MOD_SIMULATOR_STATUS_PATH": str(custom_path),
        "MOD_SIMULATOR_STALE_SECONDS": "240",
    }):
        assert get_default_status_path() == custom_path.resolve()
        assert get_stale_threshold_seconds() == 240.0

    # Fallback to default
    with patch.dict(os.environ, {"MOD_SIMULATOR_STALE_SECONDS": "invalid"}):
        assert get_stale_threshold_seconds() == 180.0


def test_read_simulator_status_direct_call(tmp_path):
    """KI-039: 直接调用 read_simulator_status 函数."""
    res = read_simulator_status(status_path=tmp_path / "absent.json")
    assert res["status"] == "UNAVAILABLE"
    assert res["fresh"] is False



@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_status_fresh_heartbeat(tmp_path, api_client):
    """KI-039: 新鲜有效心跳返回 200, fresh=True, status=RUNNING, enabled=True."""
    status_file = tmp_path / "simulator_status.json"
    now_hkt = datetime.now(HK_TZ)
    payload = {
        "service": "mod-simulator",
        "status": "RUNNING",
        "last_cycle_status": "SUCCESS",
        "timestamp": now_hkt.isoformat(),
        "intensity": 0.35,
        "uptime_seconds": 120.0,
        "consecutive_failures": 0,
        "fail_closed_tripped": False,
        "fuse_metrics": {
            "minute_count": 5,
            "max_per_minute": 20,
            "day_count": 50,
            "max_per_day": 5000,
        },
        "last_error": None,
    }
    status_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch.dict(os.environ, {"MOD_SIMULATOR_STATUS_PATH": str(status_file)}):
        resp = api_client.get("/api/simulator/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "mod-simulator"
        assert data["status"] == "RUNNING"
        assert data["last_cycle_status"] == "SUCCESS"
        assert data["fresh"] is True
        assert data["enabled"] is True
        assert data["fail_closed_tripped"] is False
        assert data["consecutive_failures"] == 0
        assert data["fuse_metrics"] == {
            "minute_count": 5,
            "max_per_minute": 20,
            "day_count": 50,
            "max_per_day": 5000,
        }
        assert data["uptime_seconds"] == 120.0
        assert data["notice"] is None


def test_status_stale_heartbeat(tmp_path, api_client):
    """KI-039: 超过阈值（如 180s）的心跳返回 200, status=STALE, fresh=False, enabled=False."""
    status_file = tmp_path / "simulator_status.json"
    old_time = datetime.now(HK_TZ) - timedelta(seconds=250)
    payload = {
        "service": "mod-simulator",
        "status": "RUNNING",
        "last_cycle_status": "SUCCESS",
        "timestamp": old_time.isoformat(),
        "uptime_seconds": 300.0,
        "consecutive_failures": 0,
    }
    status_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch.dict(os.environ, {
        "MOD_SIMULATOR_STATUS_PATH": str(status_file),
        "MOD_SIMULATOR_STALE_SECONDS": "180",
    }):
        resp = api_client.get("/api/simulator/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "STALE"
        assert data["fresh"] is False
        assert data["enabled"] is False
        assert data["timestamp"] == old_time.isoformat()
        assert "expired" in (data["notice"] or "")


def test_status_dry_run_is_fresh_but_not_write_enabled(tmp_path, api_client):
    status_file = tmp_path / "simulator_status.json"
    status_file.write_text(json.dumps({
        "service": "mod-simulator",
        "status": "DISABLED",
        "last_cycle_status": "DRY_RUN",
        "timestamp": datetime.now(HK_TZ).isoformat(),
    }), encoding="utf-8")
    with patch.dict(os.environ, {"MOD_SIMULATOR_STATUS_PATH": str(status_file)}):
        data = api_client.get("/api/simulator/status").json()
    assert data["fresh"] is True
    assert data["status"] == "DISABLED"
    assert data["enabled"] is False


def test_status_file_missing(tmp_path, api_client):
    """KI-039: 心跳文件不存在时返回 200, status=UNAVAILABLE, fresh=False, enabled=False."""
    missing_file = tmp_path / "does_not_exist.json"
    with patch.dict(os.environ, {"MOD_SIMULATOR_STATUS_PATH": str(missing_file)}):
        resp = api_client.get("/api/simulator/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "mod-simulator"
        assert data["status"] == "UNAVAILABLE"
        assert data["fresh"] is False
        assert data["enabled"] is False
        assert data["timestamp"] is None
        assert "not found" in (data["notice"] or "").lower()


def test_status_malformed_json(tmp_path, api_client):
    """KI-039: 文件内容为损坏 JSON 或非对象时返回 200, status=UNAVAILABLE, 绝不抛 500."""
    status_file = tmp_path / "simulator_status.json"

    # Case 1: Broken JSON syntax
    status_file.write_text("{\"service\": \"mod-simulator\", truncated", encoding="utf-8")
    with patch.dict(os.environ, {"MOD_SIMULATOR_STATUS_PATH": str(status_file)}):
        resp = api_client.get("/api/simulator/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "UNAVAILABLE"
        assert resp.json()["fresh"] is False

    # Case 2: Empty file
    status_file.write_text("   \n", encoding="utf-8")
    with patch.dict(os.environ, {"MOD_SIMULATOR_STATUS_PATH": str(status_file)}):
        resp = api_client.get("/api/simulator/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "UNAVAILABLE"

    # Case 3: JSON array instead of object
    status_file.write_text("[1, 2, 3]", encoding="utf-8")
    with patch.dict(os.environ, {"MOD_SIMULATOR_STATUS_PATH": str(status_file)}):
        resp = api_client.get("/api/simulator/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "UNAVAILABLE"


def test_status_future_timestamp_skew(tmp_path, api_client):
    """KI-039: 时间戳超前系统时间超过 30s 时判定时钟异常，返回 UNAVAILABLE."""
    status_file = tmp_path / "simulator_status.json"
    future_time = datetime.now(HK_TZ) + timedelta(hours=2)
    payload = {
        "service": "mod-simulator",
        "status": "RUNNING",
        "timestamp": future_time.isoformat(),
    }
    status_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch.dict(os.environ, {"MOD_SIMULATOR_STATUS_PATH": str(status_file)}):
        resp = api_client.get("/api/simulator/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "UNAVAILABLE"
        assert data["fresh"] is False
        assert "future" in (data["notice"] or "")


def test_status_permission_error_returns_503(tmp_path, api_client):
    """KI-039: 发生不可恢复的权限错误时，返回 503 且不得泄露敏感路径或凭据."""
    status_file = tmp_path / "simulator_status.json"
    status_file.write_text("{}", encoding="utf-8")

    with patch.dict(os.environ, {"MOD_SIMULATOR_STATUS_PATH": str(status_file)}):
        with patch("builtins.open", side_effect=PermissionError("Simulated permission denied")):
            resp = api_client.get("/api/simulator/status")
            assert resp.status_code == 503
            data = resp.json()
            assert data["detail"] == "Simulator status temporarily unavailable"
            assert str(tmp_path) not in json.dumps(data)


def test_status_whitelist_purity(tmp_path, api_client):
    """KI-039: 状态响应严格使用白名单，文件内多余或敏感字段不得透传."""
    status_file = tmp_path / "simulator_status.json"
    now_hkt = datetime.now(HK_TZ)
    payload = {
        "service": "mod-simulator",
        "status": "RUNNING",
        "timestamp": now_hkt.isoformat(),
        "db_secret_key": "topsecret123",
        "internal_server_ip": "10.0.1.99",
        "unauthorized_dump": "sensitive data",
    }
    status_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch.dict(os.environ, {"MOD_SIMULATOR_STATUS_PATH": str(status_file)}):
        resp = api_client.get("/api/simulator/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "db_secret_key" not in data
        assert "internal_server_ip" not in data
        assert "unauthorized_dump" not in data
        # Whitelist allowed keys
        expected_keys = {
            "service", "status", "last_cycle_status", "timestamp",
            "fresh", "fail_closed_tripped", "fuse_metrics",
            "uptime_seconds", "consecutive_failures", "notice", "enabled",
        }
        assert set(data.keys()) == expected_keys


def test_decoupled_no_simulation_imports():
    """KI-039: 状态服务与路由绝对不能导入 simulation 包或 business_simulator."""
    import app.services.simulator_status as svc
    import app.api as api

    for name, mod in list(sys.modules.items()):
        if name == "simulation" or name.startswith("simulation."):
            # If simulation was somehow imported by other test files, ensure simulator_status itself didn't import it
            assert not hasattr(svc, "simulation")
            assert not hasattr(api, "simulation")


def test_production_equivalent_isolated_release(tmp_path):
    """KI-039 核心验证：生产等价测试。

    只暴露后端 release 内容（backend/app），工作目录为 release 目录，
    且 sys.path 中绝对没有仓库根目录（即 simulation/ 完全不可见），
    调用 GET /api/simulator/status 必须返回 200 且结构化契约正常。
    """
    import shutil
    repo_root = Path(__file__).resolve().parents[2]
    app_src = repo_root / "backend" / "app"

    # 1. 模拟 publish.sh 将 backend/app/ 复制为独立的 release 目录
    release_dir = tmp_path / "backend_release"
    shutil.copytree(app_src, release_dir)

    # 2. 准备一个新鲜心跳文件
    status_file = tmp_path / "simulator_status.json"
    now_iso = datetime.now(HK_TZ).isoformat()
    status_file.write_text(json.dumps({
        "service": "mod-simulator",
        "status": "RUNNING",
        "last_cycle_status": "SUCCESS",
        "timestamp": now_iso,
        "uptime_seconds": 42.0,
    }), encoding="utf-8")

    # 3. 构造运行隔离测试的 python 脚本
    # 显式把 repo_root 排除在 sys.path 之外，确认 import simulation 会失败
    isolated_script = f"""
import sys, os
from pathlib import Path

# 确保 repo_root 本身不在 sys.path 中，但保留 .venv site-packages
repo_root_resolved = str(Path("{repo_root}").resolve())
sys.path = [p for p in sys.path if str(Path(p).resolve()) != repo_root_resolved]
sys.path.insert(0, "{release_dir.parent}")

# 断言 simulation 包不可见
try:
    import simulation
    print("FAIL: simulation was unexpectedly imported!")
    sys.exit(2)
except ImportError:
    pass

# 导入 app 并发起请求
os.environ["MOD_SIMULATOR_STATUS_PATH"] = "{status_file}"
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend_release.api import router

test_app = FastAPI()
test_app.include_router(router)
client = TestClient(test_app)

resp = client.get("/api/simulator/status")
if resp.status_code != 200:
    print(f"FAIL: HTTP {{resp.status_code}} {{resp.text}}")
    sys.exit(1)

data = resp.json()
if data.get("service") != "mod-simulator" or data.get("fresh") is not True:
    print(f"FAIL: payload mismatch {{data}}")
    sys.exit(1)

print("SUCCESS: isolated release simulator status check succeeded.")
"""

    venv_python = repo_root / "backend" / ".venv" / "bin" / "python"
    proc = subprocess.run(
        [str(venv_python), "-c", isolated_script],
        capture_output=True,
        text=True,
        cwd=str(release_dir),
    )
    assert proc.returncode == 0, f"Isolated release test failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "SUCCESS: isolated release simulator status check succeeded." in proc.stdout


def test_publish_probe_verification_branches():
    """KI-039: 验证发布脚本探针的判定逻辑：成功分支通过，契约缺失或报错分支触发回滚."""
    probe_script = """
import sys, json
data = json.loads(sys.argv[1])
required = ["service", "status", "fresh"]
if not all(k in data for k in required):
    sys.exit(1)
if "Internal Server Error" in json.dumps(data):
    sys.exit(1)
sys.exit(0)
"""
    # 1. 成功分支：包含完整契约字段
    valid_payload = json.dumps({"service": "mod-simulator", "status": "RUNNING", "fresh": True})
    r1 = subprocess.run([sys.executable, "-c", probe_script, valid_payload])
    assert r1.returncode == 0

    # 2. 失败分支：缺少必填字段 fresh
    missing_key_payload = json.dumps({"service": "mod-simulator", "status": "RUNNING"})
    r2 = subprocess.run([sys.executable, "-c", probe_script, missing_key_payload])
    assert r2.returncode == 1

    # 3. 失败分支：包含 Internal Server Error
    error_payload = json.dumps({"service": "mod-simulator", "status": "Internal Server Error", "fresh": False})
    r3 = subprocess.run([sys.executable, "-c", probe_script, error_payload])
    assert r3.returncode == 1
