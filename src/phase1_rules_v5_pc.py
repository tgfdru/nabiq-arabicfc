"""
phase1_rules_v5_pc.py
NABIQ-v2-PC pipeline.

Input:  data/processed_latest/  (train + dev)
Output: outputs/submissions/nabiq_v2_pc_stage*.jsonl

Stages
------
Stage 1 – Run the full v1 pipeline (router + nearest-args + direct-extract +
           conservative post-process + none-threshold) on processed_latest data.
Stage 2 – Apply normalization maps: canonical currency codes, language codes,
           zakat types, termination types, quran search types, country names.
Stage 3 – Improved per-tool rule fixes on top of stage 2.

Evaluation is run after each stage against:
  data/processed_latest/dev_gold_track_a.jsonl
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

TRAIN_PATH = PROJECT_ROOT / "data" / "processed_latest" / "train_processed.jsonl"
DEV_PATH   = PROJECT_ROOT / "data" / "processed_latest" / "dev_processed.jsonl"
GOLD_PATH  = PROJECT_ROOT / "data" / "processed_latest" / "dev_gold_track_a.jsonl"
SUBS_DIR   = PROJECT_ROOT / "outputs" / "submissions"
REPS_DIR   = PROJECT_ROOT / "outputs" / "reports"

STAGE1_PATH = SUBS_DIR / "nabiq_v2_pc_stage1.jsonl"
STAGE2_PATH = SUBS_DIR / "nabiq_v2_pc_stage2.jsonl"
STAGE3_PATH = SUBS_DIR / "nabiq_v2_pc_stage3.jsonl"
FINAL_PATH  = SUBS_DIR / "nabiq_v2_pc.jsonl"

# ── Normalisation maps ─────────────────────────────────────────────────────────
from normalization_maps_v2_pc import (
    CURRENCY_TO_ISO,
    LANGUAGE_TO_ISO,
    ZAKAT_TYPE_MAP,
    TERMINATION_TYPE_MAP,
    QURAN_SEARCH_TYPE_MAP,
    COUNTRY_TO_ARABIC,
)

# ── Arabic text helpers ────────────────────────────────────────────────────────
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

def norm_text(text: Any) -> str:
    text = str(text or "").translate(ARABIC_DIGITS)
    text = re.sub(r"[ً-ٰٟ]", "", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()

def has_any(text: str, keywords: list[str]) -> bool:
    n = norm_text(text)
    return any(norm_text(k) in n for k in keywords)

def extract_numbers(text: str) -> list[float]:
    normalized = str(text or "").translate(ARABIC_DIGITS).replace(",", "")
    values = []
    for m in re.finditer(r"\d+(?:\.\d+)?", normalized):
        try: values.append(float(m.group(0)))
        except ValueError: pass
    NUMBER_WORDS = {
        "واحد": 1.0, "واحده": 1.0, "اثنين": 2.0, "اتنين": 2.0, "ثنين": 2.0,
        "ثلاث": 3.0, "ثلاثه": 3.0, "تلاته": 3.0, "اربعه": 4.0,
        "خمسه": 5.0, "سته": 6.0, "سبعه": 7.0, "ثمانيه": 8.0,
        "تسعه": 9.0, "عشره": 10.0,
    }
    n = norm_text(text)
    for word, val in NUMBER_WORDS.items():
        if word in n:
            values.append(val)
    return values

def extract_first_id(text: str) -> str | None:
    n = str(text or "").translate(ARABIC_DIGITS)
    m = re.search(r"\d{3,}", n)
    return m.group(0) if m else None

def extract_iban(text: str) -> str | None:
    n = str(text or "").translate(ARABIC_DIGITS)
    for pat in [r"\b[A-Z]{2}\d{2}[A-Z0-9]{8,}\b", r"\b[A-Z]{2}\d[A-Z0-9]{8,}\b", r"\bIBAN[A-Z0-9]*\b"]:
        m = re.search(pat, n, flags=re.IGNORECASE)
        if m: return m.group(0)
    return None

# ── I/O ────────────────────────────────────────────────────────────────────────
def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def save_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

# ── Router + retriever (from nearest_args_baseline) ───────────────────────────
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline

def build_router_text(row: dict[str, Any]) -> str:
    user_text = row.get("user_text") or ""
    dialect = row.get("dialect") or ""
    tool_descriptions = []
    for tool in row.get("available_tools", []):
        name = tool.get("name") or ""
        description = tool.get("description") or ""
        params = tool.get("parameters") or {}
        param_names = " ".join(params.keys())
        tool_descriptions.append(f"{name} {description} {param_names}")
    return f"USER:\n{user_text}\n\nDIALECT:\n{dialect}\n\nAVAILABLE_TOOLS:\n{chr(10).join(tool_descriptions)}".strip()

def build_retrieval_text(row: dict[str, Any]) -> str:
    return f"{row.get('dialect','')}\n{row.get('user_text','')}".strip()

def get_available_tool_names(row: dict[str, Any]) -> set[str]:
    names = {t.get("name") for t in row.get("available_tools", []) if t.get("name")}
    names.add("none")
    return names

def train_router(train_rows: list[dict[str, Any]]) -> Pipeline:
    x = [build_router_text(r) for r in train_rows]
    y = [r.get("tool_called", "none") for r in train_rows]
    model = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=2, max_features=120000)),
        ("clf",   LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs")),
    ])
    print("  Training router...")
    model.fit(x, y)
    return model

def predict_tool(model: Pipeline, row: dict[str, Any]) -> str:
    text = build_router_text(row)
    available = get_available_tool_names(row)
    clf = model.named_steps["clf"]
    probs = model.predict_proba([text])[0]
    for label, _ in sorted(zip(clf.classes_, probs), key=lambda x: -x[1]):
        if label in available:
            return label
    return "none"

class NearestArgRetriever:
    def __init__(self):
        self.tool_rows: dict[str, list] = defaultdict(list)
        self.vecs: dict[str, TfidfVectorizer] = {}
        self.mats: dict[str, Any] = {}

    def fit(self, train_rows: list[dict[str, Any]]) -> None:
        for row in train_rows:
            self.tool_rows[row.get("tool_called", "none")].append(row)
        print(f"  Training retrievers for {len(self.tool_rows)} tools...")
        for tool, rows in self.tool_rows.items():
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2,5), min_df=1, max_features=80000)
            mat = vec.fit_transform([build_retrieval_text(r) for r in rows])
            self.vecs[tool] = vec; self.mats[tool] = mat

    def predict(self, row: dict[str, Any], tool: str) -> dict[str, Any]:
        if tool == "none" or tool not in self.tool_rows:
            return {}
        q = self.vecs[tool].transform([build_retrieval_text(row)])
        scores = cosine_similarity(q, self.mats[tool])[0]
        best = self.tool_rows[tool][int(scores.argmax())]
        args = best.get("arguments") or {}
        return {k: v for k, v in args.items() if v is not None}

# ── Gazetteer ──────────────────────────────────────────────────────────────────
def build_gazetteer(train_rows: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    raw: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for row in train_rows:
        tool = row.get("tool_called")
        for k, v in (row.get("arguments") or {}).items():
            if isinstance(v, str) and len(v.strip()) >= 2:
                raw[tool][k].add(v.strip())
    out: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for tool, arg_map in raw.items():
        for k, vals in arg_map.items():
            out[tool][k] = sorted(vals, key=lambda v: len(norm_text(v)), reverse=True)
    return out

def gazetteer_match(text: str, candidates: list[str]) -> str | None:
    n = norm_text(text)
    for c in candidates:
        if len(norm_text(c)) >= 2 and norm_text(c) in n:
            return c
    return None

# ── Schema helpers ─────────────────────────────────────────────────────────────
def get_schema_args(row: dict[str, Any], tool: str) -> set[str]:
    for t in row.get("available_tools", []):
        if t.get("name") == tool:
            return set((t.get("parameters") or {}).keys())
    return set()

def clean_to_schema(row: dict[str, Any], tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool == "none": return {}
    schema = get_schema_args(row, tool)
    if not schema:
        return {k: v for k, v in args.items() if v is not None}
    return {k: v for k, v in args.items() if k in schema and v is not None}

# ── Direct extraction (v1 style) ───────────────────────────────────────────────
ID_PARAM = {"check_traffic_violations": "id_number",
            "check_iqama_status": "iqama_number",
            "check_visa_status": "visa_number"}

def direct_extract(row: dict[str, Any], tool: str,
                   gazetteer: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
    text = row.get("user_text") or ""
    schema = get_schema_args(row, tool)
    ext: dict[str, Any] = {}
    if tool == "none": return ext

    # ID tools
    if tool in ID_PARAM:
        n = extract_first_id(text)
        p = ID_PARAM[tool]
        if n and p in schema: ext[p] = n

    # Insurance number
    if tool == "check_insurance_coverage":
        n = extract_first_id(text)
        if n and "insurance_number" in schema: ext["insurance_number"] = n

    nums = extract_numbers(text)

    # Numeric amount
    if tool in ("convert_currency", "transfer_money", "calculate_zakat") and nums:
        if "amount" in schema: ext["amount"] = nums[0]

    if tool == "calculate_customs" and nums:
        if "product_value" in schema: ext["product_value"] = nums[-1]

    # End-of-service
    if tool == "calculate_end_of_service":
        large = [n for n in nums if n >= 1000]
        small = [n for n in nums if 0 < n <= 50]
        if large and "salary" in schema: ext["salary"] = large[0]
        if small and "years_of_service" in schema: ext["years_of_service"] = small[-1]

    # Hotels / umrah people count
    if tool in ("search_hotels", "search_umrah_packages"):
        n = norm_text(text)
        people_words = ["اشخاص","شخص","افراد","فرد","ضيوف","ضيف","guests","persons"]
        if any(w in n for w in people_words) and nums:
            small = [x for x in nums if 1 <= x <= 20]
            if small:
                if "num_persons" in schema: ext["num_persons"] = small[0]
                if "guests" in schema: ext["guests"] = small[0]

    # Weather days
    if tool == "get_weather":
        n = norm_text(text)
        days = None
        if any(w in n for w in ["اسبوع","week"]): days = 7.0
        elif any(w in n for w in ["يومين","يومان"]): days = 2.0
        elif any(w in n for w in ["اليوم","today"]): days = 1.0
        elif nums and any(w in n for w in ["ايام","يوم","days"]): days = nums[0]
        if days is not None and "days" in schema: ext["days"] = days

    # Transfer money IBAN + recipient
    if tool == "transfer_money":
        iban = extract_iban(text)
        if iban and "recipient_iban" in schema: ext["recipient_iban"] = iban
        m = re.search(
            r"(?:الى|إلى|لـ|ل)\s+([A-Za-z؀-ۿ ]{2,40}?)(?:\s+(?:على|علي|في|بمبلغ|مبلغ|رقم|ايبان|IBAN)|$)",
            text, flags=re.IGNORECASE)
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            if 2 <= len(name) <= 40 and not re.search(r"\d", name):
                if "recipient_name" in schema: ext["recipient_name"] = name

    # Gazetteer
    for arg, candidates in gazetteer.get(tool, {}).items():
        if arg not in schema: continue
        v = gazetteer_match(text, candidates)
        if v is not None: ext[arg] = v

    return ext

# ── Conservative post-process (v1 style) ──────────────────────────────────────
def conservative_clean(row: dict[str, Any], tool: str, args: dict[str, Any]) -> dict[str, Any]:
    text = row.get("user_text") or ""
    a = dict(args)
    if tool == "search_quran":
        cleaned = {}
        if "query" in a: cleaned["query"] = a["query"]
        if "search_type" in a:
            if has_any(text, ["تفسير","فسر","شرح","معنى"]): cleaned["search_type"] = a["search_type"]
            elif has_any(text, ["ابحث عن آية","ابحث عن ايه","آية عن","ايه عن"]): cleaned["search_type"] = a["search_type"]
        return cleaned
    if tool == "search_hotels":
        if "guests" in a and not has_any(text, ["ضيف","ضيوف","شخص","اشخاص","افراد","فرد","guests","persons"]): a.pop("guests")
        if "stars" in a and not has_any(text, ["نجوم","نجمات","star","stars"]): a.pop("stars")
    if tool == "book_doctor_appointment":
        if "doctor_name" in a and not has_any(text, ["الدكتور","دكتور ","dr ","doctor"]): a.pop("doctor_name")
    if tool == "compare_prices":
        if "category" in a and not has_any(text, ["فئة","قسم","تصنيف","category"]): a.pop("category")
    if tool == "check_insurance_coverage":
        if "insurance_number" in a and not re.search(r"\d+", str(text).translate(ARABIC_DIGITS)): a.pop("insurance_number")
    return a

# ── None-detector ──────────────────────────────────────────────────────────────
def build_none_text(row: dict[str, Any]) -> str:
    user_text = row.get("user_text") or ""
    dialect = row.get("dialect") or ""
    neg_cat = row.get("negative_category") or ""
    tool_texts = []
    for tool in row.get("available_tools", []):
        name = tool.get("name") or ""
        desc = tool.get("description") or ""
        params = tool.get("parameters") or {}
        tool_texts.append(f"{name} {desc} {' '.join(params.keys())}")
    return f"USER:\n{user_text}\n\nDIALECT:\n{dialect}\n\nNEGATIVE_CATEGORY:\n{neg_cat}\n\nAVAILABLE_TOOLS:\n{chr(10).join(tool_texts)}".strip()

def train_none_detector(train_rows: list[dict[str, Any]]) -> Pipeline:
    x = [build_none_text(r) for r in train_rows]
    y = [1 if r.get("tool_called") != "none" and r.get("requires_function") else 0 for r in train_rows]
    model = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=2, max_features=120000)),
        ("clf",   LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs")),
    ])
    print("  Training none-detector...")
    model.fit(x, y)
    return model

def get_function_prob(model: Pipeline, row: dict[str, Any]) -> float:
    text = build_none_text(row)
    clf = model.named_steps["clf"]
    probs = model.predict_proba([text])[0]
    classes = list(clf.classes_)
    return float(probs[classes.index(1)]) if 1 in classes else 1.0

NONE_THRESHOLD = 0.60  # same as v1 best

# ── Evaluation ─────────────────────────────────────────────────────────────────
def evaluate(gold_rows: list[dict[str, Any]], pred_rows: list[dict[str, Any]], label: str) -> dict:
    gold_by_id = {r["id"]: r for r in gold_rows}
    pred_by_id = {r.get("id"): r for r in pred_rows}
    total = len(gold_rows)
    fn_ok = arg_ok = 0
    tool_stats: dict[str, dict] = {}
    for g in gold_rows:
        rid = g["id"]
        p = pred_by_id.get(rid)
        tool = g["tool_called"]
        if tool not in tool_stats: tool_stats[tool] = {"n":0,"fn":0,"arg":0}
        tool_stats[tool]["n"] += 1
        g_args = {k:v for k,v in (g.get("arguments") or {}).items() if v is not None}
        p_args = {k:v for k,v in (p.get("arguments") or {}).items() if v is not None} if p else {}
        t_ok = p and p.get("tool_called") == tool
        a_ok = g_args == p_args
        if t_ok: fn_ok += 1; tool_stats[tool]["fn"] += 1
        if a_ok: arg_ok += 1; tool_stats[tool]["arg"] += 1
    fn = fn_ok/total; arg = arg_ok/total
    print(f"\n{'='*58}")
    print(f"  {label}")
    print(f"  FnAcc={fn:.4f}  ArgEM={arg:.4f}  OverallA={0.4*fn+0.6*arg:.4f}  ({total} rows)")
    print(f"  {'Tool':<35} {'N':>4} {'ArgEM':>6}")
    for t, s in sorted(tool_stats.items(), key=lambda x: x[1]["arg"]/x[1]["n"]):
        print(f"  {t:<35} {s['n']:>4} {s['arg']/s['n']:>6.3f}")
    return {"FnAcc": fn, "ArgEM": arg, "OverallA": 0.4*fn+0.6*arg, "tool_stats": tool_stats}

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 – v1 pipeline on processed_latest
# ══════════════════════════════════════════════════════════════════════════════
def run_stage1(train_rows, dev_rows):
    print("\n[Stage 1] Running v1 pipeline on processed_latest data...")
    router = train_router(train_rows)
    retriever = NearestArgRetriever(); retriever.fit(train_rows)
    gazetteer = build_gazetteer(train_rows)
    none_detector = train_none_detector(train_rows)

    preds = []
    for row in dev_rows:
        tool = predict_tool(router, row)
        nearest = retriever.predict(row, tool)
        direct  = direct_extract(row, tool, gazetteer)
        merged  = {**nearest, **direct}
        merged  = conservative_clean(row, tool, merged)
        merged  = clean_to_schema(row, tool, merged)

        # none detection
        prob = get_function_prob(none_detector, row)
        if prob < NONE_THRESHOLD:
            tool = "none"; merged = {}

        preds.append({"id": row["id"], "tool_called": tool, "arguments": merged})

    save_jsonl(preds, STAGE1_PATH)
    print(f"  Saved: {STAGE1_PATH}")
    return preds

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 – Normalization maps
# ══════════════════════════════════════════════════════════════════════════════
def map_value(text: Any, mapping: list[tuple[str, list[str]]]) -> str | None:
    """Return canonical form if any alias matches in norm_text(text)."""
    n = norm_text(str(text or ""))
    for canonical, aliases in mapping:
        for alias in aliases:
            if norm_text(alias) in n:
                return canonical
    return None

def normalize_currency(text: str) -> str | None:
    """Match currency in text, return ISO code."""
    n = norm_text(text)
    for iso, aliases in CURRENCY_TO_ISO:
        for alias in aliases:
            if norm_text(alias) in n:
                return iso
    return None

def find_currencies_in_text(text: str) -> list[str]:
    """Return list of ISO codes for all currencies mentioned in text (in order of first mention)."""
    n = norm_text(text)
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for iso, aliases in CURRENCY_TO_ISO:
        if iso in seen: continue
        for alias in aliases:
            na = norm_text(alias)
            idx = n.find(na)
            if idx >= 0:
                found.append((idx, iso))
                seen.add(iso)
                break
    found.sort(key=lambda x: x[0])
    return [iso for _, iso in found]

def normalize_pred(row: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    tool = pred.get("tool_called", "none")
    args = dict(pred.get("arguments") or {})
    text = row.get("user_text") or ""

    # ── convert_currency ──
    if tool == "convert_currency":
        currencies = find_currencies_in_text(text)
        if len(currencies) >= 2:
            args["from_currency"] = currencies[0]
            args["to_currency"]   = currencies[1]
        elif len(currencies) == 1:
            # Only one found — try to normalise whatever pred had
            if "from_currency" in args:
                c = normalize_currency(args["from_currency"])
                if c: args["from_currency"] = c
            if "to_currency" in args:
                c = normalize_currency(args["to_currency"])
                if c: args["to_currency"] = c
        else:
            if "from_currency" in args:
                c = normalize_currency(args["from_currency"])
                if c: args["from_currency"] = c
            if "to_currency" in args:
                c = normalize_currency(args["to_currency"])
                if c: args["to_currency"] = c

    # ── transfer_money ──
    if tool == "transfer_money" and "currency" in args:
        # Try from text first, then from value
        currencies = find_currencies_in_text(text)
        if currencies:
            args["currency"] = currencies[0]
        else:
            c = normalize_currency(args["currency"])
            if c: args["currency"] = c

    # ── calculate_zakat ──
    if tool == "calculate_zakat":
        if "currency" in args:
            # Keep short Arabic forms that are common in gold (ريال, دولار, etc.)
            # Only map full names to ISO where training uses ISO
            c = normalize_currency(args["currency"]) or normalize_currency(text.split()[-1] if text else "")
            # Only override if the current value is a long Arabic phrase
            if c and len(args["currency"]) > 5:
                args["currency"] = c
        if "type" in args:
            t = map_value(args["type"], ZAKAT_TYPE_MAP) or map_value(text, ZAKAT_TYPE_MAP)
            if t: args["type"] = t

    # ── calculate_end_of_service ──
    if tool == "calculate_end_of_service" and "termination_type" in args:
        t = map_value(args["termination_type"], TERMINATION_TYPE_MAP)
        if not t: t = map_value(text, TERMINATION_TYPE_MAP)
        if t: args["termination_type"] = t

    # ── translate_text ──
    if tool == "translate_text" and "target_language" in args:
        lang = map_value(args["target_language"], LANGUAGE_TO_ISO)
        if not lang: lang = map_value(text, LANGUAGE_TO_ISO)
        if lang: args["target_language"] = lang

    # ── search_quran ──
    if tool == "search_quran" and "search_type" in args:
        st = map_value(args["search_type"], QURAN_SEARCH_TYPE_MAP)
        if not st: st = map_value(text, QURAN_SEARCH_TYPE_MAP)
        if st: args["search_type"] = st

    # ── compare_prices / calculate_customs ──
    for country_field in ["country", "destination_country"]:
        if tool in ("compare_prices", "calculate_customs") and country_field in args:
            arabic = map_value(args[country_field], COUNTRY_TO_ARABIC)
            if arabic: args[country_field] = arabic

    return {"id": pred["id"], "tool_called": tool, "arguments": {k:v for k,v in args.items() if v is not None}}

def run_stage2(dev_rows, stage1_preds):
    print("\n[Stage 2] Applying normalization maps...")
    dev_by_id = {r["id"]: r for r in dev_rows}
    preds = [normalize_pred(dev_by_id[p["id"]], p) for p in stage1_preds]
    save_jsonl(preds, STAGE2_PATH)
    print(f"  Saved: {STAGE2_PATH}")
    return preds

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 – Improved per-tool fixes
# ══════════════════════════════════════════════════════════════════════════════
def improve_check_insurance(text: str, args: dict[str, Any]) -> dict[str, Any]:
    a = dict(args)
    n = extract_first_id(text)
    if n: a["insurance_number"] = n
    else: a.pop("insurance_number", None)
    procedure_keywords = [
        "عملية ليزك", "عملية الليزك", "الليزك", "ليزك",
        "علاج الاسنان", "علاج الأسنان",
        "العلاج الطبيعي", "علاج طبيعي",
        "عملية القلب المفتوح", "عملية القلب", "جراحة القلب",
        "عملية المراره", "عملية المرارة", "استئصال المرارة",
        "عملية جراحيه", "عملية جراحية",
        "عملية الركبه", "عملية الركبة", "جراحة الركبة",
        "علاج السرطان", "علاج الاورام", "علاج الأورام",
        "فحص الدم", "فحص النظر",
        "عملية الزايده", "عملية الزايدة",
        "عملية الولاده", "عملية الولادة",
        "عملية الليزر",
    ]
    for kw in procedure_keywords:
        if has_any(text, [kw]):
            a["procedure"] = kw.replace("ه", "ة")  # normalise taa marbuta in output
            break
    return a

def improve_translate_text(text: str, args: dict[str, Any]) -> dict[str, Any]:
    a = dict(args)
    lang = map_value(text, LANGUAGE_TO_ISO)
    if lang: a["target_language"] = lang
    # Extract quoted text
    m = re.search(r'[\"""\'\'\'`](.+?)[\"""\'\'\'`]', text)
    if m: a["text"] = m.group(1).strip()
    return a

def improve_convert_currency(text: str, args: dict[str, Any]) -> dict[str, Any]:
    a = dict(args)
    nums = extract_numbers(text)
    if nums: a["amount"] = nums[0]
    currencies = find_currencies_in_text(text)
    if len(currencies) >= 2:
        a["from_currency"] = currencies[0]
        a["to_currency"]   = currencies[1]
    elif len(currencies) == 1:
        if "from_currency" not in a: a["from_currency"] = currencies[0]
        elif "to_currency" not in a:  a["to_currency"]   = currencies[0]
    return a

def improve_transfer_money(text: str, args: dict[str, Any]) -> dict[str, Any]:
    a = dict(args)
    nums = extract_numbers(text)
    if nums: a["amount"] = nums[0]
    currencies = find_currencies_in_text(text)
    if currencies: a["currency"] = currencies[0]
    iban = extract_iban(text)
    if iban: a["recipient_iban"] = iban
    m = re.search(
        r"(?:الى|إلى|لـ|ل)\s+([A-Za-z؀-ۿ ]{2,40}?)(?:\s+(?:على|في|بمبلغ|مبلغ|رقم|ايبان|IBAN)|$)",
        text, flags=re.IGNORECASE)
    if m:
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        if 2 <= len(name) <= 40 and not re.search(r"\d", name):
            a["recipient_name"] = name
    return a

def improve_calculate_zakat(text: str, args: dict[str, Any]) -> dict[str, Any]:
    a = dict(args)
    nums = extract_numbers(text)
    if nums: a["amount"] = nums[0]
    t = map_value(text, ZAKAT_TYPE_MAP)
    if t: a["type"] = t
    currencies = find_currencies_in_text(text)
    if currencies:
        a["currency"] = currencies[0]
    elif "currency" in a and len(a["currency"]) > 5:
        c = normalize_currency(a["currency"])
        if c: a["currency"] = c
    return a

def improve_end_of_service(text: str, args: dict[str, Any]) -> dict[str, Any]:
    a = dict(args)
    nums = extract_numbers(text)
    large = [n for n in nums if n >= 1000]
    small = [n for n in nums if 0 < n <= 50]
    if large: a["salary"] = large[0]
    if small: a["years_of_service"] = small[-1]
    t = map_value(text, TERMINATION_TYPE_MAP)
    if t: a["termination_type"] = t
    return a

def improve_search_quran(text: str, args: dict[str, Any]) -> dict[str, Any]:
    a = {}
    if "query" in args: a["query"] = args["query"]
    if "search_type" in args:
        st = map_value(args["search_type"], QURAN_SEARCH_TYPE_MAP) or map_value(text, QURAN_SEARCH_TYPE_MAP)
        if st: a["search_type"] = st
    return a

def improve_prediction(row: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    tool = pred.get("tool_called", "none")
    text = row.get("user_text") or ""
    args = dict(pred.get("arguments") or {})

    if tool == "convert_currency":
        args = improve_convert_currency(text, args)
    elif tool == "transfer_money":
        args = improve_transfer_money(text, args)
    elif tool == "calculate_zakat":
        args = improve_calculate_zakat(text, args)
    elif tool == "calculate_end_of_service":
        args = improve_end_of_service(text, args)
    elif tool == "translate_text":
        args = improve_translate_text(text, args)
    elif tool == "search_quran":
        args = improve_search_quran(text, args)
    elif tool == "check_insurance_coverage":
        args = improve_check_insurance(text, args)

    args = clean_to_schema(row, tool, args)
    return {"id": pred["id"], "tool_called": tool, "arguments": args}

def run_stage3(dev_rows, stage2_preds):
    print("\n[Stage 3] Applying per-tool rule improvements...")
    dev_by_id = {r["id"]: r for r in dev_rows}
    preds = [improve_prediction(dev_by_id[p["id"]], p) for p in stage2_preds]
    save_jsonl(preds, STAGE3_PATH)
    print(f"  Saved: {STAGE3_PATH}")
    return preds

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("Loading processed_latest data...")
    train_rows = load_jsonl(TRAIN_PATH)
    dev_rows   = load_jsonl(DEV_PATH)
    gold_rows  = load_jsonl(GOLD_PATH)
    print(f"  train={len(train_rows)}  dev={len(dev_rows)}  gold={len(gold_rows)}")

    # ── Stage 1 ──
    s1 = run_stage1(train_rows, dev_rows)
    r1 = evaluate(gold_rows, s1, "Stage 1 — v1 pipeline on latest data")

    # ── Stage 2 ──
    s2 = run_stage2(dev_rows, s1)
    r2 = evaluate(gold_rows, s2, "Stage 2 — + normalization maps")

    # ── Stage 3 ──
    s3 = run_stage3(dev_rows, s2)
    r3 = evaluate(gold_rows, s3, "Stage 3 — + per-tool rule improvements")

    # ── Pick best stage ──
    scores = [(r1, s1, "Stage 1"), (r2, s2, "Stage 2"), (r3, s3, "Stage 3")]
    best_r, best_s, best_name = max(scores, key=lambda x: x[0]["OverallA"])

    print(f"\n{'='*58}")
    print(f"  Best stage: {best_name}  (OverallA={best_r['OverallA']:.4f})")
    save_jsonl(best_s, FINAL_PATH)
    print(f"  Final file: {FINAL_PATH}")

    # ── Summary report ──
    REPS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPS_DIR / "nabiq_v2_pc_report.md"
    lines = [
        "# NABIQ-v2-PC Report",
        "",
        "## Dataset",
        "- Source: data/processed_latest/ (from raw_latest, verified 10550 train / 545 dev)",
        "- Gold changed vs old: 66 rows (currency ISO, zakat/termination/language/quran type normalization)",
        "",
        "## Stage Results",
        f"| Stage | FnAcc | ArgEM | OverallA |",
        f"|-------|-------|-------|----------|",
        f"| Stage 1 (v1 pipeline on latest) | {r1['FnAcc']:.4f} | {r1['ArgEM']:.4f} | {r1['OverallA']:.4f} |",
        f"| Stage 2 (+ normalization maps)   | {r2['FnAcc']:.4f} | {r2['ArgEM']:.4f} | {r2['OverallA']:.4f} |",
        f"| Stage 3 (+ per-tool rules)       | {r3['FnAcc']:.4f} | {r3['ArgEM']:.4f} | {r3['OverallA']:.4f} |",
        "",
        "## Reference: Official Laptop NABIQ-v2",
        "| FnAcc | ArgEM | OverallA |",
        "|-------|-------|----------|",
        "| 0.9706 | 0.5600 | 0.7243 |",
        "",
        f"## Best PC stage: {best_name}",
        f"- FnAcc: {best_r['FnAcc']:.4f}",
        f"- ArgEM: {best_r['ArgEM']:.4f}",
        f"- OverallA: {best_r['OverallA']:.4f}",
        "",
        "## Per-tool ArgEM (best stage)",
    ]
    for t, s in sorted(best_r["tool_stats"].items(), key=lambda x: x[1]["arg"]/x[1]["n"]):
        lines.append(f"- {t}: {s['arg']/s['n']:.3f} ({s['n']} samples)")
    lines += [
        "",
        "## Files",
        f"- Stage 1: outputs/submissions/nabiq_v2_pc_stage1.jsonl",
        f"- Stage 2: outputs/submissions/nabiq_v2_pc_stage2.jsonl",
        f"- Stage 3: outputs/submissions/nabiq_v2_pc_stage3.jsonl",
        f"- Final:   outputs/submissions/nabiq_v2_pc.jsonl  (= {best_name})",
        "",
        "## Safety",
        "- dev_gold_track_a.jsonl NOT uploaded — local eval only",
        "- Old submissions NOT overwritten",
        "- No think field present",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  Report: {report_path}")


if __name__ == "__main__":
    main()
