#!/usr/bin/env python3
"""
scripts/kiro/inspect_gateway_usage.py
=====================================
只读巡检 Cloudflare AI Gateway (mod-gateway) 的调用用量与缓存命中率。
用于确认长期演示期间的 LLM 成本可控（ADR-0010 成本闸门）。

需环境变量：CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN（运行主机已配）。
用法：python scripts/kiro/inspect_gateway_usage.py [--per-page 50]
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

GATEWAY = "mod-gateway"


def main() -> int:
    parser = argparse.ArgumentParser(description="mod-gateway 用量巡检（只读）")
    parser.add_argument("--per-page", type=int, default=50, help="拉取最近日志条数")
    args = parser.parse_args()

    acct = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    tok = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not acct or not tok:
        print("缺少 CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN 环境变量")
        return 1

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{acct}"
        f"/ai-gateway/gateways/{GATEWAY}/logs?per_page={args.per_page}"
    )
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {tok}",
        "User-Agent": "MOD-GatewayInspect/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"查询失败：{type(exc).__name__}")
        return 1

    if not data.get("success"):
        print("API 返回失败：", data.get("errors"))
        return 1

    logs = data.get("result", [])
    cached = sum(1 for l in logs if l.get("cached"))
    tokens = sum((l.get("tokens_in", 0) or 0) + (l.get("tokens_out", 0) or 0) for l in logs)
    errors = sum(1 for l in logs if str(l.get("status_code", "")).startswith(("4", "5")))

    print(f"mod-gateway 最近 {len(logs)} 条调用：")
    print(f"  缓存命中：{cached}/{len(logs)}（命中率 {cached * 100 // max(1, len(logs))}%）")
    print(f"  累计 tokens：约 {tokens}")
    print(f"  错误(4xx/5xx)：{errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
