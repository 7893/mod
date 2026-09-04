#!/usr/bin/env python3
"""
MOD V2 千万级容量评估工具
=============================
用途：基于本地 CSV 封版数据，估算将 V2 表规模扩展到目标行数时
      Oracle MySQL（InnoDB）所需的存储空间，并给出风险等级。

重要声明
--------
- 本工具的所有数值均为估算，不代表实测结果。
- InnoDB 行存储存在页填充、行格式、数据碎片等因素，实际占用通常
  高于原始 CSV 字节数；本工具通过可配置倍率进行修正，但不保证精度。
- Oracle MySQL HeatWave Always Free DB System 的存储上限和配额
  以 OCI 控制台当前显示为准；Always Free DB System 的存储配额
  不可在线扩展（截至 2026 年已知约束，未来版本可能变更）。
- 本工具不连接数据库、不访问 OCI、不读取任何凭据文件。

用法示例
--------
    python3 capacity_estimator.py
    python3 capacity_estimator.py --target-rows 10000000
    python3 capacity_estimator.py --target-rows 5000000 --storage-gib 100
    python3 capacity_estimator.py --target-rows 10000000 --storage-gib 50 --json

    # 调整倍率（高精度场景下可传入自定义值）
    python3 capacity_estimator.py \\
        --innodb-overhead 2.5 \\
        --index-multiplier 1.4 \\
        --tmp-multiplier 0.3 \\
        --log-multiplier 0.2 \\
        --backup-multiplier 1.0 \\
        --storage-gib 100

参数说明
--------
--data-dir        CSV 目录（默认 ../../artifacts/v2-sim-data）
--target-rows     目标总行数（默认 10_000_000）
--storage-gib     可用存储 GiB（默认 50，可配置）
--innodb-overhead InnoDB 行存储相对 CSV 原始字节的膨胀倍率
                  （默认 2.2；含页头、隐藏列、MVCC 版本链、碎片）
--index-multiplier 索引空间 = 数据空间 × 该倍率（默认 0.5）
--tmp-multiplier   临时表空间 = 数据空间 × 该倍率（默认 0.2）
--log-multiplier   Redo/Undo 日志 = 数据空间 × 该倍率（默认 0.15）
--backup-multiplier 备份副本 = 数据空间 × 该倍率（默认 0.0，不计入余量校验）
--json            以 JSON 格式输出结果
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 默认路径：相对于本脚本所在目录向上两级，再进入 artifacts/v2-sim-data
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_DATA_DIR = _SCRIPT_DIR.parent.parent / "artifacts" / "v2-sim-data"

# ---------------------------------------------------------------------------
# 风险等级阈值（使用率 %）
# ---------------------------------------------------------------------------
RISK_THRESHOLDS = {
    "LOW":     (0,  60),   # 0–60%：充裕
    "MEDIUM":  (60, 80),   # 60–80%：适中
    "HIGH":    (80, 95),   # 80–95%：紧张
    "CRITICAL": (95, 200), # ≥95%：超限风险
}

GIB = 1024 ** 3


def discover_csv_files(data_dir: Path) -> list[Path]:
    """扫描目录，返回所有 .csv 文件路径（不递归子目录）。"""
    return sorted(data_dir.glob("*.csv"))


def count_csv_rows(csv_path: Path) -> int:
    """统计 CSV 行数（不含表头）。使用逐行迭代，避免全量读入内存。"""
    count = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            next(reader)  # 跳过表头
        except StopIteration:
            return 0
        for _ in reader:
            count += 1
    return count


def parse_manifest(data_dir: Path) -> dict:
    """
    读取 manifest.json（若存在），返回各表的 rows 和 size；
    若不存在则返回空字典，退回到从 CSV 文件直接读取。
    """
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tables", {})
    except Exception:
        return {}


def collect_table_stats(data_dir: Path, manifest_tables: dict) -> list[dict]:
    """
    汇总每张 CSV 表的统计信息：
      - table_name
      - csv_rows（当前行数）
      - csv_bytes（当前文件字节数）
      - bytes_per_row（平均每行字节数，用于外推）
      - columns（列名列表，若 manifest 有则从那里取，否则从 CSV 表头读）
    """
    csv_files = discover_csv_files(data_dir)
    stats = []

    for csv_path in csv_files:
        table_name = csv_path.stem
        file_bytes = csv_path.stat().st_size

        # 优先使用 manifest 中的行数（已验证），再退回实时统计
        if table_name in manifest_tables and "rows" in manifest_tables[table_name]:
            csv_rows = manifest_tables[table_name]["rows"]
            manifest_bytes = manifest_tables[table_name].get("size", file_bytes)
            columns = manifest_tables[table_name].get("columns", [])
        else:
            csv_rows = count_csv_rows(csv_path)
            manifest_bytes = file_bytes
            # 从 CSV 读表头
            columns = []
            try:
                with open(csv_path, newline="", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    columns = next(reader, [])
            except Exception:
                pass

        bytes_per_row = (manifest_bytes / csv_rows) if csv_rows > 0 else 0

        stats.append(
            {
                "table_name": table_name,
                "csv_rows": csv_rows,
                "csv_bytes": manifest_bytes,
                "bytes_per_row": bytes_per_row,
                "columns": columns,
            }
        )

    return stats


def estimate_innodb_data_bytes(
    stats: list[dict],
    target_rows: int,
    innodb_overhead: float,
) -> tuple[int, list[dict]]:
    """
    按比例外推：假设各表行数在目标总行数下保持与当前相同的占比。
    返回 (总估算 InnoDB 数据字节数, 带扩展字段的 stats 列表)。
    """
    current_total = sum(s["csv_rows"] for s in stats)
    if current_total == 0:
        return 0, stats

    scale_factor = target_rows / current_total
    total_innodb_bytes = 0

    enriched = []
    for s in stats:
        target_table_rows = round(s["csv_rows"] * scale_factor)
        # CSV 字节线性外推 → InnoDB 数据字节（含膨胀倍率）
        csv_bytes_projected = s["bytes_per_row"] * target_table_rows
        innodb_data_bytes = csv_bytes_projected * innodb_overhead
        total_innodb_bytes += innodb_data_bytes

        enriched.append(
            {
                **s,
                "scale_factor": round(scale_factor, 4),
                "target_rows": target_table_rows,
                "csv_bytes_projected": round(csv_bytes_projected),
                "innodb_data_bytes": round(innodb_data_bytes),
            }
        )

    return round(total_innodb_bytes), enriched


def risk_level(usage_pct: float) -> str:
    for level, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= usage_pct < hi:
            return level
    return "CRITICAL"


def format_gib(b: int | float) -> str:
    return f"{b / GIB:.2f} GiB"


def build_report(
    stats: list[dict],
    target_rows: int,
    storage_gib: float,
    innodb_overhead: float,
    index_multiplier: float,
    tmp_multiplier: float,
    log_multiplier: float,
    backup_multiplier: float,
) -> dict:
    """
    核心估算函数，返回结构化结果字典。
    """
    current_total_rows = sum(s["csv_rows"] for s in stats)
    current_total_bytes = sum(s["csv_bytes"] for s in stats)

    total_innodb_bytes, enriched_stats = estimate_innodb_data_bytes(
        stats, target_rows, innodb_overhead
    )

    index_bytes   = round(total_innodb_bytes * index_multiplier)
    tmp_bytes     = round(total_innodb_bytes * tmp_multiplier)
    log_bytes     = round(total_innodb_bytes * log_multiplier)
    backup_bytes  = round(total_innodb_bytes * backup_multiplier)

    # 余量校验不计入备份（备份通常在独立存储/对象存储）
    required_bytes = total_innodb_bytes + index_bytes + tmp_bytes + log_bytes
    available_bytes = storage_gib * GIB
    usage_pct = (required_bytes / available_bytes) * 100
    free_bytes = available_bytes - required_bytes
    level = risk_level(usage_pct)

    # Always Free DB System 50 GiB 警告
    always_free_warning = None
    if storage_gib <= 50:
        always_free_warning = (
            "检测到 storage-gib ≤ 50 GiB，接近 Oracle MySQL HeatWave Always Free "
            "DB System 的存储配额（约 50 GiB）。Always Free DB System 的存储容量"
            "不可在线增加；若需更大空间，须重建为付费实例或迁移数据。"
            "以上约束以 OCI 控制台当前显示为准，未来版本可能变更。"
        )

    # HeatWave 内存风险提示
    heatwave_note = (
        "HeatWave 集群将数据列式加载到内存中。千万级行规模下，"
        "大宽表（如 business_document、accounting_voucher_line）的内存占用"
        "可能达到数 GiB；Always Free HeatWave 节点内存有限，"
        "建议在目标行数达到 1 000 万前对核心宽表做列裁剪或分区评估。"
        "内存用量以 OCI 官方 HeatWave 节点规格为准，本工具不计算内存。"
    )

    return {
        "disclaimer": (
            "本工具输出为估算值，不代表实测结果。"
            "实际 InnoDB 占用受行格式、字符集、压缩、页填充率、碎片等因素影响。"
            "各倍率参数均可通过命令行参数覆盖。"
        ),
        "inputs": {
            "data_dir": str(_DEFAULT_DATA_DIR),
            "current_total_rows": current_total_rows,
            "current_csv_bytes": current_total_bytes,
            "current_csv_gib": round(current_total_bytes / GIB, 4),
            "target_rows": target_rows,
            "storage_gib": storage_gib,
            "innodb_overhead_multiplier": innodb_overhead,
            "index_multiplier": index_multiplier,
            "tmp_multiplier": tmp_multiplier,
            "log_multiplier": log_multiplier,
            "backup_multiplier": backup_multiplier,
        },
        "estimates": {
            "innodb_data_bytes": total_innodb_bytes,
            "innodb_data_gib": round(total_innodb_bytes / GIB, 3),
            "index_bytes": index_bytes,
            "index_gib": round(index_bytes / GIB, 3),
            "tmp_bytes": tmp_bytes,
            "tmp_gib": round(tmp_bytes / GIB, 3),
            "log_bytes": log_bytes,
            "log_gib": round(log_bytes / GIB, 3),
            "backup_bytes_reference": backup_bytes,
            "backup_gib_reference": round(backup_bytes / GIB, 3),
            "required_bytes_excl_backup": required_bytes,
            "required_gib_excl_backup": round(required_bytes / GIB, 3),
            "available_bytes": round(available_bytes),
            "available_gib": storage_gib,
            "free_bytes": round(free_bytes),
            "free_gib": round(free_bytes / GIB, 3),
            "usage_pct": round(usage_pct, 2),
            "risk_level": level,
        },
        "per_table": [
            {
                "table": s["table_name"],
                "columns": len(s.get("columns", [])),
                "current_rows": s["csv_rows"],
                "target_rows": s["target_rows"],
                "innodb_data_gib": round(s["innodb_data_bytes"] / GIB, 4),
            }
            for s in enriched_stats
        ],
        "warnings": {
            "always_free_storage": always_free_warning,
            "heatwave_memory": heatwave_note,
        },
    }


def print_human(report: dict) -> None:
    """人类可读格式输出。"""
    d = report["disclaimer"]
    i = report["inputs"]
    e = report["estimates"]
    w = report["warnings"]

    sep = "=" * 68
    thin = "-" * 68

    print(sep)
    print("  MOD V2 千万级容量评估报告（估算，非实测）")
    print(sep)
    print(f"  ⚠  {d}")
    print()

    print("【输入参数】")
    print(f"  CSV 目录       : {i['data_dir']}")
    print(f"  当前总行数     : {i['current_total_rows']:>12,}")
    print(f"  当前 CSV 合计  : {format_gib(i['current_csv_bytes']):>12}")
    print(f"  目标总行数     : {i['target_rows']:>12,}")
    print(f"  可用存储       : {i['storage_gib']:>8.1f} GiB")
    print(f"  InnoDB 膨胀倍率: {i['innodb_overhead_multiplier']:>8.2f}×")
    print(f"  索引空间倍率   : {i['index_multiplier']:>8.2f}×")
    print(f"  临时空间倍率   : {i['tmp_multiplier']:>8.2f}×")
    print(f"  日志空间倍率   : {i['log_multiplier']:>8.2f}×")
    print(f"  备份参考倍率   : {i['backup_multiplier']:>8.2f}× （仅参考，不计入余量）")
    print()

    print("【估算结果】")
    print(thin)
    print(f"  InnoDB 数据    : {format_gib(e['innodb_data_bytes']):>12}")
    print(f"  索引空间       : {format_gib(e['index_bytes']):>12}")
    print(f"  临时表空间     : {format_gib(e['tmp_bytes']):>12}")
    print(f"  Redo/Undo 日志 : {format_gib(e['log_bytes']):>12}")
    print(thin)
    print(f"  所需合计（不含备份）: {format_gib(e['required_bytes_excl_backup']):>10}")
    print(f"  备份参考空间        : {format_gib(e['backup_bytes_reference']):>10}  （参考）")
    print(thin)
    print(f"  可用存储            : {format_gib(e['available_bytes']):>10}")
    print(f"  剩余空间            : {format_gib(e['free_bytes']):>10}")
    print(f"  存储使用率          : {e['usage_pct']:>9.2f} %")
    print()

    level = e["risk_level"]
    level_icon = {"LOW": "✅", "MEDIUM": "⚠️ ", "HIGH": "🔴", "CRITICAL": "🚨"}.get(level, "❓")
    print(f"  风险等级   : {level_icon}  {level}")
    print()

    print("【各表估算（目标行数 & 数据空间）】")
    print(f"  {'表名':<32} {'列数':>4} {'当前行':>10} {'目标行':>12} {'数据(GiB)':>10}")
    print(thin)
    for t in sorted(report["per_table"], key=lambda x: -x["innodb_data_gib"]):
        print(
            f"  {t['table']:<32} {t['columns']:>4} "
            f"{t['current_rows']:>10,} {t['target_rows']:>12,} "
            f"{t['innodb_data_gib']:>10.4f}"
        )
    print()

    print("【风险提示】")
    if w["always_free_storage"]:
        print(f"  [Always Free 存储] {w['always_free_storage']}")
        print()
    print(f"  [HeatWave 内存]    {w['heatwave_memory']}")
    print()
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MOD V2 千万级容量评估工具（估算，不连接数据库）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=_DEFAULT_DATA_DIR,
        help="CSV 数据目录（默认：%(default)s）",
    )
    parser.add_argument(
        "--target-rows",
        type=int,
        default=10_000_000,
        metavar="N",
        help="目标总行数（默认：10000000）",
    )
    parser.add_argument(
        "--storage-gib",
        type=float,
        default=50.0,
        metavar="GIB",
        help="可用存储 GiB（默认：50；Always Free 约 50 GiB，以 OCI 控制台为准）",
    )
    parser.add_argument(
        "--innodb-overhead",
        type=float,
        default=2.2,
        metavar="X",
        help="InnoDB 相对 CSV 字节的膨胀倍率（默认：2.2）",
    )
    parser.add_argument(
        "--index-multiplier",
        type=float,
        default=0.5,
        metavar="X",
        help="索引空间 = 数据空间 × 该倍率（默认：0.5）",
    )
    parser.add_argument(
        "--tmp-multiplier",
        type=float,
        default=0.2,
        metavar="X",
        help="临时表空间 = 数据空间 × 该倍率（默认：0.2）",
    )
    parser.add_argument(
        "--log-multiplier",
        type=float,
        default=0.15,
        metavar="X",
        help="Redo/Undo 日志 = 数据空间 × 该倍率（默认：0.15）",
    )
    parser.add_argument(
        "--backup-multiplier",
        type=float,
        default=0.0,
        metavar="X",
        help="备份参考空间 = 数据空间 × 该倍率（默认：0.0，仅参考不计入余量）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )

    args = parser.parse_args()

    data_dir: Path = args.data_dir
    if not data_dir.exists():
        print(f"错误：CSV 目录不存在：{data_dir}", file=sys.stderr)
        sys.exit(1)

    if args.target_rows <= 0:
        print("错误：--target-rows 必须为正整数", file=sys.stderr)
        sys.exit(1)
    if args.storage_gib <= 0:
        print("错误：--storage-gib 必须为正数", file=sys.stderr)
        sys.exit(1)

    manifest_tables = parse_manifest(data_dir)
    stats = collect_table_stats(data_dir, manifest_tables)

    if not stats:
        print(f"错误：在 {data_dir} 中未找到任何 CSV 文件", file=sys.stderr)
        sys.exit(1)

    report = build_report(
        stats=stats,
        target_rows=args.target_rows,
        storage_gib=args.storage_gib,
        innodb_overhead=args.innodb_overhead,
        index_multiplier=args.index_multiplier,
        tmp_multiplier=args.tmp_multiplier,
        log_multiplier=args.log_multiplier,
        backup_multiplier=args.backup_multiplier,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
