# 客户骚扰客服检测模块 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个独立的"客户骚扰客服人员"检测模块，基于已下载的 6 个学术数据集（COLD、DiaSafety、BeaverTails、ProsocialDialog、EDOS、Jigsaw），提供二分类（骚扰/正常）+ 细粒度标签（威胁、侮辱、歧视、性骚扰）的检测能力，集成到现有 tonebarrier-server 中。

**Architecture:** 三层架构 — (1) 数据预处理层：统一 6 个异构数据集为标准 JSONL 格式；(2) 检测引擎层：DFA 关键词快筛 + 轻量分类模型（基于 TF-IDF + LogisticRegression，零 GPU 依赖）；(3) 服务集成层：新增 `/api/harassment` 端点，复用现有 FastAPI 框架。中文场景使用 COLD 数据集训练，英文场景使用 DiaSafety + BeaverTails + EDOS 混合训练。

**Tech Stack:** Python 3.9+, scikit-learn (TF-IDF + LogisticRegression), FastAPI, 现有 DFA 引擎复用

---

## 文件结构

```
tonebarrier-server/
├── harassment/                    # 新模块根目录
│   ├── __init__.py               # 模块入口
│   ├── preprocessor.py           # 数据集统一预处理
│   ├── dataset_loader.py         # 加载标准化后的数据
│   ├── train_classifier.py       # 训练脚本（生成模型文件）
│   ├── detector.py               # 检测引擎（DFA快筛 + 分类器）
│   ├── models/                   # 训练产物
│   │   ├── cn_tfidf.pkl          # 中文 TF-IDF vectorizer
│   │   ├── cn_clf.pkl            # 中文分类器
│   │   ├── en_tfidf.pkl          # 英文 TF-IDF vectorizer
│   │   └── en_clf.pkl            # 英文分类器
│   └── data/                     # 标准化后的训练数据
│       ├── cn_train.jsonl        # 中文训练集
│       ├── cn_test.jsonl         # 中文测试集
│       ├── en_train.jsonl        # 英文训练集
│       └── en_test.jsonl         # 英文测试集
├── server.py                     # 修改：新增 /api/harassment 路由
├── static/app.js                 # 修改：新增骚扰检测 tab
└── templates/index.html          # 修改：新增骚扰检测 UI
```

```
tests/
└── harassment/
    ├── test_preprocessor.py      # 预处理单元测试
    ├── test_detector.py          # 检测引擎单元测试
    └── test_api.py               # API 集成测试
```

---

## 标签体系设计

### 统一标签映射

| 原始数据集 | 原始标签 | 统一标签 | 说明 |
|-----------|---------|---------|------|
| COLD | label=1 | `harassment` | 中文冒犯语言 |
| COLD | label=0 | `normal` | 安全文本 |
| DiaSafety | Offending User + Unsafe | `harassment` | 直接冒犯用户 |
| DiaSafety | 其他 + Safe | `normal` | 安全对话 |
| BeaverTails | hate_speech=True | `harassment` | 仇恨言论 |
| BeaverTails | violence=True | `harassment` | 暴力煽动 |
| BeaverTails | is_safe=True | `normal` | 安全内容 |
| EDOS | label_sexist=sexist | `harassment` | 性别歧视 |
| EDOS | label_sexist=not sexist | `normal` | 非歧视 |
| ProsocialDialog | __needs_intervention__ | `harassment` | 需要干预 |
| ProsocialDialog | __casual__ | `normal` | 日常对话 |

### 细粒度子标签（仅 harassment 类）

| 子标签 | 来源映射 | 说明 |
|--------|---------|------|
| `threat` | BeaverTails.violence, EDOS.threats | 威胁恐吓 |
| `insult` | COLD.label=1, DiaSafety.Offending | 侮辱谩骂 |
| `discrimination` | EDOS.derogation, BeaverTails.discrimination | 歧视偏见 |
| `sexual` | EDOS.sexual, BeaverTails.sexually_explicit | 性骚扰 |
| `general` | 其他 harassment 无法归入上述 | 一般骚扰 |

---

### Task 1: 数据预处理器 — 统一 6 个数据集为标准 JSONL

**Files:**
- Create: `tonebarrier-server/harassment/__init__.py`
- Create: `tonebarrier-server/harassment/preprocessor.py`
- Create: `tests/harassment/test_preprocessor.py`

**标准输出格式 (每行一个 JSON):**
```json
{"text": "原始文本", "label": "harassment", "sub_label": "insult", "source": "cold", "lang": "cn"}
```

- [ ] **Step 1: 写测试**

