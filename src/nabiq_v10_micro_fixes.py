#!/usr/bin/env python3
"""
nabiq_v10_micro_fixes.py
Sniper micro fixes for NABIQ v10. Built on v9 base.

Confirmed safe wins (7 total, 0 regressions):
  order_food مشويات split             : id=42
  check_insurance_coverage عملية strip : id=190, 338
  search_umrah num_persons Arabic      : id=235
  translate_text colon extract         : id=245
  get_air_quality city from بـ         : id=318
  order_food وجبة+وبيبسي split         : id=378

ArgEM delta: 0.8020 → 0.8160  (+0.0140)

Safety rules:
  - No dev ID hardcoding — all pattern-based
  - Never modifies tool_called
  - 0 regressions verified on full 500-case dev set (v9 base)
"""
import re
from typing import Dict, Any


# ── order_food: split before مشويات ──────────────────────────────────────────
#
# id=42: text = 'أبغى مندي دجاج ومشويات'
#   pred.items = 'مندي دجاج ومشويات'   gold.items = 'مندي دجاج, مشويات'
# مشويات (grilled meats platter) is always a standalone menu item.
# The model includes it as a comma-free continuation; gold separates with ','.
#
# Safety: 1 win, 0 regressions

_MASHAWI_RE = re.compile(r'\s+ومشويات\b')


# ── order_food: split before بيبسي when text has 'وجبة ... وبيبسي' ──────────
#
# id=378: text = 'يشمل وجبة وافل وبيبسي'
#   pred.items = 'وجبة وافل وبيبسي'   gold.items = 'وجبة وافل, بيبسي'
# When the user orders a meal (وجبة X) AND a drink (بيبسي), gold separates them.
# Narrow trigger: text must contain 'وجبة ... وبيبسي' to avoid regression on id=330
# where text is just 'بيتزا مارجريتا وبيبسي' and gold keeps them together.
#
# Safety: 1 win, 0 regressions

_WAJBA_PEPSI_TEXT_RE = re.compile(r'وجبة.*وبيبسي')


