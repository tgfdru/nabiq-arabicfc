# -*- coding: utf-8 -*-
"""
run_nabiq_blind.py — Clean blind/test runner for NABIQ-Think-v14.

Replays the frozen NABIQ v14 prediction chain FROM RAW TEXT for an unseen
blind/test JSONL file and writes Track A + Track B submission files.

Frozen chain (exactly the configuration that produced the official Rank #1
dev files — stage choices are hard-coded, decided on dev BEFORE blind release):

  raw rows → processed rows (user/developer text + simplified tool schemas)
  → phase1 base   : train-fitted TF-IDF router + nearest-arg retriever +
                    direct extraction + none-detector  (stages 1→2→3)
  → v3  stages 1→3 (train-mined gazetteer normalization)
  → v4  stages 1→3 (extractors; v5 consumed v4_stage3)
  → v5  strategy B → strategy C selector
  → v6  ArgEM fixes
  → v7  FnAcc fixes ONLY (official v7 = stage1_fnacc)
  → v8  ArgEM fixes → tool packs (stage-3 selector = identity)
  → v9  micro fixes  → v10 micro fixes (selectors = identity)
  → v11 → v12 → v13 micro fixes
  → clean2: general IBAN-validity filter on recipient_iban
  → v14 stage2_toolpacks rules (official v14 final = stage 2)
  → Track B = Track A + generated Arabic think

LEGALITY GUARANTEES
  - No gold file of any kind is read (dev or test). A hard guard refuses
    input paths containing gold / answer / label / dev_gold.
  - No row-ID-specific logic: every step is a pure function of
    (tool, arguments, user_text[, developer_context]) or train-fitted models.
  - Train data is the only supervision source (router/retriever/gazetteers).
  - The golden v14 files are never read, written, or overwritten (guarded).
  - No dataset files are modified; this script only writes its two outputs.

USAGE
  python src/run_nabiq_blind.py \
      --input   data/blind/test.jsonl \
      --track-a outputs/submissions/nabiq_blind_track_a.jsonl \
      --track-b outputs/submissions/nabiq_blind_track_b.jsonl

  Optional:
      --train data/processed_v13/train_processed.jsonl   (default)
"""
import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

# ── Frozen-chain building blocks (all pure / train-fitted; import-safe) ─────
import phase1_rules_v5_pc as p1                       # noqa: E402
import nabiq_v3_pc_pipeline as v3mod                  # noqa: E402
import nabiq_v4_elite_pipeline as v4mod               # noqa: E402
import nabiq_v5_pipeline as v5mod                     # noqa: E402
from nabiq_v6_argem_fixes import apply_v6_fixes       # noqa: E402
from nabiq_v7_fnacc_fixes import apply_fnacc_fixes    # noqa: E402
from nabiq_v8_argem_fixes import apply_v8_fixes       # noqa: E402
from nabiq_v8_tool_packs import apply_pack            # noqa: E402
from nabiq_v9_micro_fixes import apply_v9_fixes       # noqa: E402
from nabiq_v10_micro_fixes import apply_v10_fixes     # noqa: E402
from nabiq_v11_micro_fixes import apply_v11_fixes     # noqa: E402
from nabiq_v12_micro_fixes import apply_v12_fixes     # noqa: E402
from nabiq_v13_micro_fixes import apply_v13_fixes     # noqa: E402
from nabiq_v14_micro_fixes import apply_stage2 as apply_v14_stage2  # noqa: E402

# Golden files that must never be overwritten by this runner.
PROTECTED = {
    (ROOT / 'outputs/submissions/nabiq_v14_pc.jsonl').resolve(),
    (ROOT / 'outputs/submissions/nabiq_think_v14.jsonl').resolve(),
    (ROOT / 'outputs/submissions/nabiq_think_v14_pc.jsonl').resolve(),
}

IBAN_RE = re.compile(r'^[A-Za-z]{2}[0-9A-Za-z]{4,}$')


# ── IO helpers ───────────────────────────────────────────────────────────────
def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


# ── Raw → processed (gold-free replica of prepare_dataset_v13.process_rows) ─
def _msg(messages, role):
    for m in messages or []:
        if m.get('role') == role:
            return m
    return None


def _simplify_tool(tool):
    fn = tool.get('function') or {}
    params = fn.get('parameters') or {}
    props = params.get('properties') or {}
    return {'name': fn.get('name'), 'description': fn.get('description'),
            'parameters': {k: v for k, v in props.items() if v is not None}}


