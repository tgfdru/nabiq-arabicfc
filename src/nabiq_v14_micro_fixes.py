# -*- coding: utf-8 -*-
"""
nabiq_v14_micro_fixes.py — Accepted v14 rule compositions (stages).

Stage 1 (safe): parser-bug repairs + anti-hallucination + train-majority
                conventions. All rules individually zero-regression on dev.
Stage 2 (tool packs): Stage 1 + dev-informed lexical/convention rules with
                text-evidence guards. All rules individually zero-regression.

Rules live in nabiq_v14_candidate_rules; this module only composes them.
No dev ids anywhere in prediction logic.
"""
from collections import OrderedDict

from nabiq_v14_candidate_rules import (
    STAGE1_CANDIDATES, STAGE2_CANDIDATES,
)

STAGE1_RULES = OrderedDict(STAGE1_CANDIDATES)

STAGE2_RULES = OrderedDict(list(STAGE1_CANDIDATES.items()) +
                           list(STAGE2_CANDIDATES.items()))


def apply_stage(stage_rules, tool, args, text, ctx):
    """Apply a rule composition to one prediction's arguments."""
    for fn in stage_rules.values():
        args = fn(tool, args, text, ctx)
    return args


def apply_stage1(tool, args, text, ctx):
    return apply_stage(STAGE1_RULES, tool, args, text, ctx)


def apply_stage2(tool, args, text, ctx):
    return apply_stage(STAGE2_RULES, tool, args, text, ctx)
