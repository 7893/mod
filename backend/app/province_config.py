"""
31 省份配置 - 基于经济发达程度和人口规模
用于 AI 驱动的业务增长模拟
"""

from dataclasses import dataclass
from typing import Dict, List
from enum import Enum


class RegionTier(Enum):
    """地区等级"""
    A = "发达"      # 单位多、业务量大、早期上线
    B = "较发达"    # 单位中等、业务量中等
    C = "中等"      # 单位较少、较晚上线
    D = "欠发达"    # 单位少、业务量小、最晚上线


@dataclass
class ProvinceConfig:
    """省份配置"""
    name: str                  # 省份全称
    short_name: str            # 简称
    tier: RegionTier           # 地区等级
    target_org_count: int      # 目标单位数（最终规模）
    initial_batch: int         # 首次上线批次（1-5）
    business_multiplier: float # 业务量系数（相对于平均值）
    
    @property
    def avg_contacts_per_org(self) -> int:
        """每单位平均联系人数"""
        base = 8
        if self.tier == RegionTier.A:
            return int(base * 1.2)  # 发达地区组织更大
        elif self.tier == RegionTier.D:
            return int(base * 0.8)  # 欠发达地区组织较小
        return base

    @property
    def avg_docs_per_org_monthly(self) -> int:
        """每单位月均单据量"""
        base = 120
        return int(base * self.business_multiplier)


# 31 省份配置（不含港澳台，替换为真实省份分布）
PROVINCE_CONFIGS: Dict[str, ProvinceConfig] = {
    # ========== A 类：发达地区（6个）==========
    "北京市": ProvinceConfig(
        name="北京市", short_name="京", tier=RegionTier.A,
        target_org_count=95, initial_batch=1, business_multiplier=1.8
    ),
    "上海市": ProvinceConfig(
        name="上海市", short_name="沪", tier=RegionTier.A,
        target_org_count=90, initial_batch=1, business_multiplier=1.9
    ),
    "江苏省": ProvinceConfig(
        name="江苏省", short_name="苏", tier=RegionTier.A,
        target_org_count=130, initial_batch=2, business_multiplier=1.7
    ),
    "浙江省": ProvinceConfig(
        name="浙江省", short_name="浙", tier=RegionTier.A,
        target_org_count=110, initial_batch=2, business_multiplier=1.6
    ),
    "广东省": ProvinceConfig(
        name="广东省", short_name="粤", tier=RegionTier.A,
        target_org_count=140, initial_batch=2, business_multiplier=1.8
    ),
    "山东省": ProvinceConfig(
        name="山东省", short_name="鲁", tier=RegionTier.A,
        target_org_count=120, initial_batch=2, business_multiplier=1.5
    ),
    
    # ========== B 类：较发达地区（10个）==========
    "天津市": ProvinceConfig(
        name="天津市", short_name="津", tier=RegionTier.B,
        target_org_count=55, initial_batch=3, business_multiplier=1.3
    ),
    "福建省": ProvinceConfig(
        name="福建省", short_name="闽", tier=RegionTier.B,
        target_org_count=65, initial_batch=3, business_multiplier=1.3
    ),
    "湖北省": ProvinceConfig(
        name="湖北省", short_name="鄂", tier=RegionTier.B,
        target_org_count=70, initial_batch=3, business_multiplier=1.2
    ),
    "湖南省": ProvinceConfig(
        name="湖南省", short_name="湘", tier=RegionTier.B,
        target_org_count=75, initial_batch=3, business_multiplier=1.2
    ),
    "四川省": ProvinceConfig(
        name="四川省", short_name="川", tier=RegionTier.B,
        target_org_count=80, initial_batch=3, business_multiplier=1.1
    ),
    "河南省": ProvinceConfig(
        name="河南省", short_name="豫", tier=RegionTier.B,
        target_org_count=95, initial_batch=3, business_multiplier=1.1
    ),
    "河北省": ProvinceConfig(
        name="河北省", short_name="冀", tier=RegionTier.B,
        target_org_count=70, initial_batch=3, business_multiplier=1.1
    ),
    "辽宁省": ProvinceConfig(
        name="辽宁省", short_name="辽", tier=RegionTier.B,
        target_org_count=60, initial_batch=3, business_multiplier=1.2
    ),
    "安徽省": ProvinceConfig(
        name="安徽省", short_name="皖", tier=RegionTier.B,
        target_org_count=70, initial_batch=3, business_multiplier=1.0
    ),
    "江西省": ProvinceConfig(
        name="江西省", short_name="赣", tier=RegionTier.B,
        target_org_count=60, initial_batch=3, business_multiplier=1.0
    ),
    
    # ========== C 类：中等地区（11个）==========
    "重庆市": ProvinceConfig(
        name="重庆市", short_name="渝", tier=RegionTier.C,
        target_org_count=55, initial_batch=4, business_multiplier=0.95
    ),
    "陕西省": ProvinceConfig(
        name="陕西省", short_name="陕", tier=RegionTier.C,
        target_org_count=55, initial_batch=4, business_multiplier=0.9
    ),
    "山西省": ProvinceConfig(
        name="山西省", short_name="晋", tier=RegionTier.C,
        target_org_count=50, initial_batch=4, business_multiplier=0.9
    ),
    "吉林省": ProvinceConfig(
        name="吉林省", short_name="吉", tier=RegionTier.C,
        target_org_count=45, initial_batch=4, business_multiplier=0.85
    ),
    "黑龙江省": ProvinceConfig(
        name="黑龙江省", short_name="黑", tier=RegionTier.C,
        target_org_count=50, initial_batch=4, business_multiplier=0.85
    ),
    "广西壮族自治区": ProvinceConfig(
        name="广西壮族自治区", short_name="桂", tier=RegionTier.C,
        target_org_count=55, initial_batch=4, business_multiplier=0.8
    ),
    "云南省": ProvinceConfig(
        name="云南省", short_name="滇", tier=RegionTier.C,
        target_org_count=50, initial_batch=4, business_multiplier=0.75
    ),
    "贵州省": ProvinceConfig(
        name="贵州省", short_name="黔", tier=RegionTier.C,
        target_org_count=45, initial_batch=4, business_multiplier=0.7
    ),
    "内蒙古自治区": ProvinceConfig(
        name="内蒙古自治区", short_name="蒙", tier=RegionTier.C,
        target_org_count=40, initial_batch=4, business_multiplier=0.75
    ),
    "新疆维吾尔自治区": ProvinceConfig(
        name="新疆维吾尔自治区", short_name="新", tier=RegionTier.C,
        target_org_count=40, initial_batch=4, business_multiplier=0.7
    ),
    "海南省": ProvinceConfig(
        name="海南省", short_name="琼", tier=RegionTier.C,
        target_org_count=35, initial_batch=4, business_multiplier=0.8
    ),
    
    # ========== D 类：欠发达地区（4个）==========
    "甘肃省": ProvinceConfig(
        name="甘肃省", short_name="甘", tier=RegionTier.D,
        target_org_count=35, initial_batch=5, business_multiplier=0.6
    ),
    "宁夏回族自治区": ProvinceConfig(
        name="宁夏回族自治区", short_name="宁", tier=RegionTier.D,
        target_org_count=25, initial_batch=5, business_multiplier=0.55
    ),
    "青海省": ProvinceConfig(
        name="青海省", short_name="青", tier=RegionTier.D,
        target_org_count=25, initial_batch=5, business_multiplier=0.5
    ),
    "西藏自治区": ProvinceConfig(
        name="西藏自治区", short_name="藏", tier=RegionTier.D,
        target_org_count=20, initial_batch=5, business_multiplier=0.4
    ),
}


