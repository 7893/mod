#!/usr/bin/env python3
"""
scripts/project/heatwave_manager.py

HeatWave 内存分析集群（RAPID 引擎）运维管理与监控脚本：
- status: 检查集群节点内存、健康度、已加载表及全局查询下推计数
- load:   对 MOD 核心报表分析大表执行 RAPID 声明与 SECONDARY_LOAD
- verify: 强制 (FORCED) 执行 EXPLAIN 校验执行计划是否命中 secondary engine RAPID

符合安全规范：不硬编码密码，通过环境变量读取凭据。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pymysql
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 核心需要进入 HeatWave 内存加速的业务与核算大表
TARGET_MOD_TABLES = [
    "business_document_line",
    "accounting_voucher_line",
    "business_document",
    "accounting_voucher",
    "integration_result",
    "rollout_status_snapshot",
    "construction_task",
    "dual_run_result",
    "org_unit",
]


def get_db_connection() -> pymysql.connections.Connection:
    """获取具备 DDL/写入权限的管理级 MySQL 连接（优先 .env.systemd 或环境变量）。"""
    env_systemd = REPO_ROOT / ".env.systemd"
    cfg: dict[str, str | None] = {}
    if env_systemd.exists():
        cfg = dotenv_values(str(env_systemd))

    host = os.getenv("MOD_DB_HOST") or cfg.get("MOD_DB_HOST", "127.0.0.1")
    port = int(os.getenv("MOD_DB_PORT") or cfg.get("MOD_DB_PORT", "3306"))
    user = os.getenv("MOD_DB_USER") or cfg.get("MOD_DB_USER", "root")
    password = os.getenv("MOD_DB_PASSWORD") or cfg.get("MOD_DB_PASSWORD", "") # secret-scan: allow
    database = os.getenv("MOD_DB_NAME") or cfg.get("MOD_DB_NAME", "mod")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,  # secret-scan: allow
        database=database,

        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def cmd_status() -> int:
    """检查集群节点拓扑、内存负载、MOD 库表加载状态与全局加速指标。"""
    print("================================================================================")
    print("                    MySQL HeatWave (RAPID) 集群巡检状态                         ")
    print("================================================================================")

    try:
        conn = get_db_connection()
    except Exception as e:
        print(f"[ERROR] 无法连接数据库: {e}")
        return 1

    with conn.cursor() as cur:
        # 1. 节点拓扑与内存
        print("\n[1] HeatWave 集群节点拓扑与内存容量:")
        try:
            cur.execute("""
                SELECT 
                    ID AS node_id,
                    CORES,
                    MEMORY_USAGE,
                    MEMORY_TOTAL,
                    BASEREL_MEMORY_USAGE,
                    STATUS,
                    IP,
                    PORT
                FROM performance_schema.rpd_nodes
            """)
            nodes = cur.fetchall()
            if not nodes:
                print("  [WARN] 未检测到在线的 HeatWave 节点（rpd_nodes 为空）")
            for n in nodes:
                used_gb = n["MEMORY_USAGE"] / 1024 / 1024 / 1024
                tot_gb = n["MEMORY_TOTAL"] / 1024 / 1024 / 1024
                free_gb = tot_gb - used_gb
                print(f"  Node #{n['node_id']} ({n['IP']}:{n['PORT']}): 状态={n['STATUS']} 核心数={n['CORES']}")
                print(f"    内存使用: {used_gb:.2f} GB / {tot_gb:.2f} GB (空闲: {free_gb:.2f} GB, 占比: {used_gb*100/tot_gb:.1f}%)")
        except Exception as e:
            print(f"  [ERROR] 查询 rpd_nodes 失败: {e}")

        # 2. 已加载的表
        print("\n[2] HeatWave 内存集群中加载的表清单 (rpd_tables):")
        try:
            cur.execute("""
                SELECT 
                    i.NAME AS schema_table,
                    t.LOAD_STATUS,
                    t.LOAD_PROGRESS,
                    t.NROWS,
                    t.SIZE_BYTES / 1024 / 1024 AS size_mb
                FROM performance_schema.rpd_tables t
                JOIN performance_schema.rpd_table_id i ON t.ID = i.ID
                ORDER BY t.NROWS DESC
            """)
            loaded = cur.fetchall()
            print(f"  当前集群已加载表总数: {len(loaded)}")
            for r in loaded:
                is_mod = r["schema_table"].startswith("mod.")
                tag = "★ [MOD]" if is_mod else "  [OTHER]"
                print(f"  {tag} {r['schema_table']:<32} 状态={r['LOAD_STATUS']} 进度={r['LOAD_PROGRESS']:.1f}% 行数={r['NROWS']:<8} 内存占用={r['size_mb']:.2f} MB")
        except Exception as e:
            print(f"  [ERROR] 查询 rpd_tables 失败: {e}")

        # 3. 全局 HeatWave 计数
        print("\n[3] 全局 HeatWave 查询分流指标:")
        try:
            cur.execute("SHOW GLOBAL STATUS LIKE 'Heatwave%'")
            hw_status = {r["Variable_name"]: r["Value"] for r in cur.fetchall()}
            offloaded = hw_status.get("Heatwave_queries_offloaded", "0")
            print(f"  Heatwave_queries_offloaded (累计成功下推查询数): {offloaded}")
            for k, v in hw_status.items():
                if k != "Heatwave_queries_offloaded":
                    print(f"  {k}: {v}")
        except Exception as e:
            print(f"  [ERROR] 查询 HeatWave status 失败: {e}")

    conn.close()
    return 0


def cmd_load() -> int:
    """遍历目标 MOD 表，确保 SECONDARY_ENGINE=RAPID 并执行 SECONDARY_LOAD。"""
    print("================================================================================")
    print("                   MySQL HeatWave (RAPID) 表加载与激活流程                       ")
    print("================================================================================")

    try:
        conn = get_db_connection()
    except Exception as e:
        print(f"[ERROR] 无法连接数据库: {e}")
        return 1

    with conn.cursor() as cur:
        # 获取当前已加载表
        cur.execute("""
            SELECT i.NAME AS schema_table, t.LOAD_STATUS
            FROM performance_schema.rpd_tables t
            JOIN performance_schema.rpd_table_id i ON t.ID = i.ID
            WHERE i.NAME LIKE 'mod.%'
        """)
        loaded_map = {r["schema_table"].replace("mod.", ""): r["LOAD_STATUS"] for r in cur.fetchall()}

        for table in TARGET_MOD_TABLES:
            status = loaded_map.get(table)
            if status == "AVAIL_RPDGSTABSTATE":
                print(f"  [SKIP] mod.{table} 已经在 HeatWave 中加载并就绪 (AVAIL_RPDGSTABSTATE)")
                continue

            print(f"  [LOAD] 开始处理 mod.{table}...")
            # 1. 确保 SECONDARY_ENGINE = RAPID
            try:
                cur.execute(f"ALTER TABLE `mod`.`{table}` SECONDARY_ENGINE = RAPID")
            except Exception:
                # 若已设置可能抛出无害提示
                pass

            # 2. 执行 SECONDARY_LOAD
            start = time.time()
            try:
                cur.execute(f"ALTER TABLE `mod`.`{table}` SECONDARY_LOAD")
                dur = time.time() - start
                print(f"  [SUCCESS] mod.{table} SECONDARY_LOAD 耗时 {dur:.2f}s")
            except Exception as e:
                print(f"  [ERROR] mod.{table} SECONDARY_LOAD 失败: {e}")

    conn.close()
    return 0


def cmd_verify() -> int:
    """强制使用次级引擎 (FORCED) 执行典型业务 EXPLAIN，验证是否真正命中 RAPID。"""
    print("================================================================================")
    print("                   MySQL HeatWave (RAPID) 执行计划验证                          ")
    print("================================================================================")

    try:
        conn = get_db_connection()
    except Exception as e:
        print(f"[ERROR] 无法连接数据库: {e}")
        return 1

    test_queries = [
        (
            "mod.org_unit 省份单位分布统计",
            """
            EXPLAIN SELECT region, COUNT(*), SUM(CASE WHEN status = '已上线' THEN 1 ELSE 0 END)
            FROM mod.org_unit
            GROUP BY region
            """
        ),
        (
            "mod.rollout_status_snapshot 推广历史走势聚合",
            """
            EXPLAIN SELECT
                snapshot_date,
                SUM(status IN ('已上线', '稳定运行')) AS launched,
                SUM(status = '双轨运行中') AS `dual`
            FROM mod.rollout_status_snapshot
            WHERE snapshot_date <= '2026-08-30'
            GROUP BY snapshot_date
            ORDER BY snapshot_date DESC
            LIMIT 6
            """
        ),
        (
            "mod.business_document 百万单据多维统计",
            """
            EXPLAIN SELECT nature, type, status, COUNT(*), SUM(amount)
            FROM mod.business_document
            GROUP BY nature, type, status
            """
        ),
        (
            "mod.business_document_line 四百万明细聚合",
            """
            EXPLAIN SELECT COUNT(*), SUM(amount), AVG(quantity)
            FROM mod.business_document_line
            """
        ),
        (
            "mod.accounting_voucher 凭证金额借贷平衡校验",
            """
            EXPLAIN SELECT type, status, COUNT(*), SUM(debit), SUM(credit)
            FROM mod.accounting_voucher
            GROUP BY type, status
            """
        ),
        (
            "mod.integration_result 百万集成流水统计",
            """
            EXPLAIN SELECT status, COUNT(*) AS count
            FROM mod.integration_result
            GROUP BY status
            """
        ),
        (
            "mod.dual_run_result 双轨差异聚合统计",
            """
            EXPLAIN SELECT result, COUNT(*) AS count, SUM(diff_amount)
            FROM mod.dual_run_result
            GROUP BY result
            """
        ),
    ]

    all_passed = True
    with conn.cursor() as cur:
        cur.execute("SET use_secondary_engine = FORCED")
        for title, sql in test_queries:
            print(f"\n* 测试: {title}")
            try:
                cur.execute(sql)
                rows = cur.fetchall()
                explain_text = "\n".join(str(r.get("EXPLAIN") or r) for r in rows)
                if "secondary engine RAPID" in explain_text:
                    print("  [PASS] 成功下推执行计划包含: Using secondary engine RAPID")
                else:
                    print(f"  [FAIL] 执行计划未包含 secondary engine RAPID:\n{explain_text}")
                    all_passed = False
            except Exception as e:
                print(f"  [FAIL] 强制次级引擎执行失败: {e}")
                all_passed = False

    conn.close()
    if all_passed:
        print("\n================================================================================")
        print("  所有核心测试查询均 100% 成功下推至 Oracle HeatWave (RAPID) 内存集群！")
        print("================================================================================")
        return 0
    else:
        print("\n[ERROR] 部分查询未能通过 HeatWave RAPID 校验，请检查表加载状态与 autocommit 配置。")
        return 1


def cmd_watchdog() -> int:
    """检查 MOD 核心表加载状态，若有缺失或未就绪自动触发 SECONDARY_LOAD 补偿自愈。"""
    print("================================================================================")
    print("                  MySQL HeatWave (RAPID) 看门狗巡检与自愈                      ")
    print("================================================================================")
    try:
        conn = get_db_connection()
    except Exception as e:
        print(f"[ERROR] 看门狗无法连接数据库: {e}")
        return 1

    with conn.cursor() as cur:
        cur.execute("""
            SELECT i.TABLE_NAME, t.LOAD_STATUS
            FROM performance_schema.rpd_tables t
            JOIN performance_schema.rpd_table_id i ON t.ID = i.ID
            WHERE i.SCHEMA_NAME = 'mod' AND t.LOAD_STATUS = 'AVAIL_RPDGSTABSTATE'
        """)
        loaded = {r["TABLE_NAME"] for r in cur.fetchall()}
        missing = [t for t in TARGET_MOD_TABLES if t not in loaded]

        if not missing:
            print(f"[OK] HeatWave 内存加速正常，全部 {len(TARGET_MOD_TABLES)} 张核心表已就绪 (AVAIL_RPDGSTABSTATE)。")
            conn.close()
            return 0

        print(f"[WARN] 检测到 HeatWave 内存加速缺失 ({len(loaded)}/{len(TARGET_MOD_TABLES)} 就绪): {missing}")
        print("开始触发自愈补载流程...")

    conn.close()
    return cmd_load()


def main() -> int:
    parser = argparse.ArgumentParser(description="Oracle MySQL HeatWave (RAPID) 运维管理工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    subparsers.add_parser("status", help="查看 HeatWave 节点容量、已加载表及运行状态")
    subparsers.add_parser("load", help="对所有 MOD 核心表执行 SECONDARY_ENGINE 与 SECONDARY_LOAD")
    subparsers.add_parser("verify", help="使用 FORCED 验证查询执行计划是否下推至 RAPID")
    subparsers.add_parser("watchdog", help="巡检核心表加载状态并在缺失时自动触发自愈补载")

    args = parser.parse_args()
    if args.command == "status":
        return cmd_status()
    elif args.command == "load":
        return cmd_load()
    elif args.command == "verify":
        return cmd_verify()
    elif args.command == "watchdog":
        return cmd_watchdog()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
