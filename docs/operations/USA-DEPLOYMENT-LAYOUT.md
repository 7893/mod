# USA 纯部署目录

更新日期：2026-09-17
状态：现行有效（根据 ADR-0012 恢复）
适用范围：USA `/home/ubuntu/mod` 生产部署目录

> 架构通知：2026-09-11 正式恢复 USA 生产部署机与 JPA 专属开发机架构（ADR-0012）。
> 生产运行（API、模拟器、定时调度、Nginx、HeatWave 加速）统一部署于 USA 主机；
> JPA 主机专职承载源码、Git 工作区与测试构建，并通过 `publish.sh` 执行远程发布。

USA 的 `/home/ubuntu/mod` 不是开发工作区，不初始化 Git，也不保存历史、工具或原始数据。

允许保留：

```text
/home/ubuntu/mod/
├── .env.systemd          # 600 权限，仅运行服务读取
├── backend/
│   ├── .venv/            # Python 生产运行环境
│   ├── releases/<ts>/    # 后端、simulation 与运行脚本的不可变 release
│   ├── current -> releases/<ts>
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── releases/<ts>/    # 已验证的静态构建
│   └── current -> releases/<ts>
└── deploy/               # systemd 与 Nginx 配置来源
```

禁止保留源码工作台、测试、`node_modules`、生成器、导入脚本、项目文档、历史归档、CSV 数据集、
CLI 临时脚本和旧环境文件。部署前必须通过 `make check`；部署后检查统一系统级 `mod.service`、8100 单一监听、
`/api/health`、`/api/simulator/status`、`/api/dashboard/snapshot`、静态资源和禁止索引响应头。

现行生产维护只保留 3 个定时器：`mod-daily-briefing.timer`、`mod-heatwave-watchdog.timer`、
`mod-ml-retrain.timer`。`mod-backup.*`、`mod-api.service` 与 `mod-simulator.service` 均已退役，不得恢复。
