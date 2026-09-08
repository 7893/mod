#!/usr/bin/env python3
"""
KI-051 阶段2 并行高性能版：4核并行生成 TSV（独立 id 区间不撞）→ 串行 LOAD DATA。

发挥 jpa 多核：生成阶段（CPU 瓶颈）多进程并行，写入阶段 LOAD DATA 快速。
复用 ExpensePlaybook 保勾稽。每 worker 预分配不重叠 id 区间。
需 MOD_SIMULATION_ENGINE_ENABLED=true。
"""
from __future__ import annotations

import argparse
import calendar
import csv
import os
import random
import sys
import time
from datetime import datetime, date, timedelta
from multiprocessing import Pool
from pathlib import Path

from dotenv import load_dotenv
import pymysql

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
for f in [BASE_DIR / ".env.systemd", BASE_DIR / ".env"]:
    if f.exists():
        load_dotenv(f); break

from simulation.expense_playbook import ExpensePlaybook
from simulation.engine_context import IdAllocator, load_simulation_baseline
from simulation.models import TimePatternSystem

WINDOW_BEGIN = date(2023, 8, 1)
WINDOW_END = date.today()
TMP = BASE_DIR / "scripts" / "kiro" / "output" / "ki051_par"
NWORKERS = 4
# 每凭证最大 id 消耗：单据1 明细3 凭证1 分录2 集成1
MAX_PER_VCH = {"business_document": 1, "business_document_line": 3,
               "accounting_voucher": 1, "accounting_voucher_line": 2,
               "integration_result": 1}


def get_conn():
    return pymysql.connect(
        host=os.getenv("MOD_DB_HOST", "127.0.0.1"), port=int(os.getenv("MOD_DB_PORT", "3306")),
        user=os.getenv("MOD_DB_USER", ""), password=os.getenv("MOD_DB_PASSWORD", ""),  # secret-scan: allow
        database=os.getenv("MOD_DB_NAME", "mod"), charset="utf8mb4", autocommit=True, local_infile=True)


