# ADR-0012: 恢复 USA 生产部署机与 JPA 专属开发机架构

- 状态：采纳（取代 ADR-0006）
- 日期：2026-09-11

## 背景
2026-09-05 曾为收敛环境将工作区与生产合并到单机 JPA（ADR-0006）。然而随着业务数据规模爆发至 4600 万行、凭证借贷分录突破 1566 万行，单机承载密集开发构建与生产常驻仿真（`mod-simulator`、`modo-ingest`、HeatWave 分析、AutoML 训练）存在资源抢占隐患；同时美国 Always Free 资源（`MySQL.Free` + 1 节点 `HeatWave.Free` + ADB `db534404`）具备独立的同子网局域网加速优势（跨洋 172ms 骤降至同子网 < 0.2ms）。

## 决策
正式恢复**JPA 专属开发机**与**USA 纯生产部署机**职责分离架构：
1. **JPA（开发工作区机）**：
   - 承载完整 Git 仓库、全套开发与测试工具链（`pytest`、`vitest`、`vue-tsc`、`ruff`、`local-harness`）。
   - 保留本地 Osaka MySQL（`10.1.0.186` / `10.0.1.25`）作为本地开发与自动化单测专用库。
   - 停用 JPA 上的生产常驻写服务（`mod-simulator` 与 `modo-ingest`）。
   - 统领 CI/CD 发布：通过升级后的 `scripts/project/publish.sh` 在本地执行 `make check` 门禁，全绿后自动化打包推送产物至 USA 生产机。
2. **USA（纯生产部署机）**：
   - 严格遵守 `docs/operations/USA-DEPLOYMENT-LAYOUT.md` 纯部署目录规范，不初始化 Git、不保存历史和开发工具。
   - 承载生产运行环境：FastAPI API 网关（`mod-api` 8100 端口）、真实拟真引擎（`mod-simulator`）、MODO 遥测数据网桥（`modo-api` 8000 端口与 `modo-ingest`）、Nginx 逆向代理。
   - 数据库连接同子网 US MySQL HeatWave（`10.0.0.145`），API 服务使用最小权限只读账号 `mod_readonly`，仅后台写服务使用管理凭据。
   - 4 项生产维护定时器（看门狗、模型重训、每日简报、容灾备份）在 USA 独立常驻调度。

## 理由
- **同子网极速通信**：USA 生产主机（`10.0.0.152`）与 US MySQL（`10.0.0.145`）同属 Ashburn 局域网子网，网络 RTT < 0.2ms，彻底消除了跨洋调用带来的 172ms 网络惩罚。
- **物理故障隔离**：开发、构建、文档治理与测试完全在 JPA 进行，USA 生产机仅接收已通过全量测试的 release 打包产物，物理隔离彻底消除“开发击穿生产”的可能。
- **权限最小化**：线上 API 服务使用专用只读账号 `mod_readonly` 隔离运行，模型元数据库与业务大表受严格权限保护。

## 后果
- ADR-0006 标记为被本决策取代；更新 `docs/CURRENT-STATE.md` 与 `docs/operations/USA-DEPLOYMENT-LAYOUT.md`。
- 生产部署严格通过 JPA 运行 `scripts/project/publish.sh` 远程自动化发布，发布脚本在远端原子切换软链并在异常时毫秒级自动回滚。
