"""
NABIQ v11 Micro-Fixes
=====================
Three surgical optional-field strippers, each with 0 regressions on v13 dev gold.

Fix 1 -- transfer_money: strip recipient_iban when no real IBAN/account in text
Fix 2 -- calculate_customs: strip destination_country when no country name in text
Fix 3 -- calculate_end_of_service: strip termination_type when no explicit signal in text

Each fix is text-evidence-based. No id-specific rules. No gold oracle at test time.
"""

import re

# ---------------------------------------------------------------------------
# Fix 1 - transfer_money: strip recipient_iban when text has no real IBAN
# ---------------------------------------------------------------------------
# Matches standard IBANs (e.g., SA1234567890AB) or long numeric account numbers (10+ digits).
REAL_IBAN_RE = re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4,}|\d{10,}')

def fix_transfer_money_iban(tool_name, args, user_text):
    """Strip recipient_iban if prediction hallucinated it (no IBAN in user text)."""
    if tool_name != 'transfer_money':
        return args
    if 'recipient_iban' not in args:
        return args
    if REAL_IBAN_RE.search(user_text):
        return args  # real IBAN found in text -- keep it
    # No real IBAN in text -> strip the hallucinated field
    return {k: v for k, v in args.items() if k != 'recipient_iban'}


# ---------------------------------------------------------------------------
# Fix 2 - calculate_customs: strip destination_country when not in text
# ---------------------------------------------------------------------------
# IMPORTANT: Use only canonical 'al-' prefixed forms ('السعودية' not 'سعودية').
# Arabic preposition fusion: 'للسعودية' = 'ل' + 'ل' + 'سعودية' (no alef),
# so 'السعودية' does NOT match inside 'للسعودية'. This is intentional --
# we detect standalone country names, not incidental sub-word matches.
COUNTRY_IN_TEXT_RE = re.compile(
    'السعودية|الإمارات|الامارات|مصر|الكويت|قطر|البحرين'
    '|عُمان|عمان|الأردن|الاردن|لبنان|العراق|سوريا|اليمن'
    '|تركيا|إيران|ايران|باكستان|الهند|الصين'
    '|أمريكا|امريكا|الولايات المتحدة'
    '|ألمانيا|المانيا|فرنسا|إيطاليا|ايطاليا|بريطانيا|إنجلترا|انجلترا'
    '|كوريا|اليابان|كندا|استراليا|أستراليا'
    '|دبي|أبوظبي|ابوظبي|الشارقة'
    '|المغرب|تونس|الجزائر|ليبيا|السودان'
)

def fix_calculate_customs_country(tool_name, args, user_text):
    """Strip destination_country if no standalone country name found in user text."""
    if tool_name != 'calculate_customs':
        return args
    if 'destination_country' not in args:
        return args
    if COUNTRY_IN_TEXT_RE.search(user_text):
        return args  # country name in text -- keep it
    return {k: v for k, v in args.items() if k != 'destination_country'}


# ---------------------------------------------------------------------------
# Fix 3 - calculate_end_of_service: strip termination_type when no signal in text
# ---------------------------------------------------------------------------
EXPLICIT_TT_RE = re.compile(
    'استقال|استقالة'
    '|إنهاء العقد|إنهاء عقد|انتهاء العقد|انتهاء مدة العقد'
    '|النوع إنهاء|النوع.{0,10}انتهاء'
    '|نوع الاستغناء|نوع الفصل|نوع الإنهاء|سبب الفصل|سبب الإنهاء'
    '|وتم إنهاء|بسبب انتهاء'
    '|برضاي|بإرادة الموظف'
    '|طرد|فصل|فُصل'
    '|الاستغناء|تقليص|ترشيد'
    '|سوء سلوك|تأديبي'
)

def fix_calculate_end_of_service_tt(tool_name, args, user_text):
    """Strip termination_type if no explicit termination reason found in text."""
    if tool_name != 'calculate_end_of_service':
        return args
    if 'termination_type' not in args:
        return args
    if EXPLICIT_TT_RE.search(user_text):
        return args  # explicit signal present -- keep the field
    return {k: v for k, v in args.items() if k != 'termination_type'}


# ---------------------------------------------------------------------------
# Main entry point: apply all fixes in sequence
# ---------------------------------------------------------------------------
def apply_v11_fixes(tool_name, args, user_text):
    """
    Apply all v11 micro-fixes to a prediction.
    Returns a (possibly modified) copy of args with safe fixes applied.
    """
    if not isinstance(args, dict):
        return args
    args = fix_transfer_money_iban(tool_name, args, user_text)
    args = fix_calculate_customs_country(tool_name, args, user_text)
    args = fix_calculate_end_of_service_tt(tool_name, args, user_text)
    return args


# ---------------------------------------------------------------------------
# Validation: run simulation on dev gold
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import json, sys
    from pathlib import Path

    BASE = Path(__file__).parent.parent
    sys.path.insert(0, str(BASE / 'src'))
    from v12_scorer import args_match_v12

    v10  = {r['id']: r for r in (json.loads(l) for l in open(BASE / 'outputs/submissions/nabiq_v10.jsonl'))}
    v13g = {r['id']: r for r in (json.loads(l) for l in open(BASE / 'data/processed_v13/dev_gold_track_a.jsonl'))}
    devs = {r['id']: r for r in (json.loads(l) for l in open(BASE / 'data/processed_v13/dev_processed.jsonl'))}

    eligible_ids = sorted([gid for gid, g in v13g.items() if g['tool_called'] != 'none'])
    wins, regressions, unchanged_wrong, unchanged_right = [], [], 0, 0

    for gid in eligible_ids:
        gold = v13g[gid]; pred = v10[gid]; text = devs[gid]['user_text']
        tool = pred.get('tool_called', ''); pa = pred.get('arguments', {}); ga = gold.get('arguments', {})
        if tool != gold['tool_called']:
            continue
        new_pa = apply_v11_fixes(tool, pa, text)
        was_ok = args_match_v12(pa, ga); now_ok = args_match_v12(new_pa, ga)
        if not was_ok and now_ok: wins.append(gid)
        elif was_ok and not now_ok: regressions.append(gid)
        elif was_ok: unchanged_right += 1
        else: unchanged_wrong += 1

    v10_correct = total = len(eligible_ids)
    v10_correct = unchanged_right + len(regressions)  # correct before fix
    v11_correct = unchanged_right + len(wins)
    # simpler:
    base_correct = len(eligible_ids) - unchanged_wrong - len(wins)
    print(f'Wins:        {len(wins)}  {wins}')
    print(f'Regressions: {len(regressions)}  {regressions}')
    print(f'v10 ArgEM (eligible): {(len(eligible_ids) - unchanged_wrong - len(wins)) / len(eligible_ids):.4f}')
    print(f'v11 ArgEM (eligible): {(len(eligible_ids) - unchanged_wrong - len(wins) + len(wins) - len(regressions)) / len(eligible_ids):.4f}')
