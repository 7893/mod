"""Business simulation domain models and probability systems."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

@dataclass
class GrowthTarget:
    """增长目标配置"""
    # 目标时间点
    target_date: datetime = field(default_factory=lambda: datetime(2027, 3, 1))
    
    # 目标值（允许区间）
    document_target: Tuple[int, int] = (9_500_000, 10_500_000)  # 950万~1050万
    voucher_target: Tuple[int, int] = (7_000_000, 8_000_000)
    integration_target: Tuple[int, int] = (6_500_000, 7_500_000)
    
    # 当前起点（从数据库读取）
    document_current: int = 5_000_000
    voucher_current: int = 3_200_000
    integration_current: int = 3_000_000
    
    def get_progress_factor(self, metric: str, current: int, now: datetime) -> float:
        """
        计算进度因子：偏离目标时轻微调整
        返回 0.8~1.2，用于微调增长速度
        """
        targets = {
            "document": self.document_target,
            "voucher": self.voucher_target,
            "integration": self.integration_target,
        }
        starts = {
            "document": self.document_current,
            "voucher": self.voucher_current,
            "integration": self.integration_current,
        }
        
        target_range = targets.get(metric, (0, 0))
        start = starts.get(metric, 0)
        target_mid = (target_range[0] + target_range[1]) / 2
        
        # 计算时间进度
        total_days = (self.target_date - datetime(2026, 9, 1)).days
        elapsed_days = (now - datetime(2026, 9, 1)).days
        time_progress = max(0, min(1, elapsed_days / total_days))
        
        # 期望值
        expected = start + (target_mid - start) * time_progress
        
        # 偏差率
        if expected <= 0:
            return 1.0
        deviation = (current - expected) / expected
        
        # 偏离时轻微调整（最多±20%）
        if deviation > 0.05:  # 超前
            return max(0.8, 1.0 - deviation * 0.5)
        elif deviation < -0.05:  # 落后
            return min(1.2, 1.0 - deviation * 0.5)
        return 1.0


# ===== 第二层：时间规律系统 =====

class TimePatternSystem:
    """时间规律系统 - 计算业务活跃度"""
    
    # 小时系数（北京时间）
    HOUR_FACTORS = {
        0: 0.02, 1: 0.01, 2: 0.01, 3: 0.01, 4: 0.01, 5: 0.02,
        6: 0.10, 7: 0.25, 8: 0.50,
        9: 1.00, 10: 1.20, 11: 1.10,  # 上午高峰
        12: 0.40, 13: 0.50,            # 午休
        14: 1.10, 15: 1.30, 16: 1.20, 17: 0.80,  # 下午高峰
        18: 0.30, 19: 0.15, 20: 0.10, 21: 0.05, 22: 0.03, 23: 0.02,
    }
    
    # 工作日系数
    WEEKDAY_FACTORS = {
        0: 1.0,   # 周一
        1: 1.05,  # 周二
        2: 1.05,  # 周三
        3: 1.0,   # 周四
        4: 0.95,  # 周五（下午略少）
        5: 0.15,  # 周六
        6: 0.10,  # 周日
    }
    
    # 月内日期系数
    DAY_OF_MONTH_FACTORS = {
        "early": 0.9,     # 1-5日
        "normal": 1.0,    # 6-20日
        "month_end": 1.4, # 21-25日（结算高峰）
        "last_days": 1.6, # 26-31日（月末冲刺）
    }
    
    # 节假日（简化版，实际应从配置读取）
    HOLIDAYS_2026 = [
        # 春节
        (datetime(2026, 1, 28), datetime(2026, 2, 4), 0.05),
        # 清明
        (datetime(2026, 4, 4), datetime(2026, 4, 6), 0.2),
        # 劳动节
        (datetime(2026, 5, 1), datetime(2026, 5, 5), 0.15),
        # 端午
        (datetime(2026, 6, 25), datetime(2026, 6, 27), 0.2),
        # 国庆
        (datetime(2026, 10, 1), datetime(2026, 10, 7), 0.08),
    ]
    
    @classmethod
    def get_activity_level(cls, dt: datetime) -> float:
        """
        计算某时刻的业务活跃度
        返回 0.01 ~ 2.0 之间的系数
        """
        # 转北京时间
        beijing_dt = dt + timedelta(hours=8)
        
        # 1. 小时系数
        hour_factor = cls.HOUR_FACTORS.get(beijing_dt.hour, 0.5)
        
        # 2. 工作日系数
        weekday_factor = cls.WEEKDAY_FACTORS.get(beijing_dt.weekday(), 1.0)
        
        # 3. 月内日期系数
        day = beijing_dt.day
        if day <= 5:
            day_factor = cls.DAY_OF_MONTH_FACTORS["early"]
        elif day <= 20:
            day_factor = cls.DAY_OF_MONTH_FACTORS["normal"]
        elif day <= 25:
            day_factor = cls.DAY_OF_MONTH_FACTORS["month_end"]
        else:
            day_factor = cls.DAY_OF_MONTH_FACTORS["last_days"]
        
        # 4. 节假日检查
        holiday_factor = 1.0
        for start, end, factor in cls.HOLIDAYS_2026:
            if start <= beijing_dt.replace(tzinfo=None) <= end:
                holiday_factor = factor
                break
        
        # 组合（乘法）
        activity = hour_factor * weekday_factor * day_factor * holiday_factor
        
        # 添加轻微随机扰动（±5%）
        noise = random.gauss(1.0, 0.025)
        activity *= max(0.9, min(1.1, noise))
        
        return max(0.01, min(2.0, activity))


# ===== 第三层：业务事件链 =====

class EventStatus(Enum):
    """事件状态"""
    # 单据状态
    DOC_SUBMITTED = "doc_submitted"
    DOC_PENDING_APPROVAL = "doc_pending_approval"
    DOC_APPROVED = "doc_approved"
    DOC_REJECTED = "doc_rejected"
    
    # 凭证状态
    VOUCHER_GENERATED = "voucher_generated"
    VOUCHER_PENDING_INTEGRATION = "voucher_pending_integration"
    
    # 集成状态
    INTEGRATION_PENDING = "integration_pending"
    INTEGRATION_SUCCESS = "integration_success"
    INTEGRATION_FAILED = "integration_failed"
    INTEGRATION_RETRY = "integration_retry"
    
    # 终态
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class BusinessEvent:
    """业务事件"""
    event_id: str
    org_id: int
    event_type: str  # expense, payment, receipt, transfer
    amount: float
    status: EventStatus
    created_at: datetime
    updated_at: datetime
    
    # 关联ID
    doc_id: Optional[int] = None
    voucher_id: Optional[int] = None
    integration_id: Optional[int] = None
    
    # 状态数据
    approval_time: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    
    # 元数据
    applicant: str = ""
    province: str = ""


class BusinessEventChain:
    """业务事件链 - 管理事件状态转换"""
    
    # 审批通过概率（按类型）
    APPROVAL_PROB = {
        "expense": 0.92,
        "payment": 0.95,
        "receipt": 0.98,
        "transfer": 0.96,
    }
    
    # 审批耗时分布参数（对数正态，单位：分钟）
    # 演示模式：极短（几秒内审批完成）
    APPROVAL_TIME_PARAMS = {
        "expense": (-2.0, 0.3),   # 约 0.1 分钟 = 6 秒
        "payment": (-2.2, 0.3),   # 约 0.1 分钟 = 6 秒
        "receipt": (-2.5, 0.2),   # 约 0.08 分钟 = 5 秒
        "transfer": (-2.2, 0.3),  # 约 0.1 分钟 = 6 秒
    }
    
    # 集成失败率（正常情况）
    BASE_INTEGRATION_FAILURE_RATE = 0.02
    
    # 重试间隔（分钟）
    RETRY_INTERVALS = [1, 5, 15, 30, 60]
    
    @classmethod
    def generate_approval_time(cls, event_type: str) -> float:
        """生成审批耗时（分钟），使用对数正态分布"""
        mu, sigma = cls.APPROVAL_TIME_PARAMS.get(event_type, (3.0, 0.8))
        # 对数正态分布：大部分快，少数慢
        time_minutes = math.exp(random.gauss(mu, sigma))
        # 限制范围：0.05分钟(3秒) ~ 8小时
        return max(0.05, min(480, time_minutes))
    
    @classmethod
    def should_approve(cls, event_type: str) -> bool:
        """判断是否审批通过"""
        prob = cls.APPROVAL_PROB.get(event_type, 0.95)
        return random.random() < prob
    
    @classmethod
    def should_integration_fail(cls, failure_rate: float = None) -> bool:
        """判断集成是否失败"""
        rate = failure_rate or cls.BASE_INTEGRATION_FAILURE_RATE
        return random.random() < rate
    
    @classmethod
    def get_next_retry_time(cls, retry_count: int, now: datetime) -> datetime:
        """计算下次重试时间"""
        idx = min(retry_count, len(cls.RETRY_INTERVALS) - 1)
        interval = cls.RETRY_INTERVALS[idx]
        # 添加少量随机抖动
        jitter = random.randint(-10, 30)
        return now + timedelta(minutes=interval, seconds=jitter)


# ===== 第四层：概率分布 =====

class ProbabilityDistributions:
    """概率分布系统（纯 Python 实现）"""
    
    @staticmethod
    def _lognormal(mu: float, sigma: float) -> float:
        """对数正态分布"""
        return math.exp(random.gauss(mu, sigma))
    
    @staticmethod
    def _negative_binomial(r: float, p: float) -> int:
        """负二项分布的简化实现"""
        # 使用伽马-泊松混合
        # 当 r 较大时近似泊松分布
        if p >= 1:
            return 0
        mean = r * (1 - p) / p
        # 简化：使用泊松近似 + 额外方差
        variance_factor = 1 / p
        adjusted_mean = mean * random.uniform(0.5, 1.5 * variance_factor)
        # 泊松采样
        L = math.exp(-max(0.1, adjusted_mean))
        k = 0
        p_val = 1.0
        while p_val > L:
            k += 1
            p_val *= random.random()
        return k - 1
    
    @staticmethod
    def document_arrival_count(base_rate: float, activity: float) -> int:
        """
        单据到达数量 - 负二项分布
        允许比泊松分布更容易出现高峰
        """
        mean = base_rate * activity
        if mean <= 0:
            return 0
        
        # 负二项分布参数
        r = 5
        p = r / (r + mean)
        
        try:
            count = ProbabilityDistributions._negative_binomial(r, p)
            return int(min(count, mean * 5))  # 限制上限
        except (OverflowError, ValueError):
            return int(max(0, random.gauss(mean, mean * 0.3)))
    
    @staticmethod
    def amount_distribution(event_type: str) -> float:
        """
        金额分布 - 对数正态分布
        大部分金额适中，少数特别大
        """
        params = {
            "expense": (8.5, 1.2),    # 中位数约5000
            "payment": (9.5, 1.5),    # 中位数约13000
            "receipt": (9.0, 1.3),    # 中位数约8000
            "transfer": (10.0, 1.0),  # 中位数约22000
        }
        mu, sigma = params.get(event_type, (9.0, 1.2))
        amount = ProbabilityDistributions._lognormal(mu, sigma)
        # 限制范围：100 ~ 500万
        return round(max(100, min(5_000_000, amount)), 2)
    
    @staticmethod
    def org_activity_weight(org_id: int, base_weight: float = 1.0) -> float:
        """
        单位活跃度权重 - 每个单位有稳定的权重
        使用 org_id 作为种子确保一致性
        """
        # 使用 org_id 生成稳定的随机权重
        rng = random.Random(org_id * 31337)
        # 对数正态分布：大部分单位中等活跃，少数特别活跃
        weight = math.exp(rng.gauss(0, 0.5))
        return base_weight * max(0.2, min(3.0, weight))


# ===== 第五层：情景系统 =====

class ScenarioType(Enum):
    """情景类型"""
    MONTH_END_SETTLEMENT = "month_end_settlement"      # 月末集中结算
    BATCH_ONBOARDING = "batch_onboarding"              # 批量上线
    INTERFACE_OUTAGE = "interface_outage"              # 接口故障
    TRAINING_SESSION = "training_session"              # 集中培训
    PRE_HOLIDAY_RUSH = "pre_holiday_rush"              # 节前报销高峰
    NIGHT_BATCH_PROCESS = "night_batch_process"        # 夜间批处理
    POST_OUTAGE_CATCHUP = "post_outage_catchup"        # 故障恢复积压释放


@dataclass
class ActiveScenario:
    """活跃的情景"""
    scenario_type: ScenarioType
    started_at: datetime
    ends_at: datetime
    intensity: float  # 影响强度 0.5~2.0
    affected_provinces: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class ScenarioSystem:
    """情景系统 - 偶发事件制造真实感"""
    
    def __init__(self):
        self.active_scenarios: List[ActiveScenario] = []
        self._last_check = None
    
    def update(self, now: datetime) -> List[ActiveScenario]:
        """更新情景状态，返回当前活跃的情景"""
        # 移除已结束的情景
        self.active_scenarios = [
            s for s in self.active_scenarios if s.ends_at > now
        ]
        
        # 检查是否触发新情景（每小时检查一次）
        if self._last_check is None or (now - self._last_check).seconds >= 3600:
            self._last_check = now
            self._maybe_trigger_scenarios(now)
        
        return self.active_scenarios
    
    def _maybe_trigger_scenarios(self, now: datetime):
        """概率触发新情景"""
        beijing_dt = now + timedelta(hours=8)
        
        # 月末结算（21-31日，概率触发）
        if 21 <= beijing_dt.day <= 31 and random.random() < 0.3:
            if not any(s.scenario_type == ScenarioType.MONTH_END_SETTLEMENT 
                      for s in self.active_scenarios):
                self.active_scenarios.append(ActiveScenario(
                    scenario_type=ScenarioType.MONTH_END_SETTLEMENT,
                    started_at=now,
                    ends_at=now + timedelta(hours=random.randint(4, 12)),
                    intensity=random.uniform(1.3, 1.8),
                ))
        
        # 接口故障（小概率）
        if random.random() < 0.02:
            if not any(s.scenario_type == ScenarioType.INTERFACE_OUTAGE 
                      for s in self.active_scenarios):
                self.active_scenarios.append(ActiveScenario(
                    scenario_type=ScenarioType.INTERFACE_OUTAGE,
                    started_at=now,
                    ends_at=now + timedelta(minutes=random.randint(10, 60)),
                    intensity=0.1,  # 集成成功率降低
                    metadata={"failure_rate": random.uniform(0.3, 0.8)},
                ))
        
        # 夜间批处理（22:00-06:00）
        if 22 <= beijing_dt.hour or beijing_dt.hour < 6:
            if random.random() < 0.1:
                if not any(s.scenario_type == ScenarioType.NIGHT_BATCH_PROCESS 
                          for s in self.active_scenarios):
                    self.active_scenarios.append(ActiveScenario(
                        scenario_type=ScenarioType.NIGHT_BATCH_PROCESS,
                        started_at=now,
                        ends_at=now + timedelta(hours=random.randint(1, 3)),
                        intensity=random.uniform(2.0, 5.0),  # 夜间批处理量大
                    ))
    
    def get_integration_failure_rate(self) -> float:
        """获取当前集成失败率"""
        base_rate = BusinessEventChain.BASE_INTEGRATION_FAILURE_RATE
        
        for scenario in self.active_scenarios:
            if scenario.scenario_type == ScenarioType.INTERFACE_OUTAGE:
                return scenario.metadata.get("failure_rate", 0.5)
        
        return base_rate
    
    def get_activity_multiplier(self) -> float:
        """获取情景对活跃度的影响"""
        multiplier = 1.0
        
        for scenario in self.active_scenarios:
            if scenario.scenario_type in [
                ScenarioType.MONTH_END_SETTLEMENT,
                ScenarioType.PRE_HOLIDAY_RUSH,
                ScenarioType.POST_OUTAGE_CATCHUP,
            ]:
                multiplier *= scenario.intensity
            elif scenario.scenario_type == ScenarioType.NIGHT_BATCH_PROCESS:
                multiplier *= scenario.intensity
        
        return multiplier
