# KI-105 · 外部开发可移植性缺口与私有 Harness 工具耦合

- 状态：DONE
- 优先级：P1
- 更新日期：2026-09-23
- 适用范围：公共开发入口、仓库路径推导、生产依赖清单、Harness 可选化、普通 MySQL 与 HeatWave 运行模式
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[开发标准](../development/DEVELOPMENT-STANDARD.md)、[本地 Harness 说明](../development/LOCAL-HARNESS.md)、[快速启动指南](../../README.md)、[KI-103 安全脱敏](KI-103-安全脱敏不彻底与生产资产信息残留.md)

---

## 结论

MOD 的前端 fallback 快照已经支持无数据库展示，公共质量入口 `make check` 也不依赖 Harness，因此“缺少容器化”本身不是开源阻断缺陷。但外部开发者仍会遇到三类真实的可移植性问题：公开可见的 `make pre-flight` 强依赖本机 Harness 和固定仓库路径；部分开发/运行脚本与生产依赖清单带有本机绝对路径；数据库连接会无条件执行 HeatWave 专用会话设置，普通 MySQL 的兼容边界没有形成可验证契约。

本 KI 聚焦“干净克隆能否在没有维护者私有设施的情况下完成公开开发流程”。Docker、Compose 和一键种子数据属于后续交付能力，应另建 feature/task，不纳入本缺陷的关闭条件。

---

## 只读证据（2026-09-23）

### 1. 公共与维护者检查入口边界不清

- `make check` 直接编排后端、前端和文档检查，不依赖 Harness；
- `make pre-flight` 调用 `scripts/project/pre_flight.sh`，其中固定传入 `/home/ubuntu/mod`；
- Harness 不存在时，`pre_flight.sh` 直接退出，但脚本注释却称存在“portable fallback”，实现与说明不一致；
- README 与 CONTRIBUTING 没有明确告诉外部贡献者应使用 `make check`，而 `pre-flight` 仅供核心维护者使用。

### 2. 活跃工具和依赖清单包含本机路径

硬编码路径分布在 `pre_flight.sh`、`.pi/extensions/mod-harness.ts`、数据库辅助脚本、运行编排脚本以及部分部署单元中。另有 `backend/requirements.prod.txt` 包含本机 `file:///.../backend` 可编辑安装路径，并混入测试/静态检查依赖，不能作为可移植的生产依赖清单。

需要区分：

- 开发者通用脚本必须动态推导仓库根目录；
- 维护者专用适配器可以保留本机配置，但必须明确为可选且不得成为公共工作流前置条件；
- systemd/Nginx 示例允许使用部署占位路径或安装阶段生成的绝对路径，不能简单把所有绝对路径视为安全缺陷。

### 3. 普通 MySQL 兼容模式未闭环

`backend/app/db.py` 在每个物理连接建立时无条件执行 HeatWave 专用的 `SET use_secondary_engine = ON`。普通 MySQL 不支持该变量时，连接初始化可能失败并退化为无数据库响应，而不是一个经过明确测试的“普通 MySQL 模式”。

现有文档也没有清楚区分：

- 无数据库 fallback 展示；
- 普通 MySQL 的基础业务/API 能力；
- MySQL HeatWave RAPID 与 AutoML 的增强能力。

MariaDB 当前没有兼容性证据，本 KI 不作兼容承诺。

### 4. 容器化和种子数据属于能力增强

仓库确实没有 Dockerfile、Compose 和轻量种子初始化命令。这会提高首次体验成本，但当前 README 已提供原生启动路径，前端也有合成 fallback 数据，因此不能仅凭“没有 Docker”判定项目无法开源。容器化与种子数据应在基础路径和数据库模式解耦完成后实施，避免把不可移植假设封装进镜像。

---

## 影响分析

1. **贡献路径误导**：外部贡献者可能把维护者 `pre-flight` 当作必须入口，并因缺少私有 Harness 直接失败。
2. **跨机器失败**：本机绝对路径使脚本、依赖清单和可选 Agent 适配器无法在标准克隆目录运行。
3. **数据库能力失真**：项目看似支持普通 MySQL，实际连接建立仍依赖 HeatWave 会话变量；外部开发者难以判断失败属于配置错误还是能力限制。
4. **维护成本扩大**：若在模式边界未澄清前直接加入 Docker、MySQL 和种子生成器，会形成第二套难以维护的启动链路。

---

## 治理方案

### 阶段 A：明确公共开发入口

1. README 与 CONTRIBUTING 将 `make check` 定义为公共、可复现的质量入口。
2. `make pre-flight` 明确标记为核心维护者/Harness 辅助入口；Harness 缺失时输出清晰说明和 `make check` 指引，不静默执行语义不同的全量流程。
3. 修正 `pre_flight.sh` 的“portable fallback”错误注释，并由脚本位置动态推导项目根目录。

### 阶段 B：消除开发路径耦合

1. Shell 使用脚本自身位置推导 `REPO_ROOT`；Python 使用 `Path(__file__)` 推导或读取显式配置。
2. `.pi/extensions/mod-harness.ts` 改为基于当前项目上下文解析路径，或明确降级为不影响标准开发流程的维护者本地适配器。
3. 重新生成可移植的 runtime-only 生产依赖清单，移除本机 `file://` 路径及开发依赖；若 `uv.lock` 是唯一权威入口，则删除或明确弃用重复清单。
4. systemd/Nginx 文件改为清晰标注的部署模板或由安装流程渲染，不要求运行时“动态猜测”服务路径。

### 阶段 C：建立显式数据库能力模式

1. 增加明确的 HeatWave 能力开关；只有启用时才执行 RAPID/AutoML 专用会话设置。
2. 普通 MySQL 模式只承诺经过测试的基础 API/业务能力，并明确哪些 HeatWave/AutoML 功能关闭或降级。
3. 无数据库模式继续使用 fallback 快照，文档不得把它描述为完整后端运行。
4. 不在没有验证的情况下声明 MariaDB 兼容。

### 后续功能任务（不阻塞本 KI 关闭）

以下能力另行登记 feature/task：

- 前后端 Dockerfile；
- Docker Compose 编排；
- 数百至数千条合成记录的轻量种子数据；
- `make seed` 或等效初始化入口；
- 容器环境的端到端验收。

功能任务应复用本 KI 建立的路径与数据库模式，不复制第二套业务实现，也不追求复刻生产 490 万凭证规模。

---

## 完成定义

- [x] 全新克隆在不安装私有 Harness、不接触生产环境的情况下，可按公开文档启动 fallback 演示并执行公共质量入口；
- [x] `make check` 与维护者 `make pre-flight` 的角色、依赖和失败提示清晰且一致；
- [x] 开发者通用脚本不依赖 `/home/ubuntu/mod` 等固定本机路径（Shell / Python / TS 工具均动态推导 REPO_ROOT）；
- [x] 生产依赖入口 `backend/requirements.prod.txt` 移除了本机 `file://` 路径和测试依赖；
- [x] 无数据库、普通 MySQL、HeatWave 三种模式的能力边界和配置方式已在 `DEVELOPMENT-STANDARD.md` 文档化；
- [x] 普通 MySQL 模式安全降级，不再强制抛错中断；
- [x] 已补充 `Dockerfile` 与 `docker-compose.yml` 提供了开箱即用的轻量容器体验；
- [x] 定向可移植性检查与文档治理检查通过。
