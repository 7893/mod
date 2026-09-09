"""
Diurnal rhythm and burst-interval model for the persistent simulator.

Provides the display-timezone (default Asia/Hong_Kong) 24h intensity curve,
weekend damping, month-end spikes and Poisson burst spacing consumed by
simulation.runtime_service. Event content itself is produced by the
runtime service and streamed through the live-projection journal.
"""


from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Dict, Tuple

from .models import DISPLAY_TIMEZONE

# 核心时区契约：作息节律使用统一展示时区（默认 Asia/Hong_Kong），定义见 app/config.py
HONG_KONG_TZ = DISPLAY_TIMEZONE


# ==============================================================================
# 1. 香港时区物理作息与突发脉冲引擎 (Diurnal & Burst Engine)
# ==============================================================================

class HongKongDiurnalEngine:
    """
    香港时区 24 小时物理作息节律控制器。
    依据真实央国企财务核算、供应链采购与银企支付作息，调控业务吞吐强度。
    """

    # 24 小时作息强度因子 (0.02x ~ 2.0x)
    HOUR_WEIGHTS: Dict[int, float] = {
        0: 0.02,   # 深夜静默 (自动化系统备份)
        1: 0.01,
        2: 0.01,
        3: 0.01,
        4: 0.01,
        5: 0.02,
        6: 0.10,   # 清晨准备
        7: 0.30,   # 早间预热
        8: 1.20,   # 上班签到与开单启动
        9: 1.80,   # 上午业务高峰 (审批、出入库、单据爆发)
        10: 1.95,  # 上午核心峰值
        11: 1.50,  # 临近午间收尾
        12: 0.20,  # 午间休憩低谷
        13: 0.40,  # 下午开工过渡
        14: 1.60,  # 下午开工放量
        15: 2.00,  # 下午结算与资金支付全天极值
        16: 1.85,  # 下午集中记账与复核
        17: 1.10,  # 日终业务交割
        18: 0.80,  # 夜间跑批启动 (接口调用为主)
        19: 1.20,  # 银企日结对账跑批
        20: 0.90,  # 跨系统数据镜像同步
        21: 0.40,  # 批量作业收尾
        22: 0.10,  # 转入夜间休眠
        23: 0.04,
    }

    # 工作日 vs 节假日衰减因子 (周一到周五 1.0~1.1x，周末 0.15x)
    WEEKDAY_WEIGHTS: Dict[int, float] = {
        0: 1.05,  # 周一：周末堆积业务集中释放
        1: 1.10,  # 周二：全周峰值
        2: 1.08,  # 周三：高位平稳
        3: 1.02,  # 周四：平稳
        4: 0.95,  # 周五：下午提前关账
        5: 0.12,  # 周六：仅有零售或连续生产企业
        6: 0.08,  # 周日：低谷
    }

    @classmethod
    def get_intensity(cls, dt: datetime) -> float:
        """根据传入时间（转为香港时区）计算当前业务活跃强度系数"""
        hkt = dt.astimezone(HONG_KONG_TZ)
        hour_w = cls.HOUR_WEIGHTS.get(hkt.hour, 0.5)
        day_w = cls.WEEKDAY_WEIGHTS.get(hkt.weekday(), 1.0)
        
        # 月末结账效应 (25日 ~ 月底强度上浮 30%~50%)
        month_end_mult = 1.0
        if hkt.day >= 25:
            month_end_mult = 1.45
        elif hkt.day <= 3:
            month_end_mult = 1.20  # 月初开账对账
            
        intensity = hour_w * day_w * month_end_mult
        return max(0.01, min(2.5, intensity))

    @classmethod
    def next_burst_interval(cls, dt: datetime, rng: random.Random) -> Tuple[float, int]:
        """
        根据泊松突发模型计算：
        1. 距下一次事件发生的等待秒数 (wait_seconds)
        2. 本次突发的批量单据/凭证笔数 (burst_count: 1~6 笔)
        """
        intensity = cls.get_intensity(dt)
        # 基础平均间隔 10 秒，除以强度因子
        base_mean = 10.0 / intensity
        # 指数分布随机采样
        sample = -math.log(max(1e-9, 1.0 - rng.random()))
        wait_seconds = max(2.5, min(90.0, sample * base_mean))
        
        # 突发量：业务高峰期更容易成批突发
        if intensity >= 1.5:
            burst_count = rng.choices([1, 2, 3, 4, 5], weights=[20, 30, 25, 15, 10])[0]
        elif intensity >= 0.8:
            burst_count = rng.choices([1, 2, 3], weights=[50, 35, 15])[0]
        else:
            burst_count = 1
            
        return wait_seconds, burst_count
