#!/usr/bin/env python3
"""
CLI Runner and Lifecycle Manager for MOD Realistic Business Simulation Engine.

Modes:
  --status: Read and print runtime service status and fail-closed flag state.
  --dry-run: Run in dry-run mode (0 database writes, calculates intensity & events).
  --once: Run a single cycle tick and exit.
  --clear-fail-closed: Clear persistent fail-closed flag to resume service.
  (default): Run continuously as 7x24 resident daemon with graceful signal handling.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import signal
import sys
import threading
from typing import Any
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.simulation.runtime_service import (  # noqa: E402
    FailClosedManager,
    SimulatorRuntimeConfig,
    SimulatorRuntimeService,
)

HK_TZ = ZoneInfo("Asia/Hong_Kong")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mod-simulator")


def load_environment() -> None:
    for env_file in [BASE_DIR / ".env.systemd", BASE_DIR / ".env.local", BASE_DIR / ".env"]:
        if env_file.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(env_file)
            except ImportError:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip().strip("'\""))
            break


def check_status(config: SimulatorRuntimeConfig) -> int:
    fail_mgr = FailClosedManager(config.fail_closed_flag_path, config.audit_log_path)
    flag_tripped = fail_mgr.is_tripped()
    trip_info = fail_mgr.get_trip_info() if flag_tripped else None

    status_data: dict[str, Any] = {}
    if config.status_file_path.exists():
        try:
            with open(config.status_file_path, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        except Exception as ex:
            status_data = {"error": f"Failed to read status file: {ex}"}

    print("\n=======================================================")
    print("      MOD REALISTIC SIMULATOR RUNTIME STATUS           ")
    print("=======================================================")
    print(f"Service Name:            mod-simulator")
    print(f"Current System Time:     {datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M:%S')} HKT")
    print(f"Fail-Closed Tripped:     {flag_tripped}")

    if flag_tripped and trip_info:
        print(f"  └─ Trip Timestamp:     {trip_info.get('timestamp')}")
        print(f"  └─ Trip Reason:        {trip_info.get('reason')}")
        print(f"  └─ Trip Details:       {trip_info.get('details')}")

    if status_data:
        print(f"Service State:           {status_data.get('status', 'UNKNOWN')}")
        print(f"Last Cycle Status:       {status_data.get('last_cycle_status', 'UNKNOWN')}")
        print(f"Last Heartbeat:          {status_data.get('timestamp', 'UNKNOWN')}")
        print(f"Current Intensity:       {status_data.get('intensity', 'N/A')}")
        print(f"Uptime:                  {status_data.get('uptime_seconds', 0)}s")
        print(f"Consecutive Failures:    {status_data.get('consecutive_failures', 0)}")
        fuse = status_data.get("fuse_metrics", {})
        print(f"Rate Limiter (Minute):   {fuse.get('minute_count', 0)} / {fuse.get('max_per_minute', 0)}")
        print(f"Rate Limiter (Daily):    {fuse.get('day_count', 0)} / {fuse.get('max_per_day', 0)}")
        if status_data.get("last_error"):
            print(f"Last Error:              {status_data.get('last_error')}")
    else:
        print("Status File:             No heartbeat recorded yet.")
    print("=======================================================\n")

    return 1 if flag_tripped else 0


def clear_fail_closed(config: SimulatorRuntimeConfig) -> int:
    fail_mgr = FailClosedManager(config.fail_closed_flag_path, config.audit_log_path)
    if not fail_mgr.is_tripped():
        logger.info("Fail-closed flag is not set. Nothing to clear.")
        return 0

    success = fail_mgr.clear()
    if success:
        logger.info("Successfully cleared persistent fail-closed flag.")
        return 0
    else:
        logger.error("Failed to clear persistent fail-closed flag.")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="MOD Realistic Simulation Engine Service Runner")
    parser.add_argument("--status", action="store_true", help="Print runtime status and exit")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (0 DB writes)")
    parser.add_argument("--once", action="store_true", help="Run a single simulation cycle tick and exit")
    parser.add_argument("--clear-fail-closed", action="store_true", help="Clear persistent fail-closed flag and exit")
    parser.add_argument("--max-per-minute", type=int, default=20, help="Hard rate limit fuse cap per minute")
    parser.add_argument("--max-per-day", type=int, default=5000, help="Hard rate limit fuse cap per day")

    args = parser.parse_args()
    load_environment()

    output_dir = BASE_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    config = SimulatorRuntimeConfig(
        max_events_per_minute=args.max_per_minute,
        max_events_per_day=args.max_per_day,
        fail_closed_flag_path=output_dir / "simulator_fail_closed.flag",
        status_file_path=output_dir / "simulator_status.json",
        audit_log_path=output_dir / "simulation_audit.log",
        dry_run=args.dry_run,
    )

    if args.status:
        return check_status(config)

    if args.clear_fail_closed:
        return clear_fail_closed(config)

    service = SimulatorRuntimeService(config=config)

    if args.once:
        logger.info(f"Running single simulation cycle tick (dry_run={config.dry_run})...")
        res = service.run_once()
        logger.info(
            f"Cycle completed: status={res.status}, events={res.events_written}, "
            f"intensity={res.intensity:.3f}, duration={res.cycle_duration_ms:.1f}ms"
        )
        if res.error:
            logger.warning(f"Cycle message: {res.error}")
        return 0 if res.status in ["SUCCESS", "RATE_LIMITED", "DRY_RUN"] else 1

    # Resident Daemon Mode
    stop_event = threading.Event()

    def handle_signal(sig: int, frame: Any) -> None:
        logger.info(f"Received signal {sig}. Initiating graceful shutdown...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info(
        f"Starting resident background simulator service "
        f"(dry_run={config.dry_run}, rate_limits={config.max_events_per_minute}/m, {config.max_events_per_day}/d)..."
    )
    service.run_forever(stop_event=stop_event)
    logger.info("MOD Realistic Simulator service gracefully stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
