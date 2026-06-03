import sys
import json
import re

CN_NUMERAL_MAP = {
    "零": 0, "〇": 0,
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}
EN_NUMERAL_MAP = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def parse_cn_number(token):
    """解析 1-99 范围内的常见中文数字。"""
    if not token:
        return None
    if token in CN_NUMERAL_MAP:
        return CN_NUMERAL_MAP[token]
    if "十" in token:
        left, _, right = token.partition("十")
        if left == "":
            tens = 1
        else:
            tens = CN_NUMERAL_MAP.get(left)
        ones = 0 if right == "" else CN_NUMERAL_MAP.get(right)
        if tens is None or ones is None:
            return None
        return tens * 10 + ones
    return None


def normalize_cn_number_words(text):
    """把常见中文数字时间/日期中的数字部分转为阿拉伯数字。"""
    pattern = re.compile(r"[零〇一二两三四五六七八九十]+(?=[天日周个月年号])")

    def repl(match):
        value = parse_cn_number(match.group(0))
        return str(value) if value is not None else match.group(0)

    return pattern.sub(repl, text)


def normalize_small_number_word(text):
    """把常见中英文小数字转为阿拉伯数字，用于时间量等价比较。"""
    lowered = text.lower()
    for word, value in EN_NUMERAL_MAP.items():
        lowered = re.sub(r"\b" + word + r"\b", str(value), lowered)
    return normalize_cn_number_words(lowered)


def number_values(text):
    """抽取数字值，允许 2999 与 2999.00 等价。"""
    normalized = normalize_small_number_word(str(text))
    values = []
    for raw in re.findall(r"\d+(?:\.\d+)?", normalized):
        value = float(raw)
        if value.is_integer():
            values.append(int(value))
        else:
            values.append(value)
    return values


ENTITY_PATTERNS = [
    (r"订单(?:[号编]|编号)\s*[：:]*\s*[A-Za-z0-9\-_]+", "订单号"),
    (r"[订货发快递物流][单号]\s*[：:]*\s*[A-Za-z0-9\-_]+", "物流单号"),
    (r"单号\s*[：:]*\s*[A-Za-z0-9\-_]+", "单号"),
    (r"ORDERID[_:：]\s*\d+", "订单ID"),
    (r"金额\s*[：:]*\s*[¥￥]?\s*\d+\.?\d*", "金额"),
    (r"[¥￥]\s*\d+\.?\d*", "金额"),
    (r"\d+\.?\d*\s*元", "金额"),
    (r"1[3-9]\d{9}", "手机号"),
    (r"\d{3,4}-\d{7,8}", "座机号"),
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "邮箱"),
    # 模式1：中文路名地址，不含行政区划前缀（如张江路666号、建国路88号）
    # Pattern 1: Road-name Chinese addresses without admin prefix (张江路666号, 建国路88号)
    (r"(?:[一-鿿]{2,5}(?:路|街|巷|大道|弄|胡同))[\d号栋单元室层楼座一-鿿]{0,10}[号栋单元室]", "地址"),
    # 模式2：英文/混合地址（如221B Baker Street、1600 Amphitheatre Parkway、London）
    # Pattern 2: English/mixed addresses (221B Baker Street, 1600 Amphitheatre Parkway, London)
    (r"\d+[A-Za-z]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Lane|Drive|Dr\.?|Parkway|Boulevard|Blvd\.?|Way|Court|Plaza|Square)(?:,?\s+[A-Z][a-z]+)?)", "地址"),
    (r"(?:[一-鿿]{1,4}(?:省|市|区|县|自治州))[^，。\t\n的]{2,20}(?:[路街巷大道村组号楼]|栋|单元|室)", "地址"),
    (r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?", "日期"),
    (r"\d{1,2}月\d{1,2}[日号]", "日期短格式"),
    (r"\d+[天日周个月年]", "时间量"),
    # 中文数字时间
    # Chinese numeric time expressions
    (r"[一二三四五六七八九十两几半]+[天日周个月年][左右前内]?", "时间量-中文"),
    (r"[一二三四五六七八九十]+月[一二三四五六七八九十]+[日号]?", "日期-中文"),
    # 英文数字时间
    # English numeric time expressions
    (r"\b(?:a\s+few|several|a\s+couple\s+of|one|two|three|four|five|six|seven|eight|nine|ten|half\s+a)\s+(?:day|days|week|weeks|month|months|year|years)\b", "时间量-英文"),
    # 英文阿拉伯数字+时间单位 (2 weeks, 15 days, 6 months)
    (r"\b\d+\s+(?:days?|weeks?|months?|years?|hours?|minutes?)\b", "时间量-英文"),
    (r"(?<![a-zA-Z])(?!(?:known|ai|debugging|gathering|support|sending|linear|hard|user)-)(?:[A-Za-z0-9]*[A-Za-z][A-Za-z0-9]*[-_][A-Za-z0-9]*[0-9][A-Za-z0-9]*|[A-Za-z0-9]*[0-9][A-Za-z0-9]*[-_][A-Za-z0-9]*[A-Za-z][A-Za-z0-9]*)", "产品型号"),
]

