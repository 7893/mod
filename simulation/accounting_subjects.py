"""KI-052 会计科目体系与分录生成（符合《企业会计准则》）。

按单据类型 + 明细费用类别生成真实多科目借贷分录，借贷严格平衡，含增值税进/销项。
离线规则驱动，零运行时 AI。供 ExpensePlaybook 及历史改造复用。
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple

# 费用明细类别 → 费用科目(借方)
EXPENSE_ITEM_TO_SUBJECT = {
    "差旅交通费": ("660201", "管理费用-差旅费"),
    "住宿费": ("660201", "管理费用-差旅费"),
    "市内交通及通信补贴": ("660202", "管理费用-交通通讯费"),
    "会议及会务培训费": ("660203", "管理费用-会议费"),
    "业务招待费": ("660204", "管理费用-业务招待费"),
    "办公耗材采购费": ("660205", "管理费用-办公费"),
    "明细1": ("660299", "管理费用-其他"),
    "明细2": ("660299", "管理费用-其他"),
    "明细3": ("660299", "管理费用-其他"),
}
DEFAULT_EXPENSE_SUBJECT = ("660299", "管理费用-其他")

# 费用类别的进项税率（可抵扣）；招待费不可抵扣、补贴无票 → 不计进项
ITEM_TAX_RATE = {
    "差旅交通费": Decimal("0.09"),
    "住宿费": Decimal("0.06"),
    "会议及会务培训费": Decimal("0.06"),
    "办公耗材采购费": Decimal("0.13"),
    "业务招待费": Decimal("0.00"),      # 招待费进项不得抵扣
    "市内交通及通信补贴": Decimal("0.00"),
    "明细1": Decimal("0.00"), "明细2": Decimal("0.00"), "明细3": Decimal("0.00"),
}

BANK = ("100201", "银行存款")
CASH = ("1001", "库存现金")
PETTY = ("122101", "其他应收款-备用金")
TAX_INPUT = ("222101", "应交税费-应交增值税-进项税额")
TAX_OUTPUT = ("222102", "应交税费-应交增值税-销项税额")

Q = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(Q, rounding=ROUND_HALF_UP)


# 分录：(subject_code, subject_name, debit, credit)
Line = Tuple[str, str, Decimal, Decimal]


def build_lines(doc_type: str, total: Decimal, item_names: List[str], rng) -> List[Line]:
    """按单据类型与明细生成借贷平衡的多科目分录（total = 单据总额，含税口径）。"""
    if doc_type in ("费用报销单", "报销申请", "expense") or doc_type not in _DISPATCH:
        return _expense(total, item_names, rng)
    return _DISPATCH[doc_type](total, item_names, rng)


def _split_amount(total: Decimal, n: int, rng) -> List[Decimal]:
    """把 total 拆成 n 份，精确求和不丢分。"""
    if n <= 1:
        return [total]
    ws = [rng.uniform(0.2, 1.0) for _ in range(n)]
    s = sum(ws)
    parts, acc = [], Decimal("0.00")
    for i in range(n - 1):
        p = _q(total * Decimal(str(ws[i] / s)))
        parts.append(p)
        acc += p
    parts.append(total - acc)
    return parts


def _expense(total: Decimal, item_names: List[str], rng) -> List[Line]:
    """费用报销：借 各费用科目(+可抵扣进项税), 贷 银行存款/现金/备用金。
    total 为含税付款额；费用净额 + 进项税 = total。"""
    items = item_names or ["明细1"]
    shares = _split_amount(total, len(items), rng)
    debits: List[Line] = []
    tax_total = Decimal("0.00")
    for it, amt in zip(items, shares):
        code, name = EXPENSE_ITEM_TO_SUBJECT.get(it, DEFAULT_EXPENSE_SUBJECT)
        rate = ITEM_TAX_RATE.get(it, Decimal("0.00"))
        if rate > 0:
            net = _q(amt / (Decimal("1") + rate))
            tax = _q(amt - net)
        else:
            net, tax = amt, Decimal("0.00")
        debits.append((code, name, net, Decimal("0.00")))
        tax_total += tax
    if tax_total > 0:
        debits.append((TAX_INPUT[0], TAX_INPUT[1], tax_total, Decimal("0.00")))
    # 贷方付款：小额偶尔现金/备用金，其余银行存款
    if total < Decimal("2000") and rng.random() < 0.15:
        pay = CASH if rng.random() < 0.6 else PETTY
    else:
        pay = BANK
    credits: List[Line] = [(pay[0], pay[1], Decimal("0.00"), total)]
    return _balance_fix(debits + credits, total)


def _purchase(total: Decimal, items, rng) -> List[Line]:
    # 借 库存商品 + 进项税(13%), 贷 应付账款
    net = _q(total / Decimal("1.13"))
    tax = _q(total - net)
    return [("140501", "库存商品", net, Decimal("0.00")),
            (TAX_INPUT[0], TAX_INPUT[1], tax, Decimal("0.00")),
            ("220201", "应付账款", Decimal("0.00"), total)]


def _project(total: Decimal, items, rng) -> List[Line]:
    net = _q(total / Decimal("1.09"))
    tax = _q(total - net)
    cr = BANK if rng.random() < 0.7 else ("220201", "应付账款")
    return [("160401", "在建工程", net, Decimal("0.00")),
            (TAX_INPUT[0], TAX_INPUT[1], tax, Decimal("0.00")),
            (cr[0], cr[1], Decimal("0.00"), total)]


def _fund(total: Decimal, items, rng) -> List[Line]:
    # 资金划转：银行存款 ↔ 其他货币资金/内部往来
    dr = BANK if rng.random() < 0.5 else ("100301", "其他货币资金")
    cr = ("100301", "其他货币资金") if dr == BANK else BANK
    return [(dr[0], dr[1], total, Decimal("0.00")),
            (cr[0], cr[1], Decimal("0.00"), total)]


def _income(total: Decimal, items, rng) -> List[Line]:
    # 借 银行存款/应收账款, 贷 主营业务收入 + 销项税(6%)
    net = _q(total / Decimal("1.06"))
    tax = _q(total - net)
    dr = BANK if rng.random() < 0.6 else ("112201", "应收账款")
    return [(dr[0], dr[1], total, Decimal("0.00")),
            ("600101", "主营业务收入", Decimal("0.00"), net),
            (TAX_OUTPUT[0], TAX_OUTPUT[1], Decimal("0.00"), tax)]


def _asset(total: Decimal, items, rng) -> List[Line]:
    # 资产处置：借 银行存款, 贷 固定资产清理 + 销项税(13%)
    net = _q(total / Decimal("1.13"))
    tax = _q(total - net)
    return [(BANK[0], BANK[1], total, Decimal("0.00")),
            ("160105", "固定资产清理", Decimal("0.00"), net),
            (TAX_OUTPUT[0], TAX_OUTPUT[1], Decimal("0.00"), tax)]


_DISPATCH = {
    "费用报销单": _expense,
    "采购结算单": _purchase, "采购申请": _purchase,
    "工程付款单": _project,
    "资金收付单": _fund, "转账申请": _fund, "transfer": _fund, "payment": _fund,
    "收入结算单": _income, "receipt": _income,
    "资产处理单": _asset,
    "支付申请": _expense, "借款申请": _fund,
}


def _balance_fix(lines: List[Line], total: Decimal) -> List[Line]:
    """确保借贷平衡：因舍入产生的分差补到最后一条借方费用行。"""
    dsum = sum(line[2] for line in lines)
    csum = sum(line[3] for line in lines)
    diff = _q(csum - dsum)  # 借方应补 diff
    if diff != 0:
        for i in range(len(lines)):
            if lines[i][2] > 0:  # 借方行
                c, n, dr, cr = lines[i]
                lines[i] = (c, n, _q(dr + diff), cr)
                break
    return lines