def process_raw_rows(rows):
    """Build prediction-input rows. NO gold fields are extracted — the gold
    placeholders exist only because downstream train-time helpers expect the
    keys; they are never read for prediction (verified in the v14 audit)."""
    out = []
    for idx, row in enumerate(rows):
        messages = row.get('messages') or []
        user_msg = _msg(messages, 'user')
        dev_msg = _msg(messages, 'developer')
        raw_tools = row.get('tools_sampled') or row.get('tools') or []
        out.append({
            'id': row['id'] if 'id' in row else idx,
            'user_text': (user_msg.get('content', '') if user_msg
                          else row.get('text', '') or row.get('user_text', '')),
            'developer_context': dev_msg.get('content', '') if dev_msg else '',
            'available_tools': [_simplify_tool(t) for t in raw_tools],
            'dialect': row.get('dialect'),
            'negative_category': row.get('negative_category'),
            # placeholders (never used for prediction):
            'requires_function': False, 'tool_called': 'none',
            'arguments': {}, 'think': '',
        })
    return out


def prepare_input(rows):
    """Accept either raw rows (messages/tools) or already-processed rows."""
    if rows and 'user_text' in rows[0] and 'available_tools' in rows[0]:
        # already processed — strip any gold fields defensively
        clean = []
        for idx, r in enumerate(rows):
            c = dict(r)
            c.setdefault('id', idx)
            c['tool_called'], c['arguments'], c['think'] = 'none', {}, ''
            clean.append(c)
        return clean
    return process_raw_rows(rows)


# ── Chain stages ─────────────────────────────────────────────────────────────
def phase1_base(rows, train_rows):
    """phase1_rules_v5_pc stages 1→2→3, reimplemented WITHOUT the dev-file
    side-writes of run_stage1/2/3 (those would overwrite historical artifacts).
    Identical per-row logic; models fitted on train only."""
    print('[base] fitting router / retriever / gazetteer / none-detector on train ...')
    router = p1.train_router(train_rows)
    retriever = p1.NearestArgRetriever()
    retriever.fit(train_rows)
    gazetteer = p1.build_gazetteer(train_rows)
    none_detector = p1.train_none_detector(train_rows)

    preds = []
    for row in rows:
        tool = p1.predict_tool(router, row)
        merged = {**retriever.predict(row, tool),
                  **p1.direct_extract(row, tool, gazetteer)}
        merged = p1.conservative_clean(row, tool, merged)
        merged = p1.clean_to_schema(row, tool, merged)
        if p1.get_function_prob(none_detector, row) < p1.NONE_THRESHOLD:
            tool, merged = 'none', {}
        preds.append({'id': row['id'], 'tool_called': tool, 'arguments': merged})

    by_id = {r['id']: r for r in rows}
    preds = [p1.normalize_pred(by_id[p['id']], p) for p in preds]      # stage 2
    preds = [p1.improve_prediction(by_id[p['id']], p) for p in preds]  # stage 3
    return preds


def per_row_fix(preds, rows_by_id, fn, label):
    """Apply an (tool, args, text) → args fix function row-wise."""
    out, changed = [], 0
    for r in preds:
        r = deepcopy(r)
        tool, args = r.get('tool_called', 'none'), r.get('arguments')
        if tool != 'none' and isinstance(args, dict):
            text = rows_by_id[r['id']]['user_text']
            new = fn(tool, deepcopy(args), text)
            if new is not None and new != args:
                r['arguments'] = new
                changed += 1
        out.append(r)
    print(f'[{label}] changed rows: {changed}')
    return out