CORE_TAGS = {
    "订单号", "物流单号", "单号", "订单ID", "金额",
    "手机号", "座机号", "邮箱", "地址",
    "日期", "日期短格式", "时间量", "产品型号",
    "日期-中文", "时间量-中文", "时间量-英文",
}


def extract_entities(text):
    entities = []
    for pattern, label in ENTITY_PATTERNS:
        for m in re.finditer(pattern, text):
            entities.append({"text": m.group(), "label": label})
    return entities


def entity_key(entity):
    text = entity["text"]
    label = entity["label"]

    if label in ("订单号", "物流单号", "单号", "订单ID"):
        m = re.search(r'[A-Za-z0-9][A-Za-z0-9\-_]*$', text)
        return m.group() if m else text

    if label == "金额":
        nums = number_values(text)
        return nums if nums else text

    if label in ("手机号", "座机号"):
        return text

    if label == "邮箱":
        return text

    if "日期" in label or "时间量" in label:
        nums = number_values(text)
        return nums if nums else text

    if label == "地址":
        return text

    return text


def keys_match(key1, key2, label=None):
    if not key1 or not key2:
        return False
    if key1 == key2:
        return True
    if label == "地址":
        return False
    # 精确匹配标识符：任何变化都视为失败
    # Exact-match identifiers: any mutation = failure
    if label in ("手机号", "座机号", "邮箱", "产品型号"):
        return False
    # 订单号：精确字符串匹配（字母有意义——ABCD20240523 ≠ WXYZ20240523）
    # Order IDs: exact string match (letters matter — ABCD20240523 ≠ WXYZ20240523)
    if label in ("订单号", "物流单号", "单号", "订单ID"):
        return key1 == key2
    # 数字实体：精确比较数字序列，不允许子集匹配
    # Numeric entities: compare digit sequences exactly, no subset matching
    if label in ("金额", "日期", "日期短格式", "时间量", "日期-中文", "时间量-中文", "时间量-英文") or "日期" in (label or "") or "时间量" in (label or ""):
        nums1 = number_values(key1)
        nums2 = number_values(key2)
        if nums1 or nums2:
            return nums1 == nums2
        return key1 == key2
    # 未知实体类型的通用回退方案
    # Generic fallback for unknown entity types
    if key1 in key2 or key2 in key1:
        return True
    nums1 = set(re.findall(r'\d+', str(key1)))
    nums2 = set(re.findall(r'\d+', str(key2)))
    return bool(nums1 & nums2)


def labels_compatible(label1, label2):
    """判断实体标签是否可比较；数字/日期格式转换后标签可能变化。"""
    if label1 == label2:
        return True
    if label1 == "金额" and label2 == "金额":
        return True
    if ("时间量" in label1 or "日期" in label1) and ("时间量" in label2 or "日期" in label2):
        return True
    return False


def main():
    data = json.load(sys.stdin)
    original = data["original"]
    sanitized = data["sanitized"]

    orig_entities = extract_entities(original)
    sanitized_entities = extract_entities(sanitized)

    lost = []
    for oe in orig_entities:
        okey = entity_key(oe)
        found = False
        for se in sanitized_entities:
            if labels_compatible(oe["label"], se["label"]):
                skey = entity_key(se)
                if keys_match(okey, skey, oe["label"]):
                    found = True
                    break
        if not found:
            lost.append(oe)

    core_lost = any(e["label"] in CORE_TAGS for e in lost)

    result = {
        "original_entity_count": len(orig_entities),
        "sanitized_entity_count": len(sanitized_entities),
        "preserved_count": len(orig_entities) - len(lost),
        "lost_count": len(lost),
        "lost_entities": [{"type": e["label"], "value": e["text"]} for e in lost],
        "passed": not core_lost,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
