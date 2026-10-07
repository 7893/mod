# Project scripts

此目录只保存经过审阅、可重复运行且有明确用途的项目级脚本。每个脚本必须说明参数、输出、
只读/写入属性、风险和验证方式。CLI 的临时脚本不得直接放入这里。

## 已维护脚本

- `check_public_sanitization.py`：只读扫描全部 Git 受跟踪文本，阻断具体公网/私网地址、
  云资源标识、已登记生产域名及维护者私有资产清单命中；诊断不回显真实值。默认由
  pre-commit、`make doc-check` 和 CI 执行。维护者发布审计可通过未跟踪文件
  `MOD_SENSITIVE_ASSET_FILE=/secure/path/assets.txt` 注入精确资产清单。
  同时阻断宿主机 home 路径及非示例邮箱；例外仅限测试目录中登记的模拟用户名。
  共享脱敏器保留项目/部署/备份角色及相对文件名，不输出匹配原值；
  `scripts/project/tests/test_public_sanitization.py` 验证规则和重复脱敏的一致性。
- `pre_flight.sh`：本机公共 harness 存在时委托其按变更领域检查，返回摘要与日志路径；
  缺失时以非零状态提示改用公共 `make check`，避免把“未执行”误报成成功。检查写入本地
  测试/构建产物，不发布或查库。
  用 `make pre-flight` 验证，具体边界见 `docs/development/LOCAL-HARNESS.md`。

- `frontend/capture-dashboard.mjs`：截取本地驾驶舱页面；通过 `MOD_SCREENSHOT_URL` 和
  `MOD_SCREENSHOT_PATH` 指定地址与输出路径。
- `lint_frontend_arbitrary_values.py`：扫描 `frontend/src/**/*.vue` 中禁止的 Tailwind 任意值（字号/颜色/间距等），供 `make check` 与 CI 共用。
- `lint_frontend_styles.py`：校验前端样式层契约——`frontend/src/styles/` 仅含 theme/base/shell/blocks 四文件、色值字面量只出现在 `theme.css` 与 `charts/theme.ts`、ECharts 字号必须引用 `charts/tokens.ts`、禁止旧变量（`--c-*`/`--space-*`/`--text-xs` 等）、媒体查询与 `clamp()` 仅限 `shell.css`、全局 CSS 选择器必须被 `.vue`/`.ts` 引用、引用 Token 的 SFC `<style>` 须以 `@reference` 开头。纳入 `make check` 与 CI。
- `check_document_governance.py`：只读阻断文档删除、冻结正文减损、KI 状态分裂、必需元数据缺失和现行索引漏项。
- `check_doc_sync.py`：只读检查行为与运行事实变更是否在同一改动中同步 `docs/CURRENT-STATE.md`；未同步时阻断。
- `check_changelog.py`：只读校验 git-cliff 版本契约、基线提交可达性、TOML 配置和 CHANGELOG 生成标记。
- `generate_changelog.py`：用锁定的 git-cliff 2.13.1 从 `.git-cliff-baseline` 到指定 revision 生成变更日志；默认只输出 stdout。

凭据扫描、提交信息、Markdown 链接及前端通用 lint 已由锁定的成熟工具承担，
配置分别位于 `.pre-commit-config.yaml`、`.gitlint`、`frontend/eslint.config.js` 与
`frontend/stylelint.config.mjs`，不再向本目录添加同类通用脚本。

## 文档治理检查

```bash
# 检查当前工作树（只读）
python3 scripts/project/check_document_governance.py
python3 scripts/project/check_doc_sync.py

# CI 中检查指定提交区间（只读）
python3 scripts/project/check_document_governance.py --base <base> --head <head>
python3 scripts/project/check_doc_sync.py --base <base> --head <head>
```

两个工具只读取文件与 Git 差异，不修改文档、提交、数据库或生产环境。工具回归测试位于 `scripts/project/tests/`，由 `make check` 自动执行。

## CHANGELOG 生成

