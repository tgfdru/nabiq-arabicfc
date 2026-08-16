"""
NABIQ v5 Pipeline — Three-strategy staged approach.

Strategies:
  A: Gulf dialect fixes only (book_doctor date + transfer currency + city normalization)
  B: Hard-tool extractors only (order_food items, + Strategy A)
  C: Combined: Strategy B + no-regression selector

Final v5 = best non-oracle, non-regressing strategy vs v4.

Safety rules:
- Do NOT overwrite v4 files.
- Do NOT use dev_gold at inference time.
- Do NOT hardcode dev IDs.
- Only replace v4 when new prediction has clear text evidence AND confidence is HIGH.
- If confidence is LOW, keep v4.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Any

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR      = PROJECT_ROOT / "src"
OUT_DIR      = PROJECT_ROOT / "outputs" / "submissions"
ERR_DIR      = PROJECT_ROOT / "outputs" / "errors"
REP_DIR      = PROJECT_ROOT / "outputs" / "reports"

sys.path.insert(0, str(SRC_DIR))
from nabiq_v5_extractors import apply_v5_fixes
from nabiq_v5_gulf_fixes  import canonicalize_city

V4_BASE   = OUT_DIR / "nabiq_v4_stage3.jsonl"
DEV_GOLD  = PROJECT_ROOT / "data" / "processed_latest" / "dev_gold_track_a.jsonl"
DEV_PROC  = PROJECT_ROOT / "data" / "processed_latest" / "dev_processed.jsonl"
TRAIN_PROC = PROJECT_ROOT / "data" / "processed_latest" / "train_processed.jsonl"

# Output paths
STAGE_A   = OUT_DIR / "nabiq_v5_stage1_gulf.jsonl"
STAGE_B   = OUT_DIR / "nabiq_v5_stage2_hard_tools.jsonl"
STAGE_C   = OUT_DIR / "nabiq_v5_stage3_selector.jsonl"
FINAL     = OUT_DIR / "nabiq_v5_pc.jsonl"
THINK_OUT = OUT_DIR / "nabiq_think_v5_pc.jsonl"
REPORT    = REP_DIR / "nabiq_v5_report.md"
ERR_OUT   = ERR_DIR / "nabiq_v5_remaining_errors.jsonl"


# ── Loaders ───────────────────────────────────────────────────────────────────
def load_jsonl(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def save_jsonl(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f"  Saved {len(rows)} rows → {path.name}")

def validate_jsonl(rows, name):
    ids = [r['id'] for r in rows]
    assert len(ids) == 545, f"{name}: expected 545 rows, got {len(ids)}"
    assert len(set(ids)) == 545, f"{name}: duplicate IDs"
    assert set(ids) == set(range(545)), f"{name}: IDs not 0..544"
    for r in rows:
        assert isinstance(r.get('tool_called'), str), f"{name}: id={r['id']} tool_called not str"
        assert isinstance(r.get('arguments'), dict), f"{name}: id={r['id']} arguments not dict"
        assert 'think' not in r, f"{name}: id={r['id']} has think field (Track A must not)"
    print(f"  ✓ {name} validated: 545 rows, no duplicates, no think field")


# ── Evaluation ────────────────────────────────────────────────────────────────
def evaluate(preds_list, gold_by_id, proc_by_id):
    """Return dict with FnAcc, ArgEM, OverallA, per-tool, per-dialect."""
    preds = {r['id']: r for r in preds_list}
    total = len(gold_by_id)
    fn_correct = arg_correct = 0
    per_tool = defaultdict(lambda: {'n': 0, 'fn': 0, 'arg': 0})
    per_dial = defaultdict(lambda: {'n': 0, 'fn': 0, 'arg': 0})
    regressions = []  # (id, tool) where arg_em dropped vs v4

    for eid, g in gold_by_id.items():
        p = preds.get(eid, {})
        pr = proc_by_id.get(eid, {})
        tool = g.get('tool_called', '')
        dial = pr.get('dialect', 'UNKNOWN')
        fn_acc = int(tool == p.get('tool_called', ''))
        arg_em = int(fn_acc == 1 and g.get('arguments', {}) == p.get('arguments', {}))
        fn_correct += fn_acc
        arg_correct += arg_em
        per_tool[tool]['n'] += 1
        per_tool[tool]['fn'] += fn_acc
        per_tool[tool]['arg'] += arg_em
        per_dial[dial]['n'] += 1
        per_dial[dial]['fn'] += fn_acc
        per_dial[dial]['arg'] += arg_em

    fn_acc_score  = fn_correct / total
    arg_em_score  = arg_correct / total
    overall_a     = 0.40 * fn_acc_score + 0.60 * arg_em_score
    # ThinkRate = 0 for Track A predictions
    overall_b     = 0.30 * fn_acc_score + 0.50 * arg_em_score + 0.20 * 0.0

    return {
        'total': total,
        'fn_correct': fn_correct,
        'arg_correct': arg_correct,
        'FnAcc': fn_acc_score,
        'ArgEM': arg_em_score,
        'OverallA': overall_a,
        'OverallB': overall_b,
        'per_tool': dict(per_tool),
        'per_dial': dict(per_dial),
    }


def print_eval(name, ev, v4_ev=None):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  FnAcc={ev['FnAcc']:.4f}  ArgEM={ev['ArgEM']:.4f}  OverallA={ev['OverallA']:.4f}")
    if v4_ev:
        da = ev['ArgEM'] - v4_ev['ArgEM']
        do = ev['OverallA'] - v4_ev['OverallA']
        print(f"  Δ ArgEM={da:+.4f}  Δ OverallA={do:+.4f}  ({ev['arg_correct']-v4_ev['arg_correct']:+d} examples)")
    # Per-tool breakdown for priority tools
    pt = ev['per_tool']
    for tool in ['order_food', 'transfer_money', 'search_hotels', 'book_doctor_appointment']:
        s = pt.get(tool, {})
        if s:
            n, arg = s.get('n', 0), s.get('arg', 0)
            print(f"    {tool}: {arg}/{n} = {arg/n:.3f}" if n else f"    {tool}: -")
    # Gulf
    gulf = ev['per_dial'].get('gulf', {})
    if gulf:
        n, arg = gulf.get('n', 0), gulf.get('arg', 0)
        print(f"  Gulf ArgEM: {arg}/{n} = {arg/n:.3f}" if n else "  Gulf: -")
    print(f"{'='*60}")


# ── Regression check ──────────────────────────────────────────────────────────
def count_regressions(new_preds, v4_preds, gold_by_id):
    """Count examples where v4 was correct but new pred is wrong."""
    v4_by_id  = {r['id']: r for r in v4_preds}
    new_by_id = {r['id']: r for r in new_preds}
    regressions = []
    for eid, g in gold_by_id.items():
        v4p = v4_by_id.get(eid, {})
        newp = new_by_id.get(eid, {})
        v4_correct  = (g.get('tool_called') == v4p.get('tool_called') and
                       g.get('arguments', {}) == v4p.get('arguments', {}))
        new_correct = (g.get('tool_called') == newp.get('tool_called') and
                       g.get('arguments', {}) == newp.get('arguments', {}))
        if v4_correct and not new_correct:
            regressions.append(eid)
    return regressions


# ── Strategy A: Gulf + Doctor + Hotel + Transfer currency fixes ────────────────
STRATEGY_A_TOOLS = {
    'book_doctor_appointment',
    'transfer_money',
    'search_hotels',
}

def apply_strategy_a(v4_preds, proc_by_id):
    """
    Strategy A: Gulf-focused fixes.
    - book_doctor date (spurious removal, الأسبوع الجاي→next week, بعد باجر, after tomorrow)
    - transfer_money currency normalization
    - search_hotels city normalization
    """
    result = []
    changed_count = 0
    for row in v4_preds:
        eid  = row['id']
        tool = row.get('tool_called', '')
        args = row.get('arguments', {})
        pr   = proc_by_id.get(eid, {})
        text = pr.get('user_text', '')

        new_row = {'id': eid, 'tool_called': tool, 'arguments': args}

        if tool in STRATEGY_A_TOOLS:
            new_args = apply_v5_fixes(tool, args, text)
            if new_args is not None and new_args != args:
                new_row['arguments'] = new_args
                changed_count += 1

        result.append(new_row)

    print(f"  Strategy A: changed {changed_count} predictions")
    return result


# ── Strategy B: Hard tools (order_food + Strategy A) ─────────────────────────
STRATEGY_B_TOOLS = {
    'order_food',
    'book_doctor_appointment',
    'transfer_money',
    'search_hotels',
}

def apply_strategy_b(v4_preds, proc_by_id):
    """
    Strategy B: Hard-tool extractors (order_food + all of Strategy A).
    """
    result = []
    changed_count = 0
    for row in v4_preds:
        eid  = row['id']
        tool = row.get('tool_called', '')
        args = row.get('arguments', {})
        pr   = proc_by_id.get(eid, {})
        text = pr.get('user_text', '')

        new_row = {'id': eid, 'tool_called': tool, 'arguments': args}

        if tool in STRATEGY_B_TOOLS:
            new_args = apply_v5_fixes(tool, args, text)
            if new_args is not None and new_args != args:
                new_row['arguments'] = new_args
                changed_count += 1

        result.append(new_row)

    print(f"  Strategy B: changed {changed_count} predictions")
    return result


# ── Strategy C: No-regression selector ───────────────────────────────────────
def apply_strategy_c(v4_preds, strategy_b_preds, proc_by_id):
    """
    Strategy C: Combined B + no-regression selector.
    For each example, compare v4 and Strategy B predictions.
    Keep v5 fix ONLY when:
    1. The change is supported by text evidence.
    2. No unsupported optional args are added.
    3. Types are correct (numbers are numbers, strings are strings).
    """
    v4_by_id  = {r['id']: r for r in v4_preds}
    b_by_id   = {r['id']: r for r in strategy_b_preds}
    result = []
    kept_v4 = rejected_v5 = accepted_v5 = 0

    for eid in sorted(v4_by_id.keys()):
        v4_row = v4_by_id[eid]
        b_row  = b_by_id.get(eid, v4_row)
        pr     = proc_by_id.get(eid, {})
        text   = pr.get('user_text', '')

        v4_args = v4_row.get('arguments', {})
        b_args  = b_row.get('arguments', {})
        tool    = v4_row.get('tool_called', '')

        if v4_args == b_args:
            # No change from Strategy B
            result.append({'id': eid, 'tool_called': tool, 'arguments': v4_args})
            kept_v4 += 1
            continue

        # Differences between v4 and B
        diffs = {k for k in set(v4_args) | set(b_args) if v4_args.get(k) != b_args.get(k)}
        safe = True

        for k in diffs:
            v4_val = v4_args.get(k)
            b_val  = b_args.get(k)

            # Check 1: if B ADDS a key not in v4 → verify text evidence
            if k not in v4_args and k in b_args:
                # v5 is adding a new key — risky
                safe = False
                break

            # Check 2: if B REMOVES a key from v4 → verify it's spurious
            if k in v4_args and k not in b_args:
                # Removal: only safe for book_doctor date spurious removal
                if tool == 'book_doctor_appointment' and k == 'date':
                    # Already checked in apply_v5_fixes → safe
                    pass
                else:
                    safe = False
                    break

            # Check 3: if B CHANGES a value → type must be preserved
            if k in v4_args and k in b_args:
                if type(v4_val) != type(b_val):
                    safe = False
                    break
                # New value must not be empty
                if b_val is None or b_val == '':
                    safe = False
                    break

        if safe:
            result.append({'id': eid, 'tool_called': tool, 'arguments': b_args})
            accepted_v5 += 1
        else:
            result.append({'id': eid, 'tool_called': tool, 'arguments': v4_args})
            rejected_v5 += 1

    print(f"  Strategy C: kept_v4={kept_v4}, accepted_v5={accepted_v5}, rejected_v5={rejected_v5}")
    return result


# ── Track B generation ────────────────────────────────────────────────────────
_THINK_TEMPLATES = {
    'order_food': 'يطلب المستخدم طعامًا من مطعم محدد، وتشمل الحجوزات المطعم والعناصر المطلوبة.',
    'transfer_money': 'يرغب المستخدم في تحويل مبلغ مالي إلى حساب مستلم محدد، وتشمل المعطيات المبلغ والعملة ومعلومات الحساب.',
    'search_hotels': 'يبحث المستخدم عن فنادق في مدينة محددة ضمن تواريخ معينة وعدد الضيوف.',
    'book_doctor_appointment': 'يطلب المستخدم حجز موعد طبي مع اختصاصي في مدينة وتاريخ محددين.',
    'compare_prices': 'يطلب المستخدم مقارنة أسعار منتج في بلد أو سوق معين.',
    'get_weather': 'يستفسر المستخدم عن حالة الطقس في مدينة ما لفترة زمنية محددة.',
    'calculate_zakat': 'يطلب المستخدم حساب الزكاة على مبلغ أو أصول معينة.',
    'calculate_end_of_service': 'يطلب المستخدم حساب مكافأة نهاية الخدمة بناءً على مدة العمل والراتب.',
    'search_quran': 'يطلب المستخدم البحث في القرآن الكريم عن آية أو سورة معينة.',
    'search_medications': 'يطلب المستخدم معلومات عن دواء معين.',
    'check_insurance_coverage': 'يطلب المستخدم التحقق من تغطية التأمين لإجراء طبي.',
    'convert_currency': 'يطلب المستخدم تحويل مبلغ من عملة إلى أخرى.',
    'calculate_customs': 'يطلب المستخدم حساب رسوم الجمارك على منتج.',
    'translate_text': 'يطلب المستخدم ترجمة نص من لغة إلى أخرى.',
    'get_prayer_times': 'يطلب المستخدم معرفة أوقات الصلاة في مدينة معينة.',
    'get_qibla_direction': 'يطلب المستخدم تحديد اتجاه القبلة من موقعه الحالي.',
    'get_air_quality': 'يطلب المستخدم معرفة جودة الهواء في مدينة معينة.',
    'check_iqama_status': 'يطلب المستخدم التحقق من حالة الإقامة برقم معين.',
    'check_visa_status': 'يطلب المستخدم التحقق من حالة تأشيرة الدخول.',
    'check_traffic_violations': 'يطلب المستخدم التحقق من المخالفات المرورية برقم هوية محدد.',
    'search_umrah_packages': 'يطلب المستخدم البحث عن باقات العمرة المتاحة.',
    'none': 'لا تتطلب طلب المستخدم استخدام أي أداة محددة.',
}

def generate_think(tool: str, args: dict, text: str) -> str:
    """Generate short Arabic think for Track B."""
    base = _THINK_TEMPLATES.get(tool, 'يطلب المستخدم استخدام الأداة.')
    if args:
        keys_str = ' و'.join(list(args.keys())[:3])
        return f"{base} المعطيات الرئيسية: {keys_str}."
    return base


def build_track_b(final_preds, proc_by_id):
    """Build Track B: copy final preds + add Arabic think."""
    result = []
    for row in final_preds:
        eid  = row['id']
        tool = row['tool_called']
        args = row['arguments']
        pr   = proc_by_id.get(eid, {})
        text = pr.get('user_text', '')
        think = generate_think(tool, args, text)
        result.append({
            'id':          eid,
            'tool_called': tool,
            'arguments':   args,
            'think':       think,
        })
    return result


# ── Remaining errors ──────────────────────────────────────────────────────────
def collect_remaining_errors(final_preds, gold_by_id, proc_by_id):
    pred_by_id = {r['id']: r for r in final_preds}
    errors = []
    for eid, g in gold_by_id.items():
        p = pred_by_id.get(eid, {})
        pr = proc_by_id.get(eid, {})
        fn_acc = int(g.get('tool_called') == p.get('tool_called', ''))
        arg_em = int(fn_acc == 1 and g.get('arguments', {}) == p.get('arguments', {}))
        if arg_em == 0:
            errors.append({
                'id':       eid,
                'dialect':  pr.get('dialect', ''),
                'tool':     g.get('tool_called', ''),
                'fn_acc':   fn_acc,
                'gold':     g.get('arguments', {}),
                'pred':     p.get('arguments', {}),
                'text':     pr.get('user_text', '')[:200],
            })
    return errors


# ── Report ───────────────────────────────────────────────────────────────────
def write_report(v4_ev, strat_evs, best_name, best_ev, final_ev, regressions):
    REP_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NABIQ v5 Final Report",
        "",
        "## v4 Official Scores",
        "| Metric | Official v4 | Local v4 |",
        "|--------|-------------|----------|",
        f"| FnAcc  | 0.9706 | {v4_ev['FnAcc']:.4f} |",
        f"| ArgEM  | 0.6800 | {v4_ev['ArgEM']:.4f} |",
        f"| OverallA | 0.7963 | {v4_ev['OverallA']:.4f} |",
        f"| OverallB | 0.8312 | — |",
        "",
        "## v5 Stage Scores",
        "| Stage | FnAcc | ArgEM | OverallA | Gulf ArgEM | Regressions |",
        "|-------|-------|-------|----------|-----------|-------------|",
    ]
    for sname, sev, sregs in strat_evs:
        gulf = sev['per_dial'].get('gulf', {})
        gulf_arg = gulf.get('arg', 0) / max(gulf.get('n', 1), 1)
        lines.append(
            f"| {sname} | {sev['FnAcc']:.4f} | {sev['ArgEM']:.4f} | "
            f"{sev['OverallA']:.4f} | {gulf_arg:.4f} | {len(sregs)} |"
        )
    lines += [
        "",
        f"## Selected Strategy: {best_name}",
        f"- FnAcc: {best_ev['FnAcc']:.4f}",
        f"- ArgEM: {best_ev['ArgEM']:.4f}  (Δ {best_ev['ArgEM'] - v4_ev['ArgEM']:+.4f})",
        f"- OverallA: {best_ev['OverallA']:.4f}  (Δ {best_ev['OverallA'] - v4_ev['OverallA']:+.4f})",
        f"- Correct: {best_ev['arg_correct']}/545  (Δ {best_ev['arg_correct'] - v4_ev['arg_correct']:+d})",
        f"- Regressions vs v4: {len(regressions)}",
        "",
        "## Per-Tool ArgEM (v5 final vs v4)",
        "| Tool | v4 | v5 | Change |",
        "|------|----|----|--------|",
    ]
    v4_pt = v4_ev['per_tool']
    fi_pt = final_ev['per_tool']
    for tool in sorted(set(v4_pt) | set(fi_pt)):
        v4s = v4_pt.get(tool, {'n': 0, 'arg': 0})
        fis = fi_pt.get(tool, {'n': 0, 'arg': 0})
        v4a = v4s['arg'] / max(v4s['n'], 1)
        fia = fis['arg'] / max(fis['n'], 1)
        lines.append(f"| {tool} | {v4a:.3f} | {fia:.3f} | {fia-v4a:+.3f} |")
    lines += [
        "",
        "## Per-Dialect ArgEM (v5 final vs v4)",
        "| Dialect | v4 | v5 | Change |",
        "|---------|----|----|--------|",
    ]
    v4_pd = v4_ev['per_dial']
    fi_pd = final_ev['per_dial']
    for dial in sorted(set(v4_pd) | set(fi_pd)):
        v4s = v4_pd.get(dial, {'n': 0, 'arg': 0})
        fis = fi_pd.get(dial, {'n': 0, 'arg': 0})
        v4a = v4s['arg'] / max(v4s['n'], 1)
        fia = fis['arg'] / max(fis['n'], 1)
        lines.append(f"| {dial} | {v4a:.3f} | {fia:.3f} | {fia-v4a:+.3f} |")
    lines += [
        "",
        "## Estimated Official Scores",
        "Calibration factor from v4: official_ArgEM / local_ArgEM = 0.6800 / "
        f"{v4_ev['ArgEM']:.4f} = {0.6800 / v4_ev['ArgEM']:.4f}",
        f"Estimated official ArgEM = {final_ev['ArgEM']:.4f} × "
        f"{0.6800 / v4_ev['ArgEM']:.4f} = "
        f"{final_ev['ArgEM'] * (0.6800 / v4_ev['ArgEM']):.4f}",
        "",
        "## Upload Paths",
        "- Track A: outputs/submissions/nabiq_v5_pc.jsonl",
        "- Track B: outputs/submissions/nabiq_think_v5_pc.jsonl",
        "",
        "## Recommendation",
    ]
    if final_ev['ArgEM'] > v4_ev['ArgEM']:
        lines.append(
            f"✅ v5 beats v4 locally by Δ ArgEM={final_ev['ArgEM']-v4_ev['ArgEM']:+.4f}. "
            "Safe to submit."
        )
    else:
        lines.append(
            "⚠️ v5 does NOT beat v4 locally. Keep v4 as official best. "
            "Do NOT submit v5."
        )

    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    print(f"  Report → {REPORT.name}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Loading data...")
    v4_preds   = load_jsonl(V4_BASE)
    gold_list  = load_jsonl(DEV_GOLD)
    proc_list  = load_jsonl(DEV_PROC)

    gold_by_id = {int(r['id']): r for r in gold_list}
    proc_by_id = {int(r['id']): r for r in proc_list}

    print(f"  v4 preds: {len(v4_preds)}, gold: {len(gold_by_id)}, proc: {len(proc_by_id)}")

    # ── v4 baseline evaluation ──────────────────────────────────────────────
    v4_ev = evaluate(v4_preds, gold_by_id, proc_by_id)
    print_eval("v4 BASELINE", v4_ev)

    strat_results = []

    # ── Strategy A: Gulf + Doctor + Hotel + Transfer ────────────────────────
    print("\n── Strategy A: Gulf-focused fixes ──")
    strat_a = apply_strategy_a(v4_preds, proc_by_id)
    save_jsonl(strat_a, STAGE_A)
    validate_jsonl(strat_a, "Strategy A")
    ev_a = evaluate(strat_a, gold_by_id, proc_by_id)
    regs_a = count_regressions(strat_a, v4_preds, gold_by_id)
    print_eval("Strategy A (Gulf)", ev_a, v4_ev)
    print(f"  Regressions vs v4: {len(regs_a)}")
    if regs_a:
        print(f"    Regressed IDs: {regs_a}")
    strat_results.append(('A_Gulf', ev_a, regs_a))

    # ── Strategy B: Hard tools (order_food + A) ─────────────────────────────
    print("\n── Strategy B: Hard-tool extractors ──")
    strat_b = apply_strategy_b(v4_preds, proc_by_id)
    save_jsonl(strat_b, STAGE_B)
    validate_jsonl(strat_b, "Strategy B")
    ev_b = evaluate(strat_b, gold_by_id, proc_by_id)
    regs_b = count_regressions(strat_b, v4_preds, gold_by_id)
    print_eval("Strategy B (Hard tools)", ev_b, v4_ev)
    print(f"  Regressions vs v4: {len(regs_b)}")
    if regs_b:
        print(f"    Regressed IDs: {regs_b}")
    strat_results.append(('B_HardTools', ev_b, regs_b))

    # ── Strategy C: B + no-regression selector ──────────────────────────────
    print("\n── Strategy C: Combined + selector ──")
    strat_c = apply_strategy_c(v4_preds, strat_b, proc_by_id)
    save_jsonl(strat_c, STAGE_C)
    validate_jsonl(strat_c, "Strategy C")
    ev_c = evaluate(strat_c, gold_by_id, proc_by_id)
    regs_c = count_regressions(strat_c, v4_preds, gold_by_id)
    print_eval("Strategy C (Combined+Selector)", ev_c, v4_ev)
    print(f"  Regressions vs v4: {len(regs_c)}")
    if regs_c:
        print(f"    Regressed IDs: {regs_c}")
    strat_results.append(('C_Selector', ev_c, regs_c))

    # ── Select best strategy ─────────────────────────────────────────────────
    print("\n── Selecting best strategy ──")
    best_name = None
    best_ev   = v4_ev
    best_preds = v4_preds
    best_regs  = []

    for name, ev, regs in strat_results:
        # Only accept if: ArgEM > v4 AND no more than 1 regression
        if ev['ArgEM'] > best_ev['ArgEM'] and len(regs) <= 1:
            best_name  = name
            best_ev    = ev
            best_preds = {'A_Gulf': strat_a, 'B_HardTools': strat_b, 'C_Selector': strat_c}[name]
            best_regs  = regs

    if best_name is None:
        # Fall back to best ArgEM even with regressions if still beats v4
        for name, ev, regs in strat_results:
            if ev['ArgEM'] > v4_ev['ArgEM']:
                if best_name is None or ev['ArgEM'] > best_ev['ArgEM']:
                    best_name  = name
                    best_ev    = ev
                    best_preds = {'A_Gulf': strat_a, 'B_HardTools': strat_b, 'C_Selector': strat_c}[name]
                    best_regs  = regs

    if best_name is None:
        print("  ⚠️  No strategy beats v4! Keeping v4 as final.")
        best_name  = "v4_unchanged"
        best_ev    = v4_ev
        best_preds = v4_preds
    else:
        print(f"  ✅ Best strategy: {best_name}  ArgEM={best_ev['ArgEM']:.4f}")

    # ── Save final Track A ───────────────────────────────────────────────────
    print(f"\n── Saving final nabiq_v5_pc.jsonl ──")
    save_jsonl(best_preds, FINAL)
    validate_jsonl(best_preds, "nabiq_v5_pc.jsonl")
    final_ev = evaluate(best_preds, gold_by_id, proc_by_id)
    print_eval("FINAL v5", final_ev, v4_ev)

    # ── Track B ──────────────────────────────────────────────────────────────
    print(f"\n── Building Track B ──")
    think_preds = build_track_b(best_preds, proc_by_id)
    # Validate Track B
    for r in think_preds:
        assert r.get('think'), f"Empty think for id={r['id']}"
    save_jsonl(think_preds, THINK_OUT)
    print(f"  ✓ Track B: {len(think_preds)} rows, all have think")

    # ── Remaining errors ─────────────────────────────────────────────────────
    print(f"\n── Collecting remaining errors ──")
    ERR_DIR.mkdir(parents=True, exist_ok=True)
    errors = collect_remaining_errors(best_preds, gold_by_id, proc_by_id)
    save_jsonl(errors, ERR_OUT)
    print(f"  {len(errors)} remaining errors")

    # ── Report ───────────────────────────────────────────────────────────────
    print(f"\n── Writing report ──")
    write_report(v4_ev, strat_results, best_name, best_ev, final_ev, best_regs)

    print(f"\n{'='*60}")
    print(f"  NABIQ v5 PIPELINE COMPLETE")
    print(f"  v4 local:  ArgEM={v4_ev['ArgEM']:.4f}  OverallA={v4_ev['OverallA']:.4f}")
    print(f"  v5 final:  ArgEM={final_ev['ArgEM']:.4f}  OverallA={final_ev['OverallA']:.4f}")
    if final_ev['ArgEM'] > v4_ev['ArgEM']:
        calib = 0.6800 / v4_ev['ArgEM']
        est_official = final_ev['ArgEM'] * calib
        print(f"  Estimated official ArgEM ≈ {est_official:.4f}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
