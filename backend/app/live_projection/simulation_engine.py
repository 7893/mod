"""
AI-Powered Realistic Business Simulation Engine.
独立模拟逻辑内核文件 (docs/28 规范落地实现).

核心特性：
1. 展示时区（默认 Asia/Hong_Kong，UTC+8）物理作息节律与泊松突发脉冲 (Poisson Burst)
2. 企业体量二八定律 (Pareto Tiered Distribution) 空间概率加权
3. 装备制造、能源化工、高校科研、双轨核对、合规审计 5 大板块高仿真剧情语义库
4. 全要素生命周期因果门禁 (已上线产凭证，双轨出核对，在建出考核，储备出入池)
5. 偶发轻微摩擦与自愈闭环联动机制
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

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


# ==============================================================================
# 2. 企业体量金字塔与帕累托分布 (Tiered Pareto Distribution)
# ==============================================================================

class TieredParetoEngine:
    """
    企业体量二八定律加权模型。
    在已上线的单位中，沿海工业制造业重镇常态高频放量，长尾科研所低频偶发。
    """

    # 沿海核心工业大省（经济高权重省份）
    TIER1_REGIONS = {"广东", "江苏", "山东", "上海", "浙江", "辽宁"}
    TIER2_REGIONS = {"北京", "四川", "湖北", "河南", "河北", "陕西", "安徽", "福建", "湖南", "重庆", "天津", "江西", "山西"}

    @classmethod
    def classify_unit(cls, name: str, region: str) -> str:
        """将单位划分为 Tier 1 (龙头), Tier 2 (骨干), Tier 3 (长尾)"""
        norm_r = region.replace("省", "").replace("市", "").replace("壮族自治区", "").replace("回族自治区", "").replace("维吾尔自治区", "").replace("特别行政区", "").replace("自治区", "")
        
        is_heavy_ind = any(k in name for k in ("装备", "重工", "石化", "制造", "能源", "钢铁", "供应链", "工程", "先进"))
        
        if norm_r in cls.TIER1_REGIONS and is_heavy_ind:
            return "TIER_1"  # 龙头重镇
        elif norm_r in cls.TIER1_REGIONS or norm_r in cls.TIER2_REGIONS or is_heavy_ind:
            return "TIER_2"  # 骨干企业
        else:
            return "TIER_3"  # 长尾机构

    @classmethod
    def get_unit_sampling_weight(cls, tier: str) -> float:
        """根据能级返回采样权重 (Tier 1 占 50%, Tier 2 占 35%, Tier 3 占 15%)"""
        if tier == "TIER_1":
            return 5.0
        elif tier == "TIER_2":
            return 2.0
        return 0.5


# ==============================================================================
# 3. AI 行业高仿真剧情语义库 (Industry Semantic Story Library)
# ==============================================================================

class IndustryStoryLibrary:
    """
    专业财税、供应链与企业生命周期真实剧情生成器。
    彻底消灭千篇一律的机械数字拼接。
    """

    STORIES = {
        "HEAVY_MANUFACTURING": [
            "完成深海耐蚀钛合金阀门批次验收，录入采购入库单并生成应付暂估凭证",
            "大型数控五轴机床关键部件出库装配，自动核算结转直接材料生产成本",
            "通过国家级工业计量中心精度复验，触发固定资产验收转固会计凭证",
            "海外重点基建项目特种起重设备发运，自动生成预收账款确认与提单凭证",
            "自动化冲压车间完成夜间连续作业交割，系统自动汇总归集当班工单能耗成本",
        ],
        "ENERGY_CHEMICAL": [
            "长输天然气管道干线完成跨省气量平衡对账，生成管输费往来结算单据",
            "大型炼化一体化装置大宗原油到港卸载，自动校验报关完税凭单并暂估入账",
            "光伏绿电制氢示范站完成上网电量智能对账，自动开具增值税专用发票",
            "煤化工基地热电联产机组完成月度备件盘点，系统自动生成存货盘盈盘亏凭证",
        ],
        "TECH_RESEARCH": [
            "承担国家重点研发计划攻关专项，科研人员提交试剂耗材采购报销通过 AI 验真",
            "第三代半导体晶圆洁净实验室完成中试流片，专项研发费用自动按期资本化转资",
            "高校联合实验室专家技术咨询费发放完成个税代扣代缴并生成银行直联代发流水",
            "工业软件核心算法攻坚团队申领高算力集群云资源机时费，系统自动记入研发支出",
        ],
        "DUAL_RUN_RECON": [
            "执行新老 ERP 系统第 7 轮月末总账凭证真机比对，1,420 笔分录借贷双方完全平账",
            "新老财务双轨并行校验发现固定资产累计折旧尾差 0.08 元，AI 规则引擎生成智能调整分录",
            "双轨冲刺试跑增值税进项发票批量认证，新老两套系统抵扣税额勾稽一致率 100%",
            "模拟下月单轨月结关账试跑，损益类科目全额自动结平，资产负债表借贷分文不差",
        ],
        "COMPLIANCE_AUDIT": [
            "AI 财税风控模型智能识别并拦截一笔跨期增值税专票，系统自动挂起并转入待核验台账",
            "某项目部差旅费报销单超出发票核准预算阈值 3.2%，智能审批流已触发财务总监特别复核",
            "银企直联前置机因银行夜间清算出现短暂微秒级响应延迟，系统已自动重试成功并闭环",
        ],
        "ORGANIZATION_EXPANSION": [
            "集团新设立控股高新子公司已完成法人工商代码登记，自动纳入第八批动态储备池待命",
            "混合所有制改革新划转低空经济产业单位完成档案录入，已统一分配组织机构编码并入池",
        ],
        "TRAINING_ENABLEMENT": [
            "在建批次第 14 期一线制单人机房实操通关考试顺利结业，新增 18 名财务人员获得上岗证书",
            "外围外协单位完成资金结算系统标准接口规范培训，26 名关键用户通过沙箱演练考核",
        ],
    }

    AMOUNTS = [
        "¥128,450.00", "¥385,200.00", "¥642,800.00", "¥1,250,000.00",
        "¥2,480,500.00", "¥4,120,000.00", "¥8,650,000.00", "¥16,800,000.00"
    ]

    @classmethod
    def generate_story(cls, business_type: str, org_name: str, tier: str, rng: random.Random) -> Dict[str, Any]:
        """根据业务类型与企业特征生成高拟真业务剧情"""
        if business_type == "org_pooled":
            story = rng.choice(cls.STORIES["ORGANIZATION_EXPANSION"])
            return {"title": "组织扩容", "desc": story, "amount": None, "badgeTone": "slate"}
            
        elif business_type == "training_certified":
            story = rng.choice(cls.STORIES["TRAINING_ENABLEMENT"])
            return {"title": "培训赋能", "desc": story, "amount": None, "badgeTone": "emerald"}
            
        elif business_type == "dual_run_verified":
            story = rng.choice(cls.STORIES["DUAL_RUN_RECON"])
            return {"title": "双轨核对", "desc": story, "amount": None, "badgeTone": "amber"}
            
        elif business_type in ("document_created", "voucher_created", "integration_completed"):
            # 根据单位名称判断行业
            if any(k in org_name for k in ("装备", "重工", "制造", "工程", "机械")):
                story = rng.choice(cls.STORIES["HEAVY_MANUFACTURING"])
            elif any(k in org_name for k in ("能源", "石化", "油", "煤", "电力", "水务")):
                story = rng.choice(cls.STORIES["ENERGY_CHEMICAL"])
            else:
                story = rng.choice(cls.STORIES["TECH_RESEARCH"])
                
            amount = rng.choice(cls.AMOUNTS) if tier in ("TIER_1", "TIER_2") else "¥48,600.00"
            
            if business_type == "integration_completed":
                title = "接口集成"
                badge_tone = "blue"
            elif business_type == "voucher_created":
                title = "会计凭证"
                badge_tone = "cyan"
            else:
                title = "业务单据"
                badge_tone = "teal"
                
            return {"title": title, "desc": story, "amount": amount, "badgeTone": badge_tone}
            
        return {"title": "实时动态", "desc": "业务平稳处理中", "amount": None, "badgeTone": "default"}


# ==============================================================================
# 4. 全真模拟逻辑统一调度器 (RealisticSimulationEngine)
# ==============================================================================

@dataclass
class SimulationTickResult:
    """单次模拟产生的完整上下文对象"""
    event_id: str
    occurred_at: datetime
    hkt_time_str: str
    business_type: str
    unit_id: int
    unit_name: str
    province: str
    batch_name: str
    batch_id: int
    tier: str
    story_title: str
    story_desc: str
    amount: Optional[str]
    badge_tone: str
    doc_increment: int
    voucher_increment: int
    integration_increment: int
    friction_issue: Optional[Dict[str, Any]] = None


class RealisticSimulationEngine:
    """
    高仿真模拟逻辑总调度器。
    严格执行生命周期因果门禁，输出包含真实语义、合理金额与体量加权的事件流。
    """

    def __init__(self, units_pool: List[Dict[str, Any]], rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()
        self._units_pool = units_pool
        self._sequence = 0

        # 累计因果计数：凭证不得超过单据，接口不得超过凭证（全生命周期因果不变量）
        self._cum_docs = 0
        self._cum_vouchers = 0
        self._cum_integrations = 0
        
        # 将单位按批次与能级预先分类，方便因果采样
        self.launched_units: List[Dict[str, Any]] = []      # 1~5 批
        self.dual_run_units: List[Dict[str, Any]] = []       # 6 批
        self.construction_units: List[Dict[str, Any]] = []   # 7 批
        self.reserve_units: List[Dict[str, Any]] = []        # 8 批
        
        self._classify_units_pool()

    def _classify_units_pool(self) -> None:
        """对单位池进行生命周期阶段与能级打标"""
        for u in self._units_pool:
            bid = u.get("batch_id") or u.get("batchId", 8)
            status = u.get("status", "")
            
            # 计算体量能级
            tier = TieredParetoEngine.classify_unit(u["name"], u["province"])
            u["tier"] = tier
            u["sampling_weight"] = TieredParetoEngine.get_unit_sampling_weight(tier)
            
            if status in ("已上线", "稳定运行") or bid <= 5:
                self.launched_units.append(u)
            elif status == "双轨运行中" or bid == 6:
                self.dual_run_units.append(u)
            elif bid == 7:
                self.construction_units.append(u)
            else:
                self.reserve_units.append(u)

    def next_interval(self, now: Optional[datetime] = None) -> Tuple[float, int]:
        """获取下一次事件发生等待秒数与突发规模"""
        now = now or datetime.now(UTC)
        return HongKongDiurnalEngine.next_burst_interval(now, self.rng)

    def generate_next_event(self, now: Optional[datetime] = None) -> Optional[SimulationTickResult]:
        """
        核心调度方法：
        按照香港当前时钟，结合因果门禁，生成下一笔真实事件。
        """
        now = now or datetime.now(UTC)
        hkt = now.astimezone(HONG_KONG_TZ)
        hkt_str = hkt.strftime("%Y-%m-%d %H:%M:%S")
        
        self._sequence += 1
        event_id = f"sim-{self._sequence:08d}"
        
        # 1. 决定事件大类：
        # 75% 属于投产业务 (已上线单位)
        # 15% 属于双轨真机核对 (第6批)
        # 8% 属于人员通关认证 (第7批)
        # 2% 属于新单位入池 (第8批)
        dice = self.rng.random()
        
        if dice < 0.02 and self.reserve_units:
            # 【因果线 1：第八批未启动储备池 ➔ 仅限新增单位入池】
            unit = self.rng.choice(self.reserve_units)
            b_type = "org_pooled"
            inc_doc, inc_vch, inc_int = 0, 0, 0
            
        elif dice < 0.10 and self.construction_units:
            # 【因果线 2：第七批在建联调 ➔ 仅限培训认证通关，严禁产生业务单据】
            unit = self.rng.choice(self.construction_units)
            b_type = "training_certified"
            inc_doc, inc_vch, inc_int = 0, 0, 0
            
        elif dice < 0.25 and self.dual_run_units:
            # 【因果线 3：第六批双轨冲刺 ➔ 仅限双轨真机比对流水】
            unit = self.rng.choice(self.dual_run_units)
            b_type = "dual_run_verified"
            inc_doc, inc_vch, inc_int = 0, 0, 0
            
        else:
            # 【因果线 4：第一至五批已投产 ➔ 真实业务单据、凭证与接口】
            if not self.launched_units:
                return None
                
            # 按体量二八定律加权采样
            weights = [u["sampling_weight"] for u in self.launched_units]
            unit = self.rng.choices(self.launched_units, weights=weights, k=1)[0]
            
            sub_dice = self.rng.random()
            if sub_dice < 0.40:
                b_type = "document_created"
                inc_doc = self.rng.randint(1, 3)
                inc_vch, inc_int = 0, 0
            elif sub_dice < 0.85:
                b_type = "voucher_created"
                inc_vch = self.rng.randint(1, 2)
                inc_doc, inc_int = 0, 0
            else:
                b_type = "integration_completed"
                inc_int = 1
                inc_doc, inc_vch = 0, 0

            # 因果门禁：凭证累计不得超过单据累计，接口累计不得超过凭证累计。
            # 违反时降级为补单据事件，保证 documents >= vouchers >= integrations 恒成立。
            if b_type == "voucher_created" and self._cum_vouchers + inc_vch > self._cum_docs:
                b_type = "document_created"
                inc_doc = self.rng.randint(1, 3)
                inc_vch, inc_int = 0, 0
            elif b_type == "integration_completed" and self._cum_integrations + inc_int > self._cum_vouchers:
                b_type = "document_created"
                inc_doc = self.rng.randint(1, 3)
                inc_vch, inc_int = 0, 0

        # 2. 生成业务剧情与语义
        tier = unit.get("tier", "TIER_2")
        story_meta = IndustryStoryLibrary.generate_story(b_type, unit["name"], tier, self.rng)
        
        # 3. 偶发轻微业务摩擦与自愈对偶模拟 (每千分之三概率触发)
        friction_issue = None
        if b_type == "integration_completed" and self.rng.random() < 0.05:
            friction_issue = {
                "issue_id": f"ISSUE-SIM-{self._sequence}",
                "org_name": unit["name"],
                "province": unit["province"],
                "desc": "银企直联前置机网络轻微抖动响应超阈值，已触发自愈重试机制",
                "level": "低",
                "status": "处理中",
                "will_heal_in_seconds": 25,
            }

        bid = unit.get("batch_id") or unit.get("batchId", 8)
        batch_name = unit.get("batch_name") or f"第{bid}批"

        # 更新累计因果计数，供后续门禁判断使用
        self._cum_docs += inc_doc
        self._cum_vouchers += inc_vch
        self._cum_integrations += inc_int

        return SimulationTickResult(
            event_id=event_id,
            occurred_at=now,
            hkt_time_str=hkt_str,
            business_type=b_type,
            unit_id=unit.get("id", 0),
            unit_name=unit["name"],
            province=unit["province"],
            batch_name=batch_name,
            batch_id=bid,
            tier=tier,
            story_title=story_meta["title"],
            story_desc=story_meta["desc"],
            amount=story_meta["amount"],
            badge_tone=story_meta["badgeTone"],
            doc_increment=inc_doc,
            voucher_increment=inc_vch,
            integration_increment=inc_int,
            friction_issue=friction_issue,
        )
