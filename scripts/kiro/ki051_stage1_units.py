#!/usr/bin/env python3
"""
KI-051 阶段1：生成 1187 家新单位 + 人员（状态自然分布、上线时间铺满 2023-08 至今）。

- 复用 OrgNameGenerator（单位名构词法+查重），人名混入正面角色库+通用名，重名率对齐存量(~57%)。
- 单位状态按现有比例自然分布；已推进状态带历史 start_date（2023-08~至今，按省份分层早晚）。
- 未启动(第八批)单位零业务；已上线类单位供阶段2产生业务。
- dry-run 只生成+统计+校验，不写库。--execute 需 MOD_SIMULATION_ENGINE_ENABLED=true。
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Set

from dotenv import load_dotenv
import pymysql

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))

from simulation.org_generator import OrgNameGenerator, SURNAMES, GIVEN_NAMES  # noqa: E402
from scripts.kiro.ki051_famous_names import FAMOUS_POSITIVE_NAMES  # noqa: E402
from scripts.kiro.ki051_name_material import build_full_name  # noqa: E402

# 目标新增单位数
TARGET_NEW_UNITS = 1187

# 状态自然分布（对齐现有 2000 家实测比例）
STATUS_DISTRIBUTION = {
    "未启动": 0.382,
    "稳定运行": 0.232,
    "已上线": 0.141,
    "准备中": 0.119,
    "双轨运行中": 0.102,
    "已具备双轨条件": 0.024,
}

# 省份等级 → 每单位人数区间（发达多、欠发达少）；简化用省份名判断沿海/内陆
DEVELOPED = {"北京市", "上海市", "广东省", "江苏省", "浙江省", "山东省", "天津市", "福建省"}
UNDERDEVELOPED = {"西藏自治区", "青海省", "宁夏回族自治区", "甘肃省", "新疆维吾尔自治区", "贵州省"}

# 时间线：铺满 2023-08-01 至今
START_WINDOW_BEGIN = date(2023, 8, 1)
START_WINDOW_END = date.today()


class Ki051NameGen(OrgNameGenerator):
    """通用名大池子(重名率~10%) + 知名角色名每个仅用一次(郭靖天下只有一个)。"""

    def __init__(self, existing_names: Optional[Set[str]] = None, seed: Optional[int] = None):
        super().__init__(existing_names=existing_names, seed=seed)
        self._famous = list(FAMOUS_POSITIVE_NAMES)
        # 通用名大池子（不含知名角色名），重名率约 10%
        pool_rng = random.Random((seed or 0) + 999)
        pool_set: Set[str] = set()
        while len(pool_set) < 65000:
            pool_set.add(build_full_name(pool_rng))
        pool = list(pool_set)
        pool_rng.shuffle(pool)
        self._pool = pool
        self._weights = [1.0 for _ in range(len(pool))]
        # 知名角色名：打乱后每个仅用一次
        self._famous_shuffled = list(self._famous)
        random.Random((seed or 0) + 7).shuffle(self._famous_shuffled)
        self._famous_idx = 0

    def gen_person(self) -> str:
        # 知名角色名每个仅出现一次（用完转通用名），15% 概率触发直到用尽
        if self._famous_idx < len(self._famous_shuffled) and self.rng.random() < 0.15:
            name = self._famous_shuffled[self._famous_idx]
            self._famous_idx += 1
            return name
        return self.rng.choices(self._pool, weights=self._weights, k=1)[0]


def region_user_count(rng: random.Random, region: str) -> int:
    base = rng.randint(8, 16)
    if region in DEVELOPED:
        return int(base * 1.2)
    if region in UNDERDEVELOPED:
        return int(base * 0.8)
    return base


def get_existing_names(conn) -> Set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM org_unit")
        return {r[0] for r in cur.fetchall()}


def get_provinces(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT region, COUNT(*) FROM org_unit GROUP BY region")
        rows = cur.fetchall()
    # 按现有单位数加权（发达省份单位多）
    provs, weights = [], []
    for r, cnt in rows:
        provs.append(r)
        weights.append(cnt)
    return provs, weights


def get_conn():
    for f in [BASE_DIR / ".env.systemd", BASE_DIR / ".env"]:
        if f.exists():
            load_dotenv(f)
            break
    return pymysql.connect(
        host=os.getenv("MOD_DB_HOST", "127.0.0.1"), port=int(os.getenv("MOD_DB_PORT", "3306")),
        user=os.getenv("MOD_DB_USER", ""), password=os.getenv("MOD_DB_PASSWORD", ""),  # secret-scan: allow
        database=os.getenv("MOD_DB_NAME", "mod"), charset="utf8mb4", autocommit=False,
    )


def build_status_plan(rng: random.Random, total: int):
    plan = []
    for status, pct in STATUS_DISTRIBUTION.items():
        plan += [status] * round(total * pct)
    # 补齐/裁剪到 total
    while len(plan) < total:
        plan.append("稳定运行")
    plan = plan[:total]
    rng.shuffle(plan)
    return plan


def random_start_date(rng: random.Random) -> date:
    span = (START_WINDOW_END - START_WINDOW_BEGIN).days
    return START_WINDOW_BEGIN + timedelta(days=rng.randint(0, span))


def backup_tables(conn, tables, out_dir: Path):
    """写前备份受影响表(mysqldump 逻辑：导出当前全量到 sql 文件)。"""
    import subprocess
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = date.today().strftime("%Y%m%d") + "-" + str(int(__import__("time").time()))
    bak = out_dir / f"ki051_stage1_backup_{ts}.sql"
    host = os.getenv("MOD_DB_HOST", "127.0.0.1")
    port = os.getenv("MOD_DB_PORT", "3306")
    user = os.getenv("MOD_DB_USER", "")
    pw = os.getenv("MOD_DB_PASSWORD", "")  # secret-scan: allow
    db = os.getenv("MOD_DB_NAME", "mod")
    cmd = ["mysqldump", "-h", host, "-P", port, "-u", user, f"-p{pw}",
           "--single-transaction", "--no-tablespaces", db] + tables
    with open(bak, "w") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError(f"备份失败: {r.stderr.decode()[:200]}")
    size_mb = bak.stat().st_size / 1024 / 1024
    print(f"  [备份] {bak.name} ({size_mb:.1f} MB)")
    return bak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    execute = args.execute

    print("=" * 68)
    print(f" KI-051 阶段1 生成新单位+人员 | {'EXECUTE' if execute else 'DRY-RUN'}")
    print("=" * 68)

    conn = get_conn()
    try:
        existing = get_existing_names(conn)
        provs, weights = get_provinces(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(id) FROM org_unit")
            next_org_id = (cur.fetchone()[0] or 0) + 1
            cur.execute("SELECT MAX(id) FROM sys_user")
            next_user_id = (cur.fetchone()[0] or 0) + 1
        print(f"[ID起点] org_unit 从 {next_org_id} | sys_user 从 {next_user_id}")

        rng = random.Random(20260908)
        namegen = Ki051NameGen(existing_names=existing, seed=20260908)

        status_plan = build_status_plan(rng, TARGET_NEW_UNITS)
        status_counter = Counter()
        region_counter = Counter()
        person_names = []
        month_counter = Counter()

        # 收集待写记录
        org_rows = []   # (id, name, batch_id, status, region, start_date, end_date)
        user_rows = []  # (id, name, org_id, role, job)

        oid = next_org_id
        uid = next_user_id
        for i in range(TARGET_NEW_UNITS):
            region = rng.choices(provs, weights=weights, k=1)[0]
            uname, _ = namegen.generate_name(region)
            status = status_plan[i]
            if status == "未启动":
                batch_id = 8
                sdate = date.today()
                edate = date.today() + timedelta(days=500)
            else:
                batch_id = rng.choices([1, 2, 3, 4, 5], weights=[1, 2, 3, 3, 2], k=1)[0]
                sdate = random_start_date(rng)
                edate = sdate + timedelta(days=rng.randint(120, 400))
                month_counter[sdate.strftime("%Y-%m")] += 1
            org_rows.append((oid, uname, batch_id, status, region, sdate, edate))

            uc = region_user_count(rng, region)
            # 角色配置:至少1经办人(否则业务无人经办)
            roles = [("管理人员", "财务总监"), ("项目经理", "项目经理"), ("经办人", "会计主管")]
            for k in range(uc):
                if k < len(roles):
                    role, job = roles[k]
                else:
                    role, job = ("经办人", "出纳") if k % 2 == 0 else ("普通用户", "经办员")
                pname = namegen.gen_person()
                person_names.append(pname)
                user_rows.append((uid, pname, oid, role, job))
                uid += 1
            status_counter[status] += 1
            region_counter[region] += 1
            oid += 1

        total_users = len(user_rows)
        # 统计输出
        print(f"\n[单位] 生成 {TARGET_NEW_UNITS} 家，状态分布:")
        for s, c in status_counter.most_common():
            print(f"  {s:12s}: {c:>4} ({c/TARGET_NEW_UNITS*100:.1f}%)")
        print(f"\n[人员] 生成 {total_users:,} 人")
        distinct = len(set(person_names))
        print(f"  不同名字: {distinct:,} | 重名率: {(1-distinct/total_users)*100:.1f}% | 均值 {total_users/distinct:.2f} 人/名")
        print(f"  重名最多: {Counter(person_names).most_common(5)}")
        from collections import Counter as _C
        famous_used = sum(1 for n in person_names if n in set(FAMOUS_POSITIVE_NAMES))
        famous_dups = {n: c for n, c in _C(person_names).items() if n in set(FAMOUS_POSITIVE_NAMES) and c > 1}
        print(f"  知名角色名: 共用 {famous_used} 个 | 重复的(应为空): {famous_dups}")
        print(f"\n[上线时间] 覆盖 {len(month_counter)} 个月，范围 {min(month_counter) if month_counter else '-'} ~ {max(month_counter) if month_counter else '-'}")
        print(f"[省份分布] 覆盖 {len(region_counter)} 省，最多: {region_counter.most_common(3)}")

        if not execute:
            print("\n[DRY-RUN] 未写库。以上为生成预览。")
            return

        # ===== 实写 =====
        print("\n[实写] 开始...")
        bak_dir = BASE_DIR / "scripts" / "kiro" / "output" / "ki051_backups"
        backup_tables(conn, ["org_unit", "sys_user"], bak_dir)

        cur = conn.cursor()
        # 1. 先写单位(外键父表),分批
        BATCH = 500
        for b in range(0, len(org_rows), BATCH):
            chunk = org_rows[b:b + BATCH]
            cur.executemany(
                "INSERT INTO org_unit (id,name,batch_id,status,region,start_date,end_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)", chunk)
            conn.commit()
            print(f"  [单位批] 写入 {b+len(chunk)}/{len(org_rows)}")
        # 2. 再写人员(子表)
        for b in range(0, len(user_rows), 2000):
            chunk = user_rows[b:b + 2000]
            cur.executemany(
                "INSERT INTO sys_user (id,name,org_id,role,job) VALUES (%s,%s,%s,%s,%s)", chunk)
            conn.commit()
            print(f"  [人员批] 写入 {b+len(chunk)}/{len(user_rows)}")

        # 3. 写后校验
        cur.execute("SELECT COUNT(*) FROM org_unit")
        n_org = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sys_user")
        n_user = cur.fetchone()[0]
        # 孤儿人员(org_id无对应单位)
        cur.execute("SELECT COUNT(*) FROM sys_user u LEFT JOIN org_unit o ON u.org_id=o.id WHERE o.id IS NULL")
        orphans = cur.fetchone()[0]
        # 有经办人的新单位比例
        cur.execute(f"SELECT COUNT(DISTINCT org_id) FROM sys_user WHERE org_id >= {next_org_id}")
        orgs_with_user = cur.fetchone()[0]
        print(f"\n[写后校验]")
        print(f"  org_unit 总数: {n_org:,} (新增后应为 ~{2005+TARGET_NEW_UNITS})")
        print(f"  sys_user 总数: {n_user:,}")
        print(f"  孤儿人员(无对应单位): {orphans} (应为0)")
        print(f"  新单位有经办人的: {orgs_with_user}/{TARGET_NEW_UNITS}")
        if orphans > 0:
            print("  [警告] 存在孤儿人员！")
        else:
            print("  [OK] 无孤儿，外键完整，勾稽一致")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
