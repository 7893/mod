# KI-064 · 文档 GI 编号口径与 GitHub Issue 真实编号错位且线上状态滞后

- 状态：DONE
- 优先级：P2
- 更新日期：2026-09-09
- 适用范围：治理仿真相关文档中的 "GI-00x" 演进代际命名、GitHub Issues 真实编号（`#1`~`#4`）的一致性与线上状态维护
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[治理仿真综合](../development/GOVERNANCE-SIMULATION-SYNTHESIS.md)、[文档生命周期与组织规范](../development/DOCUMENTATION-LIFECYCLE.md)、[文档规范](../development/DOCUMENTATION-STANDARD.md)、[当前状态](../CURRENT-STATE.md)

---

## 结论

项目对 "GI"（GitHub Issue）这一概念存在**两套并行且互不对齐的编号体系**，导致读者无法从文档中的
"GI-00x" 稳定定位到 GitHub 上的真实 issue；同时 GitHub 上 `#1`/`#2`/`#3` 的核心能力已随
GI-003/GI-004 与 KI-062 实现并上线，但线上仍标 `open`，状态滞后于事实。这是一处文档/追踪口径
不一致的技术债，不是新功能需求。

## 只读证据（2026-09-09）

### 一、GitHub Issues 真实编号（线上，共 4 个）

| GitHub 编号 | 状态 | 标题（摘要） | 正文是否自称 GI 号 |
|---|---|---|---|
| `#1` | open | 风险与问题生命周期闭环（分派-处置-销项时间线） | 无 |
| `#2` | open | 模拟引擎驱动单位建设推进与风险自愈动态 | 无 |
| `#3` | open | 融合矛与盾攻防博弈仿真引擎与 CF AI 涓流回填（盘活 E/F 屏） | 无 |
| `#4` | closed | 无人值守动态自愈生态与全景大屏多维交互演进（标题含 "GI-004"） | GI-004 |

### 二、文档叙事的 "GI-00x 演进代际"（本地，共 4 代）

见 `docs/development/GOVERNANCE-SIMULATION-SYNTHESIS.md`、`docs/CURRENT-STATE.md`、
`docs/development/BUSINESS-SIMULATION-ENGINE.md`、`ML-AI-DATA-BOUNDARY.md`、`SIMULATION-DIURNAL-SPEC.md`：

- GI-001：治理状态机初探（六态有限状态机与底表）
- GI-002：矛与盾博弈雏形（88% 阻力位与解冻因果）
- GI-003：攻防博弈深化与 Cloudflare AI 算力（看门狗 3000N 熔断与多维抽屉）
- GI-004：无人值守动态自愈生态（30~45 单平衡走廊·生物钟·跨屏涟漪·实时广播）

### 三、错位事实

- **仅 GI-004 ↔ `#4` 编号对齐**（`#4` 标题显式写了 GI-004，且已正确 closed）。
- 文档 "GI-001/002/003" 是对 GitHub `#3`（盘活 E/F 屏总 issue）实现过程的**三代阶段拆解叙述**，
  并非分别对应 GitHub `#1`/`#2`/`#3`。
- 因此文档 "GI-00x" 与 GitHub `#N` **除 GI-004 外全部错位**：读者看到文档 "GI-001" 去 GitHub 找 `#1`，
  实际 `#1` 是"风险生命周期"，与"状态机初探"并非同一指代。
- GitHub `#1`/`#2`/`#3` 的核心能力均已随 GI-003/GI-004 与 KI-062 落地并部署（生产发布
  `20260909-095536`），线上却仍为 `open`，状态滞后于事实。

## 根因

- "GI" 前缀被同时用于两种含义：一是 GitHub Issue 的规范指代（应唯一指向线上 issue 编号），
  二是治理仿真文档自创的"演进代际"叙事代号。两者共用同一前缀但编号规则不同，必然错位。
- 功能实现随代码提交上线时，未同步维护对应 GitHub issue 的状态与实现说明，缺少"实现完成即回写/关闭
  对应 issue"的收尾环节。

## 影响

