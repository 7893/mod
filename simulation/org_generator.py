"""
simulation/org_generator.py
===========================
Authentic SOE organization and user profile generator for MOD simulation.
Faithfully reproduces existing 2,000-unit naming morphology:
  古雅地名 (34 provinces) + 产业/行业 + 组织后缀

Strictly zero runtime LLM calls: pure offline dictionary assembly with deduplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import random
from typing import Any, Dict, List, Optional, Set, Tuple

# 34 省份对应古雅地名/历史文化前缀 (完全提炼自现有 2,000 家单位库)
PROV_PREFIXES: Dict[str, List[str]] = {
    "北京市": ["紫禁", "蓟门", "卢沟", "燕京", "香山", "京华", "顺天", "幽州"],
    "上海市": ["申城", "沪江", "春申", "华亭", "淞沪", "浦江", "东方"],
    "天津市": ["津门", "直沽", "渤海", "沽上", "海河", "九河", "盘山"],
    "重庆市": ["巴渝", "渝州", "缙云", "嘉陵", "山城", "江津", "夔门", "巫山"],
    "河北省": ["燕赵", "太行", "冀中", "冀北", "白洋", "滹沱", "燕山", "直隶"],
    "山西省": ["三晋", "晋阳", "晋中", "平城", "太岳", "云冈", "汾河", "雁门", "并州"],
    "辽宁省": ["奉天", "盛京", "辽东", "辽源", "辽海", "关东", "千山", "浑河", "鸭绿"],
    "吉林省": ["长白", "松江", "扶余", "通化", "北山", "吉林", "辽源"],
    "黑龙江省": ["兴安", "龙江", "极北", "呼玛", "松花", "漠河", "冰城", "黑水"],
    "江苏省": ["金陵", "姑苏", "广陵", "梁溪", "建康", "徐州", "扬州", "东林", "沧浪", "云龙", "茅山"],
    "浙江省": ["钱塘", "之江", "甬上", "象山", "越州", "稽山", "瓯越", "临安", "兰亭", "万松", "鹿城"],
    "安徽省": ["黄山", "徽州", "皖江", "庐州", "庐阳", "新安", "敬亭", "太平", "琅琊"],
    "福建省": ["武夷", "八闽", "闽江", "鹭岛", "晋安", "刺桐", "建安", "延平", "榕城"],
    "江西省": ["赣江", "浔阳", "豫章", "濂溪", "井冈", "鹅湖", "庐山", "白鹿洞"],
    "山东省": ["齐鲁", "泉城", "泰山", "青州", "胶东", "琅琊", "蓬莱", "岱宗", "琴岛"],
    "河南省": ["中原", "汴京", "洛阳", "许昌", "豫中", "嵩阳", "商丘", "少林", "应天"],
    "湖北省": ["荆楚", "江城", "襄阳", "汉江", "荆州", "问津", "云梦", "武当", "玉泉"],
    "湖南省": ["潇湘", "湘江", "三湘", "岳麓", "芙蓉", "衡岳", "洞庭", "橘洲", "星城"],
    "广东省": ["羊城", "越秀", "岭南", "广府", "禅城", "鹏城", "南粤", "珠江", "大湾"],
    "广西壮族自治区": ["漓江", "八桂", "青秀", "桂海", "龙州", "花山", "苍梧", "邕江"],
    "海南省": ["天涯", "琼州", "崖州", "琼崖", "海岛", "五指", "南海", "昌江"],
    "四川省": ["青城", "锦官", "蜀道", "天府", "蓉城", "峨眉", "益州", "剑门", "蜀山"],
    "贵州省": ["黔灵", "夜郎", "黔中", "筑城", "梵净", "赤水", "黔南", "乌江", "甲秀"],
    "云南省": ["洱海", "滇池", "春城", "彩云", "南诏", "点苍", "滇南", "苍山"],
    "西藏自治区": ["雪域", "冈底斯", "藏域", "雅砻", "珠峰", "阿里", "日光", "高原"],
    "陕西省": ["长安", "关中", "太白", "三秦", "秦岭", "咸阳", "华山", "渭水", "雍州"],
    "甘肃省": ["凉州", "陇上", "敦煌", "祁连", "河西", "陇右", "嘉峪", "玉门", "金城"],
    "青海省": ["河湟", "昆仑", "柴达木", "三江", "江源", "湟水", "青海湖"],
    "宁夏回族自治区": ["六盘", "塞上", "西夏", "贺兰", "灵州", "银川", "宁朔"],
    "新疆维吾尔自治区": ["天山", "准噶尔", "塔里木", "瀚海", "西域", "丝路", "伊犁", "昆仑"],
    "香港特别行政区": ["香江", "维港", "港岛", "狮子山", "九龙"],
    "澳门特别行政区": ["濠江", "莲岛", "妈阁", "琴澳", "镜湖"],
    "台湾省": ["宝岛", "澎湖", "玉山", "阿里", "台北", "延平"],
    "内蒙古自治区": ["塞北", "阴山", "敕勒", "乌兰", "呼伦", "兴安"],
}

# 产业板块与行业细分 (符合既有 2,000 家行业分布)
INDUSTRIES: List[str] = [
    "能源", "新能源", "林业", "生物科技", "金融", "装备制造", "智能制造", "精密制造",
    "新材料", "水务", "环保", "勘测规划", "信息技术", "网络科技", "数据", "物联",
    "现代物流", "通信", "软件", "光电", "医药", "科技", "现代农业", "商业", "贸易",
    "投资", "发展", "实业", "文化", "传媒", "文化传播", "数字创意", "文旅", "咨询服务",
    "工程技术", "绿色算力", "智慧水务", "智能", "智造", "建设",
]

# 组织后缀形态
SUFFIXES: List[str] = [
    "研究院", "研究所", "事业部", "有限公司", "有限责任公司", "股份有限公司",
    "控股有限公司", "设计院", "数字工坊", "技术服务部", "运营管理部", "创新中心",
    "项目中心", "书院", "工坊", "分公司", "创新工场", "集团有限公司",
]

# 中文百家姓高频姓氏 (严格匹配 sys_user 风格)
SURNAMES: List[str] = [
    "张", "王", "李", "赵", "陈", "刘", "杨", "黄", "吴", "周",
    "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "郑",
    "韩", "唐", "冯", "于", "董", "萧", "程", "曹", "袁", "邓",
    "许", "傅", "沈", "曾", "彭", "吕", "苏", "卢", "蒋", "蔡",
    "贾", "丁", "魏", "薛", "叶", "阎", "余", "潘", "杜", "戴",
    "夏", "钟", "汪", "田", "任", "姜", "范", "方", "石", "姚",
    "谭", "廖", "邹", "熊", "金", "陆", "郝", "孔", "白", "崔",
    "康", "毛", "邱", "秦", "江", "史", "顾", "侯", "邵", "孟",
    "龙", "万", "段", "钱", "汤", "尹", "黎", "易", "常", "武",
    "乔", "贺", "赖", "龚", "文", "庞", "樊", "兰", "殷", "施",
]

# 中文名字常用字库
GIVEN_NAMES: List[str] = [
    "梓轩", "欣怡", "清风", "梦琪", "嘉懿", "梓涵", "子墨", "明轩", "嘉怡", "浩宇",
    "明月", "紫萱", "子萱", "博文", "雨泽", "俊熙", "子涵", "涵亮", "雨萱", "志强",
    "建国", "宇轩", "浩然", "诗涵", "浩辰", "语彤", "俊杰", "奕辰", "宇航", "晨曦",
    "沐阳", "锦程", "承泽", "润泽", "景明", "文彬", "远航", "宏伟", "继宗", "敬轩",
    "睿婕", "浩瀚", "俊豪", "若涵", "嘉文", "思睿", "守正", "风雷", "稼轩", "白",
]

# 标准建设任务模板 (一套 30 项全生命周期任务)
STANDARD_CONSTRUCTION_TASK_TEMPLATES: List[Dict[str, str]] = [
    {"name": "生产与容灾服务器资源规划", "type": "基础环境"},
    {"name": "网络专线连通与防火墙策略开通", "type": "基础环境"},
    {"name": "堡垒机与运维鉴权策略配置", "type": "基础环境"},
    {"name": "云原生容器基础设施环境部署", "type": "基础环境"},
    {"name": "数据库读写分离与高可用集群搭建", "type": "基础环境"},
    {"name": "全链路链路追踪与监控告警上线", "type": "基础环境"},
    {"name": "自动化数据定时备份与容灾演练", "type": "基础环境"},
    {"name": "应用网关路由与负载均衡策略调试", "type": "基础环境"},
    {"name": "组织架构及法人主体主数据同步", "type": "组织权限"},
    {"name": "业务岗位梳理与多维权限矩阵设计", "type": "组织权限"},
    {"name": "单点登录SSO与统一身份认证集成", "type": "组织权限"},
    {"name": "多级审批流引擎模型配置与验证", "type": "组织权限"},
    {"name": "敏感财务数据字段级访问控制策略", "type": "组织权限"},
    {"name": "企业开户银行及银企直联通道配置", "type": "基础数据"},
    {"name": "国家标准会计科目体系映射与下发", "type": "基础数据"},
    {"name": "内部结算价格体系与往来抵消规则", "type": "基础数据"},
    {"name": "多税种税率及自动计税规则配置", "type": "基础数据"},
    {"name": "供应商全生命周期主数据清洗与去重", "type": "基础数据"},
    {"name": "客户主数据与信用档案核对校验", "type": "基础数据"},
    {"name": "存货与物料编码分类标准对齐", "type": "基础数据"},
    {"name": "固定资产与无形资产折旧规则维护", "type": "基础数据"},
    {"name": "各核算主体总账科目期初余额导入", "type": "期初数据"},
    {"name": "固定资产卡片全量数据导入与净值校验", "type": "期初数据"},
    {"name": "应收账款客户明细期初余额核对", "type": "期初数据"},
    {"name": "应付账款供应商未结清款项明细导入", "type": "期初数据"},
    {"name": "OA费用报销单据异步推送接口测试", "type": "接口联调"},
    {"name": "采购商城与结算系统前置接口联调", "type": "接口联调"},
    {"name": "资金管理系统银企直联流水回传联调", "type": "接口联调"},
    {"name": "全员线上操作手册分发与微课学习", "type": "用户培训"},
    {"name": "关键用户实操认证与授权上岗考试", "type": "用户培训"},
]


@dataclass
class GeneratedUser:
    name: str
    role: str
    job: str


@dataclass
class GeneratedOrgProfile:
    name: str
    region: str
    batch_id: int
    status: str
    start_date: date
    end_date: date
    users: List[GeneratedUser]
    tasks: List[Dict[str, Any]]
    readiness: Dict[str, Any]


class OrgNameGenerator:
    """Offline, deterministic-capable SOE name generator with collision detection."""

    def __init__(self, existing_names: Optional[Set[str]] = None, seed: Optional[int] = None):
        self.existing_names: Set[str] = set(existing_names) if existing_names else set()
        self.rng = random.Random(seed)

    def generate_name(self, region: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate a strictly unique name conforming to SOE morphology.
        Returns: (full_name, region)
        """
        all_provinces = list(PROV_PREFIXES.keys())
        target_region = region if region and region in PROV_PREFIXES else self.rng.choice(all_provinces)
        prefixes = PROV_PREFIXES[target_region]

        # Shuffle candidates to minimize collisions
        pref_candidates = list(prefixes)
        ind_candidates = list(INDUSTRIES)
        suf_candidates = list(SUFFIXES)
        self.rng.shuffle(pref_candidates)
        self.rng.shuffle(ind_candidates)
        self.rng.shuffle(suf_candidates)

        for pref in pref_candidates:
            for ind in ind_candidates:
                for suf in suf_candidates:
                    candidate = f"{pref}{ind}{suf}"
                    if candidate not in self.existing_names:
                        self.existing_names.add(candidate)
                        return candidate, target_region

        # Fallback with rare modifier if all base combinations exhausted
        for i in range(1, 100):
            cand = f"{prefixes[0]}{ind_candidates[0]}第{i}{suf_candidates[0]}"
            if cand not in self.existing_names:
                self.existing_names.add(cand)
                return cand, target_region

        raise RuntimeError(f"Unable to generate unique name for region {target_region}")

    def generate_person_name(self, used_names_in_org: Optional[Set[str]] = None) -> str:
        """Generate an authentic Chinese person name not repeating in the same unit."""
        used = used_names_in_org or set()
        for _ in range(100):
            sur = self.rng.choice(SURNAMES)
            given = self.rng.choice(GIVEN_NAMES)
            full = f"{sur}{given}"
            if full not in used:
                used.add(full)
                return full
        return f"{self.rng.choice(SURNAMES)}明轩"

    def generate_user_roster(self, user_count: int = 3) -> List[GeneratedUser]:
        """
        Generate standard 3~5 person roster for an unstarted unit.
        Standard roles & jobs:
          1. 管理人员 / 财务总监 (Required)
          2. 项目经理 / 项目经理 (Required)
          3. 经办人 / 会计主管 (Required)
          4. 经办人 / 出纳 (Optional)
          5. 普通用户 / 经办员 (Optional)
        """
        count = max(3, min(5, user_count))
        used_names: Set[str] = set()
        roster: List[GeneratedUser] = [
            GeneratedUser(
                name=self.generate_person_name(used_names),
                role="管理人员",
                job="财务总监",
            ),
            GeneratedUser(
                name=self.generate_person_name(used_names),
                role="项目经理",
                job="项目经理",
            ),
            GeneratedUser(
                name=self.generate_person_name(used_names),
                role="经办人",
                job="会计主管",
            ),
        ]

        if count >= 4:
            roster.append(
                GeneratedUser(
                    name=self.generate_person_name(used_names),
                    role="经办人",
                    job="出纳",
                )
            )
        if count >= 5:
            roster.append(
                GeneratedUser(
                    name=self.generate_person_name(used_names),
                    role="普通用户",
                    job="经办员",
                )
            )

        return roster

    def generate_org_profile(
        self,
        region: Optional[str] = None,
        event_date: Optional[date] = None,
        user_count: Optional[int] = None,
    ) -> GeneratedOrgProfile:
        """
        Generate a complete, consistent unstarted Batch 8 organization profile.
        All progress is 0.0, status is '未启动', ready for admission.
        """
        today = event_date or date.today()
        name, reg = self.generate_name(region)
        actual_user_count = user_count or self.rng.randint(3, 5)
        users = self.generate_user_roster(actual_user_count)

        # Generate tasks assigned to the users
        tasks = []
        for idx, t_tmpl in enumerate(STANDARD_CONSTRUCTION_TASK_TEMPLATES):
            owner_user = users[idx % len(users)]
            plan_offset = 60 + (idx * 5)
            tasks.append({
                "name": t_tmpl["name"],
                "type": t_tmpl["type"],
                "owner": owner_user.name,
                "plan_time": today + timedelta(days=plan_offset),
                "actual_time": None,
                "status": "未开始",
                "progress": 0,
                "update_time": today,
            })

        # Data readiness record with 0 progress
        readiness = {
            "batch_id": 8,
            "static_total": 60,
            "static_completed": 0,
            "static_rate": "0.0%",
            "opening_total": 80,
            "opening_completed": 0,
            "opening_rate": "0.0%",
            "opening_diff_amount": Decimal("0.00"),
            "dynamic_total": 100,
            "dynamic_completed": 0,
            "dynamic_sync_success": 0,
            "dynamic_sync_fail": 0,
            "dynamic_sync_pending": 100,
            "dynamic_rate": "0.0%",
            "last_sync_time": None,
            "overall_status": "未收集",
        }

        return GeneratedOrgProfile(
            name=name,
            region=reg,
            batch_id=8,
            status="未启动",
            start_date=today,
            end_date=today + timedelta(days=500),
            users=users,
            tasks=tasks,
            readiness=readiness,
        )
