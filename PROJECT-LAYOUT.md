# MOD 项目目录说明

更新日期：2026-09-02
状态：现行
适用范围：JPA 源码工作区与 USA 部署目录的组织边界

`/home/ubuntu/mod` 是 JPA 上的唯一项目主目录和 Git 工作区；USA 同名目录仅承载生产运行文件。

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
├── database/               # 数据库工具；历史写入工具不得擅自运行
├── generator/              # 封版数据生成工具
├── tools/                  # 经维护的领域工具
├── artifacts/              # 本地数据资产，不进入部署目录
├── references/             # 原始参考材料
├── docs/                   # 当前状态、开发规范、运维和证据
└── archive/
    ├── legacy-cloudflare-worker/ # 未部署的历史实验
    ├── legacy-components/
    ├── legacy-deploy/
    ├── usa-history/        # 从 USA 迁回的历史资产，本地忽略
    └── workbench/          # 本地忽略的临时工作台
```

完整接手流程见 `CONTRIBUTING.md`；目录边界和大文件规则见
`docs/development/PROJECT-ORGANIZATION.md`；脚本归属见 `docs/development/CLI-SCRIPT-POLICY.md`；
USA 允许内容见 `docs/operations/USA-DEPLOYMENT-LAYOUT.md`。

禁止把环境文件、凭据、数据库转储、生成 CSV、依赖缓存或其他项目放入 Git。不得运行历史协作状态机，
不得部署历史 Cloudflare Worker，不得绕过门禁启用业务模拟器。
