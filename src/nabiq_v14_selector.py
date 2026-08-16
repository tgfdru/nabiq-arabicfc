# -*- coding: utf-8 -*-
"""
nabiq_v14_selector.py — Stage-3 conservative selector.

Chooses, per row, between the v13 (clean2) base prediction and the Stage-2
candidate prediction. The selection is NON-ORACLE: it never looks at dev gold.

A candidate replaces the base only if every changed string argument value is
text-evidence-valid:
  - a normalized substring of the user text, OR
  - produced by one of the closed, whitelisted canonical maps (specialty,
    procedure, ISO dates derived from text day/month tokens, word-number
    amounts, transliterated names extracted from the text), OR
  - the change is a pure REMOVAL of an unsupported argument.
Numeric changes must be evidenced by digits or word numbers in the text.
Otherwise the base prediction is kept.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from nabiq_v14_candidate_rules import (  # noqa: E402
    nrm, in_text, amount_supported, MONTHS, WORD_NUMS, ORDINALS,
)

# closed canonical outputs a rule may legitimately produce without the value
# being a verbatim substring of the text
CANONICAL_VALUES = {
    'طب الأطفال', 'الجلدية', 'الأسبوع الجاي', 'الأسبوع القادم',
    'منظار', 'الولادة', 'كشف الأسنان', 'جلسة علاج نفسي',
    'Maria', 'Hassan', 'Hussein', 'Mohammed', 'Ahmed', 'Ali', 'Fatima',
    'Khaled', 'Sara', 'Omar',
    'USD', 'EUR', 'EGP', 'SAR', 'AED', 'KWD', 'BHD', 'JOD', 'SYP', 'GBP',
}

ISO_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _iso_supported(value, text):
    """ISO date is acceptable if its day appears in the text (digit, Arabic
    digit or ordinal word) and its month appears as a month name (or the date
    was already ISO in the base)."""
    day = int(value[8:10])
    month = int(value[5:7])
    t = str(text).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    day_ok = re.search(rf'(?<!\d){day}(?!\d)', t) is not None
    if not day_ok:
        day_ok = any(v == day for k, v in ORDINALS.items() if k in text)
    month_ok = any(num == month for name, num in MONTHS.items() if name in text)
    return day_ok and month_ok


def _value_supported(value, text, base_had_iso):
    if value is None:
        return True
    if isinstance(value, (int, float)):
        return amount_supported(value, text) or float(value) <= 10
    v = str(value)
    if v in CANONICAL_VALUES:
        return True
    if ISO_RE.match(v):
        return _iso_supported(v, text) or base_had_iso
    if in_text(v, text):
        return True
    # comma/waw joined lists: every element must be evidenced
    parts = [p.strip() for p in re.split(r'[،,]| و', v) if p.strip()]
    if len(parts) > 1 and all(in_text(p, text) for p in parts):
        return True
    return False


def select(base_args, cand_args, text):
    """Return cand_args if all its changes are text-evidence-valid, else base."""
    if cand_args == base_args:
        return base_args
    base_iso = {k for k, v in base_args.items()
                if isinstance(v, str) and ISO_RE.match(v)}
    for k, v in cand_args.items():
        if k in base_args and base_args[k] == v:
            continue  # unchanged
        if not _value_supported(v, text, base_had_iso=(k in base_iso)):
            return base_args
    # removals are always acceptable (anti-hallucination direction)
    return cand_args
