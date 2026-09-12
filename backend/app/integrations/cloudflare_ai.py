"""Cloudflare Workers AI REST adapter with strict data boundaries."""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from datetime import datetime, timezone

# CloudflareAIAdapter — Cloudflare Workers AI REST API 适配器
# ---------------------------------------------------------------------------
#
# 设计原则（低频主动触发 + 强缓存架构）
# ----------------------------------------
# 1. 默认禁用：MOD_CF_AI_ENABLED 未设置或非 "true" 时，所有方法直接返回
#    {"status": "disabled"}，不发出任何网络请求。
# 2. 主动触发：外部 HTTP 调用仅由 generate_insights() 发起，
#    get_status() 不触发外部请求。
# 3. 强缓存：相同聚合指标指纹（SHA-256 截断）且 TTL 内直接复用缓存；
#    TTL 默认 6 小时，由 MOD_CF_AI_CACHE_TTL_SECONDS 配置。
# 4. 进程内每日限额（非持久化预算闸门）：默认 20 次真实调用/UTC 日，由 MOD_CF_AI_DAILY_LIMIT 配置；
#    超出返回 {"status": "rate_limited"}，按 UTC 日期自动重置。
# 5. 数据白名单：只允许下列宏观聚合整数/浮点字段进入请求体；
#    任何单位名称、联系人、单据明细、凭证编号、区域文字或凭据均被过滤掉。
# 6. 短超时：HTTP 请求套接字超时 10 秒，超时即降级。
# 7. 安全降级：任何异常（网络、HTTP 4xx/5xx、JSON 解析、字段缺失）均捕获后
#    返回 {"status": "unavailable"}，绝不向上抛出，绝不伪造结果。
# 8. 不读取凭据到内存以外：账号 ID 和 API Token 仅从环境变量读取，
#    不打印、不记录到日志，不放入任何响应字段。
#
# 环境变量
# --------
#   MOD_CF_AI_ENABLED           "true" 才启用（默认 "false"）
#   CLOUDFLARE_ACCOUNT_ID       CF 账号 ID
#   CLOUDFLARE_API_TOKEN        CF API Token（Bearer）
#   MOD_CF_AI_MODEL             模型名（默认 @cf/meta/llama-3.1-8b-instruct）
#   MOD_CF_AI_GATEWAY           AI Gateway 名（默认 mod-gateway；置空则直连，见 ADR-0010）
#   MOD_CF_AI_CACHE_TTL_SECONDS 缓存 TTL 秒数（默认 21600 = 6 小时）
#   MOD_CF_AI_DAILY_LIMIT       每 UTC 日最多请求尝试次数（当前进程，重启重置）（默认 20）
#
# 白名单字段（宏观聚合数字，无个人/单位/凭证信息）
# ------------------------------------------------

_CF_AI_ALLOWED_FIELDS: frozenset[str] = frozenset({
    "orgTotal",
    "launched",
    "launchedPct",
    "dual",
    "constructionPct",
    "voucherSuccessPct",
    "integrationSuccessPct",
    "unresolvedIssues",
    "highRisk",
    "docsTotal",
    "vouchersTotal",
    "docsTodayAdded",
    "vouchersTodayAdded",
    "regions",
})

# Cloudflare Workers AI REST 端点模板
# 直连端点（兜底：未配置网关时使用）
_CF_AI_ENDPOINT = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}"
    "/ai/run/{model}"
)
# AI Gateway 端点模板（首选：统一入口，享受缓存/限流/日志，见 ADR-0010）
# 形如 https://gateway.ai.cloudflare.com/v1/<account_id>/<gateway>/workers-ai/<model>
_CF_AI_GATEWAY_ENDPOINT = (
    "https://gateway.ai.cloudflare.com/v1/{account_id}"
    "/{gateway}/workers-ai/{model}"
)

# 发给 AI 的系统提示，限定任务范围
_SYSTEM_PROMPT = (
    "你是财务运营演练看板的摘要助手。输入仅为模拟数据的全国汇总数字，"
    "不包含趋势、区域对比、问题原因或经过验证的未来预测。"
    "只描述提供的指标，不推断增长、改善、延期或因果，不编造区域、单位、人名、单号。"
    "建议必须表述为待核实的检查动作，不得声称已定位瓶颈。"
    "仅用三个 Markdown 二级标题：## 当前概况、## 待核实事项、## 建议检查。"
    "每节最多两条短句，总计不超过350个汉字；缺少依据时明确说明数据不足。"
)