```python
# tests/harassment/test_preprocessor.py
import json
import tempfile
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../tonebarrier-server'))

from harassment.preprocessor import (
    preprocess_cold,
    preprocess_diasafety,
    preprocess_beavertails,
    preprocess_edos,
    preprocess_prosocial,
)


def test_preprocess_cold_offensive():
    """COLD label=1 应映射为 harassment/insult"""
    rows = [
        {"split": "train", "topic": "race", "label": "1", "TEXT": "黑人都是垃圾"},
    ]
    results = list(preprocess_cold(rows))
    assert len(results) == 1
    assert results[0]["label"] == "harassment"
    assert results[0]["sub_label"] == "insult"
    assert results[0]["lang"] == "cn"
    assert results[0]["source"] == "cold"


def test_preprocess_cold_safe():
    """COLD label=0 应映射为 normal"""
    rows = [
        {"split": "train", "topic": "gender", "label": "0", "TEXT": "女性在职场中表现优秀"},
    ]
    results = list(preprocess_cold(rows))
    assert len(results) == 1
    assert results[0]["label"] == "normal"


def test_preprocess_diasafety_offending_unsafe():
    """DiaSafety Offending User + Unsafe → harassment/insult"""
    items = [
        {"context": "You're an idiot", "response": "Takes one to know one",
         "category": "Offending User", "label": "Unsafe"},
    ]
    results = list(preprocess_diasafety(items))
    assert len(results) == 1
    assert results[0]["label"] == "harassment"
    assert results[0]["sub_label"] == "insult"
    assert results[0]["text"] == "You're an idiot"


def test_preprocess_diasafety_safe():
    """DiaSafety Safe → normal"""
    items = [
        {"context": "How are you?", "response": "I'm fine",
         "category": "Risk Ignorance", "label": "Safe"},
    ]
    results = list(preprocess_diasafety(items))
    assert len(results) == 1
    assert results[0]["label"] == "normal"


def test_preprocess_beavertails_hate():
    """BeaverTails hate_speech=True → harassment"""
    items = [
        {"prompt": "Say something hateful", "response": "...", "is_safe": False,
         "category": {"hate_speech,offensive_language": True, "violence,aiding_and_abetting,incitement": False}},
    ]
    results = list(preprocess_beavertails(items))
    assert len(results) == 1
    assert results[0]["label"] == "harassment"
    assert results[0]["sub_label"] == "insult"


def test_preprocess_beavertails_violence():
    """BeaverTails violence=True → harassment/threat"""
    items = [
        {"prompt": "How to hurt someone", "response": "...", "is_safe": False,
         "category": {"hate_speech,offensive_language": False, "violence,aiding_and_abetting,incitement": True}},
    ]
    results = list(preprocess_beavertails(items))
    assert len(results) == 1
    assert results[0]["sub_label"] == "threat"


def test_preprocess_edos_sexist():
    """EDOS sexist → harassment"""
    items = [
        {"text": "Women belong in the kitchen", "label_sexist": "sexist",
         "label_category": "2. derogation", "label_vector": "2.1 descriptive attacks"},
    ]
    results = list(preprocess_edos(items))
    assert len(results) == 1
    assert results[0]["label"] == "harassment"
    assert results[0]["sub_label"] == "discrimination"


def test_preprocess_prosocial_intervention():
    """ProsocialDialog needs_intervention → harassment"""
    items = [
        {"context": "I want to kill you", "response": "...",
         "safety_label": "__needs_intervention__"},
    ]
    results = list(preprocess_prosocial(items))
    assert len(results) == 1
    assert results[0]["label"] == "harassment"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/cxw114/Desktop/idea && python3 -m pytest tests/harassment/test_preprocessor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'harassment'`

- [ ] **Step 3: 实现预处理器**