def run_chain(rows, train_rows):
    by_id = {r['id']: r for r in rows}

    preds = phase1_base(rows, train_rows)                          # ≈ v2 base

    # v3 stages 1→3 (train-mined gazetteers via schema report)
    gaz3 = v3mod.load_gazetteers(v3mod.SCHEMA_REPORT_PATH)
    for stage_fn, label in [(v3mod.improve_stage1, 'v3.s1'),
                            (v3mod.improve_stage2, 'v3.s2'),
                            (v3mod.improve_stage3, 'v3.s3')]:
        preds = [stage_fn(deepcopy(p), by_id[p['id']], gaz3) for p in preds]
        print(f'[{label}] done')

    # v4 stages 1→3 (official chain consumed v4_stage3)
    known = v4mod.load_known_restaurants(train_rows)
    preds = sorted(preds, key=lambda x: x['id'])
    preds = v4mod.apply_stage1(preds, by_id, train_rows)
    preds = v4mod.apply_stage2(preds, by_id)
    preds = v4mod.apply_stage3(preds, by_id, known)
    print('[v4] stages 1-3 done')

    # v5: strategy B then conservative selector C (official v5 final ≡ C ≡ B)
    strat_b = v5mod.apply_strategy_b(preds, by_id)
    preds = v5mod.apply_strategy_c(preds, strat_b, by_id)
    print('[v5] B→C done')

    # v6 ArgEM fixes
    preds = per_row_fix(preds, by_id, apply_v6_fixes, 'v6')

    # v7: FnAcc fixes ONLY (official nabiq_v7.jsonl == v7_stage1_fnacc)
    out = []
    fn_changed = 0
    for r in preds:
        r = deepcopy(r)
        new_tool, new_args = apply_fnacc_fixes(r['tool_called'],
                                               by_id[r['id']]['user_text'])
        if new_tool != r['tool_called']:
            r['tool_called'] = new_tool
            r['arguments'] = {} if new_args is None else new_args
            fn_changed += 1
        out.append(r)
    preds = out
    print(f'[v7] FnAcc tool changes: {fn_changed}')

    # v8: ArgEM fixes → tool packs (gold_tool NEVER passed; stage3 ≡ identity)
    preds = per_row_fix(preds, by_id, apply_v8_fixes, 'v8.fixes')
    preds = per_row_fix(preds, by_id, apply_pack, 'v8.packs')

    # v9 → v13 micro fixes (selectors in v9/v10 are identity passes)
    for fn, label in [(apply_v9_fixes, 'v9'), (apply_v10_fixes, 'v10'),
                      (apply_v11_fixes, 'v11'), (apply_v12_fixes, 'v12'),
                      (apply_v13_fixes, 'v13')]:
        preds = per_row_fix(preds, by_id, fn, label)

    # clean2: general IBAN-validity filter (same rule as v14 audit base)
    dropped = 0
    for r in preds:
        args = r.get('arguments') or {}
        v = args.get('recipient_iban')
        if v is not None and not IBAN_RE.fullmatch(str(v).strip()):
            del args['recipient_iban']
            dropped += 1
    print(f'[clean2] dropped non-IBAN recipient_iban: {dropped}')

    # v14: stage2_toolpacks rules (frozen official final stage)
    out = []
    for r in preds:
        r = deepcopy(r)
        tool, args = r.get('tool_called', 'none'), r.get('arguments')
        if tool != 'none' and isinstance(args, dict):
            row = by_id[r['id']]
            r['arguments'] = apply_v14_stage2(
                tool, deepcopy(args), row['user_text'],
                row.get('developer_context', ''))
        out.append(r)
    preds = out
    print('[v14] stage2_toolpacks rules applied')

    return [{'id': r['id'], 'tool_called': r['tool_called'],
             'arguments': r['arguments']} for r in preds]


# ── Track B think generation (identical to nabiq_v14_pipeline.make_think) ───
NONE_THINK = 'الطلب لا يحتاج إلى استدعاء أي أداة لأن المطلوب خارج نطاق الوظائف المتاحة.'


def make_think(tool, args):
    if tool == 'none' or not args:
        return NONE_THINK
    kv = '، '.join(f'{k}={args[k]}' for k in args.keys())
    return (f'يطلب المستخدم تنفيذ مهمة تناسبها أداة {tool}، '
            f'وقد استخرجت من نص الطلب قيم المدخلات المطلوبة وهي: {kv}.')


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='NABIQ-v14 blind/test runner (gold-free)')
    ap.add_argument('--input', required=True, help='blind/test jsonl (raw or processed)')
    ap.add_argument('--track-a', required=True, help='output Track A jsonl')
    ap.add_argument('--track-b', required=True, help='output Track B jsonl')
    ap.add_argument('--train', default=str(ROOT / 'data/processed_v13/train_processed.jsonl'))
    args = ap.parse_args()

    # Legality guards
    forbidden = ('gold', 'answer', 'label', 'dev_gold')
    in_name = Path(args.input).name.lower()
    if any(w in in_name for w in forbidden):
        sys.exit(f'REFUSED: input filename {in_name!r} matches a forbidden pattern '
                 f'{forbidden} — this runner must never see gold/label files.')
    for out in (args.track_a, args.track_b):
        if Path(out).resolve() in PROTECTED:
            sys.exit(f'REFUSED: {out} is a protected golden file.')

    print(f'input : {args.input}')
    raw = load_jsonl(args.input)
    rows = prepare_input(raw)
    print(f'rows  : {len(rows)}')

    train_rows = load_jsonl(args.train)
    print(f'train : {len(train_rows)} rows (only supervision source)')

    track_a = run_chain(rows, train_rows)

    track_b = []
    for r in track_a:
        rb = deepcopy(r)
        rb['think'] = make_think(rb.get('tool_called', 'none'),
                                 rb.get('arguments') or {})
        track_b.append(rb)

    # Internal consistency checks (no gold involved)
    assert len(track_a) == len(rows) == len(track_b)
    assert [r['id'] for r in track_a] == [row['id'] for row in rows]
    for ra, rb in zip(track_a, track_b):
        assert isinstance(ra['tool_called'], str) and isinstance(ra['arguments'], dict)
        assert 'think' not in ra
        assert ra['id'] == rb['id'] and ra['tool_called'] == rb['tool_called']
        assert ra['arguments'] == rb['arguments']
        assert isinstance(rb['think'], str) and rb['think'].strip()

    write_jsonl(Path(args.track_a), track_a)
    write_jsonl(Path(args.track_b), track_b)
    print(f'\nTrack A -> {args.track_a}')
    print(f'Track B -> {args.track_b}')
    print('DONE - run src/validate_submission_files.py before any submission.')


if __name__ == '__main__':
    main()
