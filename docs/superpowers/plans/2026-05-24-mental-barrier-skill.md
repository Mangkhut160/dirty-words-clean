# 「精神内耗终结者」SKILL 实施计划（修订版）

> **面向执行代理：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 来逐任务实施本计划。步骤使用复选框（`- [ ]`）语法追踪进度。
>
> **修订说明：** 基于 2026-05-24 架构审查反馈优化。核心变更：移除 pypinyin 依赖（改为纯 DFA+LLM 双层管线）、零外部依赖安装、输出格式全面自然语言化、增强实体保留策略。

**目标：** 构建一个 Claude Code SKILL，将客户投诉文本中的情绪化内容过滤为冷静客观的自然语言表达，输出完整的情绪分析报告和净化后的文本。

**架构：** 双层管线。第1层：DFA 精确匹配中文(1660词)+英文(794词)脏话字典，输出命中位置和自然语言摘要供 LLM 参考。第2层：Claude 按 SKILL.md 指令执行情绪检测 + 谐音变体识别(借助 homophone_guide.md) + 讽刺转化 + 实体保留——全部在单次 `/tonebarrier` 调用内完成。零外部依赖，零 pip 安装。

**技术栈：** Python 3 标准库（仅 json、sys、os、re、subprocess）。无需 pypinyin 或任何第三方包。

---

## 文件结构

```
.claude/skills/tonebarrier/
├── SKILL.md                     # 创建：主技能文件（YAML + Markdown 指令）
├── scripts/
│   ├── dfa_filter.py            # 创建：DFA 精确匹配（无外部依赖）
│   └── validator.py             # 创建：后处理验证（实体留存检查）
├── references/
│   ├── profanity_dict.txt       # 复制自 datasets/：1660 中文脏话词
│   ├── profanity_en.txt         # 复制自 datasets/：794 英文脏话词
│   └── homophone_guide.md       # 创建：谐音变体参考（LLM主要知识源）
├── tests/
│   ├── test_cases.json          # 创建：19 条测试用例（覆盖全部场景+4边界）
│   └── test_pipeline.py         # 创建：自动化测试运行器
└── README.md                    # 创建：安装与使用文档
```

**数据依赖**（已在 `datasets/` 目录中就绪）：
- `datasets/chinese_profanity_dict_final.txt` — 1660 中文脏话词
- `datasets/profanity_datasets_offensive_speach/processed_bad_words.csv` — 794 英文脏话词

---

### 任务 1：项目脚手架与字典部署

**涉及文件：**
- 创建：`.claude/skills/tonebarrier/references/profanity_dict.txt`
- 创建：`.claude/skills/tonebarrier/references/profanity_en.txt`

- [ ] **步骤 1：创建目录结构**

```bash
mkdir -p .claude/skills/tonebarrier/{scripts,references,tests}
```

- [ ] **步骤 2：复制中文脏话字典**

```bash
cp datasets/chinese_profanity_dict_final.txt .claude/skills/tonebarrier/references/profanity_dict.txt
wc -l .claude/skills/tonebarrier/references/profanity_dict.txt
# 预期输出：1660 .claude/skills/tonebarrier/references/profanity_dict.txt
```

- [ ] **步骤 3：提取并复制英文脏话字典**

```bash
python3 -c "
import csv
words = set()
with open('datasets/profanity_datasets_offensive_speach/processed_bad_words.csv') as f:
    for row in csv.DictReader(f):
        if row.get('language') == 'en':
            words.add(row['text'])
with open('.claude/skills/tonebarrier/references/profanity_en.txt', 'w') as f:
    for w in sorted(words):
        f.write(w + '\n')
print(f'已提取 {len(words)} 个英文脏话词')
"
# 预期输出：已提取 794 个英文脏话词
```

- [ ] **步骤 4：验证字典文件就位**

```bash
ls -la .claude/skills/tonebarrier/references/
# 预期：profanity_dict.txt、profanity_en.txt 两个文件
```

- [ ] **步骤 5：提交**

```bash
git add .claude/skills/tonebarrier/references/
git commit -m "feat: 添加中英文脏话字典（1660中文+794英文）"
```

---

### 任务 2：DFA 精确匹配过滤器

**涉及文件：**
- 创建：`.claude/skills/tonebarrier/scripts/dfa_filter.py`

**变更说明：** 替代旧版 pre_filter.py。移除 pypinyin 依赖，只保留 DFA 精确匹配。输出增加自然语言摘要字段，供 LLM 直接阅读。

- [ ] **步骤 1：编写 dfa_filter.py**