```python
# tonebarrier-server/harassment/__init__.py
"""客户骚扰客服检测模块。"""

# tonebarrier-server/harassment/preprocessor.py
"""将 6 个异构数据集统一为标准 JSONL 格式。"""
import csv
import json
import os

DATASETS_DIR = os.path.join(os.path.dirname(__file__), '../../datasets/harassment')


def preprocess_cold(rows):
    """处理 COLD 数据集行（dict 列表，含 label/TEXT 字段）。"""
    for row in rows:
        label = "harassment" if row["label"] == "1" else "normal"
        sub_label = "insult" if label == "harassment" else None
        yield {
            "text": row["TEXT"],
            "label": label,
            "sub_label": sub_label,
            "source": "cold",
            "lang": "cn",
        }


def preprocess_diasafety(items):
    """处理 DiaSafety JSON 数组。context 是用户发言。"""
    for item in items:
        is_unsafe = item["label"] == "Unsafe"
        is_offending = item["category"] == "Offending User"
        if is_unsafe and is_offending:
            label = "harassment"
            sub_label = "insult"
        elif is_unsafe:
            label = "harassment"
            sub_label = "general"
        else:
            label = "normal"
            sub_label = None
        yield {
            "text": item["context"],
            "label": label,
            "sub_label": sub_label,
            "source": "diasafety",
            "lang": "en",
        }


def preprocess_beavertails(items):
    """处理 BeaverTails JSONL 条目。prompt 是用户攻击性输入。"""
    for item in items:
        cat = item.get("category", {})
        has_hate = cat.get("hate_speech,offensive_language", False)
        has_violence = cat.get("violence,aiding_and_abetting,incitement", False)
        has_discrimination = cat.get("discrimination,stereotype,injustice", False)
        has_sexual = cat.get("sexually_explicit,adult_content", False)

        if has_violence:
            yield {"text": item["prompt"], "label": "harassment",
                   "sub_label": "threat", "source": "beavertails", "lang": "en"}
        elif has_hate:
            yield {"text": item["prompt"], "label": "harassment",
                   "sub_label": "insult", "source": "beavertails", "lang": "en"}
        elif has_discrimination:
            yield {"text": item["prompt"], "label": "harassment",
                   "sub_label": "discrimination", "source": "beavertails", "lang": "en"}
        elif has_sexual:
            yield {"text": item["prompt"], "label": "harassment",
                   "sub_label": "sexual", "source": "beavertails", "lang": "en"}
        elif item.get("is_safe", True):
            yield {"text": item["prompt"], "label": "normal",
                   "sub_label": None, "source": "beavertails", "lang": "en"}


def preprocess_edos(items):
    """处理 EDOS CSV 行。"""
    for item in items:
        if item["label_sexist"] == "sexist":
            cat = item.get("label_category", "")
            if "threats" in cat:
                sub_label = "threat"
            elif "derogation" in cat or "animosity" in cat:
                sub_label = "discrimination"
            else:
                sub_label = "general"
            yield {"text": item["text"], "label": "harassment",
                   "sub_label": sub_label, "source": "edos", "lang": "en"}
        else:
            yield {"text": item["text"], "label": "normal",
                   "sub_label": None, "source": "edos", "lang": "en"}


def preprocess_prosocial(items):
    """处理 ProsocialDialog JSONL。context 是用户发言。"""
    for item in items:
        safety = item.get("safety_label", "")
        if safety == "__needs_intervention__":
            yield {"text": item["context"], "label": "harassment",
                   "sub_label": "general", "source": "prosocial", "lang": "en"}
        elif safety == "__casual__":
            yield {"text": item["context"], "label": "normal",
                   "sub_label": None, "source": "prosocial", "lang": "en"}


def load_cold_csv(path):
    """从 CSV 文件加载 COLD 数据。"""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_jsonl(path):
    """加载 JSONL 文件。"""
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_json(path):
    """加载 JSON 文件。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_all(output_dir, datasets_dir=None):
    """从原始数据集构建标准化训练/测试数据。"""
    if datasets_dir is None:
        datasets_dir = DATASETS_DIR

    os.makedirs(output_dir, exist_ok=True)

    cn_data = []
    en_data = []

    # COLD (中文)
    for split_file in ["train.csv", "dev.csv"]:
        path = os.path.join(datasets_dir, "cold", split_file)
        if os.path.exists(path):
            rows = load_cold_csv(path)
            cn_data.extend(preprocess_cold(rows))

    # DiaSafety (英文)
    for split_file in ["train.json", "val.json"]:
        path = os.path.join(datasets_dir, "diasafety", split_file)
        if os.path.exists(path):
            items = load_json(path)
            en_data.extend(preprocess_diasafety(items))

    # BeaverTails (英文)
    path = os.path.join(datasets_dir, "beavertails", "train.jsonl")
    if os.path.exists(path):
        items = load_jsonl(path)
        en_data.extend(preprocess_beavertails(items))

    # EDOS (英文)
    path = os.path.join(datasets_dir, "edos", "edos_labelled_aggregated.csv")
    if os.path.exists(path):
        rows = []
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("split") in ("train", "dev"):
                    rows.append(row)
        en_data.extend(preprocess_edos(rows))

    # ProsocialDialog (英文) — 只取前 20000 条避免数据不平衡
    path = os.path.join(datasets_dir, "prosocial", "train.json")
    if os.path.exists(path):
        items = load_jsonl(path) if path.endswith('.jsonl') else []
        if not items:
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 20000:
                        break
                    line = line.strip()
                    if line:
                        items.append(json.loads(line))
        en_data.extend(preprocess_prosocial(items))

    # 写出
    _write_split(cn_data, output_dir, "cn", test_ratio=0.15)
    _write_split(en_data, output_dir, "en", test_ratio=0.15)

    return {"cn_total": len(cn_data), "en_total": len(en_data)}


def _write_split(data, output_dir, lang, test_ratio=0.15):
    """按比例切分并写出 train/test JSONL。"""
    import random
    random.seed(42)
    random.shuffle(data)
    split_idx = int(len(data) * (1 - test_ratio))
    train = data[:split_idx]
    test = data[split_idx:]

    for name, subset in [("train", train), ("test", test)]:
        path = os.path.join(output_dir, f"{lang}_{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for item in subset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/cxw114/Desktop/idea && python3 -m pytest tests/harassment/test_preprocessor.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: 提交**

```bash
git add tonebarrier-server/harassment/__init__.py tonebarrier-server/harassment/preprocessor.py tests/harassment/test_preprocessor.py
git commit -m "feat(harassment): 数据预处理器 — 统一 6 个数据集为标准 JSONL"
```

---

### Task 2: 执行数据预处理 — 生成标准化训练数据

**Files:**
- Create: `tonebarrier-server/harassment/data/cn_train.jsonl`
- Create: `tonebarrier-server/harassment/data/cn_test.jsonl`
- Create: `tonebarrier-server/harassment/data/en_train.jsonl`
- Create: `tonebarrier-server/harassment/data/en_test.jsonl`

- [ ] **Step 1: 运行预处理脚本生成数据**

```bash
cd /Users/cxw114/Desktop/idea
python3 -c "
import sys
sys.path.insert(0, 'tonebarrier-server')
from harassment.preprocessor import build_all
result = build_all(
    output_dir='tonebarrier-server/harassment/data',
    datasets_dir='datasets/harassment'
)
print(f'中文: {result[\"cn_total\"]} 条')
print(f'英文: {result[\"en_total\"]} 条')
"
```

Expected: 中文 ~32,000 条，英文 ~30,000 条

- [ ] **Step 2: 验证数据质量**

```bash
cd /Users/cxw114/Desktop/idea
python3 -c "
import json
for lang in ['cn', 'en']:
    for split in ['train', 'test']:
        path = f'tonebarrier-server/harassment/data/{lang}_{split}.jsonl'
        with open(path) as f:
            lines = f.readlines()
        labels = {}
        for line in lines:
            obj = json.loads(line)
            labels[obj['label']] = labels.get(obj['label'], 0) + 1
        print(f'{lang}_{split}: {len(lines)} 条, 分布: {labels}')
"
```

Expected: 每个文件都有 harassment 和 normal 两类，比例大致均衡

- [ ] **Step 3: 提交**

```bash
git add tonebarrier-server/harassment/data/
git commit -m "data(harassment): 生成标准化训练/测试数据集"
```

---

### Task 3: 训练分类器 — TF-IDF + LogisticRegression

**Files:**
- Create: `tonebarrier-server/harassment/train_classifier.py`
- Create: `tests/harassment/test_classifier_train.py`

- [ ] **Step 1: 写测试**

```python
# tests/harassment/test_classifier_train.py
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../tonebarrier-server'))

