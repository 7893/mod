# 凭据扫描 pre-commit 机制设计说明

更新日期：2026-09-04
状态：现行
适用范围：所有在 `/home/ubuntu/mod` 提交代码的人类与 AI

## 目的

把 `ENFORCEMENT.md` 闸门 A（凭据不落地）从“须知”变成“动作点闸门”。
在 `git commit` 发生的那一刻，自动扫描本次暂存的改动，命中凭据特征即阻断提交，
不依赖任何人或 AI 的肉眼检查与自觉。

机制已落地：本地 pre-commit 与 GitHub Actions 调用同一个扫描器，避免两套规则漂移。

## 触发时机与范围

- 触发点：`git commit` 的 pre-commit 阶段。
- 扫描范围：**仅本次暂存区的新增内容**（`git diff --cached` 的新增行），不扫全库。
  `archive/` 前缀（回收站/历史归档）下的文件一律排除，因其为不再运行的历史残留。
  - 原因：全库扫描会命中历史残留、导致每次提交都失败、无法工作。
  - 截至 2026-09-04，含明文凭据的历史脚本已归档至 `archive/legacy-db-scripts/`，
    退出活跃代码路径；其明文值按项目决策保留（实验库，上生产将更换数据库）。
- 判定：只要有一条暂存新增行命中特征即阻断提交，并打印命中文件、行号与命中规则名。

## 检测特征（依据本项目实际泄露形态）

- 键值式明文密码：`password`、`passwd`、`pwd`、`secret`、`token` 后紧跟 `=`/`:` 与非占位符字符串。
- 数据库连接串内嵌口令：形如 `mysql+pymysql://用户:口令@主机` 的 URL。 <!-- secret-scan: allow -->
- `os.getenv("...", "回退默认值")` 中回退默认值疑似真实凭据（非空、非占位符）。
- 私钥块头：`-----BEGIN` 开头的 PEM/OPENSSH/RSA 私钥。
- 云厂商密钥格式：OCI、AWS 等访问密钥/指纹的典型特征串。

设计取向：**宁可偶尔误报，不可漏报**。误报可通过下述豁免通道放行，漏报则不可逆。

## 占位符与豁免

- 允许的安全占位符不触发阻断：如 `changeme`、`your-password-here`、`xxxx`、`***`、`<PLACEHOLDER>`、
  `example`、空字符串。
- `.env.example` 等示例文件按占位符规则处理；示例值不得是真实凭据。
- 确需放行的极少数情况，使用显式、可审计的单行豁免标记（如行尾 `# secret-scan: allow`），
  并要求提交者对该行负责。不得提供“整仓关闭扫描”的开关。

## 落地形态

- 扫描逻辑：`scripts/project/scan_secrets.py`（暂存区模式供 hook 使用，`--base`/`--head` 模式供 CI 使用）。
- Hook 载体：`.githooks/pre-commit`，调用上述脚本。
- 启用方式：`git config core.hooksPath .githooks`。
  - 注意：`.git/hooks/` 不受版本控制，克隆后不自动生效；必须用版本库内的 `.githooks/`
    配合 `core.hooksPath` 才能随仓库分发。该 `git config` 命令需人工或经授权执行一次，
    不属于“新建文件”。
- CI 载体：`.github/workflows/quality.yml`，在拉取请求和推送时扫描提交范围，并运行 `make check`。
- 提交信息：`.githooks/commit-msg` 与 CI 共同调用 `scripts/project/validate_commit_message.py`，
  强制执行英文小写 type 前缀和七词上限。

## 与现有规范的关系

- 内容依据：`docs/development/DATA-AND-SECURITY-STANDARD.md`（凭据与日志）与
  `docs/development/DEVELOPMENT-STANDARD.md`（配置不得硬编码）。
- 执行定位：`ENFORCEMENT.md` 闸门 A。本文是该闸门的具体设计。
- `ENFORCEMENT.md` 记录上述动作点及本地、CI 两层覆盖。

## 未决事项

- 历史已泄露凭据的轮换与 Git 历史清理方案（独立授权）。
- 特征规则仍需随真实提交样本持续校准误报率。