# HTTP 超时配置（秒）
_CF_AI_CONNECT_TIMEOUT = 3.0
_CF_AI_READ_TIMEOUT = 7.0


def _filter_to_whitelist(data: dict) -> dict:
    """
    从 data 中提取白名单字段，返回仅含数字（int/float）的干净字典。
    任何非数字类型（字符串、列表、嵌套 dict 等）即使在白名单内也丢弃，
    防止意外的文本字段随聚合数字一起进入请求。
    """
    result: dict[str, int | float] = {}
    for key in _CF_AI_ALLOWED_FIELDS:
        val = data.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val):
            result[key] = val
    return result


def _fingerprint(safe_payload: dict) -> str:
    """
    对白名单过滤后的聚合指标字典计算 SHA-256 指纹（取前 16 字节十六进制）。
    用于判断相同输入是否可复用缓存，不含任何敏感信息。
    """
    canonical = json.dumps(safe_payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _utc_date_str() -> str:
    """返回当前 UTC 日期字符串 YYYY-MM-DD，用于每日限额重置。"""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# 进程内缓存状态（模块级单例，线程安全）
# ---------------------------------------------------------------------------

_cf_cache_lock = threading.Lock()

# 最新缓存条目
_cf_cached_result: dict | None = None          # 上次成功调用的完整响应
_cf_cached_at: float = 0.0                     # monotonic 时间戳
_cf_cached_fingerprint: str = ""               # 对应的聚合指标指纹

# 每日调用计数
_cf_daily_date: str = ""                       # 当前计数所属 UTC 日期
_cf_daily_count: int = 0                       # 当日真实调用次数


class CloudflareAIAdapter:
    """
    Cloudflare Workers AI REST API 适配器（低频主动触发 + 强缓存）。

    - get_status()                 ：只报告配置与缓存状态，绝不发外部请求。
    - generate_insights()          ：唯一可触发外部 HTTP 请求的入口；
                                     命中缓存、限额超出或降级时均不发请求。
    """

    def __init__(self) -> None:
        self._enabled: bool = (
            os.getenv("MOD_CF_AI_ENABLED", "false").strip().lower() == "true"
        )
        self._model: str = os.getenv(
            "MOD_CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct"
        ).strip()
        # AI Gateway 名称（默认 mod-gateway）。配置了则走网关端点，享受缓存/限流/日志（ADR-0010）；
        # 显式置空则回退到直连端点。
        self._gateway: str = os.getenv("MOD_CF_AI_GATEWAY", "mod-gateway").strip()
        self._cache_ttl: int = int(
            os.getenv("MOD_CF_AI_CACHE_TTL_SECONDS", "21600")
        )
        self._daily_limit: int = int(
            os.getenv("MOD_CF_AI_DAILY_LIMIT", "20")
        )

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _read_credentials() -> tuple[str, str]:
        """
        从环境变量读取 (account_id, api_token)。
        两者均非空才返回有效值，否则返回 ("", "")。
        凭据值不进入日志或响应。
        """
        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
        return account_id, api_token

    def _credentials_configured(self) -> bool:
        """仅检查凭据是否存在（不读取具体值到返回结果）。"""
        a, t = self._read_credentials()
        return bool(a and t)

    def _get_cache_snapshot(self) -> dict:
        """线程安全地读取缓存元信息，不含凭据。"""
        with _cf_cache_lock:
            from time import monotonic
            age = monotonic() - _cf_cached_at if _cf_cached_at > 0 else None
            remaining = max(0, self._cache_ttl - int(age)) if age is not None else None
            return {
                "has_cache": _cf_cached_result is not None,
                "cached_at": _cf_cached_result.get("generated_at") if _cf_cached_result else None,
                "cache_age_seconds": int(age) if age is not None else None,
                "cache_ttl_seconds": self._cache_ttl,
                "cache_remaining_seconds": remaining,
                "cache_fingerprint": _cf_cached_fingerprint or None,
            }

    def _get_daily_count_snapshot(self) -> dict:
        """线程安全地读取当日调用计数，不含凭据。"""
        with _cf_cache_lock:
            today = _utc_date_str()
            count = _cf_daily_count if _cf_daily_date == today else 0
            return {
                "utc_date": today,
                "calls_today": count,
                "daily_limit": self._daily_limit,
                "scope": "process",
                "remaining_today": max(0, self._daily_limit - count),
            }

    # ------------------------------------------------------------------
    # 公开接口 1：状态查询（绝不发外部请求）
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """
        返回 Cloudflare AI 配置状态、缓存状态和当日调用计数。
        此方法不发出任何外部网络请求。
        """
        if not self._enabled:
            cf_status = "disabled"
            cf_message = "Cloudflare Workers AI 未启用（MOD_CF_AI_ENABLED != true）"
        elif not self._credentials_configured():
            cf_status = "unavailable"
            cf_message = "凭据未配置（CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN 缺失）"
        else:
            cf_status = "ready"
            cf_message = "已启用，凭据已配置"

        return {
            "status": cf_status,
            "message": cf_message,
            "model": self._model,
            "gateway": self._gateway or None,
            "cache": self._get_cache_snapshot(),
            "quota": self._get_daily_count_snapshot(),
            "data_boundary": sorted(_CF_AI_ALLOWED_FIELDS),
        }

    # ------------------------------------------------------------------
    # 公开接口 2：主动生成洞察（唯一可触发外部请求的入口，仅供每日简报服务调用）
    # ------------------------------------------------------------------

    def generate_insights(self, summary_data: dict) -> dict:
        """
        主动触发 Cloudflare Workers AI 调用，返回洞察文本并更新进程缓存。

        触发规则（优先级从高到低）：
        1. 未启用或凭据缺失 → 安全降级，不发请求。
        2. 白名单过滤后无有效字段 → 安全降级，不发请求。
        3. 指纹命中且 TTL 内 → 直接返回缓存，不发请求。
        4. 当日限额已耗尽 → 返回 rate_limited，不发请求。
        5. 以上均不符合 → 发起真实 HTTP 请求，请求前预占计数，成功后更新缓存。

        Parameters
        ----------
        summary_data : dict
            来自 /api/dashboard/overview 的聚合字典；
            本方法只取白名单字段，其余自动过滤。

        Returns
        -------
        dict
            成功时 status="ok"；缓存命中时 status="cache_hit"；
            限额超出时 status="rate_limited"；
            任何失败均 status="unavailable"/"disabled"，绝不伪造内容。
        """
        from time import monotonic

        global _cf_cached_result, _cf_cached_at, _cf_cached_fingerprint, _cf_daily_date, _cf_daily_count

        # ---- 0. 未启用 ----
        if not self._enabled:
            return {
                "status": "disabled",
                "message": "Cloudflare Workers AI 未启用",
                "data_boundary": sorted(_CF_AI_ALLOWED_FIELDS),
            }

        # ---- 1. 读取凭据 ----
        account_id, api_token = self._read_credentials()
        if not account_id or not api_token:
            return {
                "status": "unavailable",
                "message": "凭据未配置，无法发起请求",
                "data_boundary": sorted(_CF_AI_ALLOWED_FIELDS),
            }

        # ---- 2. 白名单过滤 ----
        safe_payload = _filter_to_whitelist(summary_data)
        if not safe_payload:
            return {
                "status": "unavailable",
                "message": "白名单过滤后无有效聚合字段，放弃请求",
                "data_boundary": sorted(_CF_AI_ALLOWED_FIELDS),
            }

        fp = _fingerprint(safe_payload)

        # ---- 3. 检查缓存（线程安全）----
        with _cf_cache_lock:
            now = monotonic()
            if (
                _cf_cached_result is not None
                and _cf_cached_fingerprint == fp
                and (now - _cf_cached_at) < self._cache_ttl
            ):
                cached = dict(_cf_cached_result)
                cached["status"] = "cache_hit"
                cached["cache_age_seconds"] = int(now - _cf_cached_at)
                return cached

        # ---- 4. 检查每日限额（线程安全）----
        with _cf_cache_lock:
            today = _utc_date_str()
            if _cf_daily_date != today:
                # UTC 日期变更，重置计数
                _cf_daily_date = today
                _cf_daily_count = 0
            if _cf_daily_count >= self._daily_limit:
                return {
                    "status": "rate_limited",
                    "message": f"当日（UTC {today}）真实调用已达上限 {self._daily_limit} 次，请明日再试",
                    "calls_today": _cf_daily_count,
                    "daily_limit": self._daily_limit,
                    "data_boundary": sorted(_CF_AI_ALLOWED_FIELDS),
                }

            _cf_daily_count += 1  # 原子预占真实请求次数，失败也计数

        # ---- 5. 构造用户消息（纯数字键值对，无文本字段）----
        user_message = "当前项目宏观指标（均为虚构模拟数据）：\n"
        for k, v in sorted(safe_payload.items()):
            user_message += f"  {k}: {v}\n"
        user_message += "\n请仅按提供的指标生成摘要，并明确未知事项。"

        # ---- 6. 构造请求 ----
        # 首选 AI Gateway 端点（统一入口 + 缓存/限流/日志）；未配置网关名时回退直连。
        if self._gateway:
            url = _CF_AI_GATEWAY_ENDPOINT.format(
                account_id=account_id,
                gateway=self._gateway,
                model=self._model,
            )
        else:
            url = _CF_AI_ENDPOINT.format(
                account_id=account_id,
                model=self._model,
            )
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            # Cloudflare 网关域名 WAF 会拦截默认 Python-urllib UA（error 1010），
            # 显式声明服务型 UA 放行。
            "User-Agent": "MOD-CockpitInsights/1.0",
        }
        body = {
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 600,
            "temperature": 0.2,
        }

        # ---- 7. 发起 HTTP 请求 ----
        try:
            import urllib.request
            import urllib.error

            req_data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            with urllib.request.urlopen(
                req, timeout=_CF_AI_CONNECT_TIMEOUT + _CF_AI_READ_TIMEOUT
            ) as resp:
                raw = resp.read()

        except urllib.error.HTTPError as exc:
            return {
                "status": "unavailable",
                "message": f"CF AI HTTP 错误 {exc.code}，已降级",
                "data_boundary": sorted(safe_payload.keys()),
            }
        except urllib.error.URLError as exc:
            return {
                "status": "unavailable",
                "message": f"CF AI 网络错误（{type(exc.reason).__name__}），已降级",
                "data_boundary": sorted(safe_payload.keys()),
            }
        except OSError:
            return {
                "status": "unavailable",
                "message": "CF AI 请求超时或网络不可达，已降级",
                "data_boundary": sorted(safe_payload.keys()),
            }
        except Exception:
            return {
                "status": "unavailable",
                "message": "CF AI 请求异常，已降级",
                "data_boundary": sorted(safe_payload.keys()),
            }

        # ---- 8. 解析响应 ----
        try:
            resp_json: dict = json.loads(raw.decode("utf-8"))
        except Exception:
            return {
                "status": "unavailable",
                "message": "CF AI 响应解析失败，已降级",
                "data_boundary": sorted(safe_payload.keys()),
            }

        if not isinstance(resp_json, dict) or not resp_json.get("success"):
            return {
                "status": "unavailable",
                "message": "CF AI 返回 success=false，已降级",
                "data_boundary": sorted(safe_payload.keys()),
            }

        result = resp_json.get("result") or {}
        if isinstance(result, dict) and result.get("finish_reason") == "length":
            return {"status": "unavailable", "message": "AI 输出被截断，未保存"}
        insight_text: str = ""

        if isinstance(result, dict):
            choices = result.get("choices")
            if choices and isinstance(choices, list) and len(choices) > 0:
                first_choice = choices[0]
                if isinstance(first_choice, dict):
                    if first_choice.get("finish_reason") == "length":
                        return {"status": "unavailable", "message": "AI 输出被截断，未保存"}
                    msg = first_choice.get("message") or {}
                    insight_text = msg.get("content") if isinstance(msg, dict) else ""

            if not insight_text:
                insight_text = (
                    result.get("response")
                    or result.get("text")
                    or result.get("content")
                    or ""
                )
        elif isinstance(result, str):
            insight_text = result

        if not isinstance(insight_text, str) or not insight_text.strip():
            return {
                "status": "unavailable",
                "message": "CF AI 响应中无有效洞察文本，已降级",
                "data_boundary": sorted(safe_payload.keys()),
            }

        # ---- 9. 写入缓存 + 更新计数（线程安全）----
        generated_at = datetime.now().isoformat()
        remaining_calls = self._get_daily_count_snapshot()["remaining_today"]
        new_entry = {
            "status": "ok",
            "content": insight_text.strip(),
            "insight": insight_text.strip(),
            "model": self._model,
            "fields_sent": sorted(safe_payload.keys()),
            "data_boundary": sorted(_CF_AI_ALLOWED_FIELDS),
            "generated_at": generated_at,
            "quota_remaining": remaining_calls,
            "fingerprint": fp,
        }
        with _cf_cache_lock:
            _cf_cached_result = new_entry
            _cf_cached_at = monotonic()
            _cf_cached_fingerprint = fp

        return new_entry
