"""Expense reimbursement simulation playbook for realistic multi-table footprint generation."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from .engine_context import IdAllocator, SimulationBaseline
from .accounting_subjects import build_lines as build_voucher_lines
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

    def _sample_worktime(self, target_date: datetime) -> datetime:
        """采样一个真实的提交时刻。

        真实作息：核心 8:30-11:30 与 13:30-17:00；允许少量早到/加班/夜间，
        但为偶发、随机、不成固定规律（避免"每周六8点加班"这类机械模式）。
        财务周期性：月末结账、季度末、报税期（每月上旬）等高强度时段，加班概率升高。
        """
        y, mo, d = target_date.year, target_date.month, target_date.day

        # 财务高强度诱因：月末(26-31)、季度末月(3/6/9/12)的月末、报税期(每月1-15)
        is_month_end = d >= 26
        is_quarter_end = mo in (3, 6, 9, 12) and d >= 24
        is_tax_period = 1 <= d <= 15  # 申报期通常月中前
        intensity = 0.0
        if is_month_end:
            intensity += 0.35
        if is_quarter_end:
            intensity += 0.25
        if is_tax_period:
            intensity += 0.10

        # 加班概率：基础很低，受强度诱因抬升；周末/夜间加班更罕见但强度期会出现
        # 用日期特征 + 随机，保证不成固定模式
        overtime_prob = min(0.45, 0.04 + intensity)
        early_prob = min(0.20, 0.03 + intensity * 0.3)

        r = self.rng.random()
        if r < early_prob:
            # 少量早到：8:00-8:30 之间（强度期偶尔更早 7:30）
            if intensity > 0.3 and self.rng.random() < 0.3:
                base = time(7, self.rng.randint(30, 59))
            else:
                base = time(8, self.rng.randint(0, 29))
            hh, mm = base.hour, base.minute
        elif r < early_prob + overtime_prob:
            # 加班：17:00 后，强度越高拖得越晚（偶发到 19-21 点，极少更晚）
            if intensity > 0.4 and self.rng.random() < 0.35:
                hh = self.rng.choice([18, 19, 20]) if self.rng.random() < 0.6 else self.rng.choice([20, 21])
            else:
                hh = 17 if self.rng.random() < 0.6 else 18
            mm = self.rng.randint(0, 59)
        else:
            # 核心工作时段：8:30-11:30 或 13:30-17:00，按上午/下午真实占比
            if self.rng.random() < 0.52:  # 上午
                total_min = self.rng.randint(0, 179)  # 8:30 起 3 小时
                hh, mm = divmod(510 + total_min, 60)  # 510=8:30
            else:  # 下午 13:30-17:00 (3.5h)
                total_min = self.rng.randint(0, 209)
                hh, mm = divmod(810 + total_min, 60)  # 810=13:30

        ss = self.rng.randint(0, 59)
        # 周末/节假日：绝大多数不加班；仅在强度诱因下小概率保留（否则挪回工作日语义由上层配额控制）
        return datetime(y, mo, d, int(hh), int(mm), ss)

    def generate_event(self, target_date: Optional[datetime] = None) -> EventFootprint:
        """Generate a single complete, valid, balanced event footprint."""
        # 1. Determine timeline
        baseline_dt = self.baseline.latest_business_date
        # KI-077 fix: cap baseline to now to prevent future date pollution propagation
        now = datetime.now()
        effective_baseline = min(baseline_dt, now)
        if target_date is None:
            # Default to next business day at 08:30+
            base_day = effective_baseline.date() + timedelta(days=1)
            target_date = datetime.combine(base_day, time(8, 30))

        if target_date.tzinfo is not None:
            target_date = target_date.replace(tzinfo=None)

        # Generate realistic working hour within target date or honor passed time
        if target_date.hour != 0 or target_date.minute != 0 or target_date.second != 0:
            submit_time = target_date
        else:
            submit_time = self._sample_worktime(target_date)

        if submit_time <= effective_baseline:
            if effective_baseline == now:
                # We are in the pollution scenario, don't generate in the future
                submit_time = now - timedelta(seconds=self.rng.randint(0, 60))
            else:
                submit_time = effective_baseline + timedelta(seconds=self.rng.randint(60, 3600))

        # Strictly ordered future stages
        approve_delta = timedelta(seconds=self.rng.randint(180, 5400))  # 3 min ~ 1.5 hr
        approve_time = submit_time + approve_delta

        gen_delta = timedelta(seconds=self.rng.randint(60, 900))  # 1 min ~ 15 min
        gen_time = approve_time + gen_delta

        int_delta = timedelta(seconds=self.rng.randint(15, 180))  # 15s ~ 3 min
        int_time = gen_time + int_delta

        # KI-077 fix: final safety check, bound all timestamps to now if they drift into future
        if int_time > now:
            int_time = now
            gen_time = min(gen_time, int_time - timedelta(seconds=1))
            approve_time = min(approve_time, gen_time - timedelta(seconds=1))
            submit_time = min(submit_time, approve_time - timedelta(seconds=1))

        # 2. Select actor: pick online unit weighted by org size (user count), with realistic applicant concentration
        # Causal link: larger entities submit proportionally higher volume
        org_weights = [
            max(0.5, len(self.baseline.org_users.get(oid, [])) / 10.0)
            for oid in self.baseline.online_org_ids
        ]
        org_id = self.rng.choices(self.baseline.online_org_ids, weights=org_weights, k=1)[0]
        unit_users = self.baseline.org_users[org_id]
        handlers = [u["name"] for u in unit_users if u.get("role") == "经办人"]
        
        # Causal link: ~15% of units exhibit high handler concentration (single person bottlenecks ~75% of operations)
        is_concentrated = (org_id % 7 == 0 or org_id % 13 == 0)
        if handlers:
            if is_concentrated and len(handlers) > 1:
                handler_weights = [0.75] + [0.25 / (len(handlers) - 1)] * (len(handlers) - 1)
                applicant = self.rng.choices(handlers, weights=handler_weights, k=1)[0]
            else:
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

        # 6. Integration status
        # Causal link: units with handler concentration or training deficits exhibit higher error rates (~15% vs ~2%)
        fail_prob = 0.15 if is_concentrated or (org_id % 11 == 0) else 0.02
        is_success = self.rng.random() >= fail_prob
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

        # 7. Voucher & voucher lines —— KI-052 真实多科目分录（按单据类型+明细类别，含税，借贷平衡）
        voucher_no = f"V-{vch_id}"
        item_names = [ln.item_name for ln in doc_lines]
        subject_lines = build_voucher_lines("费用报销单", total_amount, item_names, self.rng)
        voucher_lines = []
        for (code, name, dr, cr) in subject_lines:
            voucher_lines.append(
                VoucherLineFootprint(
                    id=self.id_allocator.next_id("accounting_voucher_line"),
                    voucher_id=vch_id,
                    subject_code=code,
                    subject_name=name,
                    debit=dr,
                    credit=cr,
                )
            )
        vch_debit = sum(line.debit for line in voucher_lines)
        vch_credit = sum(line.credit for line in voucher_lines)

        voucher = VoucherFootprint(
            id=vch_id,
            org_id=org_id,
            voucher_no=voucher_no,
            type="记账凭证",
            gen_time=gen_time,
            int_time=int_time,
            status=vch_status,
            debit=vch_debit,
            credit=vch_credit,
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
