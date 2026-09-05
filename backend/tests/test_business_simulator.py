"""
业务模拟器安全门禁测试

覆盖验收标准中要求的六个场景：
  TC-01  默认禁用：未设置 MOD_SIMULATOR_ENABLED 时 load_simulator_config 返回 enabled=False
  TC-02  显式启用：MOD_SIMULATOR_ENABLED=true + MOD_DB_WRITE_URL 均设置时返回 enabled=True
  TC-03  缺少写库 URL：启用但无 MOD_DB_WRITE_URL 时 fail-closed（SimulatorConfigError）
  TC-04  只读状态：模拟器未启动时 get_simulator_instance() 返回 None，状态接口不创建引擎
  TC-05  手动 tick 接口不存在：/api/simulator/tick POST 应返回 404 或 405
  TC-06  错误信息不泄露凭据：SimulatorConfigError 消息不含 URL、密码或主机地址

所有测试均不连接真实数据库（全部使用 mock/fake）。
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------

def _clean_modules(*mod_names: str) -> None:
    """从 sys.modules 移除指定模块，确保重新 import 时不读缓存。"""
    for name in list(sys.modules.keys()):
        for prefix in mod_names:
            if name == prefix or name.startswith(prefix + "."):
                sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# TC-01  默认禁用
# ---------------------------------------------------------------------------

class TestTC01DefaultDisabled:
    """未设置 MOD_SIMULATOR_ENABLED 时模拟器应处于禁用状态。"""

    def test_enabled_false_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("MOD_SIMULATOR_ENABLED", raising=False)
        monkeypatch.delenv("MOD_DB_WRITE_URL", raising=False)

        _clean_modules("app.simulator_config")
        from app.simulator_config import load_simulator_config

        cfg = load_simulator_config()
        assert cfg.enabled is False

    def test_enabled_false_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("MOD_SIMULATOR_ENABLED", "")
        monkeypatch.delenv("MOD_DB_WRITE_URL", raising=False)

        _clean_modules("app.simulator_config")
        from app.simulator_config import load_simulator_config

        cfg = load_simulator_config()
        assert cfg.enabled is False

    def test_enabled_false_when_arbitrary_string(self, monkeypatch):
        """非白名单的任意字符串（如 'yes_please', '1.0', 'TRUE'）均视为禁用。
        
        注：大小写不敏感，所以 'TRUE'/'True' 仍属白名单；
        这里测试真正任意字符串（不在白名单内）。
        """
        for bad_val in ("on", "enabled", "y", "ok", "1.0", "yes_please", "false"):
            monkeypatch.setenv("MOD_SIMULATOR_ENABLED", bad_val)
            _clean_modules("app.simulator_config")
            from app.simulator_config import load_simulator_config

            cfg = load_simulator_config()
            assert cfg.enabled is False, f"应禁用，但对值 {bad_val!r} 返回了 enabled=True"


# ---------------------------------------------------------------------------
# TC-02  显式启用
# ---------------------------------------------------------------------------

class TestTC02ExplicitEnable:
    """MOD_SIMULATOR_ENABLED=true 且 MOD_DB_WRITE_URL 设置时应返回 enabled=True。"""

    @pytest.mark.parametrize("truthy", ["true", "True", "TRUE", "1", "yes", "YES"])
    def test_enabled_true_with_all_whitelist_values(self, monkeypatch, truthy):
        monkeypatch.setenv("MOD_SIMULATOR_ENABLED", truthy)
        monkeypatch.setenv("MOD_DB_WRITE_URL", "mysql+pymysql://fake_user:fake_pass@localhost/fake_db")

        _clean_modules("app.simulator_config")
        from app.simulator_config import load_simulator_config

        cfg = load_simulator_config()
        assert cfg.enabled is True

    def test_db_write_url_is_returned_correctly(self, monkeypatch):
        expected_url = "mysql+pymysql://fake_user:fake_pass@fake_host:3306/fake_db"
        monkeypatch.setenv("MOD_SIMULATOR_ENABLED", "true")
        monkeypatch.setenv("MOD_DB_WRITE_URL", expected_url)

        _clean_modules("app.simulator_config")
        from app.simulator_config import load_simulator_config

        cfg = load_simulator_config()
        assert cfg.db_write_url == expected_url


# ---------------------------------------------------------------------------
# TC-03  缺少写库 URL → fail-closed
# ---------------------------------------------------------------------------

class TestTC03MissingWriteUrlFailClosed:
    """启用模拟器但缺少 MOD_DB_WRITE_URL 时必须抛出 SimulatorConfigError。"""

    def test_raises_when_url_not_set(self, monkeypatch):
        monkeypatch.setenv("MOD_SIMULATOR_ENABLED", "true")
        monkeypatch.delenv("MOD_DB_WRITE_URL", raising=False)

        _clean_modules("app.simulator_config")
        from app.simulator_config import SimulatorConfigError, load_simulator_config

        with pytest.raises(SimulatorConfigError):
            load_simulator_config()

    def test_raises_when_url_is_empty(self, monkeypatch):
        monkeypatch.setenv("MOD_SIMULATOR_ENABLED", "true")
        monkeypatch.setenv("MOD_DB_WRITE_URL", "   ")  # 纯空白

        _clean_modules("app.simulator_config")
        from app.simulator_config import SimulatorConfigError, load_simulator_config

        with pytest.raises(SimulatorConfigError):
            load_simulator_config()

    def test_error_is_simulator_config_error_subclass(self, monkeypatch):
        monkeypatch.setenv("MOD_SIMULATOR_ENABLED", "true")
        monkeypatch.delenv("MOD_DB_WRITE_URL", raising=False)

        _clean_modules("app.simulator_config")
        from app.simulator_config import load_simulator_config

        with pytest.raises(ValueError):  # SimulatorConfigError 是 ValueError 子类
            load_simulator_config()


# ---------------------------------------------------------------------------
# TC-04  只读状态：未启动时 get_simulator_instance() 返回 None
# ---------------------------------------------------------------------------

class TestTC04ReadOnlyStatus:
    """模拟器未启动时状态查询应返回 None，不应触发引擎创建。"""

    def test_get_simulator_instance_returns_none_initially(self):
        """直接测试 business_simulator 模块的 get_simulator_instance。"""
        _clean_modules("app.business_simulator")
        import app.business_simulator as bs_mod

        # 重置全局单例（模拟"从未启动"状态）
        bs_mod._simulator_instance = None
        result = bs_mod.get_simulator_instance()
        assert result is None

    def test_status_endpoint_returns_disabled_when_no_instance(self):
        """
        通过 FastAPI TestClient 调用 GET /api/simulator/status，
        在模拟器未启动时应返回 enabled=false。
        """
        # 使用 mock 隔离数据库依赖
        _clean_modules("app.business_simulator", "app.api", "app.main")

        with patch.dict("os.environ", {
            "MOD_SIMULATOR_ENABLED": "",
            "MOD_DB_WRITE_URL": "",
        }, clear=False):
            # mock DB 连接依赖（避免连接真实数据库）
            mock_conn = None  # connection 返回 None 触发 fallback 路径

            with patch("app.db.connection", return_value=mock_conn):
                import app.business_simulator as bs_mod
                bs_mod._simulator_instance = None  # 确保未启动

                from app.api import router
                from fastapi import FastAPI
                from fastapi.testclient import TestClient

                test_app = FastAPI()
                test_app.include_router(router)
                client = TestClient(test_app, raise_server_exceptions=True)

                resp = client.get("/api/simulator/status")
                assert resp.status_code == 200
                data = resp.json()
                assert data["enabled"] is False


# ---------------------------------------------------------------------------
# TC-05  POST /api/simulator/tick 接口不存在
# ---------------------------------------------------------------------------

class TestTC05TickEndpointRemoved:
    """公开写入口 POST /api/simulator/tick 应已被删除（404 或 405）。"""

    def test_post_simulator_tick_not_found(self):
        _clean_modules("app.business_simulator", "app.api", "app.main")

        with patch.dict("os.environ", {
            "MOD_SIMULATOR_ENABLED": "",
        }, clear=False):
            with patch("app.db.connection", return_value=None):
                import app.business_simulator as bs_mod
                bs_mod._simulator_instance = None

                from app.api import router
                from fastapi import FastAPI
                from fastapi.testclient import TestClient

                test_app = FastAPI()
                test_app.include_router(router)
                client = TestClient(test_app, raise_server_exceptions=False)

                resp = client.post("/api/simulator/tick")
                # 接口已删除，期望 404（路由不存在）或 405（方法不允许）
                assert resp.status_code in (404, 405), (
                    f"期望 404/405，但得到 {resp.status_code}。"
                    "POST /api/simulator/tick 写入口应已被删除。"
                )


# ---------------------------------------------------------------------------
# TC-06  错误信息不泄露凭据
# ---------------------------------------------------------------------------

class TestTC06ErrorNoCredentialLeak:
    """SimulatorConfigError 的错误信息不得包含 URL、密码、主机地址等凭据。"""

    # 常见凭据模式列表
    CREDENTIAL_PATTERNS = [
        "mysql+pymysql://",
        "mysql://",
        "postgres://",
        "@10.",
        "@192.",
        "@172.",
        "password",
        "passwd",
        "secret",
        "token",
        "Nexus",
        "dbadmin",
        "3306",
    ]

    def test_error_message_does_not_leak_credentials(self, monkeypatch):
        monkeypatch.setenv("MOD_SIMULATOR_ENABLED", "true")
        monkeypatch.delenv("MOD_DB_WRITE_URL", raising=False)

        _clean_modules("app.simulator_config")
        from app.simulator_config import SimulatorConfigError, load_simulator_config

        try:
            load_simulator_config()
            pytest.fail("应抛出 SimulatorConfigError 但未抛出")
        except SimulatorConfigError as exc:
            err_msg = str(exc).lower()
            for pattern in self.CREDENTIAL_PATTERNS:
                assert pattern.lower() not in err_msg, (
                    f"错误信息泄露了凭据模式 {pattern!r}：\n{exc}"
                )

    def test_error_message_is_helpful_without_credentials(self, monkeypatch):
        """错误信息应提及缺少的环境变量名，以便运维人员排查。"""
        monkeypatch.setenv("MOD_SIMULATOR_ENABLED", "true")
        monkeypatch.delenv("MOD_DB_WRITE_URL", raising=False)

        _clean_modules("app.simulator_config")
        from app.simulator_config import SimulatorConfigError, load_simulator_config

        try:
            load_simulator_config()
            pytest.fail("应抛出 SimulatorConfigError 但未抛出")
        except SimulatorConfigError as exc:
            # 错误信息应提及变量名（便于排查），但不含实际值
            assert "MOD_DB_WRITE_URL" in str(exc), (
                "错误信息应提及 MOD_DB_WRITE_URL 变量名，以便运维排查。"
            )
