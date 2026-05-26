#!/usr/bin/env python3
"""
添加新脏话词汇到字典。保留原有顺序和内容，在末尾追加新词。
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(SCRIPT_DIR, "..")
REF_DIR = os.path.join(SKILL_DIR, "references")
DICT_PATH = os.path.join(REF_DIR, "profanity_dict.txt")


def load_existing(path):
    """加载现有词典，返回 (原始行列表, 标准化词集合)。"""
    words_set = set()
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            lines.append(raw)
            w = raw.strip().lower()
            if w and len(w) >= 2:
                words_set.add(w)
    return lines, words_set


def main():
    lines, existing = load_existing(DICT_PATH)
    print(f"现有词典: {len(existing)} 个词条, {len(lines)} 行")

    # 精选新增词条（基于分析结果）
    new_words = [
        # === 高 FN 覆盖 (COLD 遗漏中高频命中) ===
        "黑鬼",       # 种族蔑称，82 FN
        "直男癌",      # 性别侮辱，80 FN
        "喷子",       # 网络喷子，61 FN
        "鬼子",       # 蔑称，46 FN
        "渣男",       # 渣男，38 FN（含7FP但价值高）
        "地图炮",      # 地域攻击，35 FN
        "舔狗",       # 舔狗，28 FN
        "日本鬼子",     # 特定蔑称，15 FN
        "女权癌",      # 侮辱性标签，14 FN
        "娘炮",       # 性别侮辱，8 FN
        "穷逼",       # 穷人蔑称，8 FN
        "黑子",       # 网络黑子，8 FN
        "圣母婊",      # 伪善者，8 FN
        "矮子",       # 身体侮辱，7 FN
        "白皮猪",      # 种族蔑称，6 FN
        "走狗",       # 走狗，5 FN
        "杠精",       # 抬杠者，5 FN
        "辣鸡",       # 垃圾变体，5 FN (app差评18次)
        "汉奸",       # 汉奸，5 FN
        "渣女",       # 渣女，4 FN
        "洋鬼子",      # 蔑称，4 FN
        "乡巴佬",      # 乡下人蔑称，4 FN
        "傻叉",       # 傻X变体，4 FN
        "穷鬼",       # 穷鬼，4 FN
        "找骂",       # 找骂，3 FN
        "沙雕",       # 傻屌变体，3 FN
        "荡妇",       # 荡妇，3 FN
        "奴才",       # 奴才，3 FN
        "土鳖",       # 土鳖，3 FN

        # === 中等 FN 覆盖 ===
        "母狗",       # 侮辱性称呼，2 FN
        "狗屎",       # 狗屎，2 FN
        "狗腿子",      # 狗腿子，2 FN
        "下三滥",      # 下三滥，2 FN
        "直女癌",      # 直女癌，2 FN
        "假洋鬼子",     # 假洋鬼子，2 FN
        "穷光蛋",      # 穷光蛋，2 FN

        # === 低 FN 覆盖但明确侮辱 ===
        "泥煤",       # 你妹变体，1 FN
        "土包子",      # 土包子，1 FN
        "坑货",       # 坑货，1 FN
        "疯狗",       # 疯狗，1 FN
        "制杖",       # 智障谐音，1 FN
        "丫的",       # 北京方言蔑称，1 FN
        "双标狗",      # 双标狗，1 FN
        "找抽",       # 找抽，1 FN

        # === ToxiCN/App 差评覆盖（COLD 命中为0但其他数据集中有） ===
        "恶熏",       # 恶心变体（ToxiCN命中）
        "挠弹",       # 脑残变体（ToxiCN命中）
        "蠢猪",       # 蠢猪（通用辱骂）
        "蠢蛋",       # 蠢蛋（通用辱骂）
        "坑比",       # 坑B（客服场景常见）
        "太坑了",      # 太坑了（客服场景常见）
        "烂透了",      # 烂透了（客服场景常见）
        "你丫",       # 北京方言蔑称
        "尼玛币",      # 你妈逼变体
        "畜狌",       # 畜生变体
        "废物点心",     # 废物加强版
        "卖逼",       # 卖逼
        "滚犊子",      # 滚蛋方言
        "欠抽",       # 欠抽
        "欠扁",       # 欠扁

        # === 额外常见辱骂词 ===
        "傻狗",       # 傻狗
        "狗东西",      # 狗东西
        "狗杂种",      # 狗杂种
        "王八犊子",     # 王八蛋方言变体
        "死一边去",     # 死一边去
        "给脸不要脸",    # 给脸不要脸
        "去你大爷",     # 去你大爷
        "草拟吗",      # 草泥马变体
        "卧嘈",       # 卧槽变体
        "沙币",       # 傻逼变体
        "騷货",       # 骚货繁体变体
        "賤人",       # 贱人繁体变体
        "淦你",       # 干你变体（干涸的干谐音）
        "曰你",       # 日你变体
        "鈤你",       # 日你变体
        "差劲死",      # 差劲死了（客服场景）
        "恶心死",      # 恶心死了（客服场景）
        "坑死",       # 坑死了（客服场景）
        "坑爹的",      # 坑爹的（客服场景）
    ]

    # 去重
    deduped = []
    seen = set(existing)
    for w in new_words:
        w_lower = w.strip().lower()
        if w_lower not in seen and len(w_lower) >= 2:
            deduped.append(w)
            seen.add(w_lower)
        elif w_lower in existing:
            print(f"跳过已存在: {w}")

    print(f"新增词条: {len(deduped)}")

    # 追加到文件
    with open(DICT_PATH, "a", encoding="utf-8") as f:
        for w in deduped:
            f.write(f"\n{w}")

    print(f"已写入 {DICT_PATH}")
    print(f"新词典总数: {len(existing) + len(deduped)}")

    # 输出新增列表供参考
    print("\n新增词条列表:")
    for i, w in enumerate(deduped, 1):
        print(f"  {i}. {w}")


if __name__ == "__main__":
    main()
