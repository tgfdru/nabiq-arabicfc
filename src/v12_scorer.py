"""
v12_scorer.py — v1.2 fair ArgEM scorer + full evaluation report.
Implements: Arabic/canonical aliases, digit norm, orthography norm,
            order-independent lists, currency/language aliases, int/float equality.
"""
import json, re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]

# ── Normalization helpers ──────────────────────────────────────────────────

ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
EASTERN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')

def norm_digits(s):
    if not isinstance(s, str):
        return s
    return s.translate(ARABIC_DIGITS).translate(EASTERN_DIGITS)

# Arabic orthography: alef variants, tah marbuta, ya/alef maqsura
def norm_ortho(s):
    if not isinstance(s, str):
        return s
    s = re.sub(r'[أإآٱ]', 'ا', s)    # alef variants → bare alef
    s = s.replace('ة', 'ه')           # tah marbuta → ha
    s = s.replace('ى', 'ي')           # alef maqsura → ya
    s = re.sub(r'ـ', '', s)       # tatweel
    s = re.sub(r'[ً-ٟ]', '', s)  # diacritics
    return s

def norm_str(s):
    if not isinstance(s, str):
        return s
    return norm_ortho(norm_digits(s.strip()))

# Currency aliases
CURRENCY_ALIASES = {
    'ريال': ['sar', 'riyal', 'ريال سعودي', 'رس'],
    'sar': ['ريال', 'riyal', 'ريال سعودي', 'رس'],
    'درهم': ['aed', 'درهم إماراتي', 'درهم اماراتي'],
    'aed': ['درهم', 'درهم إماراتي', 'درهم اماراتي'],
    'دينار': ['kwd', 'bhd', 'jod', 'lyd', 'tnd', 'iqd'],
    'دولار': ['usd', 'dollar'],
    'usd': ['دولار', 'dollar'],
    'يورو': ['eur', 'euro'],
    'eur': ['يورو', 'euro'],
    'جنيه': ['egp', 'gbp'],
    'egp': ['جنيه مصري'],
    'kwd': ['دينار كويتي', 'دينار'],
    'bhd': ['دينار بحريني', 'دينار'],
    'قرش': ['piaster', 'piastre'],
    'هللة': ['halala', 'هلله'],
}

# Language aliases
LANGUAGE_ALIASES = {
    'الانجليزية': ['الإنجليزية', 'انجليزي', 'إنجليزي', 'english', 'en'],
    'الإنجليزية': ['الانجليزية', 'انجليزي', 'إنجليزي', 'english', 'en'],
    'العربية': ['عربي', 'arabic', 'ar'],
    'الفرنسية': ['فرنسي', 'french', 'fr'],
    'الاسبانية': ['الإسبانية', 'اسباني', 'إسباني', 'spanish', 'es'],
    'الالمانية': ['الألمانية', 'الماني', 'ألماني', 'german', 'de'],
    'التركية': ['تركي', 'turkish', 'tr'],
    'الصينية': ['صيني', 'chinese', 'zh'],
    'اليابانية': ['ياباني', 'japanese', 'ja'],
    'الروسية': ['روسي', 'russian', 'ru'],
    'الكورية': ['كوري', 'korean', 'ko'],
    'الإيطالية': ['الايطالية', 'إيطالي', 'ايطالي', 'italian', 'it'],
    'البرتغالية': ['برتغالي', 'portuguese', 'pt'],
    'الهندية': ['هندي', 'hindi', 'hi'],
}

def build_alias_lookup(alias_dict):
    """Map each value → canonical (first key in dict)."""
    lookup = {}
    for canonical, variants in alias_dict.items():
        lookup[norm_str(canonical)] = norm_str(canonical)
        for v in variants:
            lookup[norm_str(v)] = norm_str(canonical)
    return lookup

CURRENCY_LOOKUP  = build_alias_lookup(CURRENCY_ALIASES)
LANGUAGE_LOOKUP  = build_alias_lookup(LANGUAGE_ALIASES)

def normalize_value(v):
    """Full normalization pipeline for a single value."""
    if v is None:
        return None
    # numeric equality
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return v
    s = norm_str(v)
    sl = s.lower()
    # try numeric parse
    try:
        f = float(s)
        return f
    except ValueError:
        pass
    # currency / language aliases
    if sl in CURRENCY_LOOKUP:
        return CURRENCY_LOOKUP[sl]
    if sl in LANGUAGE_LOOKUP:
        return LANGUAGE_LOOKUP[sl]
    return sl

def values_match(a, b):
    na = normalize_value(a)
    nb = normalize_value(b)
    if isinstance(na, float) and isinstance(nb, float):
        return abs(na - nb) < 1e-6
    # order-independent list: if both contain separator chars
    if isinstance(na, str) and isinstance(nb, str):
        seps = re.compile(r'[,،/|]')
        if seps.search(na) or seps.search(nb):
            la = sorted(x.strip() for x in seps.split(na) if x.strip())
            lb = sorted(x.strip() for x in seps.split(nb) if x.strip())
            return la == lb
    return na == nb

def args_match_v12(pred_args, gold_args):
    """True if pred_args == gold_args under v1.2 normalization."""
    if not isinstance(pred_args, dict) or not isinstance(gold_args, dict):
        return pred_args == gold_args
    if set(pred_args.keys()) != set(gold_args.keys()):
        return False
    for k in gold_args:
        if not values_match(pred_args.get(k), gold_args.get(k)):
            return False
    return True

