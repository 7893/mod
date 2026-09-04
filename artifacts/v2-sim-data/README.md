# MOD 项目 V2 模拟数据生成器 (V2.5)

## 1. 唯一生成命令
```bash
python3 generator/v2/generate_v2.py --force
```

## 2. 执行耗时与规模
- **预计耗时**: 30 ~ 55 秒
- **数据对象**: 17 张核心业务与快照表
- **数据总量**: 超 1,600,000 条结构化记录
- **输出目录**: `/home/ubuntu/mod/artifacts/v2-sim-data/`

## 3. 输出交付物说明
- `*.csv`: 17 张业务数据表 CSV 文件（UTF-8 编码，标准逗号分隔）
- `manifest.json`: 全量表行数、字节体积与 SHA-256 校验和清单
- `schema-proposal.sql`: 包含完整主外键与注释的 V2 数据库结构提案
- `quality-report.md`: 由真实测试断言逐项跑完生成的只读质量核验报告
- `review-samples/`: 覆盖全部八批及全部数据域的人工抽样审阅文件

## 4. 故障恢复与安全机制
- 本生成器内置覆盖保护：未传 `--force` 时若输出目录非空将直接报错拒绝。
- 传入 `--force` 时，会自动物理清理 `/home/ubuntu/mod/artifacts/v2-sim-data/` 目录中的旧遗留文件后再重新全量生成，保证数据绝对干净一致。
