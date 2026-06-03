"""训练骚扰检测分类器 — TF-IDF + LogisticRegression。

零 GPU 依赖，适合 HF Spaces 免费 CPU 实例。
中文使用 char_wb ngram(2,4)，英文使用 word ngram(1,2)。
"""
import json
import os
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)


def load_data(data_dir, lang, split):
    """加载标准化 JSONL 数据。

    Returns:
        (texts, labels): 文本列表和标签列表
    """
    path = os.path.join(data_dir, f"{lang}_{split}.jsonl")
    texts = []
    labels = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            texts.append(obj["text"])
            labels.append(obj["label"])
    return texts, labels


def train_model(data_dir, model_dir, lang):
    """训练并保存模型。

    Args:
        data_dir: 包含 {lang}_train.jsonl 的目录
        model_dir: 模型输出目录
        lang: "cn" 或 "en"

    Returns:
        dict: {"samples": int, "features": int}
    """
    os.makedirs(model_dir, exist_ok=True)

    texts, labels = load_data(data_dir, lang, "train")

    # 中文用字符级 ngram，英文用词级 ngram
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
    """在测试集上评估模型。

    Returns:
        dict: accuracy, precision, recall, f1, report
    """
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
    parser = argparse.ArgumentParser(description="训练骚扰检测分类器")
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
