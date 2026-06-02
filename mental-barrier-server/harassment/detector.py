"""骚扰检测引擎 — DFA 快筛 + 分类器推理。

双层架构：
1. DFA 关键词快筛：命中 ≥2 个脏话词直接判定骚扰
2. TF-IDF + LR 分类器：覆盖隐晦骚扰

单次推理延迟 <50ms（CPU）。
"""
import os
import pickle
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(SCRIPT_DIR)
MODEL_DIR = os.path.join(SCRIPT_DIR, "models")

# 复用现有 DFA 引擎的词典路径
SKILL_REF_DIR = os.path.join(SERVER_DIR, "skill", "references")


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


def _is_alpha_boundary(text, start, end):
    """纯英文词边界检查，防止子串误报。"""
    word = text[start:end]
    if not word.isascii() or not word.isalpha():
        return True
    if start > 0 and text[start - 1].isascii() and text[start - 1].isalpha():
        return False
    if end < len(text) and text[end].isascii() and text[end].isalpha():
        return False
    return True


def _dfa_search(root, text):
    """DFA 搜索，返回命中词列表（去重）。"""
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
                if _is_alpha_boundary(text_lower, i, j):
                    found = node["__END__"]
        if found:
            hits.append(found)
            i = j
        else:
            i += 1
    return list(set(hits))


class HarassmentDetector:
    """骚扰检测器。初始化时加载模型和 DFA 词典。

    使用方式:
        detector = HarassmentDetector()
        result = detector.detect("你这个傻逼")
        # result = {"is_harassment": True, "confidence": 0.95, ...}
    """

    def __init__(self, model_dir=None, ref_dir=None, strict=True):
        if model_dir is None:
            model_dir = MODEL_DIR
        if ref_dir is None:
            ref_dir = SKILL_REF_DIR

        # 加载分类模型
        self._models = {}
        missing_models = []
        for lang in ["cn", "en"]:
            tfidf_path = os.path.join(model_dir, f"{lang}_tfidf.pkl")
            clf_path = os.path.join(model_dir, f"{lang}_clf.pkl")
            if os.path.exists(tfidf_path) and os.path.exists(clf_path):
                with open(tfidf_path, "rb") as f:
                    tfidf = pickle.load(f)
                with open(clf_path, "rb") as f:
                    clf = pickle.load(f)
                self._models[lang] = {"tfidf": tfidf, "clf": clf}
            else:
                missing_models.append(f"{lang}_tfidf.pkl / {lang}_clf.pkl")

        # 加载 DFA 词典
        cn_dict_path = os.path.join(ref_dir, "profanity_dict.txt")
        en_dict_path = os.path.join(ref_dir, "profanity_en.txt")
        self._dfa_cn = _load_dfa_trie(cn_dict_path)
        self._dfa_en = _load_dfa_trie(en_dict_path)

        missing_dicts = []
        if not os.path.exists(cn_dict_path):
            missing_dicts.append("profanity_dict.txt")
        if not os.path.exists(en_dict_path):
            missing_dicts.append("profanity_en.txt")

        # strict 模式下缺失关键文件则 fail fast
        if strict and (missing_models or missing_dicts):
            parts = []
            if missing_models:
                parts.append(f"模型文件缺失: {', '.join(missing_models)} (目录: {model_dir})")
            if missing_dicts:
                parts.append(f"词典文件缺失: {', '.join(missing_dicts)} (目录: {ref_dir})")
            raise FileNotFoundError(
                "骚扰检测器初始化失败 — " + "; ".join(parts)
            )

    def detect(self, text: str) -> dict:
        """检测文本是否为骚扰。

        Args:
            text: 待检测文本

        Returns:
            dict: {
                "is_harassment": bool,
                "confidence": float (0-1),
                "label": "harassment" | "normal",
                "sub_label": str | None,
                "lang": "cn" | "en",
                "dfa_hits": list[str],
            }
        """
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
        # 中文路径下额外扫一遍英文词典：中英混合文本（如 "这个 service 真是 garbage"）
        # 常含英文脏话，中文词典覆盖不到，需用英文词典补充
        if lang == "cn":
            dfa_hits = _dfa_search(self._dfa_cn, text)
            en_extra = _dfa_search(self._dfa_en, text)
            for w in en_extra:
                if w not in dfa_hits:
                    dfa_hits.append(w)
        else:
            dfa_hits = _dfa_search(self._dfa_en, text)

        # 排除轻度粗口（感叹词，非骚扰性质）和通用投诉词（产品/服务差评，非指向人的骚扰）
        MILD_WORDS = {"damn", "hell", "crap", "bloody", "dammit", "damnit"}
        GENERIC_COMPLAINT_WORDS = {"垃圾", "garbage"}
        complaint_only_hits = bool(dfa_hits) and all(
            w in MILD_WORDS or w in GENERIC_COMPLAINT_WORDS for w in dfa_hits
        )
        severe_hits = [w for w in dfa_hits if w not in MILD_WORDS and w not in GENERIC_COMPLAINT_WORDS]

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

        if complaint_only_hits:
            confidence = min(confidence, 0.49)
            clf_label = "normal"

        # 综合判定：仅用明确骚扰词覆盖分类器结果；通用投诉词不覆盖，避免“产品真垃圾”误判为骚扰。
        if len(severe_hits) >= 1 and clf_label != "harassment":
            confidence = max(confidence, 0.7)
            clf_label = "harassment"

        # 推断子标签
        sub_label = None
        if clf_label == "harassment":
            sub_label = self._infer_sub_label(text, dfa_hits, lang)

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
                     "find you", "come for you",
                     "杀", "死", "弄死", "打死", "砍", "找你"]
        if any(kw in text_lower for kw in threat_kw):
            return "threat"

        # 性骚扰关键词
        sexual_kw = ["sex", "rape", "nude", "naked", "pussy", "dick",
                     "tits", "boobs",
                     "操你", "干你", "上你", "奸", "骚货"]
        if any(kw in text_lower for kw in sexual_kw):
            return "sexual"

        # 歧视关键词
        discrim_kw = ["nigger", "chink", "faggot", "retard", "tranny",
                      "黑鬼", "支那", "残废", "弱智"]
        if any(kw in text_lower for kw in discrim_kw):
            return "discrimination"

        # 默认为侮辱
        return "insult"