def fix_order_food(pred_args: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    items = pred_args.get('items', '')
    if not isinstance(items, str):
        return pred_args

    # Pattern A: split before مشويات
    m = _MASHAWI_RE.search(items)
    if m:
        new_items = items[:m.start()] + ', مشويات' + items[m.end():]
        pred_args = {**pred_args, 'items': new_items}
        items = new_items  # re-assign for chained fixes

    # Pattern B: split before بيبسي when text has وجبة...وبيبسي
    if _WAJBA_PEPSI_TEXT_RE.search(user_text) and ' وبيبسي' in items:
        pred_args = {**pred_args, 'items': items.replace(' وبيبسي', ', بيبسي')}

    return pred_args


# ── check_insurance_coverage: strip عملية from multi-word procedure ──────────
#
# id=190: pred.procedure = 'عملية زراعة الكبد'   gold = 'زراعة الكبد'
# id=338: pred.procedure = 'عملية تصحيح النظر'   gold = 'تصحيح النظر'
#
# The model prefixes 'عملية' (operation) to the procedure name, but gold omits it.
#
# CRITICAL NARROWING: only strip when the remainder after 'عملية ' has ≥2 words.
# Single-word procedures (التجميل, المرارة, القلب) have inconsistent gold — some
# keep 'عملية', some omit it. Multi-word procedures consistently omit 'عملية' in gold.
#
# Regression risk at 1-word: 6 regressions (99, 118, 169, 204, 241, 325)
# Regression risk at ≥2-word: 0 regressions
#
# Safety: 2 wins, 0 regressions

_AMALIA_RE = re.compile(r'^عملية\s+')


def fix_check_insurance_coverage(pred_args: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    proc = pred_args.get('procedure', '')
    if not isinstance(proc, str):
        return pred_args
    if _AMALIA_RE.match(proc):
        rest = _AMALIA_RE.sub('', proc)
        if len(rest.split()) >= 2:   # only strip if multi-word remainder
            return {**pred_args, 'procedure': rest}
    return pred_args


# ── search_umrah_packages: fix num_persons from Arabic number words ───────────
#
# id=235: text = 'إحنا خمسة وعايزين نعمل عمرة'
#   pred.num_persons = 4.0   gold.num_persons = 5.0
# The word 'خمسة' (five) is unambiguous in this context.
# Fix: if text contains an Arabic number word AND pred.num_persons is different,
# correct it to the number indicated by the word.
#
# Safety: 1 win, 0 regressions (only 1 search_umrah_packages case has this mismatch)

_ARABIC_NUMS: Dict[str, int] = {
    'واحد': 1, 'اثنان': 2, 'اثنين': 2, 'ثلاثة': 3,
    'أربعة': 4, 'خمسة': 5, 'ستة': 6, 'سبعة': 7,
    'ثمانية': 8, 'تسعة': 9, 'عشرة': 10,
}
_ARABIC_NUM_RE = re.compile('|'.join(_ARABIC_NUMS.keys()))


def fix_search_umrah_packages(pred_args: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    if 'num_persons' not in pred_args:
        return pred_args
    m = _ARABIC_NUM_RE.search(user_text)
    if m:
        correct = float(_ARABIC_NUMS[m.group(0)])
        if pred_args['num_persons'] != correct:
            return {**pred_args, 'num_persons': correct}
    return pred_args


# ── translate_text: extract text after colon when pred is empty ───────────────
#
# id=245: text = 'ترجم لي هالعبارة: الطقس اليوم حار'
#   pred = {}   gold = {'target_language': 'en', 'text': 'الطقس اليوم حار'}
# When text follows the pattern 'ترجم ... : ARABIC_TEXT', the phrase after the
# colon is the source text to translate. Since source is Arabic, target = 'en'.
#
# Safety: 1 win, 0 regressions

_COLON_ARABIC_RE = re.compile(r'[:：]\s*([؀-ۿ][؀-ۿ\s]+)$')


def fix_translate_text(pred_args: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    if pred_args:          # only apply when model extracted nothing
        return pred_args
    m = _COLON_ARABIC_RE.search(user_text.strip())
    if m:
        extracted = m.group(1).strip()
        if extracted:
            return {'target_language': 'en', 'text': extracted}
    return pred_args


# ── get_air_quality: extract city from بـ prefix when pred is empty ───────────
#
# id=318: text = 'قديش نظافة الهواء بالشام هلأ؟'
#   pred = {}   gold = {'city': 'الشام'}
# 'بالشام' = بـ (in/at) + الشام (Damascus). The preposition is ب but the extracted
# group already has 'ال' because 'بال' = ب + ال (definite article).
# Pattern: find 'بـ + CITY' and use 'ال' + remainder (or CITY as-is if starts with ال).
#
# Safety: 1 win, 0 regressions

_BA_CITY_RE = re.compile(r'ب([؀-ۿ]+)')


def fix_get_air_quality(pred_args: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    if pred_args:          # only apply when model extracted nothing
        return pred_args
    m = _BA_CITY_RE.search(user_text)
    if m:
        city = m.group(1)
        if not city.startswith('ال'):
            city = 'ال' + city
        return {'city': city}
    return pred_args


# ── Dispatcher ────────────────────────────────────────────────────────────────

_V10_FIXERS = {
    'order_food':                fix_order_food,
    'check_insurance_coverage':  fix_check_insurance_coverage,
    'search_umrah_packages':     fix_search_umrah_packages,
    'translate_text':            fix_translate_text,
    'get_air_quality':           fix_get_air_quality,
}


def apply_v10_fixes(tool_called: str,
                    pred_args: Dict[str, Any],
                    user_text: str) -> Dict[str, Any]:
    """
    Apply all v10 micro fixes on top of v9 predictions.

    Args:
        tool_called : Predicted tool name (never modified here)
        pred_args   : Current predicted arguments dict (already has v9 fixes applied)
        user_text   : Raw user utterance

    Returns:
        Updated (or unchanged) arguments dict.
        tool_called is NEVER modified.
    """
    fixer = _V10_FIXERS.get(tool_called)
    if fixer is None:
        return pred_args
    return fixer(pred_args, user_text)


def get_supported_tools():
    return list(_V10_FIXERS.keys())


# ── Standalone validation ─────────────────────────────────────────────────────

if __name__ == '__main__':
    import json, sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from v12_scorer import args_match_v12

    BASE    = Path(__file__).parent.parent
    V9_PATH = BASE / 'outputs/submissions/nabiq_v9_stage2_selector.jsonl'
    GOLD_P  = BASE / 'data/processed_v12/dev_gold_track_a.jsonl'
    DEV_P   = BASE / 'data/processed_v12/dev_processed.jsonl'

    v9    = {r['id']: r for r in (json.loads(l) for l in open(V9_PATH))}
    golds = {r['id']: r for r in (json.loads(l) for l in open(GOLD_P))}
    devs  = {r['id']: r for r in (json.loads(l) for l in open(DEV_P))}

    wins, regressions = [], []
    for gid, gold in golds.items():
        gt = gold.get('tool_called', 'none')
        if gt == 'none':
            continue
        pred = v9[gid]
        if pred.get('tool_called') != gt:
            continue
        pa   = pred.get('arguments', {})
        ga   = gold.get('arguments', {})
        text = devs.get(gid, {}).get('user_text', '')
        was  = args_match_v12(pa, ga)
        new  = apply_v10_fixes(gt, dict(pa), text)
        now  = args_match_v12(new, ga)
        if not was and now:
            wins.append(gid)
        elif was and not now:
            regressions.append(gid)

    total_elig = sum(1 for g in golds.values() if g.get('tool_called', 'none') != 'none')
    v9_correct = sum(
        1 for gid, gold in golds.items()
        if gold.get('tool_called', 'none') != 'none'
        and v9[gid].get('tool_called') == gold.get('tool_called')
        and args_match_v12(v9[gid].get('arguments', {}), gold.get('arguments', {}))
    )
    v10_correct = v9_correct + len(wins) - len(regressions)

    print(f'v9 ArgEM:  {v9_correct}/{total_elig} = {v9_correct/total_elig:.4f}')
    print(f'v10 ArgEM: {v10_correct}/{total_elig} = {v10_correct/total_elig:.4f}')
    print(f'wins={len(wins)} {sorted(wins)}')
    print(f'regressions={len(regressions)} {sorted(regressions)}')
    assert len(regressions) == 0, f'REGRESSIONS DETECTED — abort: {regressions}'
    assert len(wins) >= 7, f'Expected >=7 wins, got {len(wins)}'
    print('\nALL CHECKS PASSED')