- 可追溯性受损：无法从文档稳定跳转到 GitHub 真实 issue，反之亦然；"GI-001" 等叙事编号易被误读为线上 issue 号。
- 线上看板失真：`#1`/`#2`/`#3` 已实现却仍 open，外部观察者会误判为"未做"。
- 认知风险：`#4`/GI-004 是唯一对齐样本，反而强化"GI-00x 就等于 GitHub #N"的错误直觉。

## 修复方向（待实施，需按 ENFORCEMENT 确认范围与授权）

1. **统一命名口径（二选一，实施时定版）：**
   - 方案 A：将文档中的"演进代际"从 "GI-00x" 改名为不与 GitHub Issue 冲突的中性代号
     （如"治理仿真演进阶段 S1~S4"），使 "GI/#N" 严格且唯一地指向 GitHub Issue。
   - 方案 B：保留 "GI-00x" 叙事，但在 `GOVERNANCE-SIMULATION-SYNTHESIS.md` 增加一张权威映射表，
     明确每个代际实际对应哪个 GitHub issue 号与其实现/状态，消除歧义。
   - 倾向方案 A：与 AGENTS.md"GI=GitHub Issue、KI=本地缺陷看板"的分流纪律最一致，避免概念二义。
2. **回写并更新 GitHub `#1`/`#2`/`#3`**：为每个 issue 补一条实现说明（关联提交、上线版本、对应模块），
   核对是否可关闭；GitHub 写操作需项目 Owner/主控显式授权，评论与关闭文案实施前先经确认。
3. **建立收尾环节**：功能实现上线后，同一批次内回写对应 GitHub issue 状态，防止再次滞后。
4. 同步修订引用了 "GI-00x" 的现行文档（综合文档、CURRENT-STATE、BUSINESS-SIMULATION-ENGINE、
   ML-AI-DATA-BOUNDARY、SIMULATION-DIURNAL-SPEC），保持口径一致。

## 完成定义（实施时）

- [x] "GI/#N" 在全库文档中唯一指向 GitHub Issue；演进代际叙事保留 "GI-00x" 写法，并在 `GOVERNANCE-SIMULATION-SYNTHESIS.md` 第一章新增权威映射表消除歧义。
- [x] GitHub `#1`/`#2`/`#3` 已按实际实现情况补充结构化实现说明并以 `completed` 关闭；`#4` 保持 closed。全部 4 个 issue 线上均 closed，无 open 残留。
- [x] 引用 "GI-00x" 的现行文档以映射表为权威来源，口径一致，无"文档编号=GitHub 编号"的误导。
- [x] `docs/CURRENT-STATE.md` 与相关现行文档在同一提交内同步；文档治理闸门与 `make check` 全绿（提交前统一执行）。

## 备注

- 本 KI 只登记问题，不构成执行授权。涉及 GitHub 写操作（评论/关闭 issue）与文档改名，实施前分别确认范围。
- 命名口径厘清属文档/流程一致性治理，不改变任何已上线的运行行为与数据。

## 进度

- 2026-09-09 立项登记（OPEN）。承接"KI 记本地、GI 记 GitHub 线上"管理机制的梳理，发现文档 "GI-00x" 演进代际
  与 GitHub Issue 真实编号错位、且 `#1`/`#2`/`#3` 线上状态滞后。待排期实施命名统一与线上状态回写。
- 2026-09-09 处理完成（DONE）。按"保留 KI/GI 写法、理清关系与改进过程"的决策：
  1. 在 `GOVERNANCE-SIMULATION-SYNTHESIS.md` 第一章新增「编号体系与 GitHub Issue 映射」与「演进与改进过程记录」两节，
     以权威映射表固定 GI-00x 代际 ↔ GitHub `#N` ↔ 线上状态 ↔ 落地模块的对应，消除编号歧义；
  2. 对 GitHub `#1`/`#2`/`#3` 各补一条结构化实现说明（含关联提交与上线版本）并以 `completed` 关闭，与 `#4` 处理范式一致；
     核实线上 4 个 issue 全部 closed、无 open 残留；
  3. 文档口径与线上状态双向对齐，本 KI 关闭。后续新功能实现上线后同批回写对应 GitHub issue 的收尾纪律，沿用本次范式。
