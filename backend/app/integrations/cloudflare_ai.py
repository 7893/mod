"""Cloudflare Workers AI REST adapter with strict data boundaries."""

from __future__ import annotations

import hashlib
import json
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
#    get_status() 和 get_latest_cached_insights() 均不触发外部请求。
# 3. 强缓存：相同聚合指标指纹（SHA-256 截断）且 TTL 内直接复用缓存；
#    TTL 默认 6 小时，由 MOD_CF_AI_CACHE_TTL_SECONDS 配置。
# 4. 每日限额：默认 20 次真实调用/UTC 日，由 MOD_CF_AI_DAILY_LIMIT 配置；
#    超出返回 {"status": "rate_limited"}，按 UTC 日期自动重置。
# 5. 数据白名单：只允许下列宏观聚合整数/浮点字段进入请求体；
#    任何单位名称、联系人、单据明细、凭证编号、区域文字或凭据均被过滤掉。
# 6. 短超时：HTTP 请求 10 秒（connect 3 s + read 7 s），超时即降级。
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
#   MOD_CF_AI_MODEL             模型名（默认 @cf/openai/gpt-oss-20b）
#   MOD_CF_AI_CACHE_TTL_SECONDS 缓存 TTL 秒数（默认 21600 = 6 小时）
#   MOD_CF_AI_DAILY_LIMIT       每 UTC 日最多真实调用次数（默认 20）
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
_CF_AI_ENDPOINT = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}"
    "/ai/run/{model}"
)

# 发给 AI 的系统提示，限定任务范围
_SYSTEM_PROMPT = (
    "你是新一代数智财务运营管控平台的高级AI决策顾问。"
    "你将收到全国34个省级行政区、2000家大型单位系统推广的宏观聚合统计指标（均为模拟演练数据）。"
    "请以精炼、专业、管理层视角给出结构化的智能研判报告，包含三方面："
    "1.【整体推进成效】：简述当前建设与上线成果亮点；"
    "2.【关键瓶颈聚焦】：针对未解决问题、高风险项或双轨阶段提出警示；"
    "3.【管理行动建议】：给出下阶段推广指挥部的针对性督导举措。"
    "语言精炼干练、具有集团指挥部决策汇报风格，严禁臆造具体人名或单号。"
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
        if isinstance(val, (int, float)) and not isinstance(val, bool):
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
    - get_latest_cached_insights() ：只读缓存，不发外部请求。
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
            "cache": self._get_cache_snapshot(),
            "quota": self._get_daily_count_snapshot(),
            "data_boundary": sorted(_CF_AI_ALLOWED_FIELDS),
        }

    # ------------------------------------------------------------------
    # 公开接口 2：只读最新缓存（绝不发外部请求）
    # ------------------------------------------------------------------

    def get_latest_cached_insights(self) -> dict:
        """
        返回最近一次成功调用的缓存结果。
        不发外部请求，缓存为空时返回 {"status": "no_cache"}。
        """
        with _cf_cache_lock:
            if _cf_cached_result is None:
                return {
                    "status": "no_cache",
                    "message": "尚无缓存，请先调用 POST /api/v2/insights/generate",
                }
            return dict(_cf_cached_result)

    # ------------------------------------------------------------------
    # 公开接口 3：主动生成洞察（唯一可触发外部请求的入口）
    # ------------------------------------------------------------------

    def generate_insights(self, summary_data: dict) -> dict:
        """
        主动触发 Cloudflare Workers AI 调用，返回洞察文本并更新进程缓存。

        触发规则（优先级从高到低）：
        1. 未启用或凭据缺失 → 安全降级，不发请求。
        2. 白名单过滤后无有效字段 → 安全降级，不发请求。
        3. 指纹命中且 TTL 内 → 直接返回缓存，不发请求。
        4. 当日限额已耗尽 → 返回 rate_limited，不发请求。
        5. 以上均不符合 → 发起真实 HTTP 请求，成功后更新缓存与计数。

        Parameters
        ----------
        summary_data : dict
            来自 /api/v2/dashboard/overview 的聚合字典；
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

        # ---- 5. 构造用户消息（纯数字键值对，无文本字段）----
        user_message = "当前项目宏观指标（均为虚构模拟数据）：\n"
        for k, v in sorted(safe_payload.items()):
            user_message += f"  {k}: {v}\n"
        user_message += "\n请给出简洁的管理层洞察。"

        # ---- 6. 构造请求 ----
        url = _CF_AI_ENDPOINT.format(
            account_id=account_id,
            model=self._model,
        )
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
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
            import socket

            req_data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(_CF_AI_CONNECT_TIMEOUT + _CF_AI_READ_TIMEOUT)
            try:
                with urllib.request.urlopen(
                    req, timeout=_CF_AI_CONNECT_TIMEOUT + _CF_AI_READ_TIMEOUT
                ) as resp:
                    raw = resp.read()
            finally:
                socket.setdefaulttimeout(old_timeout)

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

        if not resp_json.get("success"):
            errors = resp_json.get("errors", [])
            return {
                "status": "unavailable",
                "message": "CF AI 返回 success=false，已降级",
                "cf_errors": errors[:3] if errors else [],
                "data_boundary": sorted(safe_payload.keys()),
            }

        result = resp_json.get("result") or {}
        insight_text: str = ""

        if isinstance(result, dict):
            choices = result.get("choices")
            if choices and isinstance(choices, list) and len(choices) > 0:
                first_choice = choices[0]
                if isinstance(first_choice, dict):
                    msg = first_choice.get("message") or {}
                    insight_text = msg.get("content") or ""

            if not insight_text:
                insight_text = (
                    result.get("response")
                    or result.get("text")
                    or result.get("content")
                    or ""
                )
        elif isinstance(result, str):
            insight_text = result

        if not insight_text:
            return {
                "status": "unavailable",
                "message": "CF AI 响应中无有效洞察文本，已降级",
                "data_boundary": sorted(safe_payload.keys()),
            }

        # ---- 9. 写入缓存 + 更新计数（线程安全）----
        generated_at = datetime.now().isoformat()
        remaining_calls = max(0, self._daily_limit - (_cf_daily_count + 1))
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
            # 再次确认日期（防止跨日边界竞态），递增计数
            today2 = _utc_date_str()
            if _cf_daily_date != today2:
                _cf_daily_date = today2
                _cf_daily_count = 0
            _cf_daily_count += 1

        return new_entry

    # ------------------------------------------------------------------
    # 向后兼容：保留 get_insights() 作为 generate_insights() 的别名
    # 原有调用方不受影响，但已不推荐直接调用此方法。
    # ------------------------------------------------------------------

    def get_insights(self, summary_data: dict) -> dict:
        """向后兼容别名，内部调用 generate_insights()。"""
        return self.generate_insights(summary_data)
