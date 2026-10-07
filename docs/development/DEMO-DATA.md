# 全量模拟演示启动数据

更新日期：2026-10-07
状态：现行
适用范围：MOD 模拟数据全量导出、环境脱敏、分卷保全和空库初始化

## 数据范围

根据所有者要求，保留 MOD 业务库全部表与全部记录，包括模拟器生成的人名、单位、业务文本、
主外键、金额、日期、未来预生成快照、统计资料、模型结果和日志。不抽样、不重新编号、
不改写金额、不丢弃未来模拟记录、不重算或替换原始汇总。模拟器的字典及随机生成逻辑见
`simulation/org_generator.py`、`simulation/expense_playbook.py` 和 `simulation/business_corpus.py`。

仅处理真实环境信息：真实网络地址、生产域名、云资源标识、已知凭据、邮件地址和宿主机绝对路径。
嵌套 JSON 递归处理并保持有效结构。连接凭据只进入环境与进程内存，原始记录不落盘。
冻结基线 `artifacts/v2-sim-data/` 不修改、不重复导入。

这是演示启动数据，不能恢复旧主机的凭据、部署环境或 HeatWave 原生训练目录。
模型结果作为冻结实验资料展示，不宣称已在新环境重新训练，也不触发外部 AI 调用。

## 文件格式与 GitHub

`demo-data/schema.json` 保存可移植字段、索引及外键描述；`manifest.json` 保存逐表精确行数、
逻辑数据 SHA-256、原始数据字节数和每个分卷的 SHA-256 与大小。
当前格式版本 3：先用 Parquet 无损列式编码（整数差分、字符串前缀差分、浮点字节分流），
再使用 XZ `9e` 极限模式、512 MiB 字典和最大匹配长度 273。金额保留原始十进制字符串，
日期及 JSON 保留原始字符串，浮点保留 double 精度，不做数值近似或内容改写。
各表仍有独立压缩流，但合并进共享容器，清单保存每张表的压缩偏移和长度。
共享容器按最多 49.5 MB（49,500,000 字节，十进制）分卷，大表与小表不再各自占用独立文件。
分卷可能切在压缩块内部，工具自动按偏移解读，不需要 LFS 或 Release。
工具仍可读取早期版本 2 的逐表 JSONL/XZ 候选包及此前 95 MiB 分卷的版本 3 候选包，供本地升级；不得同时发布多套数据。

GitHub 普通文件超过 50 MiB 会警告、超过 100 MiB 会被拒绝，单次 push 上限为 2 GB；
49.5 MB 分卷低于 50 MiB 警告线及拒绝阈值。分卷不绕过仓库总体积限制。
官方建议仓库最好小于 1 GB、强烈建议小于 5 GB。
2026-10-07 经核验的极限包包含 43 表、47,551,621 条记录，7 个数据分卷加 schema/manifest 共 9 个文件，
总计 324,335,667 字节（约 309.3 MiB）；前六卷各 49.5 MB，末卷 27,177,516 字节（约 27.18 MB）。
相比初版约 561 MiB 的 53 个数据分卷，包体积减少约 44.9%；全部数据不抽样。
Repository limits 另列 `.git` 磁盘体积 10 GB 为建议上限，不能将这些建议误称为免费账号的硬配额。
此包用于项目演示，不作为反复追加的数据库备份历史；压缩二进制多次替换会累积 Git 对象体积。
依据：[文件大小](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)、
[仓库限制](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)。

## 导出与核验

所有脚本在本地运行。通过受控环境设置 `MOD_DB_*`，可选提供专用只读账号；
使用项目 `safe_db_query.read_only_connection`，所有表在一个只读一致性快照中以主键分页导出，
每批最多 20,000 条，立即处理环境信息，并以最多 500,000 条一组写入临时列式文件，
单表结束后执行极限压缩，避免一次把全库放进内存。会话明确使用 UTC 和
REPEATABLE READ；每个查询限时 60 秒。连接中断后不能跨事务续接并声称同一快照，应重做完整包。
逐表导出数量必须等于同一快照的精确 COUNT。环境信息在内存中处理后才写入压缩文件。
工具沿用项目 env 机制，导出需要 `python-dotenv`。