```python
#!/usr/bin/env python3
"""
DFA 精确匹配过滤器 — 第1层。
从 stdin 读取输入文本，输出 JSON 格式的脏话检测结果。
包含自然语言摘要字段，供 LLM 直接参考。
纯 Python 标准库实现，零外部依赖。
"""
import sys
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REF_DIR = os.path.join(SCRIPT_DIR, "..", "references")


def load_trie(path):
    """将脏话词加载为 DFA 字典树（Trie）。"""
    root = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            word = line.strip().lower()
            if not word:
                continue
            node = root
            for ch in word:
                if ch not in node:
                    node[ch] = {}
                node = node[ch]
            node["__END__"] = word
    return root


def dfa_search(root, text):
    """单次遍历 DFA 字典树，返回 [{word, start, end}]。"""
    text_lower = text.lower()
    matches = []
    i = 0
    while i < len(text_lower):
        node = root
        j = i
        found = None
        while j < len(text_lower) and text_lower[j] in node:
            node = node[text_lower[j]]
            j += 1
            if "__END__" in node:
                found = {"word": node["__END__"], "start": i, "end": j}
        if found:
            matches.append(found)
            i = found["end"]  # 跳过已匹配部分，不重复检测
        else:
            i += 1
    return matches


def main():
    text = sys.stdin.read().strip()
    if not text:
        output = {
            "error": "输入文本为空",
            "total_matches": 0,
            "matches": [],
            "summary": "输入文本为空，无需过滤。",
            "has_profanity": False,
        }
        print(json.dumps(output, ensure_ascii=False))
        return

    dfa_cn = load_trie(os.path.join(REF_DIR, "profanity_dict.txt"))
    dfa_en = load_trie(os.path.join(REF_DIR, "profanity_en.txt"))

    cn_matches = dfa_search(dfa_cn, text)
    en_matches = dfa_search(dfa_en, text)

    # 合并去重（按位置）
    all_matches = []
    seen_positions = set()
    for m in cn_matches + en_matches:
        pos_key = (m["start"], m["end"])
        if pos_key not in seen_positions:
            seen_positions.add(pos_key)
            source = "中文" if m in cn_matches else "英文"
            all_matches.append({
                "type": "dfa_cn" if source == "中文" else "dfa_en",
                "word": m["word"],
                "start": m["start"],
                "end": m["end"],
            })
    all_matches.sort(key=lambda x: x["start"])

    # 生成自然语言摘要（LLM 直接阅读，融入最终输出）
    if all_matches:
        unique_words = list(dict.fromkeys(m["word"] for m in all_matches))
        word_preview = "、".join(unique_words[:8])
        if len(unique_words) > 8:
            word_preview += f" 等 {len(unique_words)} 个"
        summary = (
            f"DFA 精确匹配检测到 {len(all_matches)} 处命中，"
            f"涉及 {len(unique_words)} 个不同词条：{word_preview}。"
        )
    else:
        summary = "DFA 精确匹配未检出已知脏话词条，文本中无直接脏话命中。"

    output = {
        "original_length": len(text),
        "total_matches": len(all_matches),
        "has_profanity": len(all_matches) > 0,
        "matches": all_matches,
        "summary": summary,
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **步骤 2：测试脏话检测**

```bash
echo "你们tmd煞笔一样的设计草泥马的赶紧退款" | python3 .claude/skills/tonebarrier/scripts/dfa_filter.py | python3 -m json.tool
```

预期输出必须包含：
```json
{
    "total_matches": 3,
    "has_profanity": true,
    "matches": [
        {"type": "dfa_en", "word": "tmd", "start": 2, "end": 5},
        {"type": "dfa_cn", "word": "煞笔", "start": 5, "end": 7},
        {"type": "dfa_cn", "word": "草泥马", "start": 9, "end": 12}
    ],
    "summary": "DFA 精确匹配检测到 3 处命中，涉及 3 个不同词条：tmd、煞笔、草泥马。"
}
```

- [ ] **步骤 3：测试正常文本（确保无误报）**

```bash
echo "订单号ORDER20240523的包裹外包装破损请协助处理" | python3 .claude/skills/tonebarrier/scripts/dfa_filter.py
# 预期：{"total_matches": 0, "has_profanity": false, ...}
```

- [ ] **步骤 4：测试空输入（错误处理）**

```bash
echo "" | python3 .claude/skills/tonebarrier/scripts/dfa_filter.py
# 预期：输出包含 "error": "输入文本为空"
```

- [ ] **步骤 5：提交**

```bash
git add .claude/skills/tonebarrier/scripts/dfa_filter.py
git commit -m "feat: 添加 DFA 精确匹配过滤器，零外部依赖"
```

---

### 任务 3：验证脚本（关键信息留存检查）

**涉及文件：**
- 创建：`.claude/skills/tonebarrier/scripts/validator.py`

**变更说明：** 相比初版，增加了 `订单编号`、`单号`、`物流单号`、`邮箱` 等常见实体的正则模式，覆盖更全的客服场景。

- [ ] **步骤 1：编写 validator.py**

```python
#!/usr/bin/env python3
"""
后处理验证器：检查关键业务信息在过滤后是否仍然保留。
从 stdin 读取 JSON：{"original": "...", "sanitized": "..."}
输出 JSON 格式的验证结果。
"""
import sys
import json
import re

# 需要保留的关键实体模式（覆盖客服场景常见格式）
ENTITY_PATTERNS = [
    # 订单/单号相关
    (r"订单[号编]\s*[：:]*\s*[A-Za-z0-9\-_]+", "订单号"),
    (r"[订货发快递物流][单号]\s*[：:]*\s*[A-Za-z0-9\-_]+", "物流单号"),
    (r"单号\s*[：:]*\s*[A-Za-z0-9\-_]+", "单号"),
    (r"ORDERID[_:：]\s*\d+", "订单ID"),
    # 金额
    (r"金额\s*[：:]*\s*[¥￥]?\s*\d+\.?\d*", "金额"),
    (r"[¥￥]\s*\d+\.?\d*", "金额"),
    (r"\d+\.?\d*\s*元", "金额"),
    # 联系方式
    (r"1[3-9]\d{9}", "手机号"),
    (r"\d{3,4}-\d{7,8}", "座机号"),
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "邮箱"),
    # 地址
    (r"[省市区自治州][^，。\t\n]{2,}(?:[路街巷大道村组号楼]|栋|单元|室)", "地址"),
    # 时间
    (r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?", "日期"),
    (r"\d{1,2}月\d{1,2}[日号]", "日期短格式"),
    (r"\d+[天日周个月年]", "时间量"),
    # 产品/型号（中文+数字+英文混合）
    (r"[A-Za-z0-9]+[-_][A-Za-z0-9]+", "产品型号"),
]


def extract_entities(text):
    """从文本中提取所有关键实体。"""
    found = []
    for pattern, label in ENTITY_PATTERNS:
        for match in re.finditer(pattern, text):
            found.append({
                "label": label,
                "value": match.group(),
                "start": match.start(),
                "end": match.end()
            })
    return found


