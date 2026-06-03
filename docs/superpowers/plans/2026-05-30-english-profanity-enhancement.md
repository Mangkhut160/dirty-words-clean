# 英文脏话识别增强计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 tonebarrier 的英文脏话识别从"能用"提升到"生产可用"——降低误报率、提高变体覆盖率、增加英文测试用例。

**Architecture:** 分三层改进：(1) 词典质量清洗+分级 (2) DFA 引擎增加英文归一化预处理 (3) 测试用例扩充到 20+ 条英文场景。

**Tech Stack:** Python 3.9+, 纯标准库 DFA, JSON 测试框架

---

## 现状分析

### 当前 profanity_en.txt 的问题

| 问题 | 影响 | 示例 |
|------|------|------|
| 含高误报词 | 正常文本被标记 | "God", "balls", "wang", "willy", "twinkie" |
| 大量性术语 | 客服场景无用，增加匹配开销 | "acrotomophilia", "alabama hot pocket", "urophilia" |
| 缺少现代缩写 | 漏检 | "stfu", "gtfo", "lmao" (非脏话但常伴随), "pos" |
| 缺少审查绕过变体 | 漏检 | "f\*\*k", "sh!t", "a\*\*hole", "b1tch" 部分有但不全 |
| 无分级标注 | 无法区分级别 3 vs 4 | "damn" (级别3) 和 "fuck" (级别4) 混在一起 |
| 含种族歧视词 | 需要但需单独标注 | "wetback", "white power" — 应为级别 4 |

### 当前英文测试覆盖

仅 6 条：en_profanity_01, en_sarcastic_01, en_normal_01, en_boundary_substring_01, en_boundary_damaged_01, en_boundary_standalone_01

缺失场景：leet speak、审查绕过（f\*ck）、缩写（stfu）、种族歧视、英文谐音、混合中英、长英文投诉、多脏话叠加。

---

## Task 1: 清洗并分级 profanity_en.txt

**Files:**
- Modify: `.claude/skills/tonebarrier/references/profanity_en.txt`
- Create: `.claude/skills/tonebarrier/scripts/build_en_dict.py`（构建脚本，方便后续维护）

### 设计原则

1. **按客服场景分级**，不是按"是否是脏话"分级：
   - **Level 4 词（辱骂性）**：fuck, shit, bitch, asshole, cunt, dick (辱骂用法), motherfucker, 种族歧视词
   - **Level 3 词（感叹/轻度）**：damn, hell, crap, bloody, bastard, piss, bollocks
   - **移除（高误报）**：God, balls, wang, willy, twinkie, cock (有动物含义), 纯性术语

2. **每个词条带元数据注释**（用 `#` 注释行标注分类）

3. **变体归入主词条旁边**，方便维护

### 目标词典结构

```
# === LEVEL 4: 辱骂性脏话 (Abusive profanity) ===
fuck
fucking
fucked
fucker
fucks
f*ck
f**k
fuk
fuc
phuck
...
# === LEVEL 3: 感叹/轻度 (Exclamatory/mild) ===
damn
dammit
damned
d*mn
...
# === LEVEL 4: 种族/歧视性 (Slurs) ===
...
```

- [ ] **Step 1: 分析当前词典，标记每个词的分类**

读取 profanity_en.txt，将 798 个词条分为：
- keep_level4（辱骂性）
- keep_level3（感叹性）
- remove_false_positive（高误报）
- remove_irrelevant（纯性术语/客服场景无关）

- [ ] **Step 2: 编写 build_en_dict.py 构建脚本**

```python
#!/usr/bin/env python3
"""
从分类源文件构建 profanity_en.txt。
支持注释行（#开头）和空行，输出时保留注释结构。
用法: python3 build_en_dict.py > ../references/profanity_en.txt
"""
```

脚本功能：
- 读取 `references/profanity_en_source.yaml`（或直接维护 txt）
- 去重、排序、验证格式
- 输出最终 profanity_en.txt

- [ ] **Step 3: 重写 profanity_en.txt**

目标：
- Level 4 词条：~150 个（含变体）
- Level 3 词条：~40 个（含变体）
- 总计 ~200 个高质量词条（从 798 精简到 200，但覆盖率更高因为补充了缺失变体）

- [ ] **Step 4: 补充缺失的现代英文脏话变体**

需要新增的类别：
| 类别 | 示例 | 数量 |
|------|------|------|
| 缩写 | stfu, gtfo, ffs, smfh, pos, sob, bs | ~15 |
| 星号审查绕过 | f\*ck, s\*\*t, a\*\*, b\*tch | ~20 |
| 空格/点分隔 | f.u.c.k, s h i t | DFA 无法直接处理，留给 LLM |
| 首字母+暗示 | the f-word, the s-word | 不加入词典，LLM 处理 |
| 复合词 | dumbass, jackass, dipshit, bullshit, horseshit | ~15 |
| 英式俚语 | wanker, tosser, bellend, knobhead, twat | ~10 |
| 澳式俚语 | drongo (不加), bogan (不加) — 仅加明确脏话 | ~5 |

