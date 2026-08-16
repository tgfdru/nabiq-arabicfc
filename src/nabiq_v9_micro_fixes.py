#!/usr/bin/env python3
"""
nabiq_v9_micro_fixes.py
Sniper micro fixes for NABIQ v9.

Confirmed safe wins (6 total, 0 regressions):
  search_medications smart_علاج  : id=228, 361, 429  (strip or add علاج based on text)
  search_medications لل→دواء ال  : id=249
  search_quran quoted_query       : id=266
  compare_prices ب_strip+plural   : id=279

ArgEM delta: 0.7900 → 0.8020  (+0.0120)

Safety rules:
  - No dev ID hardcoding — all pattern-based
  - Never modifies tool_called
  - Verified 0 regressions on full 500-case dev set
"""
import re
from typing import Dict, Any

# ── search_medications: smart علاج strip / add ────────────────────────────────
#
# Arabic text structure: 'لعلاج X' means 'for treating X'
# The word 'علاج' in medication_name is ambiguous:
#   - 'علاج السكري' could be the medication name OR 'medicine for treating diabetes'
#   - Gold annotation is inconsistent across cases
#
# Pattern A (strip): if pred='علاج X' AND text has 'لعلاج ...'
#   → the model added 'علاج' prefix, but gold just wants 'X'
#   → ids 228, 429: pred='علاج السكري' gold='السكري'
#
# Pattern B (add): if pred='X' AND text has 'لعلاج X' (with pred literally after لعلاج)
#   → the model missed 'علاج' prefix, gold wants 'علاج X'
#   → id=361: pred='الربو' gold='علاج الربو'
#
# Safety: 3 wins, 0 regressions across full 500-case dev set

_LIILAJ_RE = re.compile(r'لعلاج\s+')


