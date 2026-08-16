# NOTE: this file was lightly redacted for public release --- an internal
# team-process note naming an individual was replaced with generic wording.
# No logic was changed. The unredacted original ships in the release archive.
# -*- coding: utf-8 -*-
"""
v15_reextract.py — v15-reextract-candidate, Wave 1 (G1 + G2 + G3).

EXPLORATORY. Adoption requires passing the acceptance criteria
(see outputs/reports/blind_prep/v15_reextract_decision.md). Golden v14
untouched; new file only; nothing here reads gold at prediction time.

Applied as a post-chain pass (after the frozen v14 chain), like a repair
layer: substitution/completion with verbatim text spans + one targeted
train-majority convention. Never changes tool_called. No ids.

G1  calculate_customs: drop `currency`
    Train convention 503/509 (98.8%) and dev gold 23/24 omit the key.
    The generic evidence gate could not catch this (a currency word IS in
    the text); only the per-tool convention identifies it as unexpected.

G2  transfer_money: re-extract explicit `recipient_iban`
    Fires only when the text carries an explicit account marker
    (IBAN/آيبان/حساب…رقم/رقم حساب) immediately followed by an IBAN-like or
    pure-digit token (>=6). Output is the verbatim token. Fixes the
    pure-digit gap left by the shape-only clean2 filter. Never fabricates,
    never accepts Arabic words or countries.

G3  check_insurance_coverage: `procedure` full-construct completion
    When the text contains (عملية|كشف|خلع|علاج|جلسة) + complement and the
    current predicted procedure is a strict substring of that construct,
    replace it with the full verbatim construct. Guards:
      - never fires on v14 canonical outputs (CANONICAL_VALUES)
      - candidate must be a verbatim text span
      - candidate must strictly extend the current value
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from nabiq_v14_candidate_rules import nrm  # noqa: E402
from nabiq_v14_selector import CANONICAL_VALUES  # noqa: E402

AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

IBAN_TOKEN = r'([A-Za-z]{2}[0-9A-Za-z]{4,}|\d{6,})'
IBAN_MARKERS = [
    re.compile(r'(?:IBAN|iban|Iban|آيبان|ايبان)\s*:?\s*' + IBAN_TOKEN),
    re.compile(r'رقم\s+(?:ال)?حساب\w*\s*:?\s*' + IBAN_TOKEN),
    re.compile(r'(?:ال)?حساب(?:\s+\S+){0,2}?\s+(?:ب?رقم)\s*:?\s*' + IBAN_TOKEN),
    re.compile(r'بحساب\s+رقم\s*:?\s*' + IBAN_TOKEN),
]

PROC_HEAD = re.compile(
    r'((?:ال)?(?:عملية|عمليه|كشف|خلع|علاج|جلسة|جلسه)\s+[ء-يA-Za-z][^؟?.!،,]*)')
PROC_STOP = re.compile(
    r'\s*(?:رقم|التأمين|تأميني|بالتأمين|بوليصة|البوليصة|هل|؟|\?)\S*.*$')


def g1_customs_drop_currency(tool, args, text):
    if tool == 'calculate_customs' and 'currency' in args:
        args = dict(args)
        del args['currency']
    return args


def g2_transfer_explicit_iban(tool, args, text):
    if tool != 'transfer_money' or args.get('recipient_iban'):
        return args
    t = str(text).translate(AR_DIGITS)
    for pat in IBAN_MARKERS:
        m = pat.search(t)
        if m:
            token = m.group(1).strip()
            if re.search(r'[؀-ۿ]', token):    # never Arabic words
                continue
            args = dict(args)
            args['recipient_iban'] = token
            return args
    return args


def g3_insurance_procedure_span(tool, args, text):
    if tool != 'check_insurance_coverage':
        return args
    cur = args.get('procedure')
    if not isinstance(cur, str) or not cur.strip():
        return args
    if cur in CANONICAL_VALUES:               # never override v14 canonicals
        return args
    m = PROC_HEAD.search(text)
    if not m:
        return args
    cand = PROC_STOP.sub('', m.group(1)).strip(' .،,؟?!')
    if len(cand) <= len(cur):
        return args
    if nrm(cur) not in nrm(cand):             # must strictly extend current value
        return args
    if nrm(cand) == nrm(cur):
        return args
    args = dict(args)
    args['procedure'] = cand
    return args


WAVE1 = [g1_customs_drop_currency, g2_transfer_explicit_iban,
         g3_insurance_procedure_span]


def apply_reextract(tool, args, text, groups=None):
    """Apply Wave-1 rules to one prediction's arguments. Pure function."""
    if tool == 'none' or not isinstance(args, dict):
        return args
    for fn in (groups if groups is not None else WAVE1):
        args = fn(tool, args, text)
    return args
