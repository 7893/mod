# 26 - V2 千万级容量评估工具

> 状态：已实现 | 文件：`tools/v2/capacity_estimator.py`
> 所有输出均为**估算值，不代表实测结果**。

---

## 工具用途

在不连接数据库、不访问 OCI、不读取凭据的前提下，读取本地
`artifacts/v2-sim-data/` 的 17 个 CSV 封版文件，按当前行数和字节数线性
外推到目标规模，估算 Oracle MySQL（InnoDB）所需的数据/索引/临时/日志空间，
并给出存储使用率和风险等级。

---

## 快速使用

```bash
# 默认：目标 1 000 万行，50 GiB 可用存储，人类可读输出
python3 tools/v2/capacity_estimator.py

# 指定目标行数和存储容量
python3 tools/v2/capacity_estimator.py --target-rows 5000000 --storage-gib 100

# JSON 输出（适合脚本集成）
python3 tools/v2/capacity_estimator.py --target-rows 10000000 --json

# 自定义倍率
python3 tools/v2/capacity_estimator.py \
    --innodb-overhead 2.5 \
    --index-multiplier 1.4 \
    --tmp-multiplier 0.3 \
    --log-multiplier 0.2 \
    --backup-multiplier 1.0 \
    --storage-gib 100
```

---

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--data-dir` | `artifacts/v2-sim-data` | CSV 数据目录 |
| `--target-rows` | `10_000_000` | 目标总行数 |
| `--storage-gib` | `50` | 可用存储 GiB（**可配置**，以 OCI 控制台为准） |
| `--innodb-overhead` | `2.2` | InnoDB 相对 CSV 字节的膨胀倍率 |
| `--index-multiplier` | `0.5` | 索引空间 = 数据空间 × 该值 |
| `--tmp-multiplier` | `0.2` | 临时表空间 = 数据空间 × 该值 |
| `--log-multiplier` | `0.15` | Redo/Undo 日志 = 数据空间 × 该值 |
| `--backup-multiplier` | `0.0` | 备份参考（默认不计入余量校验） |
| `--json` | — | 输出 JSON（含完整明细） |

---

## 估算方法

1. **行比例外推**：以各表当前行数占总行数的比例，推算目标总行数下各表行数。
2. **字节外推**：用 `平均每行CSV字节 × 目标行数` 得到投影 CSV 字节数。
3. **InnoDB 膨胀**：乘以 `--innodb-overhead`（默认 2.2×），
   覆盖页头、隐藏列、MVCC 版本链、页填充率和碎片。
4. **附加空间**：索引、临时表空间、Redo/Undo 日志各按数据空间的倍率累加。
5. **余量校验**：`所需合计（不含备份）/ 可用存储` 得出使用率，映射风险等级。

风险等级：

| 等级 | 使用率 | 含义 |
|---|---|---|
| LOW | < 60% | 充裕 |
| MEDIUM | 60–80% | 适中，可规划扩容窗口 |
| HIGH | 80–95% | 紧张，建议尽快规划扩容 |
| CRITICAL | ≥ 95% | 超限风险，须立即处理 |

---

## Oracle MySQL HeatWave 约束与提示

**存储（截至 2026 年已知约束，以 OCI 控制台当前显示为准）**

- Always Free DB System 的存储配额**不可在线增加**；
  若估算结果显示存储紧张，须重建为付费实例或提前迁移。
- 工具通过 `--storage-gib` 参数接受任意容量输入，默认值 50 仅对应
  当前 Always Free 的已知上限，**不应视为永久不变的平台事实**。
- 付费 MySQL HeatWave DB System 可在线扩容，上限以 OCI 文档为准。

**HeatWave 内存（计算节点）**

- HeatWave 将数据列式加载到内存；千万级行规模下，大宽表
  （如 `business_document`、`accounting_voucher_line`）内存占用可能达到数 GiB。
- Always Free HeatWave 节点内存有限，建议在规模达到目标前对核心宽表
  做列裁剪或分区评估。
- **本工具不估算内存用量**，内存规划须参考 OCI 官方节点规格。

---

## 注意事项

- 工具**不连接数据库、不访问 OCI、不读取任何凭据文件、不写入数据**。
- 行数优先取自 `manifest.json`（已验证的封版统计），文件不存在时才实时计数。
- 倍率参数均有合理默认值，但**不同行格式（COMPACT/DYNAMIC/COMPRESSED）、
  字符集、varchar 长度分布会导致实际值显著偏离**；建议在真实数据库中用
  `information_schema.INNODB_TABLESTATS` 或 `SHOW TABLE STATUS` 交叉验证。
- 备份空间默认倍率为 0（不计入余量校验），因备份通常存放在独立对象存储；
  如需计入请通过 `--backup-multiplier` 指定。
