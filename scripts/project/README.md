# Project scripts

此目录只保存经过审阅、可重复运行且有明确用途的项目级脚本。每个脚本必须说明参数、输出、
只读/写入属性、风险和验证方式。CLI 的临时脚本不得直接放入这里。

## 已维护脚本

- `frontend/capture-dashboard.mjs`：截取本地驾驶舱页面；通过 `MOD_SCREENSHOT_URL` 和
  `MOD_SCREENSHOT_PATH` 指定地址与输出路径。
- `scan_secrets.py`：只读扫描暂存区或指定 Git 范围的新增行，供 pre-commit 与 CI 共用。
- `validate_commit_message.py`：校验本地 commit message 文件或 CI Git 范围中的提交主题。
