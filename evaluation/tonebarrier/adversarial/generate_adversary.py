#!/usr/bin/env python3
"""
对抗样本生成器 — 为 tonebarrier SKILL 生成对抗测试用例。

生成 7 个类别的对抗样本 + 正常对照组，验证 DFA 层漏检时 LLM 层能否补救。
纯 Python 标准库实现，零外部依赖。

用法：python3 evaluation/tonebarrier/adversarial/generate_adversary.py
输出：evaluation/tonebarrier/adversarial/adversary_cases.json (全量) + adversary_regression.json (回归子集)
"""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "tonebarrier")
DICT_PATH = os.path.join(SKILL_DIR, "references", "profanity_dict.txt")
HOMOPHONE_PATH = os.path.join(SKILL_DIR, "references", "homophone_guide.md")

OUTPUT_FULL = os.path.join(SCRIPT_DIR, "adversary_cases.json")
OUTPUT_REGRESSION = os.path.join(SCRIPT_DIR, "adversary_regression.json")


# ──────────────────────────────────────────────
#  DFA emulation — replicate boundary-aware search
# ──────────────────────────────────────────────

def load_profanity_set(path):
    """加载脏话词典为小写集合，仅保留 >=2 字符的非纯数字词。"""
    words = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w and len(w) >= 2 and not w.isdigit():
                words.add(w)
    return words


def _is_alpha_boundary(text_lower, start, end):
    """复刻 dfa_filter.py 的 is_alpha_boundary 逻辑。"""
    word = text_lower[start:end]
    if not word.isascii() or not word.isalpha():
        return True
    if start > 0 and text_lower[start - 1].isascii() and text_lower[start - 1].isalpha():
        return False
    if end < len(text_lower) and text_lower[end].isascii() and text_lower[end].isalpha():
        return False
    return True


def dfa_would_hit(profanity_set, text):
    """
    模拟 DFA 检测：若输入文本中包含任意一个脏话词则返回 True。
    对纯英文 ASCII 词施加词边界检查（防止子串误报）。
    """
    text_lower = text.lower()
    i = 0
    while i < len(text_lower):
        found = False
        for w in profanity_set:
            wlen = len(w)
            if text_lower[i:i + wlen] == w:
                if _is_alpha_boundary(text_lower, i, i + wlen):
                    found = True
                    break
        if found:
            return True
        i += 1
    return False


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def fullwidth(s):
    """将 ASCII 字符转为全角形式。"""
    result = []
    for ch in s:
        code = ord(ch)
        if 0x21 <= code <= 0x7E:
            result.append(chr(code - 0x20 + 0xFF00))
        else:
            result.append(ch)
    return "".join(result)


def spaced(s):
    """在字符之间插入空格。"""
    return " ".join(list(s))


def symbol_sep(s, sym):
    """在字符之间插入指定符号。"""
    return sym.join(list(s))


def underscore_sep(s):
    """在字符之间插入下划线。"""
    return "_".join(list(s))


# ──────────────────────────────────────────────
#  Complaint Templates (干净模板，不含任何脏话词)
# ──────────────────────────────────────────────

CN_TEMPLATES = [
    "你们这{word}服务太令人失望了",
    "真是{word}一样的产品设计",
    "用了这{word}产品三天就出故障了",
    "这{word}客服态度实在太差了",
    "你们这{word}app又闪退了真受不了",
    "花了这么多钱买个{word}东西回来",
    "{word}的售后简直让人崩溃",
    "等了这么久就等到这{word}结果",
    "这{word}质量也敢卖这个价",
    "你们{word}这破产品还好意思拿出来卖",
    "太{word}了从来没遇到过这种问题",
    "你们的{word}系统把我的订单弄丢了",
    "这个{word}快递把我的包裹摔烂了",
    "我已经等了{word}一个星期了还没人处理",
    "你这{word}设计是谁想出来的",
]

