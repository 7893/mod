"""Rule-driven approval gate and voucherization pipeline for newly generated data."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import random

from app.business_calendar import day_type
from app.business_rules import (
    DOC_STATUS_COMPLETED,
    DOC_STATUS_PENDING_APPROVAL,
    DOC_STATUS_PENDING_VOUCHER,
    DOC_STATUS_REJECTED,
    SIMULATED_FLOW_NATURE,
)

from .accounting_subjects import build_lines as build_voucher_lines
from .approval_models import (
    ApprovalFlowBatch,
    DocumentTransition,
    SourceDocument,
    validate_approval_flow,
)
from .engine_context import IdAllocator, SimulationBaseline
from .expense_playbook import ExpensePlaybook, FAIL_REASONS
from .footprint_models import IntegrationFootprint, LinkFootprint, VoucherFootprint, VoucherLineFootprint

_ALLOCATED_TABLES = (
    "business_document",
    "business_document_line",
    "accounting_voucher",
    "accounting_voucher_line",
    "integration_result",
)


class ApprovalPipeline:
    """Build one atomic batch without touching pre-cutover historical documents."""

    def __init__(
        self,
        baseline: SimulationBaseline,
        id_allocator: IdAllocator,
        *,
        seed: int | None = None,
    ) -> None:
        self.baseline = baseline
        self.id_allocator = id_allocator
        self.rng = random.Random(seed)

    def build_batch(self, conn, submission_count: int, now: datetime) -> ApprovalFlowBatch:
        now_local = now.replace(tzinfo=None) if now.tzinfo else now
        batch = ApprovalFlowBatch(submissions=self._generate_submissions(submission_count, now_local))

        approval_capacity = self._approval_capacity(submission_count, now_local)
        for source in self._approval_candidates(conn, now_local, approval_capacity):
            rejected = self._is_rejected(source)
            batch.transitions.append(DocumentTransition(
                doc_id=source.id,
                from_status=DOC_STATUS_PENDING_APPROVAL,
                to_status=DOC_STATUS_REJECTED if rejected else DOC_STATUS_PENDING_VOUCHER,
                approve_time=now_local,
            ))

        voucher_capacity = self._voucher_capacity(submission_count, now_local)
        voucher_sources = self._voucher_candidates(conn, now_local, voucher_capacity)
        batch.source_documents = {item.id: item for item in voucher_sources}
        self._voucherize(batch, voucher_sources, now_local)
        validate_approval_flow(batch)
        return batch

    def _generate_submissions(self, count: int, now: datetime):
        if count <= 0:
            return []
        shadow_ids = {name: self.id_allocator.peek_next_id(name) for name in _ALLOCATED_TABLES}
        shadow = IdAllocator(shadow_ids)
        playbook = ExpensePlaybook(self.baseline, shadow, seed=self.rng.randint(1, 1_000_000))
        documents = []
        for event in playbook.generate_batch(count=count, target_date=now):
            doc = event.document
            expected_doc_id = self.id_allocator.next_id("business_document")
            if expected_doc_id != doc.id:
                raise RuntimeError("Document allocator diverged while staging approval submissions")
            for line in doc.lines:
                expected_line_id = self.id_allocator.next_id("business_document_line")
                if expected_line_id != line.id:
                    raise RuntimeError("Document-line allocator diverged while staging submissions")
            # Runtime ``now`` is already the authoritative HKT business clock.
            # Keep a small burst spread and do not inherit the host OS timezone
            # assumptions inside the legacy complete-event playbook.
            doc.submit_time = now - timedelta(seconds=self.rng.randint(0, 90))
            doc.nature = SIMULATED_FLOW_NATURE
            doc.status = DOC_STATUS_PENDING_APPROVAL
            doc.approve_time = None
            documents.append(doc)
        return documents

    def _approval_candidates(self, conn, now: datetime, capacity: int) -> list[SourceDocument]:
        if capacity <= 0:
            return []
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, org_id, type, amount, submit_time "
                "FROM business_document "
                "WHERE submit_time >= %s AND submit_time <= %s "
                "AND nature = %s AND status = %s "
                "ORDER BY submit_time, id LIMIT %s",
                (
                    now - timedelta(days=30), now,
                    SIMULATED_FLOW_NATURE, DOC_STATUS_PENDING_APPROVAL,
                    max(100, capacity * 8),
                ),
            )
            rows = cursor.fetchall()
        eligible = []
        for doc_id, org_id, doc_type, amount, submit_time in rows:
            if now - submit_time < self._approval_delay(int(doc_id)):
                continue
            eligible.append(SourceDocument(
                id=int(doc_id), org_id=int(org_id), type=str(doc_type), amount=Decimal(amount),
                submit_time=submit_time, approve_time=now, item_names=(),
            ))
            if len(eligible) >= capacity:
                break
        return eligible

    def _voucher_candidates(self, conn, now: datetime, capacity: int) -> list[SourceDocument]:
        if capacity <= 0:
            return []
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT d.id, d.org_id, d.type, d.amount, d.submit_time, d.approve_time, "
                "GROUP_CONCAT(l.item_name ORDER BY l.id SEPARATOR '|||') "
                "FROM business_document d "
                "JOIN business_document_line l ON l.doc_id = d.id "
                "WHERE d.submit_time >= %s AND d.nature = %s "
                "AND d.status = %s AND d.approve_time IS NOT NULL "
                "GROUP BY d.id, d.org_id, d.type, d.amount, d.submit_time, d.approve_time "
                "ORDER BY d.approve_time, d.id LIMIT %s",
                (
                    now - timedelta(days=30), SIMULATED_FLOW_NATURE,
                    DOC_STATUS_PENDING_VOUCHER, max(120, capacity * 8),
                ),
            )
            rows = cursor.fetchall()
        eligible = []
        for doc_id, org_id, doc_type, amount, submit_time, approve_time, item_names in rows:
            if now - approve_time < self._voucher_delay(int(doc_id)):
                continue
            eligible.append(SourceDocument(
                id=int(doc_id), org_id=int(org_id), type=str(doc_type), amount=Decimal(amount),
                submit_time=submit_time, approve_time=approve_time,
                item_names=tuple(str(item_names or "明细1").split("|||")),
            ))
            if len(eligible) >= capacity:
                break
        return eligible

    def _voucherize(self, batch: ApprovalFlowBatch, sources: list[SourceDocument], now: datetime) -> None:
        remaining = list(sources)
        while remaining:
            source = remaining.pop(0)
            relation_roll = self._stable_roll(source.id, 37)
            same_org = [item for item in remaining if item.org_id == source.org_id]
            if relation_roll < 0.20 and same_org:
                merge_count = min(len(same_org), 1 + int(self._stable_roll(source.id, 41) * 3))
                merged = [source, *same_org[:merge_count]]
                merged_ids = {item.id for item in merged[1:]}
                remaining = [item for item in remaining if item.id not in merged_ids]
                self._append_voucher_component(batch, merged, [sum((item.amount for item in merged), Decimal("0.00"))], now)
            elif relation_roll > 0.96:
                first = (source.amount * Decimal("0.62")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                self._append_voucher_component(batch, [source], [first, source.amount - first], now)
            else:
                self._append_voucher_component(batch, [source], [source.amount], now)

    def _append_voucher_component(
        self,
        batch: ApprovalFlowBatch,
        sources: list[SourceDocument],
        voucher_amounts: list[Decimal],
        now: datetime,
    ) -> None:
        item_names = [item for source in sources for item in source.item_names] or ["明细1"]
        for amount in voucher_amounts:
            voucher_id = self.id_allocator.next_id("accounting_voucher")
            subject_lines = build_voucher_lines(sources[0].type, amount, item_names, self.rng)
            lines = [
                VoucherLineFootprint(
                    id=self.id_allocator.next_id("accounting_voucher_line"),
                    voucher_id=voucher_id,
                    subject_code=code,
                    subject_name=name,
                    debit=debit,
                    credit=credit,
                )
                for code, name, debit, credit in subject_lines
            ]
            gen_time = max(max(item.approve_time for item in sources), now - timedelta(seconds=30))
            int_time = max(gen_time, now)
            failed = self.rng.random() < (0.12 if sources[0].org_id % 11 == 0 else 0.025)
            voucher = VoucherFootprint(
                id=voucher_id,
                org_id=sources[0].org_id,
                voucher_no=f"V-{voucher_id}",
                type="记账凭证",
                gen_time=gen_time,
                int_time=int_time,
                status="集成失败" if failed else "已集成",
                debit=amount,
                credit=amount,
                lines=lines,
            )
            batch.vouchers.append(voucher)
            for source in sources:
                batch.links.append(LinkFootprint(doc_id=source.id, voucher_id=voucher_id))
            error_code, error_message = self.rng.choice(FAIL_REASONS) if failed else ("", "成功")
            batch.integrations.append(IntegrationFootprint(
                id=self.id_allocator.next_id("integration_result"),
                voucher_id=voucher_id,
                status="FAIL" if failed else "SUCCESS",
                retry_count=self.rng.randint(1, 3) if failed else 0,
                error_code=error_code,
                error_message=error_message,
                integration_time=int_time,
            ))
        for source in sources:
            batch.transitions.append(DocumentTransition(
                doc_id=source.id,
                from_status=DOC_STATUS_PENDING_VOUCHER,
                to_status=DOC_STATUS_COMPLETED,
            ))

    def _approval_capacity(self, submissions: int, now: datetime) -> int:
        calendar_weight = 1.0 if day_type(now.date()) in ("workday", "makeup_workday") else 0.12
        if 8 <= now.hour < 19:
            hour_weight = 1.0
        elif 7 <= now.hour < 21:
            hour_weight = 0.18
        else:
            hour_weight = 0.0
        return max(0, round(submissions * self.rng.uniform(0.72, 1.06) * calendar_weight * hour_weight))

    def _voucher_capacity(self, submissions: int, now: datetime) -> int:
        calendar_weight = 1.0 if day_type(now.date()) in ("workday", "makeup_workday") else 0.10
        hour_weight = 1.0 if 7 <= now.hour < 22 else 0.05
        closing_boost = 1.22 if now.day >= 26 else 1.0
        return max(
            0,
            round(submissions * self.rng.uniform(0.68, 1.08) * calendar_weight * hour_weight * closing_boost),
        )

    @classmethod
    def _approval_delay(cls, doc_id: int) -> timedelta:
        roll = cls._stable_roll(doc_id, 11)
        if roll < 0.12:
            minutes = 3 + int(cls._stable_roll(doc_id, 12) * 12)
        elif roll < 0.67:
            minutes = 15 + int(cls._stable_roll(doc_id, 13) * 75)
        elif roll < 0.92:
            minutes = 90 + int(cls._stable_roll(doc_id, 14) * 270)
        elif roll < 0.98:
            minutes = 360 + int(cls._stable_roll(doc_id, 15) * 360)
        else:
            minutes = 1_440 + int(cls._stable_roll(doc_id, 16) * 1_440)
        return timedelta(minutes=minutes)

    @classmethod
    def _voucher_delay(cls, doc_id: int) -> timedelta:
        roll = cls._stable_roll(doc_id, 21)
        if roll < 0.45:
            minutes = 3 + int(cls._stable_roll(doc_id, 22) * 27)
        elif roll < 0.80:
            minutes = 30 + int(cls._stable_roll(doc_id, 23) * 90)
        elif roll < 0.96:
            minutes = 120 + int(cls._stable_roll(doc_id, 24) * 360)
        else:
            minutes = 720 + int(cls._stable_roll(doc_id, 25) * 1_440)
        return timedelta(minutes=minutes)

    @classmethod
    def _is_rejected(cls, source: SourceDocument) -> bool:
        threshold = 0.075 if source.amount >= Decimal("50000") else 0.035
        return cls._stable_roll(source.id, 31) < threshold

    @staticmethod
    def _stable_roll(identifier: int, salt: int) -> float:
        return random.Random(identifier * 1_000_003 + salt).random()
