"""Expense reimbursement simulation playbook for realistic multi-table footprint generation."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from .engine_context import IdAllocator, SimulationBaseline
from .footprint_models import (
    DocumentFootprint,
    DocumentLineFootprint,
    EventFootprint,
    IntegrationFootprint,
    LinkFootprint,
    VoucherFootprint,
    VoucherLineFootprint,
)

EXPENSE_ITEMS = [
    "差旅交通费",
    "住宿费",
    "业务招待费",
    "办公耗材采购费",
    "会议及会务培训费",
    "市内交通及通信补贴",
]

FAIL_REASONS = [
    ("ERR_TIMEOUT", "接口网关响应超时"),
    ("ERR_NET_RESET", "底层网络传输连接被重置"),
    ("ERR_BUSY", "核算系统集成端点服务繁忙"),
]


class ExpensePlaybook:
    """
    Playbook for Expense Reimbursement ('费用报销单').

    Enforces:
    - Applicant selected 100% from existing sys_user in the same org.
    - Only online units (status IN '已上线', '稳定运行') can emit business.
    - Date接续 stock baseline (strictly > latest_business_date).
    - Monotonic causal time: submit <= approve <= gen <= int.
    - Exact amount balance: doc.amount == sum(lines) == voucher.debit == voucher.credit.
    - Balanced accounting entries: 1002 银行存款 vs 2202 应付账款.
    - Integration success ~95%, fail ~5%.
    """

    def __init__(self, baseline: SimulationBaseline, id_allocator: IdAllocator, seed: Optional[int] = None):
        self.baseline = baseline
        self.id_allocator = id_allocator
        self.rng = random.Random(seed)

    def generate_event(self, target_date: Optional[datetime] = None) -> EventFootprint:
        """Generate a single complete, valid, balanced event footprint."""
        # 1. Determine timeline
        baseline_dt = self.baseline.latest_business_date
        if target_date is None:
            # Default to next business day at 08:30+
            base_day = baseline_dt.date() + timedelta(days=1)
            target_date = datetime.combine(base_day, time(8, 30))

        if target_date.tzinfo is not None:
            target_date = target_date.replace(tzinfo=None)

        # Generate realistic working hour within target date or honor passed time
        if target_date.hour != 0 or target_date.minute != 0 or target_date.second != 0:
            submit_time = target_date
        else:
            hour = self.rng.choices(
                [9, 10, 11, 14, 15, 16, 17],
                weights=[0.20, 0.25, 0.15, 0.15, 0.15, 0.08, 0.02],
                k=1,
            )[0]
            minute = self.rng.randint(0, 59)
            second = self.rng.randint(0, 59)
            submit_time = datetime(target_date.year, target_date.month, target_date.day, hour, minute, second)

        if submit_time <= baseline_dt:
            submit_time = baseline_dt + timedelta(seconds=self.rng.randint(60, 3600))

        # Strictly ordered future stages
        approve_delta = timedelta(seconds=self.rng.randint(180, 5400))  # 3 min ~ 1.5 hr
        approve_time = submit_time + approve_delta

        gen_delta = timedelta(seconds=self.rng.randint(60, 900))  # 1 min ~ 15 min
        gen_time = approve_time + gen_delta

        int_delta = timedelta(seconds=self.rng.randint(15, 180))  # 15s ~ 3 min
        int_time = gen_time + int_delta

        # 2. Select actor: pick online unit and applicant from that unit's sys_user pool
        org_id = self.rng.choice(self.baseline.online_org_ids)
        unit_users = self.baseline.org_users[org_id]
        handlers = [u["name"] for u in unit_users if u.get("role") == "经办人"]
        if handlers:
            applicant = self.rng.choice(handlers)
        else:
            applicant = self.rng.choice(unit_users)["name"]

        # 3. Generate realistic total amount (e.g. 500.00 ~ 65,000.00 with non-zero cents)
        raw_amount = self.rng.uniform(500.0, 65000.0)
        total_amount = Decimal(str(round(raw_amount, 2)))

        # 4. Allocate IDs
        doc_id = self.id_allocator.next_id("business_document")
        vch_id = self.id_allocator.next_id("accounting_voucher")
        integ_id = self.id_allocator.next_id("integration_result")

        # 5. Generate document lines (1 to 3 lines) summing exactly to total_amount
        line_count = self.rng.choices([1, 2, 3], weights=[0.55, 0.35, 0.10], k=1)[0]
        line_items = self.rng.sample(EXPENSE_ITEMS, k=line_count)

        doc_lines: List[DocumentLineFootprint] = []
        if line_count == 1:
            line_id = self.id_allocator.next_id("business_document_line")
            doc_lines.append(
                DocumentLineFootprint(
                    id=line_id,
                    doc_id=doc_id,
                    item_name=line_items[0],
                    amount=total_amount,
                    quantity=1,
                )
            )
        else:
            # Random split that sums exactly to total_amount
            weights = [self.rng.uniform(0.2, 0.8) for _ in range(line_count)]
            w_sum = sum(weights)
            proportions = [w / w_sum for w in weights]

            accumulated = Decimal("0.00")
            for i in range(line_count - 1):
                part = (total_amount * Decimal(str(proportions[i]))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                line_id = self.id_allocator.next_id("business_document_line")
                doc_lines.append(
                    DocumentLineFootprint(
                        id=line_id,
                        doc_id=doc_id,
                        item_name=line_items[i],
                        amount=part,
                        quantity=1,
                    )
                )
                accumulated += part

            # Remainder goes to final line to prevent any cent divergence
            last_amount = total_amount - accumulated
            line_id = self.id_allocator.next_id("business_document_line")
            doc_lines.append(
                DocumentLineFootprint(
                    id=line_id,
                    doc_id=doc_id,
                    item_name=line_items[-1],
                    amount=last_amount,
                    quantity=1,
                )
            )

        doc_no = f"DOC-{uuid.uuid4().hex[:12].upper()}"
        doc = DocumentFootprint(
            id=doc_id,
            org_id=org_id,
            type="费用报销单",
            doc_no=doc_no,
            applicant=applicant,
            nature="正式业务",
            amount=total_amount,
            submit_time=submit_time,
            approve_time=approve_time,
            status="处理完成",
            lines=doc_lines,
        )

        # 6. Integration status (~95% SUCCESS, ~5% FAIL)
        is_success = self.rng.random() < 0.95
        if is_success:
            vch_status = "已集成"
            integ_status = "SUCCESS"
            retry_count = 0
            err_code = ""
            err_msg = "成功"
        else:
            vch_status = "集成失败"
            integ_status = "FAIL"
            retry_count = self.rng.randint(1, 3)
            err_code, err_msg = self.rng.choice(FAIL_REASONS)

        # 7. Voucher & voucher lines (Debit: 1002 银行存款, Credit: 2202 应付账款)
        voucher_no = f"V-{vch_id}"
        vl1_id = self.id_allocator.next_id("accounting_voucher_line")
        vl2_id = self.id_allocator.next_id("accounting_voucher_line")

        voucher_lines = [
            VoucherLineFootprint(
                id=vl1_id,
                voucher_id=vch_id,
                subject_code="1002",
                subject_name="银行存款",
                debit=total_amount,
                credit=Decimal("0.00"),
            ),
            VoucherLineFootprint(
                id=vl2_id,
                voucher_id=vch_id,
                subject_code="2202",
                subject_name="应付账款",
                debit=Decimal("0.00"),
                credit=total_amount,
            ),
        ]

        voucher = VoucherFootprint(
            id=vch_id,
            org_id=org_id,
            voucher_no=voucher_no,
            type="记账凭证",
            gen_time=gen_time,
            int_time=int_time,
            status=vch_status,
            debit=total_amount,
            credit=total_amount,
            lines=voucher_lines,
        )

        # 8. Link & Integration
        link = LinkFootprint(doc_id=doc_id, voucher_id=vch_id)
        integration = IntegrationFootprint(
            id=integ_id,
            voucher_id=vch_id,
            status=integ_status,
            retry_count=retry_count,
            error_code=err_code,
            error_message=err_msg,
            integration_time=int_time,
        )

        return EventFootprint(
            document=doc,
            voucher=voucher,
            link=link,
            integration=integration,
        )

    def generate_batch(
        self, count: int, target_date: Optional[datetime] = None
    ) -> List[EventFootprint]:
        """Generate a batch of cohesive events."""
        events: List[EventFootprint] = []
        for _ in range(count):
            events.append(self.generate_event(target_date=target_date))
        return events
