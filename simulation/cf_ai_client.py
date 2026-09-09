"""Cloudflare Workers AI Client with Quota Watchdog & Zero-Failure Fallback.

Design Principles:
1. Hard Quota Defense: Checks QuotaWatchdog before any external HTTP call.
2. Safe Degradation: If API fails, times out, or quota exhausted, transparently falls
   back to LocalNarrativeLibrary without throwing exceptions.
3. Structured Output: Produces consistent executive-level Chinese governance narratives.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Dict, Optional

from dotenv import load_dotenv

from .governance_state_machine import LocalNarrativeLibrary
from .quota_watchdog import QuotaWatchdog

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "@cf/meta/llama-3.1-8b-instruct"
DEFAULT_TIMEOUT_SECONDS = 8.0


@dataclass
class EnrichmentResult:
    source: str  # "CLOUDFLARE_AI" | "LOCAL_FALLBACK"
    model: str
    neurons_used: float
    summary: str
    root_cause: str
    suggested_action: str


class CloudflareAIClient:
    """Zero-failure client for Cloudflare Workers AI governance enrichment."""

    def __init__(
        self,
        watchdog: Optional[QuotaWatchdog] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        load_dotenv("/home/ubuntu/mod/.env.systemd", override=True)
        self.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        self.api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
        self.enabled = os.getenv("MOD_CF_AI_ENABLED", "true").lower() == "true"
        self.model = os.getenv("MOD_CF_AI_MODEL", DEFAULT_MODEL).strip()
        self.gateway = os.getenv("MOD_CF_AI_GATEWAY", "").strip()
        self.timeout = timeout
        self.watchdog = watchdog or QuotaWatchdog()

    def is_configured(self) -> bool:
        return bool(self.account_id and self.api_token and self.enabled)

    def _get_api_url(self) -> str:
        if self.gateway:
            return (
                f"https://gateway.ai.cloudflare.com/v1/{self.account_id}"
                f"/{self.gateway}/workers-ai/{self.model}"
            )
        return (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}"
            f"/ai/run/{self.model}"
        )

    def enrich_issue(
        self,
        issue_id: str,
        issue_type: str,
        unit_name: str,
        province: str,
        current_description: str = "",
        rework_count: int = 0,
    ) -> EnrichmentResult:
        """Enrich a governance issue with AI diagnosis or seamless fallback."""
        # 1. Check if configured & enabled
        if not self.is_configured():
            logger.info("[CF_AI] AI disabled or credentials missing. Using local narrative.")
            return self._fallback_local(issue_type, unit_name, "UNCONFIGURED")

        # 2. Check QuotaWatchdog
        can_run, reason = self.watchdog.can_consume(estimated_neurons=50.0)
        if not can_run:
            logger.warning(f"[CF_AI] Quota Watchdog triggered: {reason}. Using local narrative.")
            return self._fallback_local(issue_type, unit_name, "QUOTA_EXHAUSTED")

        # 3. Call Cloudflare Workers AI
        prompt = (
            f"你是一位国家特大型能源与工业集团的数字化转型高级督察专家。\n"
            f"单位：{unit_name}（{province}）\n"
            f"风险问题类型：{issue_type}\n"
            f"当前状态描述：{current_description or '工单待排查'}\n"
            f"二次返工次数：{rework_count}\n\n"
            f"请针对该单位的建设阻塞进行专家研判，必须严格按以下 JSON 格式输出，不要有额外前缀：\n"
            f'{{"summary": "一句话问题定性", "root_cause": "深入剖析技术/管理根因（约50-100字）", "suggested_action": "具体穿透式整改举措（约50-100字）"}}'
        )

        try:
            url = self._get_api_url()
            req_body = json.dumps(
                {
                    "prompt": prompt,
                    "max_tokens": 300,
                    "temperature": 0.3,
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=req_body,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if not data.get("success", False):
                err = data.get("errors", ["Unknown error"])[0]
                logger.warning(f"[CF_AI] API returned failure: {err}. Using local fallback.")
                return self._fallback_local(issue_type, unit_name, "API_FAILURE")

            result_obj = data.get("result", {})
            response_text = result_obj.get("response", "").strip()
            usage = result_obj.get("usage", {})
            neurons = float(usage.get("neurons", 2.0))

            # Record consumption in watchdog
            self.watchdog.record_consumption(neurons_used=neurons, call_count=1)

            # Parse JSON from response
            parsed = self._extract_json(response_text)
            if parsed and "summary" in parsed and "root_cause" in parsed:
                return EnrichmentResult(
                    source="CLOUDFLARE_AI",
                    model=self.model,
                    neurons_used=neurons,
                    summary=parsed.get("summary", ""),
                    root_cause=parsed.get("root_cause", ""),
                    suggested_action=parsed.get("suggested_action", ""),
                )

            # If plain text returned
            return EnrichmentResult(
                source="CLOUDFLARE_AI",
                model=self.model,
                neurons_used=neurons,
                summary=f"【AI智能研判】{response_text[:80]}",
                root_cause=response_text[:200],
                suggested_action="根据集团数字化转型督导组专家研判意见，按期落实专项闭环销项。",
            )

        except Exception as ex:
            logger.warning(f"[CF_AI] Request exception: {ex}. Using local fallback.")
            return self._fallback_local(issue_type, unit_name, "EXCEPTION")

    def _extract_json(self, text: str) -> Optional[Dict[str, str]]:
        """Attempt to extract JSON object from text."""
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        return None

    def _fallback_local(
        self,
        issue_type: str,
        unit_name: str,
        fallback_reason: str,
    ) -> EnrichmentResult:
        """Generate high-fidelity offline narrative as fallback."""
        industry = LocalNarrativeLibrary.infer_industry(unit_name)
        diag = LocalNarrativeLibrary.get_issue_narrative(industry, issue_type, "推进中")

        return EnrichmentResult(
            source=f"LOCAL_FALLBACK ({fallback_reason})",
            model="LocalNarrativeLibrary_v1",
            neurons_used=0.0,
            summary=f"【专家研判】{unit_name}{issue_type}督办要点已明确",
            root_cause=f"{industry}板块典型约束：{diag}",
            suggested_action="调配数字化骨干专家组进驻，实行现场会审与数据挂账对账，限期恢复建设指标。",
        )