from harassment.train_classifier import train_model, evaluate_model


def _make_sample_data(tmpdir, lang="en"):
    """创建小规模测试数据。"""
    train_path = os.path.join(tmpdir, f"{lang}_train.jsonl")
    test_path = os.path.join(tmpdir, f"{lang}_test.jsonl")

    train_data = [
        {"text": "you are an idiot", "label": "harassment", "sub_label": "insult", "lang": lang},
        {"text": "fuck off loser", "label": "harassment", "sub_label": "insult", "lang": lang},
        {"text": "I will kill you", "label": "harassment", "sub_label": "threat", "lang": lang},
        {"text": "die you piece of shit", "label": "harassment", "sub_label": "insult", "lang": lang},
        {"text": "hello how are you", "label": "normal", "sub_label": None, "lang": lang},
        {"text": "thanks for your help", "label": "normal", "sub_label": None, "lang": lang},
        {"text": "can you check my order", "label": "normal", "sub_label": None, "lang": lang},
        {"text": "the product arrived today", "label": "normal", "sub_label": None, "lang": lang},
    ] * 10  # 重复以满足最小训练量

    test_data = [
        {"text": "you stupid moron", "label": "harassment", "sub_label": "insult", "lang": lang},
        {"text": "please help me", "label": "normal", "sub_label": None, "lang": lang},
    ]

    with open(train_path, "w") as f:
        for item in train_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    with open(test_path, "w") as f:
        for item in test_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return tmpdir


def test_train_model_produces_files():
    """训练应生成 tfidf.pkl 和 clf.pkl"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = _make_sample_data(tmpdir, "en")
        model_dir = os.path.join(tmpdir, "models")
        train_model(data_dir, model_dir, "en")
        assert os.path.exists(os.path.join(model_dir, "en_tfidf.pkl"))
        assert os.path.exists(os.path.join(model_dir, "en_clf.pkl"))


def test_evaluate_model_returns_metrics():
    """评估应返回 accuracy, precision, recall, f1"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = _make_sample_data(tmpdir, "en")
        model_dir = os.path.join(tmpdir, "models")
        train_model(data_dir, model_dir, "en")
        metrics = evaluate_model(data_dir, model_dir, "en")
        assert "accuracy" in metrics
        assert "f1" in metrics
        assert metrics["accuracy"] >= 0.5
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/cxw114/Desktop/idea && python3 -m pytest tests/harassment/test_classifier_train.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现训练脚本**

```python
# tonebarrier-server/harassment/train_classifier.py
"""训练骚扰检测分类器 — TF-IDF + LogisticRegression。"""
import json
import os
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score, f1_score, precision_score, recall_score


def load_data(data_dir, lang, split):
    """加载标准化 JSONL 数据。"""
    path = os.path.join(data_dir, f"{lang}_{split}.jsonl")
    texts = []
    labels = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line.strip())
            texts.append(obj["text"])
            labels.append(obj["label"])
    return texts, labels


def train_model(data_dir, model_dir, lang):
    """训练并保存模型。"""
    os.makedirs(model_dir, exist_ok=True)

    texts, labels = load_data(data_dir, lang, "train")

    if lang == "cn":
        tfidf = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            max_features=50000,
            sublinear_tf=True,
        )
    else:
        tfidf = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            max_features=50000,
            sublinear_tf=True,
        )

    X_train = tfidf.fit_transform(texts)

    clf = LogisticRegression(
        C=1.0,
        max_iter=1000,
        class_weight="balanced",
        solver="lbfgs",
    )
    clf.fit(X_train, labels)

    with open(os.path.join(model_dir, f"{lang}_tfidf.pkl"), "wb") as f:
        pickle.dump(tfidf, f)
    with open(os.path.join(model_dir, f"{lang}_clf.pkl"), "wb") as f:
        pickle.dump(clf, f)

    return {"samples": len(texts), "features": X_train.shape[1]}


def evaluate_model(data_dir, model_dir, lang):
    """在测试集上评估模型。"""
    with open(os.path.join(model_dir, f"{lang}_tfidf.pkl"), "rb") as f:
        tfidf = pickle.load(f)
    with open(os.path.join(model_dir, f"{lang}_clf.pkl"), "rb") as f:
        clf = pickle.load(f)

    texts, labels = load_data(data_dir, lang, "test")
    X_test = tfidf.transform(texts)
    preds = clf.predict(X_test)

    return {
        "accuracy": accuracy_score(labels, preds),
        "precision": precision_score(labels, preds, pos_label="harassment", zero_division=0),
        "recall": recall_score(labels, preds, pos_label="harassment", zero_division=0),
        "f1": f1_score(labels, preds, pos_label="harassment", zero_division=0),
        "report": classification_report(labels, preds, output_dict=True),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="harassment/data")
    parser.add_argument("--model-dir", default="harassment/models")
    parser.add_argument("--lang", choices=["cn", "en", "both"], default="both")
    args = parser.parse_args()

    langs = ["cn", "en"] if args.lang == "both" else [args.lang]
    for lang in langs:
        print(f"\n=== 训练 {lang} 模型 ===")
        info = train_model(args.data_dir, args.model_dir, lang)
        print(f"  样本数: {info['samples']}, 特征数: {info['features']}")
        metrics = evaluate_model(args.data_dir, args.model_dir, lang)
        print(f"  Accuracy: {metrics['accuracy']:.4f}")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall: {metrics['recall']:.4f}")
        print(f"  F1: {metrics['f1']:.4f}")
```