EN_TEMPLATES = [
    "this {word} app crashed again and I lost all my data",
    "your {word} product broke after just one week of use",
    "the {word} customer support never responds to my emails",
    "this {word} service wasted my entire afternoon for nothing",
    "what is wrong with this {word} website it keeps logging me out",
    "I paid good money for this {word} experience",
    "your {word} company cannot even process a simple refund",
    "this is the {word} worst purchase I have ever made",
    "after three attempts your {word} team still has not fixed it",
    "the {word} delivery arrived two weeks late and damaged",
]

# 用于混合中英的模板
MIX_TEMPLATES = [
    "你们这{word}产品真是绝了",
    "这{word}质量简直让人无语",
    "等了{word}这么久居然还发错货",
    "用了{word}几天就彻底坏了",
    "{word}这售后我真是服了",
]


# ──────────────────────────────────────────────
#  Category generators
# ──────────────────────────────────────────────

def _make_case(cat, subtype, text, level, source, variant, profanity_set):
    dfa_hit = dfa_would_hit(profanity_set, text)
    return {
        "category": cat,
        "subtype": subtype,
        "input": text,
        "expected_level": level,
        "expected_dfa_hit": dfa_hit,
        "source_word": source,
        "variant": variant,
    }


def generate_format_bypass(profanity_set):
    """Category 1: 格式绕过 — 空格/符号/全角/下划线分隔 (~30 cases)"""
    cases = []

    # ----- 空格分隔 -----
    space_words = [
        ("tmd", "t m d", 4),
        ("cnm", "c n m", 4),
        ("傻逼", "傻 逼", 4),
        ("fuck", "f u c k", 4),
        ("shit", "s h i t", 4),
        ("sb", "s b", 4),
        ("ass", "a s s", 4),
        ("jb", "j b", 4),
        ("垃圾", "垃 圾", 4),
        ("nmsl", "n m s l", 4),
        ("wcnm", "w c n m", 4),
        ("cao", "c a o", 4),
    ]
    for i, (src, var, lvl) in enumerate(space_words):
        tmpl = CN_TEMPLATES[i % len(CN_TEMPLATES)] if any('一' <= c <= '鿿' for c in src) else EN_TEMPLATES[i % len(EN_TEMPLATES)]
        text = tmpl.format(word=var)
        cases.append(_make_case("format_bypass", "space", text, lvl, src, var, profanity_set))

    # ----- 符号分隔 -----
    symbol_variants = [
        ("fuck", "f*u*c*k", 4),
        ("shit", "s.h.i.t", 4),
        ("tmd", "t-m-d", 4),
        ("傻逼", "傻·逼", 4),
        ("cnm", "c*n*m", 4),
        ("sb", "s.b", 4),
        ("ass", "a.s.s", 4),
        ("fuck", "f-u-c-k", 4),
        ("bitch", "b.i.t.c.h", 4),
        ("dick", "d.i.c.k", 4),
    ]
    for i, (src, var, lvl) in enumerate(symbol_variants):
        tmpl = CN_TEMPLATES[(i + 3) % len(CN_TEMPLATES)] if any('一' <= c <= '鿿' for c in src) else EN_TEMPLATES[(i + 3) % len(EN_TEMPLATES)]
        text = tmpl.format(word=var)
        cases.append(_make_case("format_bypass", "symbol", text, lvl, src, var, profanity_set))

    # ----- 全角字符 -----
    fullwidth_variants = [
        ("tmd", "ｔｍｄ", 4),
        ("fuck", "ｆｕｃｋ", 4),
        ("shit", "ｓｈｉｔ", 4),
        ("cnm", "ＣＮＭ", 4),
        ("ass", "ａｓｓ", 4),
        ("damn", "ｄａｍｎ", 4),
    ]
    for i, (src, var, lvl) in enumerate(fullwidth_variants):
        tmpl = CN_TEMPLATES[(i + 5) % len(CN_TEMPLATES)] if src in ("tmd", "cnm") else EN_TEMPLATES[(i + 5) % len(EN_TEMPLATES)]
        text = tmpl.format(word=var)
        cases.append(_make_case("format_bypass", "fullwidth", text, lvl, src, var, profanity_set))

    # ----- 下划线分隔（选不在字典中的组合）-----
    # f_u_c_k 和 s_h_i_t 已在字典中 → DFA 会命中，不在这里生成
    underscore_variants = [
        ("cnm", "c_n_m", 4),
        ("nmb", "n_m_b", 4),
        ("jb", "j_b", 4),
    ]
    for i, (src, var, lvl) in enumerate(underscore_variants):
        text = CN_TEMPLATES[(i + 7) % len(CN_TEMPLATES)].format(word=var)
        cases.append(_make_case("format_bypass", "underscore", text, lvl, src, var, profanity_set))

    return cases