def main():
    data = json.loads(sys.stdin.read())
    original = data.get("original", "")
    sanitized = data.get("sanitized", "")

    original_entities = extract_entities(original)
    sanitized_entities = extract_entities(sanitized)

    # 检查哪些实体被保留、哪些丢失
    preserved = []
    lost = []
    for ent in original_entities:
        matched = False
        for se in sanitized_entities:
            if se["label"] == ent["label"]:
                orig_nums = re.findall(r"\d+", ent["value"])
                sani_nums = re.findall(r"\d+", se["value"])
                if orig_nums and sani_nums and any(n in sani_nums for n in orig_nums):
                    matched = True
                    break
        if matched:
            preserved.append(ent)
        else:
            lost.append(ent)

    # 核心业务信息（订单号、金额）丢失 → 判定失败
    core_labels = {"订单号", "物流单号", "单号", "订单ID", "金额"}
    core_lost = [e for e in lost if e["label"] in core_labels]

    result = {
        "original_entity_count": len(original_entities),
        "sanitized_entity_count": len(sanitized_entities),
        "preserved_count": len(preserved),
        "lost_count": len(lost),
        "lost_entities": lost,
        "passed": len(core_lost) == 0,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **步骤 2：测试实体保留**

```bash
echo '{"original":"订单编号ORDER12345的破包裹还没到老子要退款！","sanitized":"订单编号ORDER12345的包裹尚未送达，客户要求退款。"}' | python3 .claude/skills/tonebarrier/scripts/validator.py
# 预期：{"passed": true, "lost_count": 0, ...}
```

- [ ] **步骤 3：测试实体丢失检测**

```bash
echo '{"original":"订单号ORDER12345的破包裹还没到金额2999元","sanitized":"包裹还没到"}' | python3 .claude/skills/tonebarrier/scripts/validator.py
# 预期：{"passed": false, "lost_count": >= 2, ...}
```

- [ ] **步骤 4：提交**

```bash
git add .claude/skills/tonebarrier/scripts/validator.py
git commit -m "feat: 添加验证脚本，增强实体模式覆盖（订单编号/单号/物流单号/邮箱）"
```

---

### 任务 4：测试用例

**涉及文件：**
- 创建：`.claude/skills/tonebarrier/tests/test_cases.json`

**变更说明：** 从 15 条增至 19 条。新增 4 条边界用例：正常拼音误报防护、长文本性能、纯数字订单号、空文本。

- [ ] **步骤 1：编写 test_cases.json**

```json
[
  {
    "id": "zh_profanity_01",
    "category": "中文脏话+英文缩写",
    "input": "你们tmd这个破产品草泥马的用了三天就坏了赶紧给老子退款",
    "expected_level": 4,
    "expected_dfa_matches": ["tmd", "草泥马"],
    "expected_sanitized_contains": ["退款", "三天"],
    "expected_sanitized_not_contains": ["破产品", "老子"]
  },
  {
    "id": "zh_profanity_02",
    "category": "中文谐音脏话",
    "input": "真是煞笔一样的设计沙比产品经理脑子进水了吧",
    "expected_level": 4,
    "expected_dfa_matches": ["煞笔", "沙比"],
    "expected_sanitized_contains": ["设计", "产品"],
    "expected_sanitized_not_contains": ["煞笔", "沙比", "脑子进水"]
  },
  {
    "id": "zh_sarcastic_01",
    "category": "中文讽刺",
    "input": "你们这物流可真快啊从北京到上海走了整整15天真不愧是极速达呢👍",
    "expected_level": 3,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["北京", "上海", "15天"],
    "expected_sanitized_not_contains": ["真快啊", "极速达"]
  },
  {
    "id": "zh_threat_01",
    "category": "中文威胁型",
    "input": "不给我退款我就去12315投诉你们让全网曝光你们的破服务",
    "expected_level": 3,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["退款", "12315"],
    "expected_sanitized_not_contains": ["破服务"]
  },
  {
    "id": "zh_critical_info_01",
    "category": "关键信息保留",
    "input": "订单编号ORDER20240523金额2999元的手机tm用了两天就死机必须退款",
    "expected_level": 4,
    "expected_dfa_matches": ["tm"],
    "expected_sanitized_contains": ["ORDER20240523", "2999", "退款"],
    "expected_sanitized_not_contains": ["tm"]
  },
  {
    "id": "en_profanity_01",
    "category": "英文脏话",
    "input": "This app is absolute garbage wasted my fucking money fix this shit or give me a refund",
    "expected_level": 4,
    "expected_dfa_matches": ["fucking", "shit", "garbage"],
    "expected_sanitized_contains": ["refund", "app"],
    "expected_sanitized_not_contains": ["fucking", "shit", "garbage"]
  },
  {
    "id": "en_sarcastic_01",
    "category": "英文讽刺",
    "input": "Great customer service waited 2 weeks for a reply really impressed",
    "expected_level": 3,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["2 weeks", "reply"],
    "expected_sanitized_not_contains": ["great", "impressed"]
  },
  {
    "id": "zh_normal_01",
    "category": "正常投诉-应透传",
    "input": "订单编号ORDER20240523的包裹签收后发现外包装破损请协助处理谢谢",
    "expected_level": 1,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["ORDER20240523", "破损"],
    "expected_sanitized_not_contains": []
  },
  {
    "id": "zh_normal_02",
    "category": "中性反馈-应透传",
    "input": "请问这个商品什么时候能补货我想买但是显示缺货了",
    "expected_level": 1,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["补货", "缺货"],
    "expected_sanitized_not_contains": []
  },
  {
    "id": "zh_leet_01",
    "category": "数字/符号绕过",
    "input": "你sh1t一样的产品经理设计的什么2b功能",
    "expected_level": 4,
    "expected_dfa_matches": ["sh1t", "2b"],
    "expected_sanitized_contains": ["产品", "功能"],
    "expected_sanitized_not_contains": ["sh1t", "2b"]
  },
  {
    "id": "zh_space_bypass_01",
    "category": "空格分隔绕过",
    "input": "你们这服务真t m d差劲等了三天了还没回复",
    "expected_level": 3,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["三天", "服务"],
    "expected_sanitized_not_contains": ["t m d"]
  },
  {
    "id": "zh_mixed_info_01",
    "category": "含地址和电话的脏话",
    "input": "送到上海市浦东新区张江路666号的包裹cnm的摔烂了打我电话13812345678来解决问题",
    "expected_level": 4,
    "expected_dfa_matches": ["cnm"],
    "expected_sanitized_contains": ["浦东新区", "张江路", "13812345678"],
    "expected_sanitized_not_contains": ["cnm"]
  },
  {
    "id": "zh_emoji_01",
    "category": "表情宣泄",
    "input": "你们这破app更新后直接闪退真的无语死了🤬🤬🤬",
    "expected_level": 3,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["闪退", "更新"],
    "expected_sanitized_not_contains": ["无语死了"]
  },
  {
    "id": "en_normal_01",
    "category": "英文正常投诉-应透传",
    "input": "Order ORDER20240523 arrived with damaged packaging please help",
    "expected_level": 1,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["ORDER20240523", "damaged"],
    "expected_sanitized_not_contains": []
  },
  {
    "id": "zh_multiple_01",
    "category": "多问题混合",
    "input": "你们发错货了我拍的是黑色的寄来个白的还有充电器也是坏的赶紧给我换",
    "expected_level": 3,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["黑色", "白色", "换"],
    "expected_sanitized_not_contains": []
  },
  {
    "id": "zh_boundary_pinyin_01",
    "category": "边界-正常拼音不应误报",
    "input": "请问这个设备要到哪里去维修设备编号是SHEBEI2024",
    "expected_level": 1,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["设备", "SHEBEI2024"],
    "expected_sanitized_not_contains": []
  },
  {
    "id": "zh_boundary_longtext_01",
    "category": "边界-长文本性能",
    "input": "我于2024年3月15日在贵平台下单购买了商品编号为IPHONE16PRO的手机一部订单号ORDER20240315001金额为人民币8999元。收到后发现手机屏幕有一条明显的划痕且电池续航严重不足与宣传严重不符。我已经联系客服三次每次都说会处理但至今没有回复。我要求要么全额退款要么换一部全新未拆封的机器。如果贵公司仍然不处理我将向12315投诉并在各大社交平台曝光你们的恶劣行为。请你们重视这个问题尽快给我一个明确的答复。我的联系电话是13812345678地址是北京市朝阳区建国路88号。",
    "expected_level": 3,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["13812345678", "8999", "北京市"],
    "expected_sanitized_not_contains": []
  },
  {
    "id": "zh_boundary_number_order_01",
    "category": "边界-纯数字订单号",
    "input": "单号20240523001的包裹你们发错地方了给我查一下物流",
    "expected_level": 1,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": ["20240523001"],
    "expected_sanitized_not_contains": []
  },
  {
    "id": "zh_boundary_empty_01",
    "category": "边界-空文本",
    "input": "",
    "expected_level": 1,
    "expected_dfa_matches": [],
    "expected_sanitized_contains": [],
    "expected_sanitized_not_contains": []
  }
]
```

- [ ] **步骤 2：验证 JSON 合法性**

```bash
python3 -c "import json; cases = json.load(open('.claude/skills/tonebarrier/tests/test_cases.json')); print(f'JSON 合法，共 {len(cases)} 条测试用例')"
```

- [ ] **步骤 3：提交**

```bash
git add .claude/skills/tonebarrier/tests/test_cases.json
git commit -m "test: 添加19条精选测试用例，含4条边界用例（长文本/纯数字订单/正常拼音/空文本）"
```

---

### 任务 5：自动化测试运行器

**涉及文件：**
- 创建：`.claude/skills/tonebarrier/tests/test_pipeline.py`

**变更说明：** 适配 dfa_filter.py 的新输出格式（增加 `expected_dfa_matches` 检查 + `summary` 字段验证）。

- [ ] **步骤 1：编写 test_pipeline.py**

```python
#!/usr/bin/env python3
"""对所有测试用例运行 DFA 过滤管道，报告准确率。"""
import json
import subprocess
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(SCRIPT_DIR, "..")
DFA_FILTER = os.path.join(SKILL_DIR, "scripts", "dfa_filter.py")


def run_dfa(text):
    """执行 DFA 过滤脚本，返回 JSON 结果。"""
    result = subprocess.run(
        ["python3", DFA_FILTER],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=10,
    )
    return json.loads(result.stdout.decode("utf-8"))


def main():
    with open(os.path.join(SCRIPT_DIR, "test_cases.json")) as f:
        cases = json.load(f)

    passed = 0
    failed = 0
    results = []

    print(f"共 {len(cases)} 条测试用例\n")
    print("=" * 60)

    for case in cases:
        try:
            output = run_dfa(case["input"])
            errors = []

            # 检查 DFA 匹配结果
            dfa_words = [m["word"] for m in output.get("matches", [])]
            expected_dfa = case.get("expected_dfa_matches", [])
            for word in expected_dfa:
                if word not in dfa_words:
                    errors.append(f"DFA 应检出 '{word}' 但未命中")

            # 检查 DFA summary 字段是否存在（自然语言摘要）
            summary = output.get("summary", "")
            if not summary:
                errors.append("缺少自然语言摘要字段 'summary'")

            # 检查 has_profanity 标记
            has_profanity = output.get("has_profanity", False)
            if len(expected_dfa) > 0 and not has_profanity:
                errors.append("has_profanity 应为 true 但为 false")
            if len(expected_dfa) == 0 and has_profanity and len(output.get("matches", [])) > 0:
                errors.append(f"不应检出脏话但检出 {len(output.get('matches', []))} 个")

            # 对于非边界用例，检查 sanitized_contains/not_contains
            # （注意：DFA 不做语义过滤，此处只检查 DFA 层能处理的部分）
            status = "通过" if not errors else "失败"
            if status == "通过":
                passed += 1

            results.append({
                "id": case["id"],
                "category": case["category"],
                "status": status,
                "errors": errors,
                "dfa_matches": dfa_words,
                "expected_level": case["expected_level"],
            })

            print(f"  {status}: {case['id']} ({case['category']})")
            for e in errors:
                print(f"    → {e}")
            if dfa_words:
                print(f"    DFA命中: {', '.join(dfa_words)}")
            print(f"    Summary: {summary[:60]}...")

        except Exception as e:
            failed += 1
            print(f"  错误: {case['id']} — {e}")

    total = len(cases)
    score = passed / total * 100 if total > 0 else 0
    print(f"\n{'=' * 60}")
    print(f"DFA 过滤测试结果: {passed}/{total} 通过 ({score:.0f}%)")
    print(f"注意: 语义过滤(情绪剥离/讽刺转化)由 LLM 层完成，不在本测试覆盖范围内。")
    print(f"{'=' * 60}")

    return 0 if score >= 80 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **步骤 2：运行测试套件**

```bash
python3 .claude/skills/tonebarrier/tests/test_pipeline.py
# 预期：>= 80% 通过率（至少 16/19）
```

- [ ] **步骤 3：提交**

```bash
git add .claude/skills/tonebarrier/tests/test_pipeline.py
git commit -m "test: 添加DFA过滤自动化测试运行器，含19条用例"
```

---

### 任务 6：谐音变体参考指南

**涉及文件：**
- 创建：`.claude/skills/tonebarrier/references/homophone_guide.md`

**变更说明：** 从 pypinyin 辅助参考升级为 LLM 的主要知识源。LLM 在处理谐音变体时直接查阅本参考，不再依赖机械匹配。

- [ ] **步骤 1：编写 homophone_guide.md**

```markdown
# 中文谐音变体脏话对照表

> **用途：** 这是 LLM 层的知识参考库。在处理客户投诉文本时，
> Claude 优先查阅本表来识别谐音/变形脏话，确保不漏掉任何变体。
>
> **与 DFA 的关系：** DFA 层处理精确匹配（傻逼、tmd、fuck），
> 本表帮助 LLM 处理 DFA 无法覆盖的模糊变体（煞笔、sh1t、t m d）。

## 核心谐音变体

| 原始词 | 常见变体形式 | 变体类型 |
|-------|------------|---------|
| 操你妈 | 草泥马 / 草拟吗 / 艹泥马 / 草你妈 / 操尼玛 | 同音字替换 |
| 傻逼 | 煞笔 / 沙比 / 撒比 / 傻b / 傻B / 傻比 | 同音字+拼音混合 |
| 我操 | 卧槽 / 我草 / 窝草 / 我艹 / 我去（弱化） | 同音字替换 |
| 你妈 | 尼玛 / 你玛 / 尼馬 / 你母 | 同音字替换 |
| 他妈 | 特么 / 特麼 / 他媽 / 踏马 / 塔玛 | 同音字替换 |
| 二逼 | 2b / 2B / 二b / 二B | 数字+字母替换 |
| 鸡巴 | jb / JB / j8 / J8 / 几把 / 鸡8 | 拼音缩写+数字替换 |

## 拼音缩写变体

| 缩写 | 实际含义 | 缩写 | 实际含义 |
|-----|---------|-----|---------|
| tmd / TMD | 他妈的 | nmd / NMD | 你妈的 |
| cnm / CNM | 操你妈 | sb / SB | 傻逼 |
| mlgb / MLGB | 妈了个逼 | nmsl / NMSL | 你妈死了 |
| wcnm / WCNM | 我操你妈 | tm / TM | 他妈 |
| wc / WC | 我操（弱化） | md / MD | 妈的 |

## 符号/数字绕过

| 绕过形式 | 原始词 | 说明 |
|---------|-------|------|
| sh1t / 5h1t | shit | 字母→数字替换 |
| f\*ck / f\*\*k | fuck | 星号替换元音 |
| a55 / @ss | ass | 字母→数字/符号替换 |
| b1tch / b!tch | bitch | 数字/符号替换 |
| d1ck / d!ck | dick | 数字/符号替换 |

## 空格/符号分隔

任何用空格、下划线、星号、点号分隔的脏话均应合并后判断：
- "t m d" → "tmd" → "他妈的"
- "傻 逼" → "傻逼"
- "f u c k" → "fuck"
- "f_u_c_k" → "fuck"
- "s.b." → "sb" → "傻逼"

## LLM 处理优先级

1. **DFA 精确匹配**（dfa_filter.py）→ 最高优先级，直接命中
2. **谐音变体识别**（本表）→ LLM 查表确认模糊变体
3. **语义推断**（LLM 上下文理解）→ 兜底，结合语境判断
   - 注意区分：调侃 vs 辱骂、正常表达 vs 谐音脏话
   - 例如 "我去取快递" → 正常，"我去你大爷" → 情绪化
```

- [ ] **步骤 2：提交**

```bash
git add .claude/skills/tonebarrier/references/homophone_guide.md
git commit -m "docs: 添加谐音变体参考指南，作为LLM层知识源"
```

---

### 任务 7：SKILL.md — 主技能文件

**涉及文件：**
- 创建：`.claude/skills/tonebarrier/SKILL.md`

**变更说明：** 移除 pypinyin 相关指令；管道简化为 DFA → LLM 双层；增加 dfa_filter.py 异常降级处理；输出格式全面自然语言化；DFA 的 summary 字段融入最终输出。

- [ ] **步骤 1：编写 SKILL.md**

```markdown
---
name: tonebarrier
description: >
  客户情绪降级与文本脱水。将充满辱骂、讽刺、情绪宣泄的客服投诉文本
  转化为冷静客观的自然语言表达。支持中文（含谐音字、拼音缩写、数字
  替换等变体）和英文。当用户输入或粘贴客户投诉文本、情绪化内容需要
  过滤时使用。
argument-hint: "[客户投诉文本]"
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash, Read
---

# 精神内耗终结者 — 情绪过滤引擎

## 你的身份

你的唯一任务：**将带有强烈负面情绪的客户投诉文本，转化为冷静、客观的自然语言表达，同时保留所有关键业务信息。**

你不是客服机器人 — 不回复客户。
你不是分类器 — 不判断这是退款还是换货。
你不是分析师 — 不输出结构化 JSON。

只做一件事：**去掉情绪，保留事实。**

## 处理流程

### 第1步：DFA 预处理（Bash 脚本）

执行 DFA 精确匹配脚本，获取脏话命中位置和自然语言摘要：

```bash
echo "[客户投诉文本]" | python3 scripts/dfa_filter.py
```

脚本返回 JSON，包含：
- `has_profanity`：是否检出脏话（布尔值）
- `total_matches`：命中总数
- `matches`：命中详情列表（word、start、end、type）
- `summary`：自然语言摘要（可直接用于最终输出）

**异常处理**：如果脚本执行失败（如 Python 未安装），跳过第1步，直接进入第2步。

如果检出脏话且存在 `summary` 字段，用 `Read` 工具读取 `references/homophone_guide.md`，了解常见谐音变体模式。

### 第2步：情绪检测

基于原始文本，判断情绪级别：

| 级别 | 说明 | 示例 |
|-----|------|------|
| 1 | 情绪平稳，客观描述问题 | "订单破损请协助处理" |
| 2 | 有轻微不满，无攻击性语言 | "等了两天还没回复有点失望" |
| 3 | 明显愤怒，含激烈用词或讽刺 | "你们这效率也太差了到底能不能解决" |
| 4 | 严重愤怒，含辱骂或人身攻击 | "你们tm的是不是脑子有问题" |

### 第3步：决策

- **级别 1-2** → 原文透传，不允许任何修改，跳至第6步输出
- **级别 3-4** → 进入第4步

### 第4步：情绪剥离

对级别 3-4 的文本执行以下规则：

1. **删除所有脏话和辱骂** — 包括：
   - DFA 检出词（在 summary 中已列出）
   - 谐音变体（煞笔=傻逼、草泥马=操你妈等，参考 homophone_guide.md）
   - 拼音缩写（tmd=他妈的、sb=傻逼等）
   - 数字/符号绕过（sh1t=shit、f\*ck=fuck等）
   - 空格分隔的变体（"t m d" → 合并后处理）

2. **讽刺转客观** — 将讽刺语气转为客观陈述
   - "你们这物流可真快啊👍15天才到" → "包裹配送耗时15天"

3. **保留所有事实信息** — 绝不删除：
   - 订单号、订单编号、物流单号
   - 金额、产品型号
   - 地址、联系方式（手机号、邮箱）
   - 时间信息、日期
   - 产品名称、问题描述

4. **不增不减** — 不添加原文不存在的信息，不遗漏关键事实

### 第5步：验证

对级别 3-4 的处理结果执行验证：
```bash
echo '{"original":"[原文]","sanitized":"[净化后文本]"}' | python3 scripts/validator.py
```

如果验证失败（passed=false）且存在核心实体丢失，重新执行第4步，特别注意保留丢失的实体。重试最多 2 次，之后即使验证未通过也输出当前结果。

### 第6步：输出

始终使用以下两段式格式输出。**输出必须是纯自然语言，不输出结构化数据：**

```
[情绪判断] <自然语言描述>

<净化后的自然语言文本>
```

情绪判断标签：
- 级别 1："客户情绪平稳，正常诉求"
- 级别 2："客户有轻微不满"
- 级别 3："客户情绪愤怒，建议优先处理"
- 级别 4："客户情绪激烈，含攻击性语言 — 以下为过滤后内容"

对于级别 3-4 且 DFA 有检出的情况，可将 `summary` 信息自然融入输出，例如：
```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

DFA 检测到 3 处情绪化表达（tmd、煞笔、草泥马），已过滤。

客户反馈购买的产品在使用三天后出现质量问题，要求退款处理。
```

## Few-shot 示例

### 示例1：中文脏话+英文缩写（级别 4）

输入："你们tmd煞笔产品草泥马的用了三天就坏赶紧退款"

处理过程：
```
第1步 (dfa_filter)：检出 3 处命中 → tmd(英文)、煞笔(中文)、草泥马(中文)
  摘要："DFA 精确匹配检测到 3 处命中，涉及 3 个不同词条：tmd、煞笔、草泥马。"
第2步 (情绪检测)：含多项辱骂 → 级别 4
第4步 (情绪剥离)：移除脏话，保留"退款""三天"
```

输出：
```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

DFA 检测到 3 处情绪化表达（tmd、煞笔、草泥马），已过滤。

客户反馈购买的产品在收货三天后出现质量问题，要求退款处理。
```

### 示例2：中文讽刺（级别 3）

输入："你们这物流可真快啊👍从北京到上海走了整整15天真不愧是极速达"

输出：
```
[情绪判断] 客户情绪愤怒，建议优先处理

客户反馈包裹从北京到上海配送耗时15天，认为超出正常时效，对配送速度不满意。
```

### 示例3：英文脏话（级别 4）

输入："This fucking app is garbage wasted my money fix this shit now or refund me"

输出：
```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

The customer is dissatisfied with the app quality and requesting either an immediate fix or a refund.
```

### 示例4：正常投诉（级别 1 — 必须透传）

输入："订单号ORDER20240523的包裹签收后发现外包装破损请协助处理"

输出：
```
[情绪判断] 客户情绪平稳，正常诉求

订单号ORDER20240523的包裹签收后发现外包装破损请协助处理
```

### 示例5：含关键信息的脏话+谐音（级别 4）

输入："你们cnm的送到浦东新区张江路666号的包裹tm摔烂了打我电话13812345678来赔"

输出：
```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

DFA 检测到 2 处情绪化表达（cnm、tm），已过滤。

送到了上海浦东新区张江路666号的包裹发生损坏，请联系13812345678协商赔付事宜。
```

### 示例6：空格分隔绕过（级别 3 — 由 LLM 识别，DFA 不命中）

输入："你们这服务真t m d差劲等了三天了还没回复"

输出：
```
[情绪判断] 客户情绪愤怒，建议优先处理

客户反馈等待三天未收到回复，对服务响应速度不满意。
```
```

- [ ] **步骤 2：验证 SKILL.md 语法和行数**

```bash
python3 -c "
with open('.claude/skills/tonebarrier/SKILL.md') as f:
    content = f.read()
# 检查 YAML frontmatter
assert content.startswith('---'), '缺少 YAML frontmatter'
parts = content.split('---', 2)
assert len(parts) >= 3, 'YAML frontmatter 格式无效'
lines = content.split('\n')
print(f'SKILL.md：{len(lines)} 行 — 符合规范（500行以内）')
print(f'YAML frontmatter 存在 — 合规')
print(f'allowed-tools: Bash, Read — 合规')
print(f'user-invocable: true — 合规')
print(f'name: tonebarrier (kebab-case) — 合规')
"
```

- [ ] **步骤 3：提交**

```bash
git add .claude/skills/tonebarrier/SKILL.md
git commit -m "feat: 添加主SKILL.md，双层管道（DFA+LLM），纯自然语言输出"
```

---

### 任务 8：README 文档

**涉及文件：**
- 创建：`.claude/skills/tonebarrier/README.md`

**变更说明：** 移除 pypinyin 依赖说明；增加字典更新后需更新索引的提示。

- [ ] **步骤 1：编写 README.md**

```markdown
# 精神内耗终结者 — ToneBarrier

客户情绪降级与文本脱水 SKILL for Claude Code。

将充满辱骂、讽刺、情绪宣泄的客服投诉文本转化为冷静客观的自然语言表达。
支持中文（含谐音字、拼音缩写、数字替换等变体）和英文。

## 特性

- **零外部依赖** — 无需 pip install 任何包，安装即用
- **双层过滤** — DFA 精确匹配 + LLM 语义理解，精确与智能兼顾
- **关键信息保留** — 自动检测并保留订单号、金额、地址、联系方式
- **两段式输出** — 情绪判断标签 + 净化后的自然语言文本
- **中文谐音变体处理** — 煞笔/沙比/卧槽/草泥马等常见变体全覆盖

## 安装

```bash
cp -r tonebarrier ~/.claude/skills/
```

或项目级安装：

```bash
cp -r tonebarrier .claude/skills/
```

安装后重启 Claude Code 即可使用。

## 使用

```
/tonebarrier 你们tmd这个破产品用了三天就坏了赶紧退款
```

输出示例：

```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

DFA 检测到 1 处情绪化表达（tmd），已过滤。

客户反馈购买的产品在收货三天后出现质量问题，要求退款处理。
```

## 架构

双层检测管道：

1. **DFA 精确匹配**（~0ms）— 1660 中文 + 794 英文脏话字典，输出自然语言摘要
2. **LLM 语义审核** — 谐音变体识别 + 空格绕过 + 讽刺转化 + 语境理解

无需外部 API 调用，全部在单次 `/tonebarrier` 调用内完成。

## 依赖

- Python 3.6+（标准库即可，无需第三方包）

## 测试

```bash
python3 tests/test_pipeline.py
```

## 字典更新说明

如需更新脏话字典（references/profanity_dict.txt），直接修改文件即可。
DFA 脚本启动时自动从文件加载，无需重新编译索引。

## 文件结构

```
tonebarrier/
├── SKILL.md                 # 主指令文件（YAML + Markdown）
├── scripts/
│   ├── dfa_filter.py        # DFA 精确匹配（零依赖）
│   └── validator.py         # 关键信息留存验证
├── references/
│   ├── profanity_dict.txt   # 1660 中文脏话词
│   ├── profanity_en.txt     # 794 英文脏话词
│   └── homophone_guide.md   # 谐音变体参考（LLM知识源）
├── tests/
│   ├── test_cases.json      # 19 条测试用例
│   └── test_pipeline.py     # 自动化测试
└── README.md                # 本文件
```

## 许可

MIT
```

- [ ] **步骤 2：提交**

```bash
git add .claude/skills/tonebarrier/README.md
git commit -m "docs: 添加README安装与使用文档"
```

---

### 任务 9：端到端集成测试

**涉及文件：**
- 修改：`.claude/skills/tonebarrier/SKILL.md`（端到端验证）

- [ ] **步骤 1：运行完整 DFA 测试套件**

```bash
python3 .claude/skills/tonebarrier/tests/test_pipeline.py
# 预期：>= 80% 通过率（最低 16/19）
```

- [ ] **步骤 2：验证 SKILL 被 Claude Code 正确识别**

```bash
ls -la .claude/skills/tonebarrier/SKILL.md
# 预期：文件存在于正确路径
```

- [ ] **步骤 3：手动测试 SKILL 调用**

在 Claude Code 中输入 `/tonebarrier`，验证自动补全显示该命令。

然后测试：
```
/tonebarrier 你们tmd煞笔产品草泥马的用了三天就坏赶紧退款
```

验证输出格式：
```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

DFA 检测到 3 处情绪化表达（tmd、煞笔、草泥马），已过滤。

<净化后的自然语言文本>
```

- [ ] **步骤 4：运行验证器边界用例**

```bash
# 测试1：关键实体保留（验证增强后的正则模式）
echo '{"original":"订单编号ORDER20240523金额2999元的手机tm坏了操","sanitized":"订单编号ORDER20240523的手机出现故障金额2999元要求处理"}' | python3 .claude/skills/tonebarrier/scripts/validator.py
# 预期：passed=true

# 测试2：实体丢失检测
echo '{"original":"订单编号ORDER20240523的包裹破了","sanitized":"包裹破了"}' | python3 .claude/skills/tonebarrier/scripts/validator.py
# 预期：passed=false, lost_count>=1

# 测试3：多字段实体保留
echo '{"original":"物流单号SF1234567890包裹送到北京市朝阳区建国路88号联系邮箱test@example.com","sanitized":"包裹已送到北京市朝阳区建国路88号物流单号SF1234567890请联系test@example.com"}' | python3 .claude/skills/tonebarrier/scripts/validator.py
# 预期：passed=true, preserved_count >= 3
```

- [ ] **步骤 5：最终提交**

```bash
git add .claude/skills/tonebarrier/
git status
# 确认所有文件均已跟踪
git commit -m "feat: 完成tonebarrier SKILL — 双层DFA+LLM情绪过滤，零外部依赖"
```

---

## 后续可选

### 演示前端（比赛路演用）

SKILL 功能完成后，可构建演示前端展示前后对比效果：

- **技术选型**：Next.js 14 + shadcn/ui + Tailwind CSS
- **布局**：左屏（原始文本，脏话红色高亮）vs 右屏（净化后输出）
- **预设演示**：5 个预置场景，一键切换
- **不在本计划范围内** — 如需前端可另行制定计划

### 分发渠道

项目完成后可提交到以下渠道：
- `github.com/anthropics/skills` — 官方 SKILL 仓库
- `skillforthat.com` — 社区 SKILL 目录
- `claude-plugins.dev` — Claude 插件注册表

---

## Codex 对抗性审查结果（2026-05-24）

以下为 Codex 对抗性审查发现的 5 项问题，需在最终发布前修复。

---

### 发现 1（Blocking）：DFA 无词边界匹配导致大量误报

**涉及文件：** `scripts/dfa_filter.py:44`、`references/profanity_dict.txt`、`references/profanity_en.txt`

**问题描述：**
`dfa_search()` 做原始子串匹配，没有词边界检查。字典中的短词（`ass`、`ma`、`sb`、`fuck`）会命中正常英文单词的内部子串，导致正常投诉被误标记为脏话：

| 正常输入 | 误报命中 | 原因 |
|---------|---------|------|
| `"class"` / `"pass-through"` | `ass` | 子串匹配 |
| `"USB-C充电器"` | `sb` | 子串匹配 |
| `"Order ... damaged packaging please help"` | `ma` | `damaged` → `ma` |

附带问题：中文词典包含了英文词条（`fuck` 在 `profanity_dict.txt:127`、`shit` 在 `profanity_dict.txt:189`），导致 `fucking` 同时命中 `fuck`(dfa_cn) 和 `fucking`(dfa_en)，类型标记混乱。

**实际程序加载的有效词条数：** 中文词典 1440 词，英文词典 793 词（过滤掉单字和纯数字词后）。

**建议修复：**
- DFA 匹配增加词边界检查（前后均为非字母字符或文本边界）
- 将英文词条从中文词典中移出，统一由英文词典管理
- 考虑移除长度 ≤ 2 的英文短词，或仅在独立出现时匹配

---

### 发现 2（Blocking）：验证器只保护核心标签，地址/联系方式丢失不报错

**涉及文件：** `scripts/validator.py:23`、`scripts/validator.py:96`

**问题描述：**
`CORE_TAGS = {"订单号", "物流单号", "单号", "订单ID", "金额"}` — 只有这 5 类核心标签丢失才会触发 `passed=false`。但 SKILL.md:75 和 README.md:12 承诺保留地址、联系方式、日期等所有事实信息。

**实测验证：** 输入原文含地址 `北京市朝阳区建国路88号` 和手机号 `13812345678`，sanitized 只保留订单号和金额，丢失地址和手机号 → validator 返回 `passed: true`。

**更严重的问题：** 地址匹配在 `entity_key()` 和 `keys_match()` 中仅比对数字部分。输入 `北京市朝阳区建国路88号` → sanitized 改为 `上海市徐汇区虹桥路88号`（偷换城市），validator 因数字 `88` 相同判定为已保留。

**建议修复：**
- 将 `CORE_TAGS` 扩展为所有实体类型，或至少增加手机号、地址
- 地址匹配改为基于地名字符串比对，而非仅比对数字
- 非核心实体丢失时至少输出 warning，而非直接判通过

---

### 发现 3（Blocking）：谐音指南加载条件与绕过场景互相矛盾

**涉及文件：** `SKILL.md:43`

**问题描述：**
SKILL.md 第 43 行只在 `has_profanity=true` 时才加载 `homophone_guide.md`：

> 若 `has_profanity` 为 true，用 Read 工具读取 `references/homophone_guide.md`

但 **所有需要谐音指南的场景恰恰是 DFA 不命中的场景**：

- 空格分隔绕过（`"t m d"`）→ DFA 不命中 → `has_profanity=false` → 指南不加载
- 谐音变体（`"草拟吗"` 等不在词典中的变体）→ DFA 不命中 → 指南不加载

SKILL.md 的示例 6（第 187 行）正是用 `"t m d"` 作为 DFA 不命中的经典场景，但这个场景下指南不会被加载。

**建议修复：**
将加载条件改为无条件加载，或在 DFA 不命中时也加载（因为绕过场景需要指南辅助识别）：

> 无论 DFA 是否命中，均用 Read 工具读取 `references/homophone_guide.md` 了解常见变体模式。

---

### 发现 4（Important）：测试只覆盖 DFA 层，不测试 sanitization 和 validator

**涉及文件：** `tests/test_pipeline.py:17`、`tests/test_cases.json`

**问题描述：**
- `test_pipeline.py` 只调用 `dfa_filter.py`，从未测试情绪剥离（sanitization）或 `validator.py`
- `test_cases.json` 中的 `expected_level`、`expected_sanitized_contains`、`expected_sanitized_not_contains` 字段完全未被使用
- 仅检查 `expected_dfa_matches` 是否全部命中（查漏），不检查是否多报了不该命中的词（查多报）— 这就是 `en_normal_01` 命中了 `ma` 但测试仍然通过的原因
- 80% 通过率阈值（`test_pipeline.py:117`）进一步掩盖已知回归

**建议修复：**
- 增加 `expected_dfa_false_positives` 检查（不应命中但命中的词）
- 对 LLM 层输出增加 sanitization 验证步骤（含 validator 调用）
- 将通过率阈值提升至 100%（或针对 DFA 层要求 100%）
- 使用 `expected_sanitized_contains` 和 `expected_sanitized_not_contains` 字段

---

### 发现 5（Important）：Few-shot 示例违反"不增不减"原则

**涉及文件：** `SKILL.md:82`、`SKILL.md:138`、`SKILL.md:184`

**问题描述：**
SKILL.md 第 82 行声明"不增不减 — 不添加原文不存在的信息，不遗漏关键事实"，但 few-shot 示例中存在事实添加：

| 示例 | 行号 | 原文 | 输出新增内容 |
|------|------|------|-------------|
| 示例 1 | :138 | `"…用了三天就坏…"` | 新增 `"收货"` 二字（原文未说何时故障） |
| 示例 5 | :184 | `"…送到浦东新区…来赔"` | 新增 `"上海"`（原文只说"浦东新区"）、新增 `"协商赔付事宜"`（原文只说"来赔"） |

在 validator 无法检测地址/非核心信息丢失的背景下，这些示例正在训练模型走向"事实漂移"，可能导致输出中添加原文不存在的城市名、承诺内容等。

**建议修复：**
- 修正 few-shot 示例，严格遵循"不增不减"：示例 1 去掉 `"收货"`，示例 5 去掉 `"上海"` 并将 `"协商赔付事宜"` 改回更贴近原文的表述
- 或在 SKILL.md 中明确区分"合理推断"与"禁止添加"的边界

---

### 审查结论

**不建议以当前状态发布。** DFA 对正常流量过度标记，validator 无法履行"保留事实"承诺，测试套件已漏掉实际存在的回归。5 项问题中 3 项为 Blocking 级别，必须修复后方可进入比赛提交或生产部署。

### 修复优先级

| 优先级 | 发现编号 | 修复项 | 预计工作量 |
|--------|---------|--------|-----------|
| P0 | #1 | DFA 词边界匹配 | 中 |
| P0 | #2 | validator 全实体保护 | 中 |
| P0 | #3 | 谐音指南加载条件修正 | 小 |
| P1 | #4 | 测试套件补全 | 大 |
| P1 | #5 | Few-shot 示例修正 | 小 |

---

*实施计划基于 2026-05-22 ~ 2026-05-24 调研成果 + 2026-05-24 架构审查反馈。*
*关键变更：移除 pypinyin 依赖、DFA+LLM 双层管线、纯自然语言输出、增强实体模式覆盖。*
*2026-05-24 Codex 对抗性审查：发现 5 项问题（3 Blocking + 2 Important），已记录于上文审查结果章节。*

---

## 修复记录（2026-05-25）

### 第一轮修复（审查发现 #1-#5）

| 发现 | 修复内容 | 涉及文件 | 状态 |
|------|---------|---------|------|
| #1 DFA 词边界 | `is_alpha_boundary()` 检查前后 ASCII 字母边界，防止 class→ass / USB-C→sb / damaged→ma | `dfa_filter.py` | ✅ |
| #2 validator 全实体 | CORE_TAGS 扩展至 手机号/座机号/邮箱/地址/日期/时间量/产品型号；地址匹配禁用子串回退 | `validator.py` | ✅ |
| #3 谐音指南加载 | 改为无条件加载 homophone_guide.md（无论 DFA 是否命中） | `SKILL.md` | ✅ |
| #4 测试套件补全 | 增加误报检查 + `expected_dfa_not_matches` 支持；阈值 80%→100%；新增 4 条边界回归（class/USB-C/damaged/standalone ass）；增加第2层验证器端到端测试 | `test_pipeline.py`, `test_cases.json` | ✅ |
| #5 Few-shot 修正 | 示例1 去掉"收货"；示例5 去掉"上海"、"协商赔付事宜"→"处理赔付" | `SKILL.md` | ✅ |

### 第二轮修复（Codex 再审查 2026-05-25）

| 发现 | 修复内容 | 涉及文件 | 状态 |
|------|---------|---------|------|
| 地址校验仍可漂移 | 地址正则增加路名直写模式（张江路666号）+ 英文地址模式（221B Baker Street）；限制正则贪婪匹配 | `validator.py` | ✅ |
| 产品型号/时间丢失不阻塞 | CORE_TAGS 新增 日期、日期短格式、时间量、产品型号 | `validator.py` | ✅ |
| DFA 测试放过额外命中 | 非空 `expected_dfa_matches` 也检查未声明的额外命中；`给老子` 加入期望列表 | `test_pipeline.py`, `test_cases.json` | ✅ |
| 透传与输出格式矛盾 | 明确两段式格式适用于所有级别，L1-2 第二段原文严格复制 | `SKILL.md` | ✅ |

### 第三轮优化（词典重建 + Benchmark 评估）

| 优化项 | 内容 | 涉及文件 | 状态 |
|--------|------|---------|------|
| CN 词典清理 | 移除 69 个误报词（纯数字、英文缩写、非脏话英文词、短拼音） | `profanity_dict.txt` | ✅ |
| 词典重建 | 从通用敏感词库（1,593 词）重建为客服投诉专用脏话词典（323 词） | `profanity_dict.txt` | ✅ |
| 产品型号正则 | 修正为要求至少一个字母+一个数字，排除 GitHub label 前缀 | `validator.py` | ✅ |
| 透传指令强化 | 增加反面教材示例（严禁润色改写行为） | `SKILL.md` | ✅ |
| Benchmark 框架 | 创建 dfa_eval.py + skill_eval.py + report.py + eval_cases.json | `benchmark/` | ✅ |

### 最终词典组成（323 词）

| 类别 | 数量 | 示例 |
|------|------|------|
| 中文脏话 | ~70 | 傻逼、草泥马、操你妈、日你妈、肏你… |
| 中文辱骂 | ~70 | 废物、白痴、智障、脑残、混蛋、王八蛋… |
| 拼音缩写 | ~35 | tmd、cnm、sb、nmsl、wcnm、mlgb… |
| 谐音变体 | ~25 | 煞笔、沙比、草拟吗、艹泥马、尼玛… |
| 英文脏话 | ~45 | fuck、shit、bitch、ass、damn、garbage… |
| 数字/符号绕过 | ~15 | 2b、sh1t、f*ck、b1tch、a55… |
| 愤怒表达 | ~40 | 操、靠、日、滚蛋、放屁、去死… |

### 最终 DFA Benchmark 指标

| 指标 | v1 (1,662词) | v3 (323词) | 变化 |
|------|-------------|-----------|------|
| COLD 精确率 | 67.4% | **90.5%** | +23pp |
| COLD 召回率 | 4.2% | **22.3%** | +18pp |
| COLD F1 | 0.078 | **0.357** | +0.279 |
| COLD 误报率 | 1.96% | 2.30% | +0.34pp |
| ToxiCN 召回率 | 3.7% | **8.5%** | +4.8pp |
| App评论命中率 | 4.9% | **28.8%** | +23.9pp |
| 词典规模 | 1,662 | **323** | -1,339 |

### 测试状态

- DFA 层: 23/23 通过
- 验证器层: 7/7 通过（含 4 条回归测试）
- 合计: **30/30 通过 (100%)**
