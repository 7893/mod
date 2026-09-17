# MOD 项目目录说明

更新日期：2026-09-17
状态：现行
适用范围：项目源码工作区与生产运行主机的组织边界

`/home/ubuntu/mod` 是主运行主机上的唯一项目主目录和 Git 工作区；同一主机同时承载生产运行文件。

```text
/home/ubuntu/mod/
├── AGENTS.md               # 仓库硬约束
├── CONTRIBUTING.md         # 接手、开发、验证与提交流程
├── backend/
│   ├── app/
│   │   ├── services/       # 应用服务与快照构建
│   │   ├── integrations/   # HeatWave、Cloudflare 等外部适配
│   │   └── simulation/     # 默认停用的模拟器领域模型
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/
│       ├── views/
│       └── styles/         # 基础、组件、页面和响应式样式
├── deploy/                 # systemd 与 Nginx 部署配置
├── scripts/                # 按 CLI 所有者隔离的脚本
├── database/               # 只读验收工具（历史批量导入/生成脚本已退役）
├── tools/                  # 经维护的领域工具
├── artifacts/              # 本地数据资产，不进入部署目录
├── references/             # 驾驶舱需求导出过程与源文件
├── docs/                   # 当前状态、开发规范、运维和证据
└── archive/
    └── legacy-issue-templates/ # 受文档治理保护的历史模板
```

完整接手流程见 `CONTRIBUTING.md`；目录边界和大文件规则见
`docs/development/PROJECT-ORGANIZATION.md`；脚本归属见 `docs/development/CLI-SCRIPT-POLICY.md`。
迁移前的旧部署目录形态见 `docs/operations/USA-DEPLOYMENT-LAYOUT.md`（已失效，仅作历史）。

禁止把环境文件、凭据、数据库转储、生成 CSV、依赖缓存或其他项目放入 Git。不得运行历史协作状态机，
不得部署历史 Cloudflare Worker，不得绕过门禁启用业务模拟器。