def generate_homophone(profanity_set):
    """Category 2: 中文谐音变体 (~50 cases)"""
    cases = []

    # 每个 (source_word, variant, expected_level)
    # known = 已在词典中的变体; unknown = 不在词典中的变体
    homophone_variants = [
        # 傻逼系列
        ("傻逼", "煞笔", 4),   # known - in dict
        ("傻逼", "沙比", 4),   # known - in dict
        ("傻逼", "傻B", 4),    # known - in dict
        ("傻逼", "傻比", 4),   # known - in dict
        ("傻逼", "沙幣", 4),   # unknown - traditional
        ("傻逼", "傻13", 4),   # unknown - number mix
        ("傻逼", "洒比", 4),   # unknown
        # 操你妈系列
        ("操你妈", "草泥马", 4),  # known
        ("操你妈", "草拟吗", 4),  # known
        ("操你妈", "艹泥马", 4),  # known
        ("操你妈", "操尼玛", 4),  # known
        ("操你妈", "草尼馬", 4),  # unknown
        ("操你妈", "操妮玛", 4),  # unknown
        ("操你妈", "草拟麻", 4),  # unknown
        # 我操系列
        ("我操", "卧槽", 3),     # known - mild
        ("我操", "我草", 3),     # known
        ("我操", "窝草", 3),     # known
        ("我操", "我艹", 3),     # known
        ("我操", "我曹", 3),     # unknown
        ("我操", "窝嘈", 3),     # unknown
        ("我操", "我擦", 3),     # known - in dict
        # 他妈系列
        ("他妈", "特么", 3),     # known
        ("他妈", "踏马", 3),     # known
        ("他妈", "特麽", 3),     # known
        ("他妈", "塔玛", 3),     # unknown
        ("他妈", "它玛", 3),     # unknown
        # 你妈系列
        ("你妈", "尼玛", 4),     # known
        ("你妈", "尼马", 4),     # known
        ("你妈", "你玛", 4),     # known
        ("你妈", "尼瑪", 4),     # unknown - traditional
        ("你妈", "尼碼", 4),     # unknown
        ("你妈", "妮马", 4),     # unknown
        # 鸡巴系列
        ("鸡巴", "jb", 4),       # known
        ("鸡巴", "几把", 4),     # known
        ("鸡巴", "鸡8", 4),      # known
        ("鸡巴", "鸡吧", 4),     # known - in dict
        ("鸡巴", "几巴", 4),     # unknown
        ("鸡巴", "j吧", 4),      # unknown - mix
        # 你妈的系列
        ("你妈的", "尼玛的", 4),  # partial known: 尼玛 in dict
        ("你妈的", "nmd", 4),    # known
        ("你妈的", "你马的", 4),  # unknown - 你马 not in dict
        ("你妈的", "妮玛的", 4),  # unknown
        # 妈了个逼系列
        ("妈了个逼", "mlgb", 4),  # known
        ("妈了个逼", "妈了gb", 4), # unknown - mix
        ("妈了个逼", "ml个b", 4),  # unknown - mix
        # 废物系列
        ("废物", "废5", 4),       # unknown
        ("废物", "废柴", 4),      # known - in dict
        ("废物", "费物", 4),      # unknown
        # 弱智系列
        ("弱智", "若智", 4),      # unknown
        ("弱智", "弱zhi", 4),     # unknown - mix pinyin
        ("弱智", "ruo智", 4),     # unknown - mix pinyin
    ]

    for i, (src, var, lvl) in enumerate(homophone_variants):
        tmpl = CN_TEMPLATES[i % len(CN_TEMPLATES)]
        text = tmpl.format(word=var)
        cases.append(_make_case("homophone", "homophone", text, lvl, src, var, profanity_set))

    return cases


