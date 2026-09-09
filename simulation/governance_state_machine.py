"""Governance state machine for issues, defects, and remediation lifecycle.

Implements the 6-stage governance lifecycle:
DISCOVERED (发现) -> ASSIGNED (分派) -> IN_PROGRESS (处置中) -> VERIFYING (核验中) -> RESOLVED (已销项) -> CLOSED (关闭)

Features:
1. Deterministic state transitions with guard conditions.
2. 15% rework loop on verification failure (波折感).
3. Expert specialist pool management (capacity = 8, queueing on exhaustion).
4. Local narrative generator (offline-first, 5 industry categories).
5. One-click dispatch boost mechanism (现场督办).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random
from typing import Any, Dict, List, Optional, Tuple


class GovernanceStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


SPECIALIST_TEAMS: List[str] = [
    "华东实施技术攻坚组·张强",
    "北方重工专项数据清洗专班·李明",
    "核心ERP接口联调支持团队·王建国",
    "财务双轨总账平账专家组·陈晓梅",
    "省信通前置网络保障小组·赵伟",
    "集团数科期初数据核验小组·孙振华",
    "西南区域督导专家团队·周林",
    "总部调度中心特别督导专员·刘波",
]


class LocalNarrativeLibrary:
    """Pre-built high-fidelity narrative seeds for offline-first resilience."""

    STORIES: Dict[str, Dict[str, Any]] = {
        "超期挂账": {
            "title_template": "《关于{name}历史往来账跨期未结清引发期初卡顿的治理工单》",
            "desc_template": "期初数据导入完成率滞后（{rate}%），历史资产负债表与老SAP总账科目存在多笔映射断裂，引发跨期挂账隐患。",
            "investigate_note": "专项组驻点机房，完成历史凭证往来余额核对，锁定 18 笔跨年坏账重分类映射异常。",
            "patch_note": "发布科目映射规则补丁，并在沙箱环境中重新跑批对账。",
            "rework_note": "首次对账试跑发现仍有 2 笔外币核算尾差不平，驳回并进入二次精细排查。",
            "resolve_note": "往来借贷完全平衡，期初数据核验通过率达 100%，正式解除挂账管控并闭环销项。",
        },
        "超预算迹象": {
            "title_template": "《关于{name}多阶段工序推进迟滞与接口联调受阻的督办单》",
            "desc_template": "建设完成度仅为 {rate}%，核心业务流程联调多次触发非标准字符阻断，多阶段返工引发预算与工期预警。",
            "investigate_note": "技术攻坚组排查发现老旧业务系统接口报文存在未转义半角字符，导致前置机报文校验中断。",
            "patch_note": "在前置机中间件增加字符过滤与自动转码插件，重新提交联调请求。",
            "rework_note": "部分历史边界接口仍存在响应超时，驳回并要求网络专线重测。",
            "resolve_note": "全部 24 个外围接口联调压力测试通过，多阶段工序恢复正常推进，工单正式销项。",
        },
        "票据异常": {
            "title_template": "《关于{name}双轨月末记账凭证汇率与尾差不平的紧急处置单》",
            "desc_template": "双轨入账凭证比对一致率仅 {rate}%，未达 95% 门禁，存在外币折算损益及借贷试算不平迹象。",
            "investigate_note": "财务平账专家组调取新老 ERP 双轨比对明细，锁定月末结汇截断时间不一致问题。",
            "patch_note": "统一下发月末总账汇率截断时间窗口，并生成单边凭证对冲调整分录。",
            "rework_note": "新系统仍发现一笔汇率截断尾差 0.04 元，触发二次复核。",
            "resolve_note": "双轨核对分录双方分文不差，一致率恢复至 100%，借贷试算平账，工单闭环销项。",
        },
        "双轨核对差异": {
            "title_template": "《关于{name}双轨真机比对分录不一致的专项整改单》",
            "desc_template": "新老财务双轨并行核对中，凭证入账一致率（{rate}%）跌破警戒线，借贷总额存在系统性偏差。",
            "investigate_note": "调取 1,420 笔比对流水，排查出老系统固定资产累计折旧四舍五入算法与新标准存在差异。",
            "patch_note": "AI 规则引擎生成智能调整补偿分录，并在双轨验证环境中复验。",
            "rework_note": "复验发现两笔特殊存货暂估分录借贷方向反向，驳回重新记账。",
            "resolve_note": "新老系统对账全平，资产负债表与利润表完全一致，销项解除风险预警。",
        },
        "准备期卡顿": {
            "title_template": "《关于{name}基础环境与组织权限配置超期未打通的通报》",
            "desc_template": "属于重点推进批次但仍停留在准备中阶段，前置网络专线或账号权限矩阵未完全就绪。",
            "investigate_note": "督导专员现场核查机房前置机配置，确认防火墙策略拦截了集团核心网段访问。",
            "patch_note": "协调省信通公司更新机房防火墙白名单，重新测试直联专线通断。",
            "rework_note": "备用链路切换测试出现时延超标，驳回并要求重新压接光纤跳线。",
            "resolve_note": "主备链路全部就绪，组织权限矩阵 100% 导入完成，顺利跃迁下一工序，工单销项。",
        },
    }

    @classmethod
    def get_template(cls, issue_type: str) -> Dict[str, Any]:
        return cls.STORIES.get(issue_type, cls.STORIES["超预算迹象"])

    @classmethod
    def infer_industry(cls, unit_name: str) -> str:
        """Infer industry sector from unit name."""
        if any(w in unit_name for w in ("煤", "矿", "焦")):
            return "煤炭开采"
        if any(w in unit_name for w in ("电", "能", "热", "风", "光")):
            return "电力能源"
        if any(w in unit_name for w in ("化", "胶", "油", "气")):
            return "化工新材"
        if any(w in unit_name for w in ("重工", "机", "造", "车", "装")):
            return "高端装备"
        if any(w in unit_name for w in ("融", "资", "财", "保", "商")):
            return "现代金融"
        return "通用工业"

    @classmethod
    def get_issue_narrative(cls, industry: str, issue_type: str, action: str = "推进中") -> str:
        """Return a domain-specific narrative description."""
        tmpl = cls.get_template(issue_type)
        note = tmpl.get("investigate_note", "专项督导组驻点排查，锁定业务数据接口异常与流程断点。")
        return f"[{industry}] {note}"



@dataclass
class ExpertPool:
    """Resource pool for specialist teams (Capacity = 8)."""

    capacity: int = 8
    assigned: Dict[str, str] = field(default_factory=dict)
    available: List[str] = field(default_factory=lambda: list(SPECIALIST_TEAMS))

    def acquire(self, issue_id: str) -> Optional[str]:
        """Acquire a specialist from pool if available."""
        if issue_id in self.assigned:
            return self.assigned[issue_id]
        if not self.available:
            return None
        specialist = self.available.pop(0)
        self.assigned[issue_id] = specialist
        return specialist

    def release(self, issue_id: str) -> Optional[str]:
        """Release specialist back to pool."""
        specialist = self.assigned.pop(issue_id, None)
        if specialist and specialist not in self.available:
            self.available.append(specialist)
        return specialist

    @property
    def free_count(self) -> int:
        return len(self.available)


class GovernanceStateMachine:
    """State machine driver for governance issues."""

    def __init__(self, pool: Optional[ExpertPool] = None, seed: Optional[int] = None):
        self.pool = pool or ExpertPool()
        self.rng = random.Random(seed)

    def transition(
        self,
        current_status: str,
        issue_id: str,
        issue_type: str,
        unit_name: str,
        now: datetime,
        force_boost: bool = False,
    ) -> Tuple[str, Optional[Tuple[str, str, str]]]:
        """Advance an issue state.

        Returns (new_status, timeline_event).
        timeline_event is (action, actor, detail) or None if state unchanged.
        """
        template = LocalNarrativeLibrary.get_template(issue_type)
        status_enum = GovernanceStatus(current_status)

        if status_enum == GovernanceStatus.DISCOVERED:
            specialist = self.pool.acquire(issue_id)
            if specialist or force_boost:
                owner = specialist or SPECIALIST_TEAMS[0]
                action = "调度派工"
                actor = "数字化转型总指挥部"
                detail = f"已下派紧急消缺督办令，指派专项责任人：{owner}"
                return GovernanceStatus.ASSIGNED.value, (action, actor, detail)
            return GovernanceStatus.DISCOVERED.value, None

        elif status_enum == GovernanceStatus.ASSIGNED:
            specialist = self.pool.assigned.get(issue_id) or SPECIALIST_TEAMS[0]
            action = "现场排查"
            actor = specialist
            detail = template["investigate_note"]
            return GovernanceStatus.IN_PROGRESS.value, (action, actor, detail)

        elif status_enum == GovernanceStatus.IN_PROGRESS:
            specialist = self.pool.assigned.get(issue_id) or SPECIALIST_TEAMS[0]
            action = "发布补丁"
            actor = specialist
            detail = template["patch_note"]
            return GovernanceStatus.VERIFYING.value, (action, actor, detail)

        elif status_enum == GovernanceStatus.VERIFYING:
            if not force_boost and self.rng.random() < 0.15:
                # 15% rework loop
                action = "二次核验"
                actor = "质量评审专家委员会"
                detail = template["rework_note"]
                return GovernanceStatus.IN_PROGRESS.value, (action, actor, detail)
            else:
                self.pool.release(issue_id)
                action = "闭环销项"
                actor = "数字化转型总指挥部"
                detail = template["resolve_note"]
                return GovernanceStatus.RESOLVED.value, (action, actor, detail)

        elif status_enum == GovernanceStatus.RESOLVED:
            return GovernanceStatus.CLOSED.value, None

        return current_status, None