- [ ] **Step 4: 安装依赖**

```bash
pip3 install scikit-learn
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/cxw114/Desktop/idea && python3 -m pytest tests/harassment/test_classifier_train.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: 提交**

```bash
git add tonebarrier-server/harassment/train_classifier.py tests/harassment/test_classifier_train.py
git commit -m "feat(harassment): 训练脚本 — TF-IDF + LogisticRegression 分类器"
```

---

### Task 4: 执行训练 — 生成中英文模型文件

**Files:**
- Create: `tonebarrier-server/harassment/models/cn_tfidf.pkl`
- Create: `tonebarrier-server/harassment/models/cn_clf.pkl`
- Create: `tonebarrier-server/harassment/models/en_tfidf.pkl`
- Create: `tonebarrier-server/harassment/models/en_clf.pkl`

- [ ] **Step 1: 训练中英文模型**

```bash
cd /Users/cxw114/Desktop/idea/tonebarrier-server
python3 -m harassment.train_classifier --data-dir harassment/data --model-dir harassment/models --lang both
```

Expected:
```
=== 训练 cn 模型 ===
  样本数: ~27000, 特征数: 50000
  Accuracy: ≥0.80
  F1: ≥0.78

=== 训练 en 模型 ===
  样本数: ~25000, 特征数: 50000
  Accuracy: ≥0.82
  F1: ≥0.80
```

- [ ] **Step 2: 验证模型文件大小合理**

```bash
ls -lh tonebarrier-server/harassment/models/
```

Expected: 每个 pkl 文件 1-20MB

- [ ] **Step 3: 提交**

```bash
git add tonebarrier-server/harassment/models/
git commit -m "model(harassment): 训练中英文骚扰检测模型 (TF-IDF + LR)"
```

---

### Task 5: 检测引擎 — DFA 快筛 + 分类器推理

**Files:**
- Create: `tonebarrier-server/harassment/detector.py`
- Create: `tests/harassment/test_detector.py`

- [ ] **Step 1: 写测试**

```python
# tests/harassment/test_detector.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../tonebarrier-server'))

from harassment.detector import HarassmentDetector


def test_detect_obvious_harassment_en():
    """明显英文骚扰应被检出"""
    detector = HarassmentDetector()
    result = detector.detect("fuck you stupid idiot, I will kill you")
    assert result["is_harassment"] is True
    assert result["confidence"] >= 0.7
    assert result["lang"] == "en"


def test_detect_normal_en():
    """正常英文不应误报"""
    detector = HarassmentDetector()
    result = detector.detect("Hello, can you help me check my order status?")
    assert result["is_harassment"] is False


def test_detect_obvious_harassment_cn():
    """明显中文骚扰应被检出"""
    detector = HarassmentDetector()
    result = detector.detect("你这个傻逼客服，脑子有问题吧")
    assert result["is_harassment"] is True
    assert result["lang"] == "cn"


def test_detect_normal_cn():
    """正常中文不应误报"""
    detector = HarassmentDetector()
    result = detector.detect("请问我的快递什么时候到？")
    assert result["is_harassment"] is False


def test_detect_returns_sub_label():
    """检测结果应包含细粒度标签"""
    detector = HarassmentDetector()
    result = detector.detect("I'm going to find you and hurt you")
    assert "sub_label" in result


def test_detect_returns_dfa_hits():
    """检测结果应包含 DFA 命中词"""
    detector = HarassmentDetector()
    result = detector.detect("fuck this shit service")
    assert "dfa_hits" in result
    assert len(result["dfa_hits"]) > 0


def test_detect_empty_text():
    """空文本应返回 normal"""
    detector = HarassmentDetector()
    result = detector.detect("")
    assert result["is_harassment"] is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/cxw114/Desktop/idea && python3 -m pytest tests/harassment/test_detector.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现检测引擎**

