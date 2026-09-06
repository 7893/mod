#!/usr/bin/env python3
"""
scripts/kiro/run_daily_briefing.py
==================================
每日指挥部决策简报生成入口（供 systemd timer 调用，ADR-0010 第二期）。

流程：读取当前 dashboard overview 聚合指标 → 经 CloudflareAIAdapter（走 mod-gateway）
生成研判简报 → 写入 daily_briefing 表。全程后台运行，大屏只读展示。

用法：
  python scripts/kiro/run_daily_briefing.py            # 生成并入库
  python scripts/kiro/run_daily_briefing.py --status   # 只读最新简报，不生成
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("daily_briefing")


def main() -> int:
    parser = argparse.ArgumentParser(description="每日决策简报生成")
    parser.add_argument("--status", action="store_true", help="只读最新简报，不生成")
    args = parser.parse_args()

    from app.db import get_engine
    from app.services.daily_briefing import generate_and_store, get_latest
    from app.services.dashboard import build_dashboard_snapshot_v2
    from app.integrations.cloudflare_ai import CloudflareAIAdapter

    engine = get_engine()

    if args.status:
        with engine.connect() as conn:
            latest = get_latest(conn)
        logger.info("最新简报状态: %s (%s)", latest.get("status"), latest.get("briefingDate"))
        return 0

    display_tz = os.getenv("MOD_DISPLAY_TIMEZONE", "Asia/Hong_Kong")

    with engine.connect() as conn:
        snap = build_dashboard_snapshot_v2(conn)
        overview = snap.get("overview", {})

    cf = CloudflareAIAdapter()
    with engine.begin() as conn:
        result = generate_and_store(conn, overview, cf, display_tz=display_tz)

    status = result.get("status")
    if status == "ok":
        logger.info("简报生成成功: %s", result.get("briefingDate"))
        return 0
    logger.warning("简报未生成（%s）: %s", status, result.get("message"))
    # LLM 降级不视为致命错误，返回 0 避免 systemd 反复重启告警
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
