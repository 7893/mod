#!/usr/bin/env python3
"""Unified supervisor for MOD production services (API Gateway + Simulation Engine).

Manages both mod-api (Uvicorn) and mod-simulator as monitored subprocesses,
handling graceful shutdown, signal forwarding, and automatic restarts.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [mod-supervisor] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mod-supervisor")

BASE_DIR = Path(__file__).resolve().parents[2]


def load_env_file(filepath: Path) -> dict[str, str]:
    """Parse a simple key=value env file without modifying os.environ."""
    env: dict[str, str] = {}
    if not filepath.exists():
        return env
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'\"")
        env[key] = val
    return env


def main() -> int:
    logger.info("Starting MOD unified core supervisor from %s", BASE_DIR)

    # API environment
    api_env_file = Path(os.getenv("MOD_API_ENV_FILE", "/home/ubuntu/mod/.env.api.systemd"))
    if not api_env_file.exists():
        api_env_file = BASE_DIR / ".env.api.systemd"
    api_env = os.environ.copy()
    api_env.update(load_env_file(api_env_file))
    api_env["PYTHONPATH"] = str(BASE_DIR)
    api_env["PYTHONUNBUFFERED"] = "1"
    api_env["PYTHONDONTWRITEBYTECODE"] = "1"
    api_env.setdefault("MOD_SIMULATOR_STATUS_PATH", "/home/ubuntu/mod/output/simulator_status.json")

    # Simulator environment
    sim_env_file = Path(os.getenv("MOD_SIM_ENV_FILE", "/home/ubuntu/mod/.env.systemd"))
    if not sim_env_file.exists():
        sim_env_file = BASE_DIR / ".env.systemd"
    sim_env = os.environ.copy()
    sim_env.update(load_env_file(sim_env_file))
    sim_env["PYTHONPATH"] = str(BASE_DIR)
    sim_env["PYTHONUNBUFFERED"] = "1"
    sim_env["PYTHONDONTWRITEBYTECODE"] = "1"
    sim_env.setdefault("MOD_OUTPUT_DIR", "/home/ubuntu/mod/output")

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8100",
        "--proxy-headers",
    ]
    sim_cmd = [
        sys.executable,
        str(BASE_DIR / "scripts/agy/run_simulator_service.py"),
    ]

    procs: dict[str, subprocess.Popen | None] = {"api": None, "sim": None}
    shutting_down = False

    def handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, propagating to child processes...", sig_name)
        for name, p in procs.items():
            if p and p.poll() is None:
                try:
                    p.terminate()
                except OSError:
                    pass

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    def start_api() -> subprocess.Popen:
        logger.info("Launching MOD API sub-service (port 8100)...")
        return subprocess.Popen(api_cmd, cwd=str(BASE_DIR), env=api_env)

    def start_sim() -> subprocess.Popen:
        logger.info("Launching MOD Simulator sub-service...")
        return subprocess.Popen(sim_cmd, cwd=str(BASE_DIR), env=sim_env)

    procs["api"] = start_api()
    procs["sim"] = start_sim()

    while not shutting_down:
        time.sleep(1)
        if shutting_down:
            break

        # Check API health
        if procs["api"] and procs["api"].poll() is not None:
            code = procs["api"].poll()
            logger.error("MOD API sub-service exited unexpectedly with code %s. Restarting in 3s...", code)
            time.sleep(3)
            if not shutting_down:
                procs["api"] = start_api()

        # Check Simulator health
        if procs["sim"] and procs["sim"].poll() is not None:
            code = procs["sim"].poll()
            logger.error("MOD Simulator sub-service exited unexpectedly with code %s. Restarting in 5s...", code)
            time.sleep(5)
            if not shutting_down:
                procs["sim"] = start_sim()

    # Graceful shutdown wait
    logger.info("Waiting for child processes to terminate...")
    deadline = time.time() + 10
    for name, p in procs.items():
        if p and p.poll() is None:
            remaining = max(0.1, deadline - time.time())
            try:
                p.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                logger.warning("Child process %s did not terminate in time, killing...", name)
                try:
                    p.kill()
                except OSError:
                    pass

    logger.info("MOD unified supervisor stopped cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