def months_between(a, b):
    y, m = a.year, a.month
    while (y, m) <= (b.year, b.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1; y += 1


def worker(wargs):
    """一个 worker：生成分配给它的凭证，写 6 个 TSV，返回文件路径。"""
    wid, id_bases, month_tasks = wargs
    conn = get_conn()
    baseline = load_simulation_baseline(conn)
    unit_starts = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id,start_date FROM org_unit WHERE status IN ('已上线','稳定运行','双轨运行中')")
        unit_starts = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()

    allocator = IdAllocator(dict(id_bases))
    TMP.mkdir(parents=True, exist_ok=True)
    files = {n: TMP / f"w{wid}_{n}.tsv" for n in ["bd", "bdl", "av", "avl", "dvl", "ir"]}
    fh = {k: open(v, "w", newline="", encoding="utf-8") for k, v in files.items()}
    wr = {k: csv.writer(f, delimiter="\t", lineterminator="\n") for k, f in fh.items()}

    made = 0
    for (y, m, quota) in month_tasks:
        mid = date(y, m, 15)
        eligible = [oid for oid, sd in unit_starts.items() if sd and sd <= mid]
        if not eligible:
            continue
        baseline.latest_business_date = datetime(y, m, 1) - timedelta(seconds=1)
        baseline.online_org_ids = eligible
        pb = ExpensePlaybook(baseline, allocator, seed=90000 + wid * 100 + m)
        last_day = calendar.monthrange(y, m)[1]
        for _ in range(quota):
            ev = pb.generate_event(target_date=datetime(y, m, random.randint(1, last_day)))
            d, v, lk, ig = ev.document, ev.voucher, ev.link, ev.integration
            wr["bd"].writerow((d.id, d.org_id, d.type, d.doc_no, d.applicant, d.nature,
                               str(d.amount), d.submit_time, d.approve_time, d.status))
            for ln in d.lines:
                wr["bdl"].writerow((ln.id, ln.doc_id, ln.item_name, str(ln.amount), ln.quantity))
            wr["av"].writerow((v.id, v.org_id, v.voucher_no, v.type, v.gen_time, v.int_time,
                               v.status, str(v.debit), str(v.credit)))
            for vl in v.lines:
                wr["avl"].writerow((vl.id, vl.voucher_id, vl.subject_code, vl.subject_name,
                                    str(vl.debit), str(vl.credit)))
            wr["dvl"].writerow((lk.doc_id, lk.voucher_id))
            wr["ir"].writerow((ig.id, ig.voucher_id, ig.status, ig.retry_count,
                               ig.error_code, ig.error_message, ig.integration_time))
            made += 1
    for f in fh.values():
        f.close()
    return wid, made, {k: str(v) for k, v in files.items()}


def load_file(conn, path, table, cols):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    sql = (f"LOAD DATA LOCAL INFILE '{path}' INTO TABLE `{table}` CHARACTER SET utf8mb4 "
           f"FIELDS TERMINATED BY '\\t' LINES TERMINATED BY '\\n' ({','.join(cols)})")
    with conn.cursor() as cur:
        cur.execute(sql)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--target", type=int, required=True)
    args = ap.parse_args()
    if args.execute and os.environ.get("MOD_SIMULATION_ENGINE_ENABLED", "").lower() not in ("true", "1", "yes"):
        print("[BLOCKED] 需 MOD_SIMULATION_ENGINE_ENABLED=true"); sys.exit(1)

    conn = get_conn()
    baseline = load_simulation_baseline(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT id,start_date FROM org_unit WHERE status IN ('已上线','稳定运行','双轨运行中')")
        unit_starts = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) FROM (SELECT voucher_id FROM accounting_voucher_line GROUP BY voucher_id HAVING ABS(SUM(debit)-SUM(credit))>0.001) t")
        imb0 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM business_document_line l LEFT JOIN business_document d ON l.doc_id=d.id WHERE d.id IS NULL")
        orp0 = cur.fetchone()[0]
    print(f"[基线] 写前勾稽 借贷不平{imb0} 孤儿{orp0} | 目标 {args.target:,} 凭证", flush=True)

    # 按月配额
    mlist = list(months_between(WINDOW_BEGIN, WINDOW_END))
    mw = []
    for (y, m) in mlist:
        online = sum(1 for sd in unit_starts.values() if sd and sd <= date(y, m, 15))
        mw.append(max(0.0, online * TimePatternSystem.get_activity_level(datetime(y, m, 15, 12))))
    wsum = sum(mw) or 1.0
    mquota = [int(args.target * w / wsum) for w in mw]

    # 把每月配额切成 NWORKERS 份，分给各 worker
    worker_tasks = [[] for _ in range(NWORKERS)]
    for idx, (y, m) in enumerate(mlist):
        q = mquota[idx]
        if q <= 0:
            continue
        per = q // NWORKERS
        rem = q % NWORKERS
        for w in range(NWORKERS):
            wq = per + (1 if w < rem else 0)
            if wq > 0:
                worker_tasks[w].append((y, m, wq))
    worker_total = [sum(t[2] for t in ts) for ts in worker_tasks]

    # 给每个 worker 预留不重叠 id 区间
    base = dict(baseline.next_ids)
    wargs = []
    cursor_ids = dict(base)
    for w in range(NWORKERS):
        id_bases = dict(cursor_ids)
        # 该 worker 最多消耗
        wt = worker_total[w]
        for tbl, mx in MAX_PER_VCH.items():
            cursor_ids[tbl] = cursor_ids.get(tbl, 1) + wt * mx + 10
        wargs.append((w, id_bases, worker_tasks[w]))

    print(f"[并行] {NWORKERS} worker，各约 {worker_total} 凭证", flush=True)
    if not args.execute:
        print("[DRY] 仅规划，不生成。"); conn.close(); return

    t0 = time.perf_counter()
    with Pool(NWORKERS) as pool:
        results = pool.map(worker, wargs)
    gen_dur = time.perf_counter() - t0
    total_made = sum(r[1] for r in results)
    print(f"[生成完成] {total_made:,} 凭证，并行生成用时 {gen_dur:.0f}s ({total_made/gen_dur*60:,.0f}/分)", flush=True)

    # 串行 LOAD（按外键顺序：所有 worker 的父表先，再子表）
    t1 = time.perf_counter()
    order = [("bd", "business_document", ["id","org_id","type","doc_no","applicant","nature","amount","submit_time","approve_time","status"]),
             ("av", "accounting_voucher", ["id","org_id","voucher_no","type","gen_time","int_time","status","debit","credit"]),
             ("bdl", "business_document_line", ["id","doc_id","item_name","amount","quantity"]),
             ("avl", "accounting_voucher_line", ["id","voucher_id","subject_code","subject_name","debit","credit"]),
             ("dvl", "document_voucher_link", ["doc_id","voucher_id"]),
             ("ir", "integration_result", ["id","voucher_id","status","retry_count","error_code","error_message","integration_time"])]
    for key, table, cols in order:
        for wid, made, files in results:
            load_file(conn, files[key], table, cols)
        print(f"  LOAD {table} 完成", flush=True)
    load_dur = time.perf_counter() - t1
    print(f"[LOAD完成] 用时 {load_dur:.0f}s", flush=True)

    # 清理文件
    for wid, made, files in results:
        for p in files.values():
            try: os.remove(p)
            except OSError: pass

    # 勾稽校验
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM (SELECT voucher_id FROM accounting_voucher_line GROUP BY voucher_id HAVING ABS(SUM(debit)-SUM(credit))>0.001) t")
        imb = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM business_document_line l LEFT JOIN business_document d ON l.doc_id=d.id WHERE d.id IS NULL")
        orp = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM accounting_voucher")
        vtot = cur.fetchone()[0]
    print(f"\n[写后勾稽] 借贷不平{imb} 孤儿{orp} (写前{imb0}/{orp0}) | 凭证总数 {vtot:,}", flush=True)
    print(f"[总用时] {time.perf_counter()-t0:.0f}s", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