def generate_leet(profanity_set):
    """Category 3: Leet 替换 — 数字/字母替换绕过 (~20 cases)"""
    cases = []

    leet_variants = [
        # known in dict
        ("shit", "sh1t", 4),
        ("ass", "@ss", 4),
        ("ass", "a55", 4),
        ("bitch", "b1tch", 4),
        ("dick", "d1ck", 4),
        ("fuck", "f*ck", 4),
        ("fuck", "f**k", 4),
        ("shit", "5h1t", 4),
        # unknown — not in dict
        ("ass", "@$$", 4),
        ("bitch", "b!tch", 4),
        ("dick", "d!ck", 4),
        ("shit", "5hit", 4),
        ("fuck", "phuck", 4),
        ("damn", "d@mn", 4),
        ("hell", "h3ll", 4),
        ("crap", "cr@p", 4),
        ("sucks", "sux", 4),
        ("fucking", "fukin", 4),
        ("fucking", "f**kin", 4),
        ("goddamn", "g0dd@mn", 4),
    ]

    for i, (src, var, lvl) in enumerate(leet_variants):
        tmpl = EN_TEMPLATES[i % len(EN_TEMPLATES)]
        text = tmpl.format(word=var)
        cases.append(_make_case("leet", "leet", text, lvl, src, var, profanity_set))

    return cases


def generate_cnen_mix(profanity_set):
    """Category 4: 中英混杂 (~20 cases)"""
    cases = []

    mix_variants = [
        # 中文 + 英文/拼音缩写混搭 — 全部避开字典中已有的词
        # 策略: 用空格/符号分隔, 或用拼音替换中文, 确保无字典词连续出现
        ("操你妈", "操 n i m a b 的", 4),          # 全分散, DFA-miss
        ("傻逼", "这 s h a b i 设计", 4),          # 分散, DFA-miss
        ("操你妈", "c a o 你 m a 的", 4),          # 分散, DFA-miss
        ("fucking", "l a j i f u c k app", 4),     # "laji" 非中文"垃圾", DFA-miss
        ("shit", "你 m a 的 s h i t", 4),          # 全分散, avoid "你妈的"
        ("操你妈", "k a o 你 m a 的玩意", 4),      # 分散, DFA-miss
        ("傻逼", "你就是个 s h a b i", 4),          # 分散, DFA-miss
        ("fuck", "你这 f u c k 产品", 4),           # 分散, DFA-miss
        ("垃圾", "纯属 t r a s h 品质", 4),          # 分散, DFA-miss
        ("cnm", "这服务 c n m 了", 4),              # 分散, DFA-miss
        ("tmd", "简直 t m d 在骗钱", 4),            # 分散, DFA-miss
        ("傻逼", "你就是个 s b", 4),                 # 分散, DFA-miss
        ("操", "w o 操这质量", 3),                   # 分散, DFA-miss
        ("你妈", "n i 妈 d e 真坑", 4),             # "妈de" ≠ "妈的", DFA-miss
        ("他妈", "t a 妈 d e 货", 4),                # "妈de" ≠ "妈的", DFA-miss
        ("恶心", "e 心死了", 3),                     # "e心" 不匹配任何词, DFA-miss
        ("操你妈", "操 u r m o m 的", 4),            # 分散, DFA-miss
        ("傻逼", "什么 j b 玩意", 4),                # "j b" ≠ "jb", DFA-miss
        ("废物", "纯纯 w a s t e 东西", 4),           # 分散, DFA-miss
        ("弱智", "像个 i d i 0 t 一样", 4),           # 分散, DFA-miss
    ]

    for i, (src, var, lvl) in enumerate(mix_variants):
        # 对于混合变体，直接使用 var 作为整个文本（已经是完整句子）
        # 如果是半句，套入 MIX_TEMPLATES
        text = MIX_TEMPLATES[i % len(MIX_TEMPLATES)].format(word=var)
        cases.append(_make_case("cnen_mix", "mix", text, lvl, src, var, profanity_set))

    return cases


