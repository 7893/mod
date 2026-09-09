"""Trickle Backfill Pipeline (涓流回填体系).

Safely backfills historical and newly created governance issues using free-tier
Cloudflare Workers AI quota (hard-capped at 3,000 neurons/day, $0.00 bill).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from typing import List, Optional

import pymysql
from dotenv import load_dotenv

from .cf_ai_client import CloudflareAIClient, EnrichmentResult
from .quota_watchdog import QuotaWatchdog

logger = logging.getLogger(__name__)


@dataclass
class BackfillReport:
    issues_processed: int
    neurons_consumed: float
    status: str  # "COMPLETED" | "QUOTA_EXHAUSTED" | "NO_ISSUES"
    enriched_ids: List[str]


class TrickleBackfiller:
    """Manages slow, safe, and realistic AI narrative enrichment over historical issues."""

    def __init__(
        self,
        conn: Optional[pymysql.Connection] = None,
        client: Optional[CloudflareAIClient] = None,
        watchdog: Optional[QuotaWatchdog] = None,
    ):
        self._conn = conn
        self.watchdog = watchdog or QuotaWatchdog(conn=conn)
        self.client = client or CloudflareAIClient(watchdog=self.watchdog)

    def _get_connection(self) -> pymysql.Connection:
        if self._conn is not None:
            return self._conn

        if not os.environ.get("MOD_DB_HOST"):
            for env_file in [".env.systemd", ".env.local", ".env"]:
                if os.path.exists(env_file):
                    load_dotenv(env_file)
                    break

        user = os.getenv("MOD_DB_USER", "")
        password = os.getenv("MOD_DB_PASSWORD", "")
        host = os.getenv("MOD_DB_HOST", "127.0.0.1")
        port = int(os.getenv("MOD_DB_PORT", 3306))
        db = os.getenv("MOD_DB_NAME", "mod")

        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,  # secret-scan: allow
            database=db,
            autocommit=True,
        )

    def run_cycle(self, batch_size: int = 3) -> BackfillReport:
        """Run one backfill batch (typically 2-3 issues to conserve neurons)."""
        # 1. Pre-flight quota check
        can_run, reason = self.watchdog.can_consume(estimated_neurons=50.0)
        if not can_run:
            logger.info(f"[BACKFILL] Skipped cycle due to quota: {reason}")
            return BackfillReport(0, 0.0, "QUOTA_EXHAUSTED", [])

        conn = self._get_connection()
        close_needed = conn != self._conn
        enriched_ids: List[str] = []
        total_neurons = 0.0

        try:
            with conn.cursor() as cur:
                # Prioritize un-enriched issues that are actively in progress or verifying
                cur.execute(
                    """
                    SELECT id, issue_type, unit_name, province, description, rework_count
                    FROM governance_issue
                    WHERE ai_enriched = 0
                    ORDER BY FIELD(status, 'IN_PROGRESS', 'VERIFYING', 'DISCOVERED', 'ASSIGNED', 'RESOLVED', 'CLOSED'),
                             updated_at DESC
                    LIMIT %s
                    """,
                    (batch_size,),
                )
                rows = cur.fetchall()

                if not rows:
                    return BackfillReport(0, 0.0, "NO_ISSUES", [])

                now = datetime.now(timezone.utc)
                for r in rows:
                    iss_id, iss_type, u_name, prov, cur_desc, rework = (
                        str(r[0]),
                        str(r[1]),
                        str(r[2]),
                        str(r[3]),
                        str(r[4] or ""),
                        int(r[5]),
                    )

                    # Enrich via AI client (with automatic zero-failure fallback)
                    res: EnrichmentResult = self.client.enrich_issue(
                        issue_id=iss_id,
                        issue_type=iss_type,
                        unit_name=u_name,
                        province=prov,
                        current_description=cur_desc,
                        rework_count=rework,
                    )

                    total_neurons += res.neurons_used

                    # Append enrichment to description
                    expanded_desc = (
                        f"{cur_desc}\n\n"
                        f"【专家深度研判 · {res.source}】\n"
                        f"问题定性：{res.summary}\n"
                        f"根本原因：{res.root_cause}\n"
                        f"督办举措：{res.suggested_action}"
                    ).strip()

                    cur.execute(
                        """
                        UPDATE governance_issue
                        SET ai_enriched = 1, description = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (expanded_desc, now, iss_id),
                    )

                    # Insert timeline event
                    timeline_detail = f"{res.summary}。根因：{res.root_cause}。建议：{res.suggested_action}"
                    cur.execute(
                        """
                        INSERT INTO issue_timeline (issue_id, action, actor, detail, occurred_at)
                        VALUES (%s, 'AI深度研判', %s, %s, %s)
                        """,
                        (iss_id, f"AI督察专家（{res.model}）", timeline_detail, now),
                    )

                    enriched_ids.append(iss_id)

                    # Check if quota got exhausted mid-batch
                    can_continue, _ = self.watchdog.can_consume(estimated_neurons=50.0)
                    if not can_continue:
                        logger.warning("[BACKFILL] Quota reached mid-batch. Halting current cycle.")
                        break

            if not getattr(conn, "autocommit", False):
                conn.commit()

            return BackfillReport(
                issues_processed=len(enriched_ids),
                neurons_consumed=round(total_neurons, 2),
                status="COMPLETED",
                enriched_ids=enriched_ids,
            )
        finally:
            if close_needed:
                conn.close()
