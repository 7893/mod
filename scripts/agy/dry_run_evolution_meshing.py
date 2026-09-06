#!/usr/bin/env python3
"""
Phase D Dry-Run Script: Fast-Slow Movie Evolution & Contradiction Meshing Audit.

Connects to MySQL database in read-only mode, loads baseline, simulates
daily event ticks driving metrics progression ("终将达标"), observes naturally
emergent difficult units (~4% friction), and performs Contradiction Meshing
verification (矛与盾读同一事实源、天然自洽).

ZERO writes are performed against the database.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
import sys

from dotenv import load_dotenv
import pymysql

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from simulation.engine_context import load_construction_baseline  # noqa: E402
from simulation.evolution_coordinator import EvolutionCoordinator  # noqa: E402
from simulation.lifecycle_advancer import LifecycleThresholds  # noqa: E402


def get_db_connection() -> pymysql.Connection:
    """Connect to MySQL using environment credentials."""
    env_file = os.path.join(BASE_DIR, ".env.systemd")
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv()

    host = os.getenv("MOD_DB_HOST") or os.getenv("MOD_V2_DB_HOST", "127.0.0.1")
    port = int(os.getenv("MOD_DB_PORT") or os.getenv("MOD_V2_DB_PORT", "3306"))
    user = os.getenv("MOD_DB_USER") or os.getenv("MOD_V2_DB_USER", "root")
    password = os.getenv("MOD_DB_PASSWORD") or os.getenv("MOD_V2_DB_PASSWORD", "")
    database = os.getenv("MOD_DB_NAME") or os.getenv("MOD_V2_DB_NAME", "mod_s_v2")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,  # secret-scan: allow
        database=database,
        charset="utf8mb4",
        autocommit=False,
    )


def run_evolution_meshing_dry_run():
    print("=" * 75)
    print(" [DRY-RUN] Fast-Slow Movie Evolution & Contradiction Meshing Audit")
    print("=" * 75)

    conn = get_db_connection()
    try:
        print("[1/4] Loading live construction baseline from database...")
        baseline = load_construction_baseline(conn)
        thresholds = LifecycleThresholds(
            prep_consecutive_days_min=3,
            dual_ready_consecutive_days_min=3,
            dual_run_consecutive_days_min=7,
        )
        coordinator = EvolutionCoordinator(baseline, thresholds=thresholds, seed=2026)

        sim_date = date(baseline.latest_business_date.year, baseline.latest_business_date.month, baseline.latest_business_date.day)
        print(f"      - Baseline date: {sim_date}")
        print(f"      - Total units: {len(baseline.orgs)}")

        # 2. Inspect friction / difficult units natural distribution
        print("\n[2/4] Analyzing difficult units distribution (自然涌现困难户)...")
        difficult_units = []
        for oid in baseline.orgs:
            is_diff, reason = coordinator.is_difficult_unit(oid)
            if is_diff:
                difficult_units.append((oid, baseline.orgs[oid]["name"], reason))

        diff_rate = len(difficult_units) / len(baseline.orgs) * 100
        print(f"      - Difficult units identified: {len(difficult_units)} / {len(baseline.orgs)} ({diff_rate:.1f}%)")
        print("      - Sample difficult units (natural business friction):")
        for oid, name, reason in difficult_units[:5]:
            print(f"        * Org {oid} ('{name}'): {reason}")

        # 3. Simulate fast movie feeding slow movie over 5 daily ticks
        print("\n[3/4] Simulating fast movie feeding slow movie (快电影喂慢电影)...")
        # Take a sample cross-section across different stages (50 units)
        sample_org_ids = []
        for st in ("准备中", "已具备双轨条件", "双轨运行中"):
            sample_org_ids.extend(baseline.orgs_by_status.get(st, [])[:15])

        print(f"      - Evolving 5 daily simulation ticks for {len(sample_org_ids)} sample units...")
        total_events_generated = 0
        for tick in range(1, 6):
            cur_tick_date = date(sim_date.year, sim_date.month, min(28, sim_date.day + tick))
            tick_events = 0
            for oid in sample_org_ids:
                evs = coordinator.evolve_unit_step(oid, cur_tick_date)
                tick_events += len(evs)
            total_events_generated += tick_events

        print(f"      - Successfully generated {total_events_generated} fast-movie activity footprints.")

        # 4. Perform Contradiction Meshing Audit
        print("\n[4/4] Contradiction Meshing Verification (矛与盾自洽审计)...")
        # Inject controlled friction into 2 units to inspect detection
        u_prep_diff = sample_org_ids[0]
        coordinator.unit_metrics[u_prep_diff].opening_diff_amount = Decimal("2450.00")
        coordinator.unit_metrics[u_prep_diff].has_blocking_risk = True

        u_dual_diff = sample_org_ids[-1]
        coordinator.unit_metrics[u_dual_diff].dual_run_consistency_rate = 93.8
        coordinator.unit_metrics[u_dual_diff].dual_run_recent_matches = 0
        coordinator.unit_metrics[u_dual_diff].has_blocking_risk = True

        report = coordinator.inspect_contradiction_meshing(sample_org_ids, sim_date)

        print(f"      - Total candidate units evaluated : {report.total_evaluated_units}")
        print(f"      - Units held back by Advancer (矛) : {report.held_back_units_count}")
        print(f"      - Units flagged by Risk View  (盾) : {report.risk_flagged_units_count}")
        print(f"      - Mutually meshed units count     : {len(report.meshed_units)}")
        print(f"      - Unmeshed (Advancer-only)        : {len(report.unmeshed_advancer_only)}")
        print(f"      - Unmeshed (Risk-View-only)       : {len(report.unmeshed_risk_only)}")
        print(f"      - Is Perfectly Meshed             : {'✓ YES (100% COHERENT)' if report.is_perfectly_meshed else '✗ NO'}")

        if report.is_perfectly_meshed:
            print("\n" + "=" * 75)
            print(" [AUDIT RESULT] CONTRADICTION MESHING VERIFIED: 0 DISCREPANCIES.")
            print("                Advancer blockers and Risk inspection read identical facts.")
            print("                0 database modifications committed.")
            print("=" * 75)
        else:
            raise RuntimeError("Contradiction meshing audit detected divergence between spear and shield!")

    finally:
        conn.close()


if __name__ == "__main__":
    run_evolution_meshing_dry_run()