def generate_pinyin_mix(profanity_set):
    """Category 5: 拼音谐音混杂 (~15 cases)"""
    cases = []

    pinyin_variants = [
        ("操你妈", "操 ni 马的", 4),
        ("我操", "wo 操这质量", 3),
        ("操你妈", "cao 你妈的垃圾", 4),
        ("他妈", "ta 马的破玩意", 3),
        ("你妈", "ni 妈的烦死了", 4),
        ("傻逼", "sha 逼一样的东西", 4),
        ("操你妈", "cao ni 妈的什么东西", 4),
        ("他妈", "真 ta 妈坑人", 3),
        ("你妈", "ni 妈的等了半个月", 4),
        ("操", "cao 这破东西", 3),
        ("操你妈", "caonimade 这质量", 4),
        ("他妈", "ta ma 的简直离谱", 3),
        ("你妈", "ni ma 的设计真烂", 4),
        ("傻逼", "sha bi CEO想出来的吧", 4),
        ("我操", "wo cao 怎么又坏了", 3),
    ]

    for i, (src, var, lvl) in enumerate(pinyin_variants):
        text = CN_TEMPLATES[(i + 2) % len(CN_TEMPLATES)].format(word=var)
        cases.append(_make_case("pinyin_mix", "pinyin", text, lvl, src, var, profanity_set))

    return cases


def generate_sarcasm(profanity_set):
    """Category 6: 讽刺语气 — 纯语义攻击，不含脏话词 (~15 cases)"""
    sarcasm_texts = [
        ("你们这物流可真快啊 从北京到上海走了整整15天 真不愧是极速达呢👍", 3,
         "讽刺物流慢"),
        ("售后太棒了 等了两个星期终于有人回我了 效率感人", 3,
         "讽刺售后慢"),
        ("退款速度绝了 比蜗牛还快 已经过去一个月了 赞一个", 3,
         "讽刺退款慢"),
        ("从来没有见过这么好用的app呢 打开就闪退 一天闪退十次 太稳定了", 3,
         "讽刺App闪退"),
        ("客服一定是博士毕业的 太专业了 一个问题都答不上来", 3,
         "讽刺客服不专业"),
        ("产品质量太好了 用了三天就开始掉漆 不愧是名牌", 3,
         "讽刺产品质量差"),
        ("你们的程序员真是天才 每次更新都能带来新的bug 太惊喜了", 3,
         "讽刺程序员"),
        ("包装真是精美 拆开发现屏幕碎了 完美 省得我自己砸", 3,
         "讽刺包装/产品质量"),
        ("这配送速度比走路还快 下单到收货只用了二十天 真是太感谢了", 3,
         "讽刺配送慢"),
        ("你们的会员服务太超值了 自动续费完全不用我同意 贴心", 3,
         "讽刺自动续费"),
        ("活动优惠力度真大 原价999 现价只要998 简直白送", 3,
         "讽刺优惠力度"),
        ("这个功能设计得太人性化了 要点五层菜单才能找到 锻炼用户耐心", 3,
         "讽刺功能设计"),
        ("你们的服务器稳定性真是业界标杆 每隔半小时就要重新登录一次", 3,
         "讽刺服务器不稳定"),
        ("这价格太实惠了 比隔壁贵了三倍 但服务只差了一点点", 3,
         "讽刺价格贵"),
        ("感谢你们让我学会了修手机 买回来就坏了全靠自己修", 3,
         "讽刺产品质量差需自修"),
    ]

    cases = []
    for text, lvl, desc in sarcasm_texts:
        cases.append(_make_case("sarcasm", desc, text, lvl, "", "", profanity_set))

    return cases


