"""Construction propeller and friction-remediation coordinator (The Spear & Shield).

Responsibilities:
1. Advances lagging construction tasks & data readiness for batch 6 & 7 units.
2. Applies the 88% friction trap: units reaching 85%-90% risk encountering blockers.
3. Locks progress when an open governance issue exists for that unit.
4. Advances governance issues via GovernanceStateMachine.
5. On issue RESOLVED: unfreezes unit progress, bumps metrics to 95%+, clearing E/F screen risks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import random
from typing import Optional

import pymysql

from .governance_state_machine import (
    ExpertPool,
    GovernanceStateMachine,
    GovernanceStatus,
    LocalNarrativeLibrary,
)

logger = logging.getLogger(__name__)


@dataclass
class PropellerCycleResult:
    units_advanced: int
    issues_advanced: int
    issues_created: int
    issues_resolved: int


class ConstructionPropeller:
    """Coordinates unit task progression with governance issue lifecycle."""

    def __init__(
        self,
        conn: pymysql.Connection,
        pool: Optional[ExpertPool] = None,
        seed: Optional[int] = None,
    ):
        self.conn = conn
        self.rng = random.Random(seed)
        self.fsm = GovernanceStateMachine(pool=pool, seed=seed)

    def step(self, now: Optional[datetime] = None, auto_commit: bool = True) -> PropellerCycleResult:
        """Execute one progression and governance cycle."""
        now = now or datetime.now(timezone.utc)
        result = PropellerCycleResult(0, 0, 0, 0)

        with self.conn.cursor() as cur:
            # 1. Advance existing open issues (The Shield)
            cur.execute("""
                SELECT id, unit_id, unit_name, issue_type, status, rework_count
                FROM governance_issue
                WHERE status IN ('DISCOVERED', 'ASSIGNED', 'IN_PROGRESS', 'VERIFYING')
                ORDER BY created_at ASC
                LIMIT 5
            """)
            open_issues = cur.fetchall()

            for iss in open_issues:
                iss_id, u_id, u_name, iss_type, cur_status, rework_cnt = iss
                new_status, timeline_evt = self.fsm.transition(
                    current_status=cur_status,
                    issue_id=iss_id,
                    issue_type=iss_type,
                    unit_name=u_name,
                    now=now,
                )

                if new_status != cur_status or timeline_evt:
                    new_rework = rework_cnt + (1 if timeline_evt and timeline_evt[0] == "二次核验" else 0)
                    resolved_at = now if new_status == GovernanceStatus.RESOLVED.value else None
                    assigned_owner = self.fsm.pool.assigned.get(iss_id)

                    cur.execute("""
                        UPDATE governance_issue
                        SET status = %s, owner = COALESCE(%s, owner), rework_count = %s,
                            updated_at = %s, resolved_at = %s
                        WHERE id = %s
                    """, (new_status, assigned_owner, new_rework, now, resolved_at, iss_id))

                    if timeline_evt:
                        act, actor, detail = timeline_evt
                        cur.execute("""
                            INSERT INTO issue_timeline (issue_id, action, actor, detail, occurred_at)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (iss_id, act, actor, detail, now))

                    result.issues_advanced += 1

                    # If issue was resolved, unfreeze and boost the unit's metrics!
                    if new_status == GovernanceStatus.RESOLVED.value:
                        result.issues_resolved += 1
                        self._boost_healed_unit(cur, u_id, now)

            # 2. Advance units that are NOT frozen by active issues (The Spear)
            cur.execute("""
                SELECT DISTINCT unit_id FROM governance_issue
                WHERE status IN ('DISCOVERED', 'ASSIGNED', 'IN_PROGRESS', 'VERIFYING')
            """)
            locked_unit_ids = {r[0] for r in cur.fetchall()}

            # Pick 3 eligible batch 6 or 7 units that have lag
            cur.execute("""
                SELECT o.id, o.name, o.region, o.batch_id, o.status,
                       COALESCE(AVG(t.progress), 0) AS avg_prog
                FROM org_unit o
                LEFT JOIN construction_task t ON t.org_id = o.id
                WHERE o.batch_id IN (6, 7)
                GROUP BY o.id, o.name, o.region, o.batch_id, o.status
                HAVING avg_prog < 95.0
                ORDER BY RAND()
                LIMIT 5
            """)
            units_to_eval = cur.fetchall()

            for unit in units_to_eval:
                u_id, u_name, u_region, b_id, u_status, avg_prog = unit
                if u_id in locked_unit_ids:
                    continue  # Frozen by open issue

                # Check if this unit encounters a friction trap (85%-90%)
                if 82.0 <= avg_prog <= 90.0 and self.rng.random() < 0.20:
                    # Spawn friction blocker issue
                    iss_created = self._spawn_friction_issue(cur, u_id, u_name, u_region, b_id, avg_prog, now)
                    if iss_created:
                        result.issues_created += 1
                        locked_unit_ids.add(u_id)
                        continue

                # Advance unit progress by +0.8% to +2.0%
                delta = round(self.rng.uniform(0.8, 2.0), 1)
                cur.execute("""
                    UPDATE construction_task
                    SET progress = LEAST(100, progress + %s), update_time = %s
                    WHERE org_id = %s AND status != '已完成'
                """, (int(delta), now.date(), u_id))

                cur.execute("""
                    UPDATE data_readiness
                    SET opening_rate = CONCAT(LEAST(100, ROUND(CAST(REPLACE(opening_rate, '%%', '') AS DECIMAL(5,1)) + %s, 1)), '%%')
                    WHERE org_id = %s
                """, (delta, u_id))

                result.units_advanced += 1

            if auto_commit:
                self.conn.commit()

        return result

    def _boost_healed_unit(self, cur: pymysql.cursors.Cursor, unit_id: int, now: datetime) -> None:
        """Boost unit completion after issue is resolved so it exits risk lists."""
        # Elevate tasks to >= 95%
        cur.execute("""
            UPDATE construction_task
            SET progress = GREATEST(progress, 95), update_time = %s
            WHERE org_id = %s
        """, (now.date(), unit_id))

        # Elevate opening_rate to >= 96%
        cur.execute("""
            UPDATE data_readiness
            SET opening_rate = '96.5%%', overall_status = '校验通过'
            WHERE org_id = %s
        """, (unit_id,))

        # If it was in 准备中 and qualified, let it become 双轨运行中
        cur.execute("""
            UPDATE org_unit
            SET status = CASE WHEN status = '准备中' THEN '已具备双轨条件' ELSE status END
            WHERE id = %s
        """, (unit_id,))

    def _spawn_friction_issue(
        self,
        cur: pymysql.cursors.Cursor,
        unit_id: int,
        unit_name: str,
        region: str,
        batch_id: int,
        current_prog: float,
        now: datetime,
    ) -> bool:
        """Create a new friction issue when unit hits a bottleneck."""
        iss_type = self.rng.choice(["超期挂账", "超预算迹象", "票据异常"])
        tmpl = LocalNarrativeLibrary.get_template(iss_type)
        iss_id = f"ISS-{now.strftime('%Y%m%d')}-{unit_id:04d}"

        title = tmpl["title_template"].format(name=unit_name)
        desc = tmpl["desc_template"].format(name=unit_name, rate=f"{current_prog:.1f}")

        cur.execute("""
            INSERT IGNORE INTO governance_issue (
                id, unit_id, unit_name, province, batch_id, issue_type,
                severity, status, owner, title, description, ai_enriched,
                rework_count, created_at, updated_at, resolved_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            iss_id, unit_id, unit_name, region, batch_id, iss_type,
            "HIGH" if iss_type == "票据异常" else "MEDIUM",
            GovernanceStatus.DISCOVERED.value, None, title, desc, 0, 0, now, now, None
        ))

        cur.execute("""
            INSERT INTO issue_timeline (
                issue_id, action, actor, detail, occurred_at
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            iss_id, "立项发现", "系统自动化巡检探针",
            f"巡检监测到指标异动并触发工程门禁锁定：{desc}", now
        ))

        return True