# 推广批次配置
@dataclass
class BatchConfig:
    """推广批次配置"""
    batch_id: int
    base_start_month: int      # 相对于起点(2023-07)的月数
    variance_days: int         # 随机浮动天数（±）
    description: str


BATCH_CONFIGS: List[BatchConfig] = [
    BatchConfig(1, 0, 15, "试点批次：北京、上海"),
    BatchConfig(2, 3, 20, "扩大试点：江苏、浙江、广东、山东"),
    BatchConfig(3, 7, 25, "全面推广：B类省份"),
    BatchConfig(4, 12, 30, "深化推广：C类省份"),
    BatchConfig(5, 18, 30, "收尾批次：D类省份"),
]


def get_provinces_by_tier(tier: RegionTier) -> List[ProvinceConfig]:
    """获取指定等级的所有省份"""
    return [p for p in PROVINCE_CONFIGS.values() if p.tier == tier]


def get_provinces_by_batch(batch_id: int) -> List[ProvinceConfig]:
    """获取指定批次上线的所有省份"""
    return [p for p in PROVINCE_CONFIGS.values() if p.initial_batch == batch_id]


def get_total_target_orgs() -> int:
    """获取所有省份目标单位总数"""
    return sum(p.target_org_count for p in PROVINCE_CONFIGS.values())


# 验证配置
def validate_config():
    """验证配置合理性"""
    total = get_total_target_orgs()
    print(f"目标单位总数: {total}")
    
    for tier in RegionTier:
        provinces = get_provinces_by_tier(tier)
        tier_total = sum(p.target_org_count for p in provinces)
        print(f"  {tier.value} ({len(provinces)}省): {tier_total} 单位")
    
    print("\n各批次分布:")
    for batch in BATCH_CONFIGS:
        provinces = get_provinces_by_batch(batch.batch_id)
        batch_total = sum(p.target_org_count for p in provinces)
        names = [p.short_name for p in provinces]
        print(f"  批次{batch.batch_id}: {batch_total} 单位 - {', '.join(names)}")


if __name__ == "__main__":
    validate_config()
