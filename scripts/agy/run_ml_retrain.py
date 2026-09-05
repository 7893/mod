#!/usr/bin/env python3
"""
scripts/agy/run_ml_retrain.py
=============================
CLI Runner and Service Entrypoint for Daily HeatWave AutoML Retraining.

Modes:
  --status:   Inspect current model metadata, verified status, and latest audit logs.
  --dry-run:  Verify feature table integrity and output planned retrain pipeline.
  --once:     Trigger a single retrain and evaluation cycle immediately.
  (default):  Runs a single retrain cycle with audit logging (suitable for systemd service).
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_engine  # noqa: E402
from sqlalchemy import text  # noqa: E402

from scripts.agy.train_and_evaluate_models import (  # noqa: E402
    check_feature_integrity,
    ensure_metadata_tables,
    load_environment,
    run_full_pipeline,
)

HK_TZ = ZoneInfo("Asia/Hong_Kong")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mod-ml-retrain")


def print_status() -> None:
    """Print current retrain status, verified models, and audit logs."""
    load_environment()
    engine = get_engine()

    with engine.connect() as conn:
        ensure_metadata_tables(conn)
        print("\n" + "=" * 78)
        print("           MOD HEATWAVE AUTOML 重训服务与模型状态 (STATUS)")
        print("=" * 78)

        models = conn.execute(
            text("SELECT * FROM `mod`.`ml_model_metadata` ORDER BY model_handle")
        ).mappings().all()

        if not models:
            print("  [状态] 暂无已记录的模型元数据，需执行初次训练。")
        else:
            for m in models:
                v_badge = "✅ 已独立验证 (VERIFIED)" if m["verified"] else "⚠️ 未验证 (UNVERIFIED)"
                print(f"\n* 模型: {m['model_handle']} ({m['model_name']}) - {v_badge}")
                print(f"  - 任务类型: {m['task_type']} | 目标列: {m['target_column']} | 算法: {m['algorithm']}")
                print(f"  - 切分方式: {m['split_method']} | 训练样本: {m['train_rows']} | 测试样本: {m['test_rows']}")
                print(f"  - 训练集自评分: {m['train_score']:.4f} | 测试集真实质量分: {m['test_score']:.4f}")
                print(f"  - 最近训练时间: {m['trained_at']} | 验证时间: {m['verified_at']}")

        print("\n" + "-" * 78)
        print("  最近 5 次训练/重训审计记录 (ml_training_log):")
        logs = conn.execute(
            text("SELECT * FROM `mod`.`ml_training_log` ORDER BY id DESC LIMIT 5")
        ).mappings().all()

        if not logs:
            print("  暂无历史审计记录。")
        else:
            for l in logs:
                print(
                    f"  [{l['created_at']}] ID#{l['id']} {l['model_handle']} | "
                    f"模式: {l['run_type']} | 状态: {l['status']} | 耗时: {l['duration_seconds']}s | "
                    f"自评分: {l['train_score']:.4f} -> 测试真实分: {l['test_score']:.4f}"
                )
        print("=" * 78 + "\n")


def execute_retrain(run_type: str = "scheduled") -> int:
    """Execute full retraining pipeline with failure logging."""
    logger.info("Starting HeatWave AutoML retrain job (run_type=%s)...", run_type)
    t0 = time.time()
    load_environment()
    engine = get_engine()

    try:
        result = run_full_pipeline(run_type=run_type)
        logger.info(
            "Retrain job completed successfully in %.2f seconds",
            result.get("duration_seconds", time.time() - t0),
        )
        return 0
    except Exception as exc:
        duration = time.time() - t0
        logger.error("Retrain job failed: %s", exc, exc_info=True)
        # Attempt to record failure in audit log
        try:
            with engine.connect() as conn:
                ensure_metadata_tables(conn)
                conn.execute(
                    text(
                        """
                        INSERT INTO `mod`.`ml_training_log` (
                            model_handle, run_type, train_rows, test_rows, train_score, test_score,
                            metrics, status, error_message, duration_seconds, created_at
                        ) VALUES (
                            'UNKNOWN', :run_type, 0, 0, 0.0, 0.0,
                            NULL, 'failed', :err, :duration, NOW()
                        )
                        """
                    ),
                    {
                        "run_type": run_type,
                        "err": str(exc)[:1000],
                        "duration": round(duration, 2),
                    },
                )
                conn.commit()
        except Exception:
            pass
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="HeatWave AutoML Daily Retraining Runner")
    parser.add_argument("--status", action="store_true", help="Print model metadata and audit logs")
    parser.add_argument("--dry-run", action="store_true", help="Verify features and print retrain plan")
    parser.add_argument("--once", action="store_true", help="Trigger a single retrain cycle immediately")
    parser.add_argument("--run-type", default="manual", help="Audit run type (manual / scheduled)")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.dry_run:
        load_environment()
        engine = get_engine()
        with engine.connect() as conn:
            ensure_metadata_tables(conn)
            check_feature_integrity(conn)
            print("Feature integrity checked. Retrain dry-run plan valid.")
        return

    # Default or --once: trigger retrain
    run_type = args.run_type if args.run_type else ("scheduled" if not args.once else "manual")
    exit_code = execute_retrain(run_type=run_type)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
