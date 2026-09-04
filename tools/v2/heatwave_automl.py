#!/usr/bin/env python3
"""
heatwave_automl.py — MOD V2 HeatWave AutoML 离线运维工具
==========================================================

功能
----
  status      查询两个模型（回归 / 分类）在 sys.ML_MODEL_METADATA 的状态
  plan        打印特征表 DDL + INSERT SQL（不写入数据库）
  build       构建训练特征表（需 --execute + MOD_HW_ML_ENABLED=true）
  train       训练两个 AutoML 模型（需 --execute + MOD_HW_ML_ENABLED=true）
  score       批量评分并写入结果表（需 --execute + MOD_HW_ML_ENABLED=true）
  predictions 从评分结果表读取预测结果（只读，始终安全）
  run-all     依次执行 build → train → score（需 --execute + MOD_HW_ML_ENABLED=true）

安全约束
--------
- 默认 plan 模式：所有命令均不写入数据库，仅输出拟执行的 SQL。
- 写入操作需同时满足：
    (1) 命令行参数 --execute
    (2) 环境变量 MOD_HW_ML_ENABLED=true
- 数据库连接参数从环境变量读取（不在命令行或代码中暴露凭据）。
- 不操作非 mod_s_v2 的数据库、不触碰 mod_s / modo_db / 生产服务。

环境变量
--------
  MOD_HW_ML_ENABLED   是否允许写入操作（true/false，默认 false）
  MOD_DB_HOST         数据库主机（默认 127.0.0.1）
  MOD_DB_PORT         端口（默认 3306）
  MOD_DB_USER         用户名（默认 mod_user）
  MOD_DB_PASSWORD     密码（从环境变量读取，不回显）
  MOD_DB_NAME         数据库名（默认 mod_s_v2）

用法示例
--------
  # plan 模式（默认，安全，不写入）
  python heatwave_automl.py status
  python heatwave_automl.py plan

  # execute 模式（需显式声明 + 环境变量）
  MOD_HW_ML_ENABLED=true python heatwave_automl.py build --execute
  MOD_HW_ML_ENABLED=true python heatwave_automl.py train --execute
  MOD_HW_ML_ENABLED=true python heatwave_automl.py score --execute
  MOD_HW_ML_ENABLED=true python heatwave_automl.py run-all --execute

  # 只读：读取预测结果
  python heatwave_automl.py predictions
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# 路径修正：允许从 tools/v2/ 直接运行，能 import backend 包
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
_BACKEND_DIR = os.path.join(_REPO_ROOT, "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# ---------------------------------------------------------------------------
# 延迟导入（允许 --help 在无 DB 依赖时正常运行）
# ---------------------------------------------------------------------------


def _get_connection():
    """
    建立 SQLAlchemy 连接到 mod_s_v2 数据库。
    凭据从环境变量读取，不在日志 / 输出中暴露密码。
    返回 (engine, connection) 元组，失败时返回 (None, None)。
    """
    try:
        from sqlalchemy import create_engine  # type: ignore

        host = os.environ.get("MOD_V2_DB_HOST") or os.environ.get("MOD_DB_HOST", "127.0.0.1")
        port = os.environ.get("MOD_V2_DB_PORT") or os.environ.get("MOD_DB_PORT", "3306")
        user = os.environ.get("MOD_V2_DB_USER") or os.environ.get("MOD_DB_USER", "mod_user")
        password = os.environ.get("MOD_V2_DB_PASSWORD") or os.environ.get("MOD_DB_PASSWORD", "")
        dbname = os.environ.get("MOD_V2_DB_NAME") or os.environ.get("MOD_DB_NAME", "mod_s_v2")

        # 安全检查：只允许连接 mod_s_v2，不得误操作其他库
        if dbname != "mod_s_v2":
            _print_error(
                f"安全中止：MOD_DB_NAME={dbname!r}，"
                "本工具仅允许连接 mod_s_v2，请检查环境变量。"
            )
            return None, None

        if not password:
            _print_warn("警告：MOD_DB_PASSWORD 为空，连接可能失败。")

        url = (
            f"mysql+pymysql://{user}:{password}"
            f"@{host}:{port}/{dbname}"
            "?charset=utf8mb4"
        )
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        conn = engine.connect()
        return engine, conn
    except Exception as exc:
        _print_error(f"数据库连接失败：{exc}")
        return None, None


# ---------------------------------------------------------------------------
# 输出工具
# ---------------------------------------------------------------------------


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _print_error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


def _print_warn(msg: str) -> None:
    print(f"[WARN]  {msg}", file=sys.stderr)


def _print_info(msg: str) -> None:
    print(f"[INFO]  {msg}")


# ---------------------------------------------------------------------------
# 子命令处理函数
# ---------------------------------------------------------------------------


def cmd_status(adapter) -> int:
    """查询两个模型的状态（只读）。"""
    _print_info("查询 HeatWave AutoML 模型状态……")
    result = adapter.get_status()
    _print_json(result)
    # 若任何模型 ready 则退出码 0，否则 1（供 shell 检测）
    return 0 if result.get("status") == "ready" else 1


def cmd_plan(adapter) -> int:
    """输出特征表 DDL 和 INSERT SQL（不写入，始终安全）。"""
    _print_info("生成特征表 SQL（plan 模式，不写入数据库）……")
    sql_dict = adapter.get_feature_build_sql()
    print("\n" + "=" * 72)
    print("# 1. 回归特征表 DDL")
    print("=" * 72)
    print(sql_dict["regression_ddl"])
    print("\n" + "=" * 72)
    print("# 2. 回归特征表 INSERT")
    print("=" * 72)
    print(sql_dict["regression_insert"])
    print("\n" + "=" * 72)
    print("# 3. 分类特征表 DDL")
    print("=" * 72)
    print(sql_dict["classifier_ddl"])
    print("\n" + "=" * 72)
    print("# 4. 分类特征表 INSERT")
    print("=" * 72)
    print(sql_dict["classifier_insert"])
    return 0


def cmd_build(adapter) -> int:
    """构建（CREATE + TRUNCATE + INSERT）训练特征表。"""
    mode = "execute" if adapter._write_allowed else "plan"
    _print_info(f"构建训练特征表（mode={mode}）……")
    result = adapter.build_feature_tables()
    _print_json(result)
    if result.get("status") == "done":
        reg = result.get("results", {}).get("regression", {})
        cls_ = result.get("results", {}).get("classifier", {})
        if reg.get("status") == "error" or cls_.get("status") == "error":
            _print_warn("部分特征表构建失败，请检查上方错误信息。")
            return 2
        return 0
    # plan 模式返回 plan 状态，也视为正常退出
    return 0


def cmd_train(adapter) -> int:
    """训练两个 AutoML 模型。"""
    mode = "execute" if adapter._write_allowed else "plan"
    _print_info(f"训练 AutoML 模型（mode={mode}）……")
    if not adapter._write_allowed:
        _print_warn(
            "当前为 plan 模式。若需实际训练，请添加 --execute 参数"
            "并设置 MOD_HW_ML_ENABLED=true。"
        )
    result = adapter.train_models()
    _print_json(result)
    if result.get("status") == "done":
        any_error = any(
            v.get("status") == "error"
            for v in result.get("results", {}).values()
        )
        return 2 if any_error else 0
    return 0


def cmd_score(adapter) -> int:
    """对特征表执行批量评分，写入结果表。"""
    mode = "execute" if adapter._write_allowed else "plan"
    _print_info(f"批量评分（mode={mode}）……")
    if not adapter._write_allowed:
        _print_warn(
            "当前为 plan 模式。若需实际评分，请添加 --execute 参数"
            "并设置 MOD_HW_ML_ENABLED=true。"
        )
    result = adapter.run_batch_scoring()
    _print_json(result)
    if result.get("status") == "done":
        any_error = any(
            v.get("status") == "error"
            for v in result.get("results", {}).values()
        )
        return 2 if any_error else 0
    return 0


def cmd_predictions(adapter) -> int:
    """读取评分结果表中的预测值（只读）。"""
    _print_info("读取预测结果……")
    preds = adapter.get_predictions()
    if not preds:
        _print_warn("暂无预测结果（评分结果表不存在或为空）。")
        _print_json([])
        return 1
    _print_info(f"共 {len(preds)} 条预测记录。")
    _print_json(preds)
    return 0


def cmd_run_all(adapter) -> int:
    """依次执行 build → train → score。"""
    _print_info("run-all：依次执行 build → train → score")
    rc = cmd_build(adapter)
    if rc not in (0,):
        _print_error(f"build 阶段失败（退出码 {rc}），中止 run-all。")
        return rc
    rc = cmd_train(adapter)
    if rc not in (0,):
        _print_error(f"train 阶段失败（退出码 {rc}），中止 run-all。")
        return rc
    rc = cmd_score(adapter)
    return rc


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MOD V2 HeatWave AutoML 离线运维工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "command",
        choices=["status", "plan", "build", "train", "score", "predictions", "run-all"],
        help="要执行的操作",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help=(
            "允许写入数据库（DDL / 训练 / 评分）。"
            "同时需要 MOD_HW_ML_ENABLED=true 环境变量。"
        ),
    )
    parser.add_argument(
        "--json",
        dest="json_only",
        action="store_true",
        default=False,
        help="所有输出使用纯 JSON（适合管道调用）",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 安全提示
    # ------------------------------------------------------------------
    hw_enabled = os.getenv("MOD_HW_ML_ENABLED", "false").lower() == "true"

    if args.execute and not hw_enabled:
        _print_warn(
            "--execute 已指定但 MOD_HW_ML_ENABLED 不为 true，"
            "写入操作仍将被阻止（plan 模式）。"
        )

    if args.execute and hw_enabled and args.command in ("build", "train", "score", "run-all"):
        _print_warn(
            "⚠  execute 模式已激活，将对 mod_s_v2 数据库执行写操作。"
            "确认后继续……"
        )

    # ------------------------------------------------------------------
    # 只读命令不需要 DB 连接（status / plan / predictions 仍需连接）
    # ------------------------------------------------------------------
    if args.command == "plan":
        # plan 仅打印 SQL，无需数据库
        from app.ml_adapter import HeatWaveMLAdapter  # type: ignore

        adapter = HeatWaveMLAdapter(conn=None, execute=False)
        return cmd_plan(adapter)

    # ------------------------------------------------------------------
    # 建立数据库连接
    # ------------------------------------------------------------------
    engine, conn = _get_connection()
    if conn is None and args.command != "plan":
        _print_error(
            "无法连接数据库。请检查 MOD_DB_HOST / MOD_DB_PORT / "
            "MOD_DB_USER / MOD_DB_PASSWORD / MOD_DB_NAME 环境变量。"
        )
        return 3

    try:
        from app.ml_adapter import HeatWaveMLAdapter  # type: ignore

        adapter = HeatWaveMLAdapter(conn=conn, execute=args.execute)

        cmd_map = {
            "status": cmd_status,
            "build": cmd_build,
            "train": cmd_train,
            "score": cmd_score,
            "predictions": cmd_predictions,
            "run-all": cmd_run_all,
        }
        handler = cmd_map.get(args.command)
        if handler is None:
            _print_error(f"未知命令：{args.command}")
            return 2
        return handler(adapter)

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