- [ ] **Step 5: 验证无误报**

对以下正常文本运行 DFA，确认零命中：
- "The class action lawsuit was dismissed"
- "Please pass the ball to the goalkeeper"
- "The cocktail party was wonderful"
- "I need to assess the damage"
- "The therapist recommended meditation"
- "She's a classic beauty"
- "The USB-C connector is broken"
- "God bless you" (如果保留 God 则需移除)

---

## Task 2: DFA 引擎增加英文归一化预处理

**Files:**
- Modify: `.claude/skills/tonebarrier/scripts/dfa_filter.py`
- Modify: `tonebarrier-server/skill/scripts/dfa_filter.py`（同步）

### 设计

当前 DFA 已有：
- 全角→半角转换
- 大小写归一化
- 词边界检查

需要新增：
- **Leet speak 归一化**：`1→i, 3→e, 4→a, 5→s, 0→o, @→a, $→s, !→i, 7→t`
- **重复字符压缩**：`fuuuuck → fuck`, `shiiit → shit`（连续 3+ 相同字符压缩为 1-2 个）
- **星号/符号剥离**：`f*ck → fck`（然后匹配 "fck" 变体）或直接在词典中加入

### 实现策略

不修改主 DFA 搜索逻辑，而是在搜索前增加一个**归一化管道**：

```python
def normalize_english(text):
    """英文文本归一化：leet speak + 重复压缩 + 符号剥离"""
    # Step 1: Leet speak 映射
    # Step 2: 重复字符压缩 (3+ → 2)
    # Step 3: 常见审查符号剥离 (* → '', 但保留词边界)
    return normalized
```

然后在 `main()` 中：对原文跑一次 DFA，对归一化文本再跑一次，合并结果（类似现有的全角处理逻辑）。

- [ ] **Step 1: 实现 normalize_leet() 函数**

```python
LEET_MAP = {'1': 'i', '3': 'e', '4': 'a', '5': 's', '0': 'o',
            '@': 'a', '$': 's', '!': 'i', '7': 't', '8': 'b'}

def normalize_leet(text):
    """将 leet speak 字符替换为对应字母。仅在字母上下文中替换。"""
    ...
```

关键：只在"看起来像英文单词"的上下文中做 leet 替换，避免把 "Order #12345" 中的数字误替换。

策略：检测连续的 字母+数字/符号 混合序列（如 "sh1t", "f@ck"），仅对这些序列做 leet 归一化。纯数字序列（订单号、电话）不处理。

- [ ] **Step 2: 实现 compress_repeats() 函数**

```python
def compress_repeats(text):
    """将连续 3+ 相同字符压缩为 2 个。fuuuck→fuuck, shiiit→shiit"""
    return re.sub(r'(.)\1{2,}', r'\1\1', text)
```

- [ ] **Step 3: 实现 strip_censor_chars() 函数**

```python
CENSOR_CHARS = set('*_-.')

def strip_censor_chars(text):
    """剥离单词内部的审查符号。f*ck→fck, s.h.i.t→shit"""
    # 仅处理字母间的审查符号，不影响句子结构
    ...
```

- [ ] **Step 4: 整合到 main() 中**

```python
# 英文归一化预处理：在归一化文本上补充扫描
en_normalized = normalize_leet(compress_repeats(strip_censor_chars(text)))
if en_normalized != text.lower():
    en_norm_matches = dfa_search(dfa_en, en_normalized)
    # 合并，标记为 (leet) 变体
```

- [ ] **Step 5: 同步到 tonebarrier-server/skill/scripts/dfa_filter.py**

- [ ] **Step 6: 运行现有测试验证无回归**

```bash
cd .claude/skills/tonebarrier && python3 tests/test_pipeline.py
```

---

## Task 3: 扩充英文测试用例

**Files:**
- Modify: `.claude/skills/tonebarrier/tests/test_cases.json`

### 新增测试用例设计（20 条）

