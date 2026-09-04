# USA 纯部署目录

更新日期：2026-09-02
状态：现行
适用范围：USA `/home/ubuntu/mod` 生产部署目录

USA 的 `/home/ubuntu/mod` 不是开发工作区，不初始化 Git，也不保存历史、工具或原始数据。

允许保留：

```text
/home/ubuntu/mod/
├── .env.systemd          # 600 权限，仅运行服务读取
├── backend/
│   ├── .venv/            # Python 生产运行环境
│   ├── app/              # FastAPI 运行代码
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   └── dist/             # 已验证的静态构建
└── deploy/               # systemd 与 Nginx 配置来源
```

禁止保留源码工作台、测试、`node_modules`、生成器、导入脚本、项目文档、历史归档、CSV 数据集、
CLI 临时脚本和旧环境文件。部署前在 JPA 运行 `make check`，部署后检查用户级服务、8100 单一监听、
`/api/v2/health`、静态资源和禁止索引响应头。
