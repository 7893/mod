"""KI-051 扩充名字素材：百家姓 + 大字库单/双字名组合，把名字空间做到数十万级，
使重名率贴近存量(~57%)。用字均为常见、正面、真实的取名用字。"""
from __future__ import annotations

# 百家姓（扩充，含复姓少量）
SURNAMES_EXT: list[str] = list(
    "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤"
)
SURNAMES_EXT = [c for c in SURNAMES_EXT if "\u4e00" <= c <= "\u9fff"]

# 取名常用字（正面、中性、真实；单字名或双字名的组成字）
NAME_CHARS: list[str] = list(
    "伟强磊军洋勇艳杰娟涛明超秀霞平刚桂英华建文辉力德云鹏飞龙鑫波兰玉萍红娥玲芬芳燕彩春菊兰凤洁梅琳素云莲真环雪荣爱妹霞香月莺媛艳瑞凡佳嘉琼勤珍贞莉桂娣叶璧璐娅琦晶妍茜秋珊莎锦黛青倩婷姣婉娴瑾颖露瑶怡婵雁蓓纨仪荷丹蓉眉君琴蕊薇菁梦岚苑婕馨瑗琰韵融园艺咏卿聪澜纯毓悦昭冰爽琬茗羽希宁欣飘育滢馥筠柔竹霭凝晓欢霄枫芸菲寒伊亚宜可姬舒影荔枝丽阳成龙春涛家和顺英华慧巧美娜静淑惠珠翠雅芝玉萍红娥玲芬芳燕彩春菊兰凤洁梅琳晨阳浩宇泽轩睿哲博远航晨曦皓宸楷瑞钧尧圣坤朗�“”"
)
NAME_CHARS = [c for c in NAME_CHARS if c not in "“”"]  # 去杂
# 防御性：只保留合法汉字(去掉任何乱码/非法字符如 �)
NAME_CHARS = [c for c in NAME_CHARS if "\u4e00" <= c <= "\u9fff"]
NAME_CHARS = list(dict.fromkeys(NAME_CHARS))  # 去重、保序

_DOUBLE_HINT = None  # 组合在运行时用 rng 生成


def build_given_name(rng) -> str:
    """~25% 单字名, ~75% 双字名。双字名为主→名字空间大→低重名率。"""
    if rng.random() < 0.25:
        return rng.choice(NAME_CHARS)
    a = rng.choice(NAME_CHARS)
    b = rng.choice(NAME_CHARS)
    while b == a:
        b = rng.choice(NAME_CHARS)
    return a + b


def build_full_name(rng) -> str:
    for _ in range(20):
        name = rng.choice(SURNAMES_EXT) + build_given_name(rng)
        if is_name_clean(name):
            return name
    # 兜底：极罕见，用安全组合
    return rng.choice(SURNAMES_EXT) + rng.choice(["文博", "嘉悦", "宁远", "思齐"])


# ── 不雅/谐音过滤 ──────────────────────────────────────────
_BAD_SUBSTR = [
    "萎", "痿", "逼", "屄", "屌", "鸡巴", "婊", "妓", "娼", "奸", "淫", "荡", "贱",
    "屎", "尿", "屁", "操", "肏", "睾", "肛", "毒", "赌", "嫖", "尸", "祸", "灾",
]
# 姓+名首字谐音黑名单（连读不雅）
_BAD_PAIRS = {
    ("史", "珍"), ("吴", "德"), ("吴", "能"), ("吴", "耻"), ("范", "剑"),
    ("秦", "寿"), ("杨", "萎"), ("阳", "萎"), ("苟", "泰"), ("赖", "德"),
    ("焦", "德"), ("戴", "乃"), ("庞", "光"), ("夏", "建"),
}


def is_name_clean(name: str) -> bool:
    if any(b in name for b in _BAD_SUBSTR):
        return False
    if len(name) >= 2 and (name[0], name[1]) in _BAD_PAIRS:
        return False
    return True
