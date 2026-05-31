import sys
import json
import re

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


CN_NUM = {'一': '1', '二': '2', '两': '2', '三': '3', '四': '4', '五': '5',
          '六': '6', '七': '7', '八': '8', '九': '9', '十': '10', '半': '0.5'}


def cn_to_digits(text):
    """将中文数字转为阿拉伯数字字符串用于比较。"""
    result = []
    for ch in text:
        if ch in CN_NUM:
            result.append(CN_NUM[ch])
        elif ch.isdigit():
            result.append(ch)
    return ''.join(result) if result else ''


def entity_key(entity):
    text = entity["text"]
    label = entity["label"]

    if label in ("订单号", "物流单号", "单号", "订单ID"):
        m = re.search(r'[A-Za-z0-9][A-Za-z0-9\-_]*$', text)
        return m.group() if m else text

    if label == "金额":
        return text

    if label in ("手机号", "座机号"):
        return text

    if label == "邮箱":
        return text

    if "日期" in label or "时间量" in label:
        nums = re.findall(r'\d+', text)
        if nums:
            return "".join(nums)
        return cn_to_digits(text) or text

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
        nums1 = re.findall(r'\d+', str(key1)) or [cn_to_digits(str(key1))]
        nums2 = re.findall(r'\d+', str(key2)) or [cn_to_digits(str(key2))]
        nums1 = [n for n in nums1 if n]
        nums2 = [n for n in nums2 if n]
        if nums1 and nums2:
            return nums1 == nums2
        return key1 == key2
    # 未知实体类型的通用回退方案
    # Generic fallback for unknown entity types
    if key1 in key2 or key2 in key1:
        return True
    nums1 = set(re.findall(r'\d+', str(key1)))
    nums2 = set(re.findall(r'\d+', str(key2)))
    return bool(nums1 & nums2)


def label_family(label):
    """将标签归入同一族，允许等价格式匹配（如 时间量-中文 ≈ 时间量-英文）。"""
    if "日期" in label:
        return "日期"
    if "时间量" in label:
        return "时间量"
    if "单号" in label or "订单" in label:
        return "订单号"
    return label


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
        oe_family = label_family(oe["label"])
        for se in sanitized_entities:
            if label_family(se["label"]) == oe_family:
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
        "lost_entities": [e["text"] for e in lost],
        "passed": not core_lost,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
