# MOD 项目目录说明

更新日期：2026-09-17
状态：现行
适用范围：项目源码工作区与生产运行主机的组织边界

JPA `/home/ubuntu/mod` 是源码、Git、文档和测试工作区；USA `/home/ubuntu/mod` 是不含 Git 历史的纯生产
release 目录。两台主机路径相同但职责不同，不得把开发工作台同步成生产目录。

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
├── references/             # 驾驶舱需求导出工具（原始 Office 资料已清理）
├── docs/                   # 当前状态、开发规范、运维和证据
└── archive/
    └── legacy-issue-templates/ # 受文档治理保护的历史模板
```

完整接手流程见 `CONTRIBUTING.md`；目录边界和大文件规则见
`docs/development/PROJECT-ORGANIZATION.md`；脚本归属见 `docs/development/CLI-SCRIPT-POLICY.md`。
USA 的现行 release 与软链目录形态见 `docs/operations/USA-DEPLOYMENT-LAYOUT.md`。

禁止把环境文件、凭据、数据库转储、生成 CSV、依赖缓存或其他项目放入 Git。不得运行历史协作状态机，
不得部署历史 Cloudflare Worker，不得绕过门禁启用业务模拟器。
