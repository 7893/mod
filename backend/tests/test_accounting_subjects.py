"""KI-052 会计科目分录生成器回归测试：借贷平衡、多科目、税率、各单据类型。"""
from __future__ import annotations

import random
from decimal import Decimal

from simulation.accounting_subjects import build_lines


def _balanced(lines):
    return sum(ln[2] for ln in lines) == sum(ln[3] for ln in lines)


def test_expense_multi_subject_balanced():
    rng = random.Random(1)
    lines = build_lines("费用报销单", Decimal("3200.00"), ["差旅交通费", "住宿费"], rng)
    assert _balanced(lines)
    names = {ln[1] for ln in lines}
    # 借方应含费用科目、贷方应含资金科目
    assert any("管理费用" in n for n in names)
    assert any(n in ("银行存款", "库存现金", "其他应收款-备用金") for n in names)


def test_entertainment_no_input_tax():
    # 业务招待费进项税不得抵扣 → 不应出现进项税科目
    rng = random.Random(2)
    lines = build_lines("费用报销单", Decimal("1500.00"), ["业务招待费"], rng)
    assert _balanced(lines)
    assert all("进项税" not in ln[1] for ln in lines)


def test_purchase_input_tax_13pct():
    rng = random.Random(3)
    lines = build_lines("采购结算单", Decimal("11300.00"), [], rng)
    assert _balanced(lines)
    # 库存商品净额 10000 + 进项税 1300
    goods = [ln for ln in lines if ln[1] == "库存商品"][0]
    tax = [ln for ln in lines if "进项税" in ln[1]][0]
    assert goods[2] == Decimal("10000.00")
    assert tax[2] == Decimal("1300.00")


def test_income_output_tax_6pct():
    rng = random.Random(4)
    lines = build_lines("收入结算单", Decimal("10600.00"), [], rng)
    assert _balanced(lines)
    rev = [ln for ln in lines if ln[1] == "主营业务收入"][0]
    tax = [ln for ln in lines if "销项税" in ln[1]][0]
    assert rev[3] == Decimal("10000.00")
    assert tax[3] == Decimal("600.00")


def test_all_types_balanced():
    rng = random.Random(5)
    for dt in ("费用报销单", "采购结算单", "工程付款单", "资金收付单", "收入结算单", "资产处理单"):
        for amt in ("100.00", "5678.90", "123456.78"):
            lines = build_lines(dt, Decimal(amt), ["明细1"], rng)
            assert _balanced(lines), f"{dt} {amt} 借贷不平"


def test_unknown_type_falls_back_to_expense():
    rng = random.Random(6)
    lines = build_lines("未知单据类型", Decimal("999.99"), ["明细1"], rng)
    assert _balanced(lines)