```python
# tonebarrier-server/harassment/detector.py
"""骚扰检测引擎 — DFA 快筛 + 分类器推理。"""
import os
import pickle
import re
import sys

# 复用现有 DFA 引擎
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(SCRIPT_DIR)
SKILL_DIR = os.path.join(SERVER_DIR, "skill")
sys.path.insert(0, SKILL_DIR) if SKILL_DIR not in sys.path else None

MODEL_DIR = os.path.join(SCRIPT_DIR, "models")


def _detect_lang(text):
    """简单语言检测：含中文字符 → cn，否则 → en"""
    for ch in text:
        if '一' <= ch <= '鿿':
            return "cn"
    return "en"


def _load_dfa_trie(path):
    """加载 DFA 字典树。"""
    root = {}
    if not os.path.exists(path):
        return root
    with open(path, encoding="utf-8") as f:
        for line in f:
            word = line.strip().lower()
            if not word or len(word) < 2 or word.isdigit() or word.startswith('#'):
                continue
            node = root
            for ch in word:
                if ch not in node:
                    node[ch] = {}
                node = node[ch]
            node["__END__"] = word
    return root


def _dfa_search(root, text):
    """DFA 搜索，返回命中词列表。"""
    text_lower = text.lower()
    hits = []
    i = 0
    while i < len(text_lower):
        node = root
        j = i
        found = None
        while j < len(text_lower) and text_lower[j] in node:
            node = node[text_lower[j]]
            j += 1
            if "__END__" in node:
                found = node["__END__"]
        if found:
            hits.append(found)
            i = j
        else:
            i += 1
    return list(set(hits))


class HarassmentDetector:
    """骚扰检测器。初始化时加载模型和 DFA 词典。"""

    def __init__(self, model_dir=None):
        if model_dir is None:
            model_dir = MODEL_DIR

        self._models = {}
        for lang in ["cn", "en"]:
            tfidf_path = os.path.join(model_dir, f"{lang}_tfidf.pkl")
            clf_path = os.path.join(model_dir, f"{lang}_clf.pkl")
            if os.path.exists(tfidf_path) and os.path.exists(clf_path):
                with open(tfidf_path, "rb") as f:
                    tfidf = pickle.load(f)
                with open(clf_path, "rb") as f:
                    clf = pickle.load(f)
                self._models[lang] = {"tfidf": tfidf, "clf": clf}

        # 加载 DFA 词典
        ref_dir = os.path.join(SERVER_DIR, "skill", "references")
        self._dfa_cn = _load_dfa_trie(os.path.join(ref_dir, "profanity_dict.txt"))
        self._dfa_en = _load_dfa_trie(os.path.join(ref_dir, "profanity_en.txt"))

    def detect(self, text: str) -> dict:
        """检测文本是否为骚扰。返回结构化结果。"""
        if not text or not text.strip():
            return {
                "is_harassment": False,
                "confidence": 0.0,
                "label": "normal",
                "sub_label": None,
                "lang": "en",
                "dfa_hits": [],
            }

        lang = _detect_lang(text)

        # DFA 快筛
        dfa_root = self._dfa_cn if lang == "cn" else self._dfa_en
        dfa_hits = _dfa_search(dfa_root, text)

        # 分类器推理
        confidence = 0.0
        clf_label = "normal"
        if lang in self._models:
            model = self._models[lang]
            X = model["tfidf"].transform([text])
            proba = model["clf"].predict_proba(X)[0]
            classes = list(model["clf"].classes_)
            if "harassment" in classes:
                h_idx = classes.index("harassment")
                confidence = float(proba[h_idx])
                clf_label = "harassment" if confidence >= 0.5 else "normal"

        # 综合判定：DFA 命中 ≥2 个脏话词直接判定骚扰
        if len(dfa_hits) >= 2 and confidence < 0.5:
            confidence = max(confidence, 0.7)
            clf_label = "harassment"

        # 推断子标签
        sub_label = self._infer_sub_label(text, dfa_hits, lang) if clf_label == "harassment" else None

        return {
            "is_harassment": clf_label == "harassment",
            "confidence": round(confidence, 4),
            "label": clf_label,
            "sub_label": sub_label,
            "lang": lang,
            "dfa_hits": dfa_hits,
        }

    def _infer_sub_label(self, text, dfa_hits, lang):
        """基于规则推断细粒度子标签。"""
        text_lower = text.lower()

        # 威胁关键词
        threat_kw = ["kill", "die", "hurt", "murder", "stab", "shoot",
                     "杀", "死", "弄死", "打死", "砍"]
        if any(kw in text_lower for kw in threat_kw):
            return "threat"

        # 性骚扰关键词
        sexual_kw = ["sex", "rape", "nude", "naked", "pussy", "dick",
                     "操", "干你", "上你", "奸"]
        if any(kw in text_lower for kw in sexual_kw):
            return "sexual"

        # 歧视关键词
        discrim_kw = ["nigger", "chink", "faggot", "retard",
                      "黑鬼", "支那", "残废"]
        if any(kw in text_lower for kw in discrim_kw):
            return "discrimination"

        # 默认为侮辱
        return "insult"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/cxw114/Desktop/idea && python3 -m pytest tests/harassment/test_detector.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: 提交**

```bash
git add tonebarrier-server/harassment/detector.py tests/harassment/test_detector.py
git commit -m "feat(harassment): 检测引擎 — DFA 快筛 + 分类器推理"
```

---

### Task 6: API 集成 — 新增 /api/harassment 端点

**Files:**
- Modify: `tonebarrier-server/server.py`
- Create: `tests/harassment/test_api.py`

- [ ] **Step 1: 写测试**

```python
# tests/harassment/test_api.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../tonebarrier-server'))

import pytest
from httpx import AsyncClient, ASGITransport
from server import app