def generate_en_dfa_miss(profanity_set):
    """Category 7: 英文 DFA 未命中 — 词典未收录的英文/俚语脏话 (~15 cases)"""
    en_miss_words = [
        ("bloody", "bloody", 3, "英式俚语"),
        ("bollocks", "bollocks", 4, "英式俚语"),
        ("wank", "wank", 4, "英式俚语"),
        ("mug", "mug", 3, "英式俚语-蠢货"),
        ("sod", "sod", 3, "英式俚语"),
        ("dodgy", "dodgy", 3, "英式俚语-可疑的"),
        ("tosser", "tosser", 4, "英式俚语"),
        ("bugger", "bugger", 4, "英式俚语"),
        ("knackered", "knackered", 3, "英式俚语-累坏了"),
        ("wanker", "wanker", 4, "英式俚语"),
        ("prat", "prat", 3, "英式俚语-蠢货"),
        ("git", "git", 3, "英式俚语-讨厌鬼"),
        ("plonker", "plonker", 3, "英式俚语"),
        ("berk", "berk", 3, "英式俚语"),
        ("pillock", "pillock", 3, "英式俚语"),
    ]

    cases = []
    for i, (src, var, lvl, desc) in enumerate(en_miss_words):
        # 构造完整投诉句子
        templates = [
            f"this {var} app is absolutely terrible and keeps crashing",
            f"what a load of {var} your product is useless",
            f"your {var} company sent me a broken item and ignored my emails",
            f"this is such a {var} service I want my money back immediately",
            f"what {var} designed this website it makes no sense at all",
            f"your {var} delivery driver threw my package over the fence",
            f"this {var} product stopped working after exactly two days",
            f"I have never used such a {var} app in my entire life",
            f"your {var} support team hung up on me three times today",
            f"the {var} quality of this item is unbelievable for the price",
            f"this {var} subscription auto-renewed without my permission",
            f"what kind of {var} service is this I have been waiting for a month",
            f"your {var} checkout system charged me twice for the same order",
            f"this is the most {var} experience I have ever had shopping online",
            f"the {var} instructions that came with the product were impossible to follow",
        ]
        text = templates[i % len(templates)]
        cases.append(_make_case("en_dfa_miss", desc, text, lvl, src, var, profanity_set))

    return cases


def generate_normal_controls(profanity_set):
    """正常对照组 — 不含任何脏话的干净投诉 (~15 cases)"""
    normal_texts = [
        "订单编号ORDER20240523的包裹签收后发现外包装破损请协助处理谢谢",
        "请问这个商品什么时候能补货我想买但是显示缺货了",
        "我于昨天收到的手机屏幕有一条划痕请安排换货处理",
        "我已经提交退款申请三天了请问什么时候能审核通过",
        "上个月买的衣服洗了一次就缩水了能否退货",
        "快递显示已签收但我并没有收到包裹请帮忙核实",
        "这个充电器用了不到两个月就不能充电了还在保修期内吗",
        "我账号里的积分突然少了2000分请问是什么原因",
        "你们的会员权益里写了免运费为什么这次还是收了运费",
        "我在你们平台买到的商品和页面描述的完全不一样",
        "这个软件安装后电脑变得很卡能帮忙看一下吗",
        "昨天直播买的商品到现在还没发货请问什么时候能发",
        "我的优惠券在支付时显示过期了但是明明还没到日期",
        "更新app后之前的订单记录全部消失了请问怎么恢复",
        "我在门店买的和你们线上卖的是同一款吗价格差了好多",
    ]

    cases = []
    for i, text in enumerate(normal_texts):
        # 验证确实是干净的
        dfa_hit = dfa_would_hit(profanity_set, text)
        lvl = 1 if dfa_hit == False else 2
        cases.append({
            "category": "normal",
            "subtype": "clean_complaint",
            "input": text,
            "expected_level": lvl,
            "expected_dfa_hit": dfa_hit,
            "source_word": "",
            "variant": "",
        })

    return cases