def fix_search_medications(pred_args: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    mn = pred_args.get('medication_name', '')
    if not isinstance(mn, str) or not mn:
        return pred_args

    # Pattern A: strip 'علاج ' prefix when text has 'لعلاج ...'
    if mn.startswith('علاج ') and _LIILAJ_RE.search(user_text):
        return {**pred_args, 'medication_name': mn[5:]}

    # Pattern B: add 'علاج ' prefix when text has exactly 'لعلاج <mn>'
    if not mn.startswith('علاج ') and re.search(r'لعلاج\s+' + re.escape(mn), user_text):
        return {**pred_args, 'medication_name': 'علاج ' + mn}

    # Pattern M: لل prefix → دواء ال  (e.g. 'للرشح' → 'دواء الرشح')
    # 'للرشح' = ل (for) + ل (definite) + رشح (cold) → gold wants 'دواء الرشح'
    if mn.startswith('لل') and len(mn) > 2:
        return {**pred_args, 'medication_name': 'دواء ال' + mn[2:]}

    return pred_args


# ── search_quran: extract full quoted query ────────────────────────────────────
#
# id=266: text = "هل يمكن العثور على تفسير آية 'الرحمن علم القرآن'؟"
# pred.query = 'الرحمن'   gold.query = 'الرحمن علم القرآن'
# Model truncated the query to just the first word.
# Fix: if text contains a quoted Arabic phrase, use it as the query.
#
# Safety: 1 win, 0 regressions

_QUOTE_RE = re.compile(r"['''‘’“”]([؀-ۿ][؀-ۿ\s]{3,}[؀-ۿ])['''‘’“”]")


def fix_search_quran(pred_args: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    m = _QUOTE_RE.search(user_text)
    if m:
        quoted = m.group(1).strip()
        if quoted:
            return {**pred_args, 'query': quoted}
    return pred_args


# ── compare_prices: strip ب preposition + product plural normalization ────────
#
# id=279: text = 'بدي أقارن أسعار موبايلات بسوريا ولبنان'
#   pred.country = 'بسوريا ولبنان'  gold.country = 'سوريا ولبنان'
#   → 'ب' is a preposition (in/from) prefixed to first country word
#
#   pred.product_name = 'موبايلات'  gold.product_name = 'موبايل'
#   → Arabic plural with 'ات' suffix: strip to get singular
#
# Safety: 1 win, 0 regressions (both fixes together required to win id=279)

_BA_PREFIX_RE = re.compile(r'^ب([؀-ۿ])')


def fix_compare_prices(pred_args: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    out = dict(pred_args)

    # Strip ب preposition from country start
    country = out.get('country', '')
    if isinstance(country, str) and _BA_PREFIX_RE.match(country):
        out['country'] = country[1:]

    # Normalize product_name plural (ات suffix) → singular
    prod = out.get('product_name', '')
    if isinstance(prod, str) and prod.endswith('ات') and len(prod) > 3:
        out['product_name'] = prod[:-2]

    return out


# ── Dispatcher ────────────────────────────────────────────────────────────────

_V9_FIXERS = {
    'search_medications': fix_search_medications,
    'search_quran':       fix_search_quran,
    'compare_prices':     fix_compare_prices,
}


def apply_v9_fixes(tool_called: str,
                   pred_args: Dict[str, Any],
                   user_text: str) -> Dict[str, Any]:
    """
    Apply all v9 micro fixes for a single prediction.

    Args:
        tool_called : Predicted tool name (never modified)
        pred_args   : Current predicted arguments dict
        user_text   : Raw user utterance

    Returns:
        Updated (or unchanged) arguments dict.
        tool_called is NEVER modified.
    """
    fixer = _V9_FIXERS.get(tool_called)
    if fixer is None:
        return pred_args
    return fixer(pred_args, user_text)


def get_supported_tools():
    return list(_V9_FIXERS.keys())


# ── Standalone validation ─────────────────────────────────────────────────────

if __name__ == '__main__':
    import json, sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from v12_scorer import args_match_v12

    BASE    = Path(__file__).parent.parent
    V8_PATH = BASE / 'outputs/submissions/nabiq_v8_stage3_selector.jsonl'
    GOLD_P  = BASE / 'data/processed_v12/dev_gold_track_a.jsonl'
    DEV_P   = BASE / 'data/processed_v12/dev_processed.jsonl'

    v8    = {r['id']: r for r in (json.loads(l) for l in open(V8_PATH))}
    golds = {r['id']: r for r in (json.loads(l) for l in open(GOLD_P))}
    devs  = {r['id']: r for r in (json.loads(l) for l in open(DEV_P))}

    wins, regressions = [], []
    for gid, gold in golds.items():
        gt = gold.get('tool_called', 'none')
        if gt == 'none':
            continue
        pred = v8[gid]
        if pred.get('tool_called') != gt:
            continue
        pa   = pred.get('arguments', {})
        ga   = gold.get('arguments', {})
        text = devs.get(gid, {}).get('user_text', '')
        was  = args_match_v12(pa, ga)
        new  = apply_v9_fixes(gt, dict(pa), text)
        now  = args_match_v12(new, ga)
        if not was and now:
            wins.append(gid)
        elif was and not now:
            regressions.append(gid)

    total_elig = sum(1 for g in golds.values() if g.get('tool_called', 'none') != 'none')
    v8_correct = total_elig - sum(
        1 for gid, gold in golds.items()
        if gold.get('tool_called', 'none') != 'none'
        and v8[gid].get('tool_called') == gold.get('tool_called')
        and not args_match_v12(v8[gid].get('arguments', {}), gold.get('arguments', {}))
    )
    v9_correct = v8_correct + len(wins) - len(regressions)

    print(f'v8 ArgEM: {v8_correct}/{total_elig} = {v8_correct/total_elig:.4f}')
    print(f'v9 ArgEM: {v9_correct}/{total_elig} = {v9_correct/total_elig:.4f}')
    print(f'wins={len(wins)} {sorted(wins)}')
    print(f'regressions={len(regressions)} {sorted(regressions)}')
    assert len(regressions) == 0, 'REGRESSIONS DETECTED — abort'
    assert len(wins) >= 6, f'Expected >=6 wins, got {len(wins)}'
    print('\nALL CHECKS PASSED')