def args_match_strict(pred_args, gold_args):
    return pred_args == gold_args

# ── Load helpers ───────────────────────────────────────────────────────────

def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]

# ── Main evaluation ────────────────────────────────────────────────────────

def evaluate(pred_path, gold_path, dev_path, label):
    preds = {r['id']: r for r in load_jsonl(pred_path)}
    golds = {r['id']: r for r in load_jsonl(gold_path)}
    devs  = {r['id']: r for r in load_jsonl(dev_path)}

    fn_correct = 0; arg_strict = 0; arg_v12 = 0
    fn_total = len(golds); arg_total = 0

    per_tool_strict = defaultdict(lambda: [0,0])  # [correct, total]
    per_tool_v12    = defaultdict(lambda: [0,0])
    per_dial_strict = defaultdict(lambda: [0,0])
    per_dial_v12    = defaultdict(lambda: [0,0])

    errors_strict = []   # errors under strict but not v12 (normalization gains)
    errors_v12    = []   # still wrong under v12

    for i in range(545):
        g = golds[i]; p = preds.get(i, {}); d = devs[i]
        gt = g['tool_called']; pt = p.get('tool_called', 'none')
        ga = g['arguments'];   pa = p.get('arguments', {})
        dialect = d.get('dialect') or 'unknown'
        tool = gt

        fn_ok = (pt == gt)
        if fn_ok:
            fn_correct += 1

        if gt != 'none':
            arg_total += 1
            s_ok  = fn_ok and args_match_strict(pa, ga)
            v12_ok = fn_ok and args_match_v12(pa, ga)
            if s_ok:  arg_strict += 1
            if v12_ok: arg_v12 += 1
            per_tool_strict[tool][1] += 1
            per_tool_v12[tool][1]    += 1
            per_dial_strict[dialect][1] += 1
            per_dial_v12[dialect][1]    += 1
            if s_ok:  per_tool_strict[tool][0] += 1
            if v12_ok: per_tool_v12[tool][0]   += 1
            if s_ok:  per_dial_strict[dialect][0] += 1
            if v12_ok: per_dial_v12[dialect][0]   += 1

            if not s_ok:
                errors_strict.append({'id': i, 'tool': tool, 'dialect': dialect,
                                       'pred_args': pa, 'gold_args': ga, 'fn_ok': fn_ok})
            if not v12_ok:
                errors_v12.append({'id': i, 'tool': tool, 'dialect': dialect,
                                    'pred_args': pa, 'gold_args': ga, 'fn_ok': fn_ok})

    fn_acc    = fn_correct / fn_total
    arg_em_s  = arg_strict / arg_total
    arg_em_v  = arg_v12    / arg_total
    overall_s = 0.40 * fn_acc + 0.60 * arg_em_s
    overall_v = 0.40 * fn_acc + 0.60 * arg_em_v

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  FnAcc        = {fn_acc:.4f}  ({fn_correct}/{fn_total})")
    print(f"  ArgEM strict = {arg_em_s:.4f}  ({arg_strict}/{arg_total})")
    print(f"  ArgEM v1.2   = {arg_em_v:.4f}  ({arg_v12}/{arg_total})")
    print(f"  OverallA str = {overall_s:.4f}")
    print(f"  OverallA v12 = {overall_v:.4f}")

    print(f"\n  --- Per-tool ArgEM ---")
    print(f"  {'Tool':<40} Strict    v1.2    Gain   N")
    for t in sorted(per_tool_strict):
        sc, sn = per_tool_strict[t]; vc, vn = per_tool_v12[t]
        sr = sc/sn if sn else 0; vr = vc/vn if vn else 0
        print(f"  {t:<40} {sr:.3f}    {vr:.3f}   {vr-sr:+.3f}  {sn}")

    print(f"\n  --- Per-dialect ArgEM ---")
    print(f"  {'Dialect':<15} Strict    v1.2    Gain   N")
    for d in sorted(per_dial_strict):
        sc, sn = per_dial_strict[d]; vc, vn = per_dial_v12[d]
        sr = sc/sn if sn else 0; vr = vc/vn if vn else 0
        print(f"  {d:<15} {sr:.3f}    {vr:.3f}   {vr-sr:+.3f}  {sn}")

    norm_gains = len(errors_strict) - len(errors_v12)
    print(f"\n  Strict errors: {len(errors_strict)}   v1.2 errors: {len(errors_v12)}")
    print(f"  Normalization gains: {norm_gains} examples")

    return {
        'fn_acc': fn_acc, 'arg_em_strict': arg_em_s, 'arg_em_v12': arg_em_v,
        'overall_strict': overall_s, 'overall_v12': overall_v,
        'errors_strict': errors_strict, 'errors_v12': errors_v12,
        'per_tool_strict': per_tool_strict, 'per_tool_v12': per_tool_v12,
        'per_dial_strict': per_dial_strict, 'per_dial_v12': per_dial_v12,
    }

if __name__ == '__main__':
    res = evaluate(
        pred_path = ROOT / 'outputs/submissions/nabiq_v6.jsonl',
        gold_path = ROOT / 'data/processed_v12/dev_gold_track_a.jsonl',
        dev_path  = ROOT / 'data/processed_v12/dev_processed.jsonl',
        label     = 'v6 on v1.2 gold',
    )
    print("\n(Done — import this module to access res dict)")
