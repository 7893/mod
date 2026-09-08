# Project scripts

此目录只保存经过审阅、可重复运行且有明确用途的项目级脚本。每个脚本必须说明参数、输出、
只读/写入属性、风险和验证方式。CLI 的临时脚本不得直接放入这里。

## 已维护脚本

- `frontend/capture-dashboard.mjs`：截取本地驾驶舱页面；通过 `MOD_SCREENSHOT_URL` 和
  `MOD_SCREENSHOT_PATH` 指定地址与输出路径。
- `scan_secrets.py`：只读扫描暂存区或指定 Git 范围的新增行，供 pre-commit 与 CI 共用。
- `validate_commit_message.py`：校验本地 commit message 文件或 CI Git 范围中的提交主题。
- `lint_frontend_arbitrary_values.py`：扫描 `frontend/src/**/*.vue` 中禁止的 Tailwind 任意值（字号/颜色/间距等），供 `make check` 与 CI 共用。
- `check_doc_links.py`：只读检查 Markdown 相对链接是否指向现存文件。
- `check_document_governance.py`：只读阻断文档删除、冻结正文减损、KI 状态分裂、必需元数据缺失和现行索引漏项。
- `check_doc_sync.py`：只读检查行为与运行事实变更是否在同一改动中同步 `docs/CURRENT-STATE.md`；未同步时阻断。

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