```bash
uv run --project backend --extra demo python scripts/project/demo_seed.py export --output demo-data
uv run --project backend --extra demo python scripts/project/demo_seed.py verify --package demo-data
# 已有完整本地候选包可直接升级，不重新连接源库；输出必须为新目录。
uv run --project backend --extra demo python scripts/project/demo_seed.py repack --source old-package --output new-package
# 已验证极限包仅需重切时，保留压缩字节与压缩参数，默认每卷 49.5 MB。
uv run --project backend --extra demo python scripts/project/demo_seed.py reshard --source old-package --output new-package
```

导出拒绝覆盖已有目录；失败候选应留在本地待检查，不能视为完整包。
核验逐卷 SHA-256、全部解压行数和逻辑数据摘要，并扫描全部解压内容中的环境信息。
已知凭据检查使用当前受控环境中的私密资产值；值只驻留内存，不打印匹配文本。
普通 Git 文本扫描不能替代压缩包核验。
本工具不推送、不部署、不启停生产服务、不写源库，也不改变生产定时器。

## 初始化与恢复

通过受控环境设置独立 `MOD_DEMO_DATABASE_URL`，不在命令行填真实口令。
工具绝不回退使用生产 `MOD_DB_*`；目标数据库须预先创建且为空。恢复保留自增字段，
以 UTC 写入并启用 `NO_AUTO_VALUE_ON_ZERO`，防止原始零 ID 被自动改号；导入每批提交 1,000 条。

```bash
# 默认仅核对目标和预计行数。
uv run --project backend --extra demo python scripts/project/demo_seed.py init
# 明确导入。
uv run --project backend --extra demo python scripts/project/demo_seed.py init --apply
# 可选快速恢复：目标服务须明确启用 local_infile。
uv run --project backend --extra demo python scripts/project/demo_seed.py init --apply --bulk-load
```

默认仅允许 loopback 目标；其他自建演示库须明确加 `--allow-remote-target`，该参数不授权操作生产库。
`--bulk-load` 每批 20,000 条通过 MySQL 原生批量装载；未指定时使用每批 1,000 条普通 INSERT。
快速模式只在系统临时目录创建权限受限的已处理演示 TSV，批次结束立即清理，任何装载警告均判失败。
极限包使用可选 `demo` 依赖 PyArrow；API 正常运行无需加载此依赖。解压字典需要约 512 MiB 内存，
恢复时每张表的已处理列式文件暂存于系统临时目录，读取每批 20,000 条后用于灌库，随后清理。
临时目录容量须容纳最大单表列式文件；当前全量包最大为 641,057,573 字节（约 611.4 MiB）。
可通过标准 `TMPDIR` 选择位置，不写死宿主机路径。
非空目标拒绝覆盖；同版本成功初始化后重复执行核对行数，不重复灌入。
MySQL DDL 会隐式提交，失败可能留下部分表或记录。工具不自动删除，恢复时应在授权范围内
弃用隔离失败目标，以新空库重试。原始数据库不受影响。

## 演示运行

设置 `MOD_DEMO_MODE=true`，并关闭 HeatWave 加速、AutoML 写入、Cloudflare AI 和模拟器写入开关。
API 返回演示标记及 `modelResultSource=demo_frozen`。原有源数据的时序、汇总或会计差异
通过核验结果如实报告，不借导出过程修正原始记录。

```bash
uv run --project backend --extra demo python -m unittest discover -s scripts/project/tests -p test_demo_seed.py
make check
```

临时数据库与无关诊断脚本放在系统临时目录，不进入仓库或 release。
本地 MariaDB 可验证兼容导入及普通 SQL 路径，但不能替代 MySQL 8 原生版本和 HeatWave 功能验收。

## 本地验证记录（2026-10-07）

### 独立演示容器与可移植服务

当前 Compose 只创建本项目独立的 MySQL 演示库，不连接既有生产数据库。
从 `.env.example` 复制到未跟踪的 `.env`，为 `MOD_DEMO_DB_PASSWORD` 与
`MOD_DEMO_ROOT_PASSWORD` 设置两个新的本地口令；不得复用生产凭据。
已有生产 env 文件不要交给 Compose。然后在项目根目录运行：

```bash
docker compose config --quiet
docker compose up --build -d
docker compose logs demo-init
docker compose ps
```

