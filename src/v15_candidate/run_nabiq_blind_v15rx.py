# NOTE: this file was lightly redacted for public release --- an internal
# team-process note naming an individual was replaced with generic wording.
# No logic was changed. The unredacted original ships in the release archive.
# -*- coding: utf-8 -*-
"""
run_nabiq_blind_v15rx.py — v15-reextract-candidate blind runner (Wave 1: G1+G2).

= the frozen v14-substitute chain (imported unchanged from src/run_nabiq_blind.py)
+ the two ACCEPTED Wave-1 re-extraction rules (G1 customs-currency convention,
  G2 explicit recipient_iban re-extraction). G3 was tested and REJECTED
  (dev −1.6 pts) and is NOT applied here.

Candidate status: PASSED all acceptance criteria (see
outputs/reports/blind_prep/v15_reextract_decision.md):
  dev  : ArgEM 0.9200 → 0.9380 (+9 wins / 0 regressions, FnAcc 1.0000)
  seeds: 5/5 improved, mean 0.6455 → 0.6532, 21 wins / 0 regressions
Final adoption for the blind submission requires the submission owner's explicit approval.

CLI identical to the v14 runner. Inherits every legality guard.
"""
import argparse
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'src' / 'v15_candidate'))

import run_nabiq_blind as rn                                   # noqa: E402
from v15_reextract import (apply_reextract,                    # noqa: E402
                           g1_customs_drop_currency,
                           g2_transfer_explicit_iban)

ACCEPTED_GROUPS = [g1_customs_drop_currency, g2_transfer_explicit_iban]


def main():
    ap = argparse.ArgumentParser(description='NABIQ v15-reextract candidate runner (G1+G2)')
    ap.add_argument('--input', required=True)
    ap.add_argument('--track-a', required=True)
    ap.add_argument('--track-b', required=True)
    ap.add_argument('--train', default=str(ROOT / 'data/processed_v13/train_processed.jsonl'))
    args = ap.parse_args()

    forbidden = ('gold', 'answer', 'label', 'dev_gold')
    in_name = Path(args.input).name.lower()
    if any(w in in_name for w in forbidden):
        sys.exit(f'REFUSED: input filename {in_name!r} matches forbidden pattern {forbidden}.')
    for out in (args.track_a, args.track_b):
        if Path(out).resolve() in rn.PROTECTED:
            sys.exit(f'REFUSED: {out} is a protected golden file.')

    rows = rn.prepare_input(rn.load_jsonl(args.input))
    train_rows = rn.load_jsonl(args.train)
    by_id = {r['id']: r for r in rows}
    print(f'rows: {len(rows)}  train: {len(train_rows)}')

    track_a = rn.run_chain(rows, train_rows)          # frozen v14-substitute chain

    changed = 0
    out_rows = []
    for r in track_a:
        r = deepcopy(r)
        if r['tool_called'] != 'none' and isinstance(r.get('arguments'), dict):
            new = apply_reextract(r['tool_called'], r['arguments'],
                                  by_id[r['id']]['user_text'], ACCEPTED_GROUPS)
            if new != r['arguments']:
                changed += 1
                r['arguments'] = new
        out_rows.append(r)
    track_a = out_rows
    print(f'[v15rx G1+G2] changed rows: {changed}')

    track_b = []
    for r in track_a:
        rb = deepcopy(r)
        rb['think'] = rn.make_think(rb['tool_called'], rb.get('arguments') or {})
        track_b.append(rb)

    assert [r['id'] for r in track_a] == [row['id'] for row in rows]
    for ra, rb in zip(track_a, track_b):
        assert isinstance(ra['tool_called'], str) and isinstance(ra['arguments'], dict)
        assert 'think' not in ra and rb['think'].strip()
        assert ra['tool_called'] == rb['tool_called'] and ra['arguments'] == rb['arguments']

    rn.write_jsonl(Path(args.track_a), track_a)
    rn.write_jsonl(Path(args.track_b), track_b)
    print(f'Track A -> {args.track_a}\nTrack B -> {args.track_b}')
    print('v15-REEXTRACT CANDIDATE OUTPUT - do not submit without owner approval.')


if __name__ == '__main__':
    main()