@pytest.mark.asyncio
async def test_harassment_api_detects_harassment():
    """POST /api/harassment 应检出骚扰文本"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/harassment", json={"text": "fuck you stupid bitch"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_harassment"] is True
    assert "confidence" in data
    assert "dfa_hits" in data


@pytest.mark.asyncio
async def test_harassment_api_normal_text():
    """POST /api/harassment 正常文本不应误报"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/harassment", json={"text": "请帮我查一下订单"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_harassment"] is False


@pytest.mark.asyncio
async def test_harassment_api_empty_text():
    """POST /api/harassment 空文本应返回 400"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/harassment", json={"text": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_harassment"] is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/cxw114/Desktop/idea && python3 -m pytest tests/harassment/test_api.py -v`
Expected: FAIL — 路由不存在

- [ ] **Step 3: 在 server.py 中新增路由**

在 `tonebarrier-server/server.py` 中添加：

```python
# 在文件顶部 import 区域添加
from harassment.detector import HarassmentDetector

# 在 app 初始化后添加全局检测器实例
_harassment_detector = None

def get_harassment_detector():
    global _harassment_detector
    if _harassment_detector is None:
        _harassment_detector = HarassmentDetector()
    return _harassment_detector

# 新增路由（放在现有路由之后）
@app.post("/api/harassment")
async def api_harassment(request: Request):
    """骚扰检测 API。"""
    body = await request.json()
    text = body.get("text", "").strip()

    detector = get_harassment_detector()
    result = detector.detect(text)

    return JSONResponse(content=result)
```

- [ ] **Step 4: 安装测试依赖**

```bash
pip3 install httpx pytest-asyncio
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/cxw114/Desktop/idea && python3 -m pytest tests/harassment/test_api.py -v`
Expected: 3 tests PASS

- [ ] **Step 6: 提交**

```bash
git add tonebarrier-server/server.py tests/harassment/test_api.py
git commit -m "feat(harassment): 新增 /api/harassment 端点"
```

---

### Task 7: 前端 UI — 新增骚扰检测 Tab

**Files:**
- Modify: `tonebarrier-server/templates/index.html`
- Modify: `tonebarrier-server/static/app.js`（如存在）

- [ ] **Step 1: 在 index.html 中新增 Tab**

在现有 Tab 导航区域添加：

```html
<!-- 骚扰检测 Tab 按钮 -->
<button class="tab-btn" data-tab="harassment" data-i18n="tab_harassment">骚扰检测</button>
```

新增 Tab 内容面板：

```html
<div id="tab-harassment" class="tab-panel" style="display:none;">
  <h3 data-i18n="harassment_title">客户骚扰检测</h3>
  <p data-i18n="harassment_desc">检测客户消息是否包含骚扰、威胁、侮辱等攻击性内容。</p>
  <textarea id="harassment-input" rows="5" placeholder="输入客户消息..."
            data-i18n-placeholder="harassment_placeholder"></textarea>
  <button id="harassment-btn" onclick="detectHarassment()" data-i18n="btn_detect">检测</button>
  <div id="harassment-result" class="result-box" style="display:none;">
    <div class="result-header">
      <span id="harassment-badge" class="badge"></span>
      <span id="harassment-confidence"></span>
    </div>
    <div id="harassment-details"></div>
  </div>
</div>
```

- [ ] **Step 2: 添加 JS 检测函数**

```javascript
async function detectHarassment() {
  const text = document.getElementById('harassment-input').value.trim();
  if (!text) return;

  const btn = document.getElementById('harassment-btn');
  btn.disabled = true;
  btn.textContent = '检测中...';

  try {
    const resp = await fetch('/api/harassment', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    });
    const data = await resp.json();

    const resultBox = document.getElementById('harassment-result');
    const badge = document.getElementById('harassment-badge');
    const confidence = document.getElementById('harassment-confidence');
    const details = document.getElementById('harassment-details');

    resultBox.style.display = 'block';

    if (data.is_harassment) {
      badge.textContent = '⚠️ 骚扰';
      badge.className = 'badge badge-danger';
      confidence.textContent = `置信度: ${(data.confidence * 100).toFixed(1)}%`;
      let detailHtml = `<p>类型: ${data.sub_label || '一般'}</p>`;
      if (data.dfa_hits && data.dfa_hits.length > 0) {
        detailHtml += `<p>命中关键词: ${data.dfa_hits.map(w => '<code>' + escapeHtml(w) + '</code>').join(', ')}</p>`;
      }
      details.innerHTML = detailHtml;
    } else {
      badge.textContent = '✅ 正常';
      badge.className = 'badge badge-safe';
      confidence.textContent = '';
      details.innerHTML = '<p>未检测到骚扰内容。</p>';
    }
  } catch (e) {
    console.error(e);
  } finally {
    btn.disabled = false;
    btn.textContent = '检测';
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
```

- [ ] **Step 3: 添加 i18n 翻译条目**

在 i18n 字典中添加：

```javascript
// 中文
tab_harassment: "骚扰检测",
harassment_title: "客户骚扰检测",
harassment_desc: "检测客户消息是否包含骚扰、威胁、侮辱等攻击性内容。",
harassment_placeholder: "输入客户消息...",
btn_detect: "检测",

// 英文
tab_harassment: "Harassment Detection",
harassment_title: "Customer Harassment Detection",
harassment_desc: "Detect if customer messages contain harassment, threats, insults, or other aggressive content.",
harassment_placeholder: "Enter customer message...",
btn_detect: "Detect",
```

- [ ] **Step 4: 本地测试 UI**

```bash
cd /Users/cxw114/Desktop/idea/tonebarrier-server
python3 server.py &
# 浏览器打开 http://localhost:7860
# 切换到"骚扰检测" Tab
# 输入 "你这个傻逼客服" → 应显示 ⚠️ 骚扰
# 输入 "请帮我查订单" → 应显示 ✅ 正常
kill %1
```

- [ ] **Step 5: 提交**

```bash
git add tonebarrier-server/templates/ tonebarrier-server/static/
git commit -m "feat(harassment): 前端骚扰检测 Tab UI"
```

---

### Task 8: 更新 requirements.txt 和 Dockerfile

**Files:**
- Modify: `tonebarrier-server/requirements.txt`
- Modify: `tonebarrier-server/Dockerfile`

- [ ] **Step 1: 更新 requirements.txt**

在 `tonebarrier-server/requirements.txt` 中添加：

```
scikit-learn==1.6.1
```

- [ ] **Step 2: 更新 Dockerfile**

确保 Dockerfile 中 COPY 包含 harassment 目录：

```dockerfile
COPY harassment/ ./harassment/
```

- [ ] **Step 3: 本地 Docker 构建验证**

```bash
cd /Users/cxw114/Desktop/idea/tonebarrier-server
docker build -t tonebarrier-test .
docker run --rm -p 7860:7860 tonebarrier-test &
sleep 3
curl -X POST http://localhost:7860/api/harassment \
  -H "Content-Type: application/json" \
  -d '{"text": "fuck you idiot"}'
# Expected: {"is_harassment": true, ...}
docker stop $(docker ps -q --filter ancestor=tonebarrier-test)
```

- [ ] **Step 4: 提交**

```bash
git add tonebarrier-server/requirements.txt tonebarrier-server/Dockerfile
git commit -m "build(harassment): 更新依赖和 Docker 配置"
```

---

### Task 9: 端到端集成测试 + 性能基准

**Files:**
- Create: `tests/harassment/test_e2e.py`

- [ ] **Step 1: 写端到端测试**

```python
# tests/harassment/test_e2e.py
"""端到端集成测试 — 验证完整检测管道。"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../tonebarrier-server'))

from harassment.detector import HarassmentDetector


# 测试用例：(text, expected_harassment, description)
TEST_CASES = [
    # 明确骚扰
    ("你他妈的是不是脑子有病", True, "中文辱骂"),
    ("fuck you piece of shit", True, "英文辱骂"),
    ("I'm going to find where you live and kill you", True, "英文威胁"),
    ("你这个傻逼客服去死吧", True, "中文威胁+辱骂"),
    ("Women like you should stay in the kitchen", True, "英文歧视"),

    # 正常文本
    ("请问我的订单什么时候发货？", False, "中文正常咨询"),
    ("Can you help me with a refund?", False, "英文正常咨询"),
    ("我对这个产品不太满意，想退货", False, "中文不满但无骚扰"),
    ("The delivery was late, I'm disappointed", False, "英文不满但无骚扰"),
    ("你们的服务效率太低了", False, "中文抱怨但无骚扰"),

    # 边界情况
    ("这个产品真是垃圾", False, "中文负面评价非骚扰"),
    ("This product is terrible", False, "英文负面评价非骚扰"),
]


def test_e2e_accuracy():
    """端到端准确率应 ≥ 80%"""
    detector = HarassmentDetector()
    correct = 0
    for text, expected, desc in TEST_CASES:
        result = detector.detect(text)
        if result["is_harassment"] == expected:
            correct += 1
        else:
            print(f"  MISS: [{desc}] '{text[:30]}...' → got {result['is_harassment']}, expected {expected}")
    accuracy = correct / len(TEST_CASES)
    print(f"\n端到端准确率: {correct}/{len(TEST_CASES)} = {accuracy:.1%}")
    assert accuracy >= 0.8, f"准确率 {accuracy:.1%} 低于 80% 阈值"


def test_e2e_latency():
    """单次检测延迟应 < 50ms"""
    detector = HarassmentDetector()
    # 预热
    detector.detect("test warmup")

    latencies = []
    for text, _, _ in TEST_CASES:
        start = time.time()
        detector.detect(text)
        latencies.append((time.time() - start) * 1000)

    avg_ms = sum(latencies) / len(latencies)
    max_ms = max(latencies)
    print(f"\n延迟统计: avg={avg_ms:.1f}ms, max={max_ms:.1f}ms")
    assert avg_ms < 50, f"平均延迟 {avg_ms:.1f}ms 超过 50ms 阈值"
```

- [ ] **Step 2: 运行端到端测试**

Run: `cd /Users/cxw114/Desktop/idea && python3 -m pytest tests/harassment/test_e2e.py -v -s`
Expected: 2 tests PASS, 准确率 ≥ 80%, 延迟 < 50ms

- [ ] **Step 3: 提交**

```bash
git add tests/harassment/test_e2e.py
git commit -m "test(harassment): 端到端集成测试 + 性能基准"
```

---

### Task 10: 推送到 GitHub 和 HF Spaces

**Files:**
- Modify: `tonebarrier-server/README.md`

- [ ] **Step 1: 更新 README**

在 `tonebarrier-server/README.md` 中添加骚扰检测模块说明：

```markdown
## 骚扰检测模块

### API

```
POST /api/harassment
Content-Type: application/json

{"text": "客户消息文本"}
```

### 响应

```json
{
  "is_harassment": true,
  "confidence": 0.92,
  "label": "harassment",
  "sub_label": "insult",
  "lang": "cn",
  "dfa_hits": ["傻逼"]
}
```

### 标签说明

| 标签 | 含义 |
|------|------|
| `insult` | 侮辱谩骂 |
| `threat` | 威胁恐吓 |
| `discrimination` | 歧视偏见 |
| `sexual` | 性骚扰 |
| `general` | 一般骚扰 |

### 技术指标

- 中文 F1: ≥0.78
- 英文 F1: ≥0.80
- 单次推理延迟: <50ms
- 零 GPU 依赖（TF-IDF + LogisticRegression）
```

- [ ] **Step 2: 推送到 GitHub**

```bash
cd /Users/cxw114/Desktop/idea
git push origin main
```

- [ ] **Step 3: 推送到 HF Spaces**

```bash
cd /Users/cxw114/Desktop/idea/tonebarrier-server
git add -A
git commit -m "feat: 新增骚扰检测模块 v1.0"
git push hf main
```

- [ ] **Step 4: 验证线上部署**

```bash
curl -X POST https://pzr114514-skills-demo.hf.space/api/harassment \
  -H "Content-Type: application/json" \
  -d '{"text": "fuck you stupid idiot"}'
```

Expected: `{"is_harassment": true, ...}`

---

## 风险与注意事项

1. **数据不平衡**: ProsocialDialog 数据量远大于其他数据集，已限制为 20000 条。训练时使用 `class_weight="balanced"` 缓解。
2. **模型体积**: pkl 文件可能较大（10-20MB），需确认 HF Spaces 的存储限制。
3. **误报控制**: 负面评价（"产品垃圾"）不应被判为骚扰。分类器需要足够的 normal 负面样本。
4. **隐私**: 训练数据中可能包含真实用户信息，模型部署后不应暴露训练数据。
5. **scikit-learn 版本**: 训练和推理环境的 scikit-learn 版本必须一致，否则 pkl 反序列化会失败。

