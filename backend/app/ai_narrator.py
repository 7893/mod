"""
AI 解说员 - 用于解释和表达，不参与数据控制

职责：
- 生成驾驶舱摘要
- 解释异常和趋势
- 把自然语言转换为模拟参数（建议，不直接执行）

设计原则：
- AI 完全关闭时，系统仍正常运行
- AI 只读取数据，不写入
- 所有 AI 建议需人工确认才生效
"""

import os
import json
import logging
import urllib.request
import urllib.error
import ssl
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 缓存
_summary_cache: Dict[str, Any] = {}
_cache_ttl = 300  # 5分钟


@dataclass
class NarratorResult:
    """AI 解说结果"""
    content: str
    generated_at: str
    source: str  # "ai" | "template"
    tokens_used: int = 0


class AINarrator:
    """AI 解说员"""
    
    def __init__(self):
        self.gateway_url = os.getenv("MOD_CF_AI_GATEWAY_URL", "").strip()
        self.api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
        explicitly_enabled = (
            os.getenv("MOD_CF_AI_ENABLED", "false").strip().lower() == "true"
        )
        self.enabled = explicitly_enabled and bool(self.gateway_url) and bool(self.api_token)
        if not self.enabled:
            logger.info("AI Narrator disabled: explicit enablement and configuration required")
    
    def _call_ai(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        """调用 AI Gateway"""
        if not self.enabled:
            return None
        
        try:
            data = json.dumps({
                "messages": [
                    {"role": "system", "content": "你是政府财务管理系统的数据分析助手。用简洁的中文回答，不超过100字。"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
            }).encode('utf-8')
            
            req = urllib.request.Request(
                self.gateway_url,
                data=data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "MOD-AINarrator/1.0",
                },
                method="POST"
            )
            
            ctx = ssl.create_default_context()
            response = urllib.request.urlopen(req, timeout=10, context=ctx)
            result = json.loads(response.read().decode('utf-8'))
            
            # 提取内容
            if "result" in result:
                r = result["result"]
                if "choices" in r and len(r["choices"]) > 0:
                    return r["choices"][0].get("message", {}).get("content", "")
                elif "response" in r:
                    resp = r["response"]
                    return resp if isinstance(resp, str) else json.dumps(resp)
            
            return None
            
        except Exception as exc:
            logger.warning("AI call failed: %s", type(exc).__name__)
            return None
    
    def generate_dashboard_summary(self, stats: Dict) -> NarratorResult:
        """
        生成驾驶舱摘要
        
        输入示例：
        {
            "today_docs": 1234,
            "yesterday_docs": 1050,
            "today_vouchers": 980,
            "top_provinces": [("广东省", 180), ("江苏省", 156)],
            "integration_success_rate": 0.98,
            "active_scenarios": ["month_end_settlement"],
        }
        """
        # 检查缓存
        cache_key = f"summary_{datetime.utcnow().strftime('%Y%m%d%H')}"
        if cache_key in _summary_cache:
            cached = _summary_cache[cache_key]
            if (datetime.utcnow() - cached["time"]).seconds < _cache_ttl:
                return NarratorResult(
                    content=cached["content"],
                    generated_at=cached["generated_at"],
                    source="cache",
                )
        
        # 计算基础指标
        today_docs = stats.get("today_docs", 0)
        yesterday_docs = stats.get("yesterday_docs", 0)
        growth_rate = ((today_docs - yesterday_docs) / yesterday_docs * 100) if yesterday_docs > 0 else 0
        top_provinces = stats.get("top_provinces", [])
        success_rate = stats.get("integration_success_rate", 1.0)
        scenarios = stats.get("active_scenarios", [])
        
        # 尝试 AI 生成
        prompt = f"""根据以下数据生成一句驾驶舱摘要：
- 今日单据：{today_docs}笔，较昨日{'增长' if growth_rate >= 0 else '下降'}{abs(growth_rate):.1f}%
- 业务集中省份：{', '.join([p[0] for p in top_provinces[:3]]) if top_provinces else '均匀分布'}
- 接口成功率：{success_rate*100:.1f}%
- 当前情景：{', '.join(scenarios) if scenarios else '正常运行'}

要求：一句话，不超过50字，说明今日业务特点。"""

        ai_content = self._call_ai(prompt, max_tokens=100)
        
        if ai_content:
            result = NarratorResult(
                content=ai_content.strip(),
                generated_at=datetime.utcnow().isoformat(),
                source="ai",
            )
        else:
            # 模板回退
            content = self._template_summary(today_docs, growth_rate, top_provinces, success_rate, scenarios)
            result = NarratorResult(
                content=content,
                generated_at=datetime.utcnow().isoformat(),
                source="template",
            )
        
        # 更新缓存
        _summary_cache[cache_key] = {
            "content": result.content,
            "generated_at": result.generated_at,
            "time": datetime.utcnow(),
        }
        
        return result
    
    def _template_summary(
        self, 
        today_docs: int, 
        growth_rate: float, 
        top_provinces: list, 
        success_rate: float,
        scenarios: list
    ) -> str:
        """模板生成摘要（AI 不可用时的回退）"""
        parts = []
        
        # 增长描述
        if growth_rate > 10:
            parts.append(f"今日单据量显著增长{growth_rate:.0f}%")
        elif growth_rate > 0:
            parts.append(f"今日单据量增长{growth_rate:.0f}%")
        elif growth_rate < -10:
            parts.append(f"今日单据量下降{abs(growth_rate):.0f}%")
        else:
            parts.append("今日业务量平稳")
        
        # 省份集中
        if top_provinces:
            top_names = [p[0].replace("省", "") for p in top_provinces[:2]]
            parts.append(f"主要集中在{'/'.join(top_names)}")
        
        # 情景影响
        scenario_names = {
            "month_end_settlement": "月末结算",
            "interface_outage": "接口波动",
            "night_batch_process": "夜间批处理",
        }
        if scenarios:
            named = [scenario_names.get(s, s) for s in scenarios[:1]]
            parts.append(f"受{named[0]}影响")
        
        # 异常提示
        if success_rate < 0.95:
            parts.append(f"接口成功率{success_rate*100:.0f}%需关注")
        
        return "，".join(parts) + "。"
    
    def explain_anomaly(self, anomaly_data: Dict) -> NarratorResult:
        """
        解释异常
        
        输入示例：
        {
            "type": "integration_failure_spike",
            "time": "14:20",
            "metric": "integration_success_rate",
            "value": 0.85,
            "baseline": 0.98,
            "related_events": ["retry_surge", "timeout_errors"],
        }
        """
        anomaly_type = anomaly_data.get("type", "unknown")
        time = anomaly_data.get("time", "")
        value = anomaly_data.get("value", 0)
        baseline = anomaly_data.get("baseline", 0)
        related = anomaly_data.get("related_events", [])
        
        prompt = f"""解释以下异常：
- 类型：{anomaly_type}
- 时间：{time}
- 当前值：{value}，基线：{baseline}
- 关联事件：{', '.join(related) if related else '无'}

要求：一句话解释可能原因，不超过40字。"""

        ai_content = self._call_ai(prompt, max_tokens=80)
        
        if ai_content:
            return NarratorResult(
                content=ai_content.strip(),
                generated_at=datetime.utcnow().isoformat(),
                source="ai",
            )
        
        # 模板回退
        templates = {
            "integration_failure_spike": f"{time}接口成功率下降至{value*100:.0f}%，可能与集中重试有关。",
            "document_surge": f"{time}单据量激增，可能为月末集中提交。",
            "low_activity": f"{time}业务量偏低，可能受节假日影响。",
        }
        content = templates.get(anomaly_type, f"{time}出现{anomaly_type}异常，需进一步排查。")
        
        return NarratorResult(
            content=content,
            generated_at=datetime.utcnow().isoformat(),
            source="template",
        )
    
    def parse_scenario_request(self, user_input: str) -> Dict:
        """
        把自然语言转换为模拟参数（只返回建议，不直接执行）
        
        输入示例："把国庆期间业务量降到平时的30%，节后两天释放积压"
        
        返回：
        {
            "understood": True,
            "suggestion": {
                "scenario_type": "holiday_effect",
                "start_date": "2026-10-01",
                "end_date": "2026-10-07",
                "activity_multiplier": 0.3,
                "catchup_days": 2,
                "catchup_multiplier": 1.5,
            },
            "explanation": "建议配置国庆期间...",
            "requires_confirmation": True,
        }
        """
        prompt = f"""用户说："{user_input}"

请提取模拟参数，返回JSON格式：
{{
  "scenario_type": "类型(holiday_effect/batch_onboarding/interface_issue)",
  "parameters": {{相关参数}},
  "explanation": "一句话解释你的理解"
}}

如果无法理解，返回 {{"understood": false, "explanation": "原因"}}"""

        ai_content = self._call_ai(prompt, max_tokens=200)
        
        if ai_content:
            try:
                # 尝试解析 JSON
                # 找到 JSON 部分
                start = ai_content.find("{")
                end = ai_content.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(ai_content[start:end])
                    parsed["requires_confirmation"] = True
                    parsed["source"] = "ai"
                    return parsed
            except json.JSONDecodeError:
                pass
        
        # 无法理解
        return {
            "understood": False,
            "explanation": "无法理解该请求，请使用更明确的描述。",
            "source": "fallback",
        }


# 全局单例
_narrator_instance: Optional[AINarrator] = None


def get_narrator() -> AINarrator:
    """获取 AI 解说员单例"""
    global _narrator_instance
    if _narrator_instance is None:
        _narrator_instance = AINarrator()
    return _narrator_instance
