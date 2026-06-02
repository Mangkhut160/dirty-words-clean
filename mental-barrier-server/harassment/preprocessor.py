"""将 6 个异构数据集统一为标准 JSONL 格式。

标准输出格式 (每行一个 JSON):
{"text": "原始文本", "label": "harassment", "sub_label": "insult", "source": "cold", "lang": "cn"}
"""
import csv
import json
import os

DATASETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../datasets/harassment')


def preprocess_cold(rows):
    """处理 COLD 数据集行（dict 列表，含 label/TEXT 字段）。
    label=1 → harassment/insult, label=0 → normal"""
    for row in rows:
        text = row.get("TEXT", "").strip()
        if not text:
            continue
        label = "harassment" if str(row["label"]).strip() == "1" else "normal"
        sub_label = "insult" if label == "harassment" else None
        yield {
            "text": text,
            "label": label,
            "sub_label": sub_label,
            "source": "cold",
            "lang": "cn",
        }


def preprocess_diasafety(items):
    """处理 DiaSafety JSON 数组。context 是用户发言。
    Offending User + Unsafe → harassment/insult
    其他 Unsafe → harassment/general
    Safe → normal"""
    for item in items:
        text = item.get("context", "").strip()
        if not text:
            continue
        is_unsafe = item.get("label") == "Unsafe"
        is_offending = item.get("category") == "Offending User"
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
            "text": text,
            "label": label,
            "sub_label": sub_label,
            "source": "diasafety",
            "lang": "en",
        }

# PLACEHOLDER_TASK1_CONTINUE

def preprocess_beavertails(items):
    """处理 BeaverTails JSONL 条目。prompt 是用户攻击性输入。
    hate_speech → insult, violence → threat, discrimination → discrimination,
    sexually_explicit → sexual, is_safe → normal"""
    for item in items:
        cat = item.get("category", {})
        has_hate = cat.get("hate_speech,offensive_language", False)
        has_violence = cat.get("violence,aiding_and_abetting,incitement", False)
        has_discrimination = cat.get("discrimination,stereotype,injustice", False)
        has_sexual = cat.get("sexually_explicit,adult_content", False)

        text = item.get("prompt", "").strip()
        if not text:
            continue

        if has_violence:
            yield {"text": text, "label": "harassment",
                   "sub_label": "threat", "source": "beavertails", "lang": "en"}
        elif has_hate:
            yield {"text": text, "label": "harassment",
                   "sub_label": "insult", "source": "beavertails", "lang": "en"}
        elif has_discrimination:
            yield {"text": text, "label": "harassment",
                   "sub_label": "discrimination", "source": "beavertails", "lang": "en"}
        elif has_sexual:
            yield {"text": text, "label": "harassment",
                   "sub_label": "sexual", "source": "beavertails", "lang": "en"}
        elif item.get("is_safe", True):
            yield {"text": text, "label": "normal",
                   "sub_label": None, "source": "beavertails", "lang": "en"}


def preprocess_edos(items):
    """处理 EDOS CSV 行。
    sexist + threats → threat, sexist + derogation/animosity → discrimination,
    其他 sexist → general, not sexist → normal"""
    for item in items:
        text = item.get("text", "").strip()
        if not text:
            continue
        if item.get("label_sexist") == "sexist":
            cat = item.get("label_category", "")
            if "threats" in cat:
                sub_label = "threat"
            elif "derogation" in cat or "animosity" in cat:
                sub_label = "discrimination"
            else:
                sub_label = "general"
            yield {"text": text, "label": "harassment",
                   "sub_label": sub_label, "source": "edos", "lang": "en"}
        else:
            yield {"text": text, "label": "normal",
                   "sub_label": None, "source": "edos", "lang": "en"}


def preprocess_prosocial(items):
    """处理 ProsocialDialog JSONL。context 是用户发言。
    __needs_intervention__ → harassment/general
    __casual__ → normal"""
    for item in items:
        text = item.get("context", "").strip()
        if not text:
            continue
        safety = item.get("safety_label", "")
        if safety == "__needs_intervention__":
            yield {"text": text, "label": "harassment",
                   "sub_label": "general", "source": "prosocial", "lang": "en"}
        elif safety == "__casual__":
            yield {"text": text, "label": "normal",
                   "sub_label": None, "source": "prosocial", "lang": "en"}

# PLACEHOLDER_TASK1_IO

def load_cold_csv(path):
    """从 CSV 文件加载 COLD 数据。"""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_jsonl(path):
    """加载 JSONL 文件（每行一个 JSON）。"""
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_json(path):
    """加载 JSON 文件（整体是一个 JSON 数组/对象）。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_all(output_dir, datasets_dir=None):
    """从原始数据集构建标准化训练/测试数据。

    Args:
        output_dir: 输出目录
        datasets_dir: 原始数据集根目录（默认 datasets/harassment）

    Returns:
        dict: {"cn_total": int, "en_total": int}
    """
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

    # ProsocialDialog (英文) — 限制 20000 条避免数据不平衡
    path = os.path.join(datasets_dir, "prosocial", "train.json")
    if os.path.exists(path):
        items = []
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