| ID | 类别 | 输入 | 预期级别 | 关键验证点 |
|----|------|------|----------|-----------|
| en_leet_01 | Leet speak | "your product is sh1t fix it now" | 4 | DFA 检出 sh1t |
| en_leet_02 | Leet speak 复合 | "what a p13ce of cr@p service" | 4 | 检出 cr@p |
| en_censor_01 | 星号审查 | "this is f\*\*king ridiculous I want a refund" | 4 | 检出 f\*\*king |
| en_censor_02 | 星号审查 | "what the h\*ll is wrong with your app" | 3 | 检出 h\*ll |
| en_abbrev_01 | 缩写 | "stfu with your excuses just fix the damn thing" | 4 | 检出 stfu, damn |
| en_abbrev_02 | 缩写 | "this is total bs and you know it" | 3 | 检出 bs |
| en_slur_01 | 种族歧视 | (不在文档中写出具体内容) | 4 | DFA 检出 |
| en_compound_01 | 复合词 | "your customer service is complete bullshit" | 4 | 检出 bullshit |
| en_compound_02 | 复合词 | "what a jackass move by your team" | 4 | 检出 jackass |
| en_british_01 | 英式 | "your support team are absolute wankers" | 4 | 检出 wankers |
| en_british_02 | 英式 | "what a load of bollocks this warranty is" | 3 | 检出 bollocks |
| en_repeat_01 | 重复字符 | "this is sooo f\*\*\*ing annoying fix it" | 4 | 归一化后检出 |
| en_multi_01 | 多脏话叠加 | "fuck this shit ass product give me my goddamn money" | 4 | 检出 fuck, shit, ass, goddamn |
| en_sarcastic_02 | 讽刺无脏话 | "Oh wow what amazing quality broke after one day truly impressive engineering" | 3 | 无 DFA 命中，LLM 判讽刺 |
| en_sarcastic_03 | 讽刺+轻度 | "Bloody brilliant service waited a month for nothing" | 3 | 检出 bloody |
| en_normal_02 | 正常英文 | "I ordered size M but received size L please exchange" | 1 | 零命中 |
| en_normal_03 | 正常英文含敏感子串 | "The assessment of the classic model shows it passed all tests" | 1 | 不误报 ass/class/passed |
| en_normal_04 | 正常英文技术词 | "The cockpit display and throttle assembly need replacement" | 1 | 不误报 cock/ass |
| en_mixed_01 | 中英混合 | "这个app真是bullshit一样的体验 damn it" | 4 | 检出 bullshit, damn |
| en_long_01 | 长英文投诉 | (200字英文投诉含2处脏话) | 4 | 保留订单号、金额等关键信息 |

- [ ] **Step 1: 编写 20 条英文测试用例 JSON**

- [ ] **Step 2: 追加到 test_cases.json**

- [ ] **Step 3: 运行测试，记录基线通过率**

---

## Task 4: 更新 SKILL.md 英文规则描述

**Files:**
- Modify: `.claude/skills/tonebarrier/SKILL.md`

### 需要补充的内容

1. **英文级别判定示例**（当前只有中文示例详细）：

| 级别 | 英文示例 |
|------|---------|
| 1 | "Order arrived damaged please help" |
| 2 | "I'm really disappointed with the service" |
| 3 | "What the hell is this? Bloody useless!" / "Damn it, still broken" |
| 4 | "This is fucking bullshit, you assholes" / "Piece of shit product" |

2. **英文变体识别规则**：
   - Leet speak: sh1t, @ss, f4ck, b!tch
   - 审查绕过: f\*\*k, s\*\*t, a\*\*
   - 缩写: stfu, gtfo, ffs, bs, pos
   - 重复: fuuuck, shiiit
   - 复合: bullshit, horseshit, dumbass, jackass

3. **英文误报防护规则**：
   - "class" ≠ "ass", "assess" ≠ "ass", "pass" ≠ "ass"
   - "cocktail" ≠ "cock", "cockpit" ≠ "cock"
   - "therapist" ≠ "the rapist"
   - "Scunthorpe problem" 意识

- [ ] **Step 1: 在 SKILL.md 第2步（情绪检测）中补充英文示例**

- [ ] **Step 2: 在第4步（情绪剥离）中补充英文变体规则**

- [ ] **Step 3: 添加英文误报防护说明**

---

## Task 5: 同步到生产服务并验证

**Files:**
- Sync: `tonebarrier-server/skill/` ← `.claude/skills/tonebarrier/`
- Test: 在 HF Spaces 上验证英文输入

- [ ] **Step 1: 同步 references/profanity_en.txt**
- [ ] **Step 2: 同步 scripts/dfa_filter.py**
- [ ] **Step 3: 推送到 HF Spaces**
- [ ] **Step 4: 在线测试英文脏话检测**

---

## 执行顺序与依赖

```
Task 1 (词典清洗) ──→ Task 2 (DFA 引擎) ──→ Task 3 (测试用例)
                                                      ↓
                                              Task 4 (SKILL.md)
                                                      ↓
                                              Task 5 (同步部署)
```

Task 1 和 Task 2 可以并行开始（词典清洗不影响引擎代码结构），但 Task 3 的测试需要 Task 1+2 都完成后才能跑通。

---

## 风险与注意事项

1. **Leet speak 归一化可能引入误报**：纯数字序列（订单号、电话）不能被 leet 替换。需要上下文感知。
2. **词典精简可能导致漏检**：移除的词需要确认在客服场景中确实不会出现。
3. **英式/澳式俚语的级别判定**：不同文化对同一词的冒犯程度不同，以"是否辱骂对方"为统一标准。
4. **DFA 性能**：归一化增加一次额外扫描，但词典从 798→200 精简后总体性能应持平或更优。
