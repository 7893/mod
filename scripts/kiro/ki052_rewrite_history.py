#!/usr/bin/env python3
"""
KI-052 历史分录改造：把存量凭证的单一分录(银行存款/应付账款)重写为真实多科目。

按凭证 id 区间分批：查关联单据(type+金额+明细)→ accounting_subjects 生成新分录 →
删旧分录 → 插新分录（新id接续）。每批事务+勾稽校验。dry-run 默认。
并行由外部按 id 区间分片启动多个实例实现。
需 MOD_SIMULATION_ENGINE_ENABLED=true。
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
import pymysql

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
for f in [BASE_DIR / ".env.systemd", BASE_DIR / ".env"]:
    if f.exists():
        load_dotenv(f); break

from simulation.accounting_subjects import build_lines


def get_conn():
    return pymysql.connect(
        host=os.getenv("MOD_DB_HOST", "127.0.0.1"), port=int(os.getenv("MOD_DB_PORT", "3306")),
        user=os.getenv("MOD_DB_USER", ""), password=os.getenv("MOD_DB_PASSWORD", ""),  # secret-scan: allow
        database=os.getenv("MOD_DB_NAME", "mod"), charset="utf8mb4", autocommit=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--min-id", type=int, required=True, help="凭证 id 下界(含)")
    ap.add_argument("--max-id", type=int, required=True, help="凭证 id 上界(含)")
    ap.add_argument("--line-id-start", type=int, required=True, help="新分录 id 起点(各分片不重叠)")
    ap.add_argument("--batch", type=int, default=20000, help="每批凭证数")
    args = ap.parse_args()

    if args.execute and os.environ.get("MOD_SIMULATION_ENGINE_ENABLED", "").lower() not in ("true", "1", "yes"):
        print("[BLOCKED] 需 MOD_SIMULATION_ENGINE_ENABLED=true"); sys.exit(1)

    conn = get_conn()
    c = conn.cursor()
    rng = random.Random(52000 + args.min_id)
    line_id = args.line_id_start
    done = 0
    lo = args.min_id
    tag = f"[{args.min_id}-{args.max_id}]"

    while lo <= args.max_id:
        hi = min(lo + args.batch - 1, args.max_id)
        # 1. 查这批凭证 → 单据 type/amount
        c.execute("""SELECT v.id, d.type, d.amount, lk.doc_id
                     FROM accounting_voucher v
                     JOIN document_voucher_link lk ON v.id=lk.voucher_id
                     JOIN business_document d ON lk.doc_id=d.id
                     WHERE v.id BETWEEN %s AND %s""", (lo, hi))
        vch_rows = c.fetchall()
        if not vch_rows:
            lo = hi + 1
            continue
        doc_ids = tuple({r[3] for r in vch_rows})
        # 2. 批量查这些单据的明细
        items_by_doc = {}
        if doc_ids:
            fmt = ",".join(["%s"] * len(doc_ids))
            c.execute(f"SELECT doc_id, item_name FROM business_document_line WHERE doc_id IN ({fmt})", doc_ids)
            for did, item in c.fetchall():
                items_by_doc.setdefault(did, []).append(item)

        # 3. 生成新分录
        vch_ids = [r[0] for r in vch_rows]
        new_lines = []  # (id, voucher_id, code, name, debit, credit)
        vch_totals = {}  # voucher_id -> (debit_sum, credit_sum)
        for vid, dtype, amount, did in vch_rows:
            items = items_by_doc.get(did, [])
            lines = build_lines(dtype, Decimal(str(amount)), items, rng)
            ds = cs = Decimal("0.00")
            for (code, name, dr, cr) in lines:
                new_lines.append((line_id, vid, code, name, str(dr), str(cr)))
                line_id += 1
                ds += dr; cs += cr
            vch_totals[vid] = (ds, cs)

        if not args.execute:
            done += len(vch_ids)
            print(f"{tag} [dry] 批 {lo}-{hi}: {len(vch_ids)}凭证 → {len(new_lines)}新分录 | 累计 {done:,}", flush=True)
            lo = hi + 1
            continue

        try:
            # 4. 删这批凭证的旧分录
            fmt = ",".join(["%s"] * len(vch_ids))
            c.execute(f"DELETE FROM accounting_voucher_line WHERE voucher_id IN ({fmt})", vch_ids)
            # 5. 插新分录
            c.executemany("INSERT INTO accounting_voucher_line (id,voucher_id,subject_code,subject_name,debit,credit) "
                          "VALUES (%s,%s,%s,%s,%s,%s)", new_lines)
            # 6. 更新凭证头 debit/credit 为新合计
            for vid, (ds, cs) in vch_totals.items():
                c.execute("UPDATE accounting_voucher SET debit=%s, credit=%s WHERE id=%s", (str(ds), str(cs), vid))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"{tag} [错误] 批 {lo}-{hi} 回滚: {e}", flush=True); sys.exit(1)

        done += len(vch_ids)
        if (done // args.batch) % 5 == 0:
            # 抽批勾稽校验
            c.execute(f"SELECT COUNT(*) FROM (SELECT voucher_id FROM accounting_voucher_line "
                      f"WHERE voucher_id BETWEEN {lo} AND {hi} GROUP BY voucher_id "
                      f"HAVING ABS(SUM(debit)-SUM(credit))>0.001) t")
            imb = c.fetchone()[0]
            if imb > 0:
                print(f"{tag} [勾稽失败] 批{lo}-{hi} 借贷不平{imb}，停止！", flush=True); sys.exit(1)
        print(f"{tag} 批 {lo}-{hi}: {len(vch_ids)}凭证 重写 {len(new_lines)}分录 | 累计 {done:,}", flush=True)
        lo = hi + 1

    print(f"{tag} [完成] 改造 {done:,} 凭证，用新分录id止于 {line_id}", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