```bash
# MOD_GIT_CLIFF_BIN 必须指向经官方 SHA-256 校验的 git-cliff 2.13.1
MOD_GIT_CLIFF_BIN=/tmp/git-cliff python3 scripts/project/generate_changelog.py

# 显式输出到文件；生成前按文档保全规则保存上一版快照
MOD_GIT_CLIFF_BIN=/tmp/git-cliff python3 scripts/project/generate_changelog.py --output /tmp/CHANGELOG.md

# 发布候选无需预先创建本地标签；显式指定将写入变更日志的版本标题
MOD_GIT_CLIFF_BIN=/tmp/git-cliff python3 scripts/project/generate_changelog.py \
  --tag v0.10.0 --output /tmp/CHANGELOG.md
```

Linux aarch64 官方 `2.13.1` 压缩包 SHA-256 为
`9619b7f0c584229f8a2331c1905afe88bd938bdc9102926c2073836a42f02455`；其他架构必须以同版本官方 Release 列出的校验值为准。

版本 tag 或人工触发的 `.github/workflows/changelog.yml` 使用同一基线和 git-cliff 2.13.1，仅上传可下载产物，不提交、推送、打标签或创建 Release。

## 全量模拟演示数据

`demo_seed.py` 支持只读全量导出、列式编码加 XZ 极限压缩、49.5 MB 共享分卷核验和显式空库初始化。
源环境与导入目标分离，不推送、不部署、不写生产库。参数、风险、恢复及验证见
[全量演示数据规范](../../docs/development/DEMO-DATA.md)。

## 演示运行与部署配置（2026-10-07）

- `run_unified.py`：从脚本位置推导项目根目录；支持 `MOD_API_ENV_FILE`、
  `MOD_SIM_ENV_FILE`、`MOD_OUTPUT_DIR`。显式进程环境优先于 env 文件。
  演示模式必须指定独立 `MOD_DEMO_DATABASE_URL`，只启动 API，关闭模拟写入及外部 AI。
- `demo_container.py init|serve`：仅用于 Compose 的独立演示库，要求新建的
  `MOD_DEMO_DB_PASSWORD`，不读取生产连接。`init` 写入全量演示数据；`serve` 启动
  Nginx 与只读 API。失败只显示异常类型。重复初始化沿用数据清单核验规则。
- `render_deploy_config.py`：通过 `--root`、`--user`、`--env-file`、`--python`、
  `--output` 在新目录生成权限受限的 systemd 配置，拒绝覆盖。路径须为绝对路径，
  不允许父目录跳转或 shell 语法。默认演示模式阻断三个后台任务；
  `--enable-background-jobs` 仅改变模板，既不启用服务，也不授权操作生产。
  生成 Nginx 配置还须同时明确传入 `--public-domain`、`--frontend-root`、
  `--ssl-cert-path`、`--ssl-key-path`、`--nginx-snippets`、`--acme-root`。
- `publish.sh`：缺少 `--apply` 时退出且不部署。执行时要求
  `MOD_DEPLOY_ROOT`、`MOD_DEPLOY_USER`、`MOD_DEPLOY_ENV_FILE`；远程还要求
  `MOD_DEPLOY_HOST`。`--local` 选择本机。该脚本会测试、构建、写入新 release、
  切换 current 并通过 sudo 重启 `mod.service`，必须另行获得部署授权。
  目标需已有 uv、独立演示库、私有 env 文件与 Nginx 配置；不会初始化数据库、
  启用定时器、清理旧 release 或修改 Nginx。健康检查失败时恢复已有的上一版本链接；
  首次部署没有上一版本，失败需人工处理。CI 仅运行检查，不调用发布脚本。

以上契约由 `scripts/project/tests/test_demo_deployment.py` 和
`backend/tests/test_demo_runtime.py` 验证；Compose 可用临时测试口令执行
`docker compose config --quiet` 核验配置。真实口令只放未跟踪环境文件，不能写进示例或参数。