`demo-db` 健康后，`demo-init` 分批恢复项目内全量包；只有初始化成功，
`mod-app` 才启动。初始化耗时取决于磁盘和 CPU，不能把尚在导入视为失败。
数据库不发布宿主机端口；网页默认绑定本机 `127.0.0.1:8080`，可用
`MOD_DEMO_HTTP_PORT` 改端口。需要对外提供演示时应另行配置入口和访问控制。
完整数据库、镜像及导入临时文件需要数 GiB 磁盘，不能仅按 309.3 MiB 压缩包预留容量。
演示 API 强制只读会话，拒绝模拟写入、训练及外部 AI，即使这些旧开关被误设为 true。
服务停止可运行 `docker compose down`，默认保留演示数据库卷；不要随意加 `-v`。
导入失败留下部分数据时先检查日志，工具不会覆盖或自动删除非空数据库。

不使用容器时，先按上文在独立空库完成初始化，再通过私有环境文件设置
`MOD_DEMO_MODE=true` 与 `MOD_DEMO_DATABASE_URL`。启动入口为
`scripts/project/run_unified.py`，无需固定项目目录。
systemd/Nginx 文件现在是参数模板，不能直接安装；先用
`scripts/project/render_deploy_config.py --help` 核对参数并在临时目录生成配置。
生成器不安装或启动服务。手动发布需要显式目标与 `--apply`，具体影响和回滚边界见
[项目脚本说明](../../scripts/project/README.md)。部署与生产下线仍须单独授权。

### 全量包与恢复记录

最终包全部 43 表、47,551,621 行的解压行数、逻辑 SHA-256、文件 SHA-256 和环境信息扫描通过，
与初版的全部逻辑记录及结构描述完全一致；首次源库导出处理了 7 处真实环境文本。
JPA 临时隔离 MariaDB 已恢复全部数据，逐表从恢复库读取全部记录并核对逻辑摘要，20 个外键建立成功。
10 个冷启动演示读取接口均返回成功；快照使用恢复库而非兜底样例，覆盖 3,211 家模拟单位，
业务日期与恢复库最新 daily_stats 一致，模型接口标记 demo_frozen。
此前 95 MiB 分卷版本搬入项目后文件摘要再次通过；重复初始化返回 already_initialized，不重复灌入记录。
MariaDB 不支持后台快照的 MySQL max_execution_time 会话参数，本次 API 兼容测试清空初始兜底缓存，
验证冷启动普通 SQL 读取；未修改该超时保护，也不宣称 MySQL 8 / HeatWave 已验收。
完整 make check 通过：后端 284、前端 169、项目脚本 45 项（普通环境一项 Arrow 测试跳过）；
使用 demo 依赖补跑专项 10 项，无跳过。测试临时目录使用 /var/tmp，未降低旧备份测试的空间门槛。
本轮未提交、推送、部署或停用生产。Git 历史中的真实地址、部署 workflow 与旧服务停用仍属于后续步骤。

所有者随后要求消除 GitHub 文件体积警告：已从先前 4 个 95 MiB 数据分卷重新切为 7 个 49.5 MB 分卷。
重切只改变文件边界和清单，各表压缩字节、偏移、行数、逻辑摘要及结构保持不变；
完整容器与 43 个独立压缩流的 SHA-256 比较均一致，全部新分卷大小及文件摘要核验通过。
沿用已验证的无损列式编码 + XZ 9e / 512 MiB 字典，不重复连接源库或恢复数据库。
49.5 MB 最终包搬入项目后文件摘要与大小再次通过；项目脚本 45 项测试全部通过（含 Arrow，无跳过）。

随后经所有者授权完成本地通用部署整理：CI 自动部署作业已从本地文件移除，
运行路径由项目位置或显式参数生成；演示 API 强制独立数据库 URL 和只读会话，
禁止模拟写入、模型训练、外部 AI。systemd 启动命令及后台任务条件明确固定渲染后的模式，
旧 EnvironmentFile 不能覆盖该边界。Compose 按独立 MySQL 健康、全量初始化成功、API 启动的顺序运行。
完整 make check 通过：后端 289、前端 169、项目脚本 51 项；普通环境跳过可选 Arrow，
demo 依赖补跑全部 51 项无跳过。最后模板补强后文档和脚本检查再次通过。
Compose 配置校验通过；Dockerfile Nginx 配置在本机非特权测试端口通过 nginx -t，未启动服务。
本机仅将验证工具下载到系统临时目录，未安装 Docker 服务；镜像构建和 MySQL 容器全量启动尚未验收。
全部最终数据包文件大小与 SHA-256 再次通过，仍为 43 表、47,551,621 行、9 文件、324,335,667 字节。
本轮无提交、推送、实际部署、生产停用或 Git 历史改写；冻结资料和历史环境信息属于后续授权范围。