# ──────────────────────────────────────────────
#  Main — generate & verify
# ──────────────────────────────────────────────

def main():
    print("加载脏话词典...")
    profanity_set = load_profanity_set(DICT_PATH)
    print(f"  已加载 {len(profanity_set)} 个脏话词")

    generators = [
        ("format_bypass", "格式绕过", generate_format_bypass),
        ("homophone", "中文谐音变体", generate_homophone),
        ("leet", "Leet替换", generate_leet),
        ("cnen_mix", "中英混杂", generate_cnen_mix),
        ("pinyin_mix", "拼音谐音混杂", generate_pinyin_mix),
        ("sarcasm", "讽刺语气", generate_sarcasm),
        ("en_dfa_miss", "英文DFA未命中", generate_en_dfa_miss),
        ("normal", "正常对照组", generate_normal_controls),
    ]

    all_cases = []
    by_category = {}
    case_id = 1

    for cat_key, cat_name, gen_func in generators:
        cases = gen_func(profanity_set)
        for c in cases:
            c["id"] = f"{cat_key}_{case_id:03d}"
            case_id += 1
        all_cases.extend(cases)
        by_category[cat_key] = len(cases)
        # 统计 DFA hit/miss
        dfa_hit_count = sum(1 for c in cases if c["expected_dfa_hit"])
        dfa_miss_count = len(cases) - dfa_hit_count
        print(f"  {cat_name}: {len(cases)} cases (DFA-hit={dfa_hit_count}, DFA-miss={dfa_miss_count})")

    total = len(all_cases)
    print(f"\n总计: {total} cases")

    # 确保 id 列在前面
    ordered_cases = []
    for c in all_cases:
        ordered = {
            "id": c["id"],
            "category": c["category"],
            "subtype": c["subtype"],
            "input": c["input"],
            "expected_level": c["expected_level"],
            "expected_dfa_hit": c["expected_dfa_hit"],
            "source_word": c["source_word"],
            "variant": c["variant"],
        }
        ordered_cases.append(ordered)

    output_full = {
        "total": total,
        "by_category": by_category,
        "cases": ordered_cases,
    }

    with open(OUTPUT_FULL, "w", encoding="utf-8") as f:
        json.dump(output_full, f, ensure_ascii=False, indent=2)
    print(f"\n全量输出: {OUTPUT_FULL}")

    # ── 回归子集：每类选 3 个 + 正常 2 个 ──
    regression = []
    reg_categories = ["format_bypass", "homophone", "leet", "cnen_mix",
                      "pinyin_mix", "sarcasm", "en_dfa_miss"]

    for cat in reg_categories:
        cat_cases = [c for c in ordered_cases if c["category"] == cat]
        # 选择: 前 2 个 DFA-miss + 1 个 DFA-hit（如有）
        dfa_miss = [c for c in cat_cases if not c["expected_dfa_hit"]][:2]
        dfa_hit = [c for c in cat_cases if c["expected_dfa_hit"]][:1]
        selected = dfa_miss + dfa_hit
        # 不足 3 个时从剩余补充
        if len(selected) < 3:
            remaining = [c for c in cat_cases if c not in selected]
            selected.extend(remaining[:3 - len(selected)])
        regression.extend(selected[:3])

    normal_cases = [c for c in ordered_cases if c["category"] == "normal"]
    regression.extend(normal_cases[:2])

    print(f"回归子集: {len(regression)} cases")
    with open(OUTPUT_REGRESSION, "w", encoding="utf-8") as f:
        json.dump(regression, f, ensure_ascii=False, indent=2)
    print(f"回归输出: {OUTPUT_REGRESSION}")


if __name__ == "__main__":
    main()
