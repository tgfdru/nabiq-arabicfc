# -*- coding: utf-8 -*-
"""
validate_submission_files.py — Pre-submission validator for NABIQ Track A/B files.

Checks (Track A):
  file exists / valid JSONL / row count == input / ids match input & unique
  tool_called is str / arguments is dict / no `think` field

Checks (Track B):
  all of the above + `think` present and non-empty in every row
  + Track B exactly matches Track A on id / tool_called / arguments

Extra safety checks:
  - recipient_iban: must be IBAN-like, no Arabic characters, not a country
    name; warned if not verbatim-supported by the source user text
  - arguments must stay inside the row's available tool schema (when the
    input file carries tool schemas)

Usage:
  python src/validate_submission_files.py \
      --input   data/blind/test.jsonl \
      --track-a outputs/submissions/nabiq_blind_track_a.jsonl \
      --track-b outputs/submissions/nabiq_blind_track_b.jsonl

Exit code 0 = ALL CHECKS PASSED, 1 = failures found.
No gold data is read (hard guard on input filename).
"""
import argparse
import json
import re
import sys
from pathlib import Path

ARABIC_RE = re.compile(r'[؀-ۿ]')
IBAN_RE = re.compile(r'^[A-Za-z]{2}[0-9A-Za-z]{4,}$')
AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

COUNTRY_NAMES = {
    'مصر', 'السعودية', 'الكويت', 'الإمارات', 'الامارات', 'قطر', 'البحرين',
    'عمان', 'الأردن', 'الاردن', 'لبنان', 'سوريا', 'العراق', 'اليمن', 'ليبيا',
    'تونس', 'الجزائر', 'المغرب', 'السودان', 'فلسطين', 'تركيا',
    'egypt', 'saudi arabia', 'kuwait', 'uae', 'qatar', 'bahrain', 'oman',
    'jordan', 'lebanon', 'syria', 'iraq', 'yemen',
}

errors = []
warnings = []


def err(msg):
    errors.append(msg)
    print(f'  ERROR   {msg}')


def warn(msg):
    warnings.append(msg)
    print(f'  WARNING {msg}')


def ok(msg):
    print(f'  OK      {msg}')


def load_jsonl(path, label):
    p = Path(path)
    if not p.exists():
        err(f'{label}: file not found: {path}')
        return None
    rows = []
    with open(p, encoding='utf-8') as f:
        for n, line in enumerate(f):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                err(f'{label}: invalid JSON at line {n + 1}: {e}')
                return None
    ok(f'{label}: valid JSONL ({len(rows)} rows)')
    return rows


def input_ids_and_meta(input_rows):
    """Extract expected ids, user texts and (optionally) tool schemas from the
    input file (raw or processed format). Gold fields are never read."""
    ids, texts, schemas = [], {}, {}
    for idx, row in enumerate(input_rows):
        rid = row['id'] if 'id' in row else idx
        ids.append(rid)
        if 'user_text' in row:
            text = row.get('user_text', '')
            tools = row.get('available_tools') or []
        else:
            text = ''
            for m in row.get('messages') or []:
                if m.get('role') == 'user':
                    text = m.get('content', '')
                    break
            if not text:
                text = row.get('text', '')
            tools = row.get('tools_sampled') or row.get('tools') or []
        texts[rid] = text
        tool_args = {}
        for t in tools:
            fn = t.get('function') or t  # raw or simplified format
            name = fn.get('name')
            params = fn.get('parameters') or {}
            props = params.get('properties', params) or {}
            if name:
                tool_args[name] = set(props.keys())
        schemas[rid] = tool_args
    return ids, texts, schemas


def check_track(rows, label, expected_ids, want_think):
    ids = [r.get('id') for r in rows]
    if len(rows) != len(expected_ids):
        err(f'{label}: row count {len(rows)} != input {len(expected_ids)}')
    if len(set(ids)) != len(ids):
        err(f'{label}: duplicate ids present')
    else:
        ok(f'{label}: ids unique')
    if ids != expected_ids:
        err(f'{label}: ids do not match input ids/order')
    else:
        ok(f'{label}: ids match input')
    for r in rows:
        i = r.get('id')
        if not isinstance(r.get('tool_called'), str):
            err(f'{label} id={i}: tool_called is not a string')
        if not isinstance(r.get('arguments'), dict):
            err(f'{label} id={i}: arguments is not a dict')
        if want_think:
            t = r.get('think')
            if not isinstance(t, str) or not t.strip():
                err(f'{label} id={i}: think missing or empty')
        else:
            if 'think' in r:
                err(f'{label} id={i}: unexpected think field in Track A')
    ok(f'{label}: field types checked')


def check_iban(rows, texts, label):
    n = 0
    for r in rows:
        v = (r.get('arguments') or {}).get('recipient_iban')
        if v is None:
            continue
        n += 1
        i, sv = r['id'], str(v).strip()
        if ARABIC_RE.search(sv):
            err(f'{label} id={i}: recipient_iban contains Arabic text: {sv!r}')
        if sv.lower() in COUNTRY_NAMES:
            err(f'{label} id={i}: recipient_iban is a country name: {sv!r}')
        if not IBAN_RE.fullmatch(sv):
            err(f'{label} id={i}: recipient_iban not IBAN-like: {sv!r}')
        text = texts.get(i, '')
        if text and sv not in text and sv not in text.translate(AR_DIGITS):
            warn(f'{label} id={i}: recipient_iban {sv!r} not verbatim in user text')
    ok(f'{label}: recipient_iban checked ({n} rows carry it)')


def check_schema(rows, schemas, label):
    checked = unknown = 0
    for r in rows:
        tool, i = r.get('tool_called'), r['id']
        if tool == 'none':
            continue
        tool_args = schemas.get(i) or {}
        if tool not in tool_args:
            unknown += 1  # schema not available for this row/tool
            continue
        allowed = tool_args[tool]
        if not allowed:
            continue
        checked += 1
        extra = set((r.get('arguments') or {}).keys()) - allowed
        if extra:
            err(f'{label} id={i}: arguments outside {tool} schema: {sorted(extra)}')
    ok(f'{label}: schema conformity checked ({checked} rows; {unknown} rows without schema info)')


def check_b_matches_a(a_rows, b_rows):
    a_by_id = {r['id']: r for r in a_rows}
    mism = 0
    for rb in b_rows:
        ra = a_by_id.get(rb['id'])
        if ra is None:
            err(f'Track B id={rb["id"]}: no matching Track A row')
            mism += 1
            continue
        if ra['tool_called'] != rb['tool_called'] or ra['arguments'] != rb['arguments']:
            err(f'Track B id={rb["id"]}: tool/arguments differ from Track A')
            mism += 1
    if mism == 0:
        ok('Track B exactly matches Track A on id/tool_called/arguments')


def main():
    ap = argparse.ArgumentParser(description='Validate NABIQ Track A/B submission files')
    ap.add_argument('--input', required=True, help='the blind/test input jsonl')
    ap.add_argument('--track-a', required=True)
    ap.add_argument('--track-b', required=True)
    args = ap.parse_args()

    forbidden = ('gold', 'answer', 'label', 'dev_gold')
    in_name = Path(args.input).name.lower()
    if any(w in in_name for w in forbidden):
        sys.exit(f'REFUSED: validator input {in_name!r} matches a forbidden pattern '
                 f'{forbidden} — the input must be the blind/test file, never gold/labels.')

    print('== Input ==')
    input_rows = load_jsonl(args.input, 'input')
    if input_rows is None:
        sys.exit(1)
    expected_ids, texts, schemas = input_ids_and_meta(input_rows)

    print('\n== Track A ==')
    a_rows = load_jsonl(args.track_a, 'Track A')
    if a_rows is not None:
        check_track(a_rows, 'Track A', expected_ids, want_think=False)
        check_iban(a_rows, texts, 'Track A')
        check_schema(a_rows, schemas, 'Track A')

    print('\n== Track B ==')
    b_rows = load_jsonl(args.track_b, 'Track B')
    if b_rows is not None:
        check_track(b_rows, 'Track B', expected_ids, want_think=True)
        check_iban(b_rows, texts, 'Track B')
        check_schema(b_rows, schemas, 'Track B')

    if a_rows is not None and b_rows is not None:
        print('\n== Cross-track ==')
        check_b_matches_a(a_rows, b_rows)

    print('\n' + '=' * 60)
    print(f'RESULT: {len(errors)} error(s), {len(warnings)} warning(s)')
    if errors:
        print('VERDICT: DO NOT SUBMIT — fix errors first.')
        sys.exit(1)
    if warnings:
        print('VERDICT: PASSED WITH WARNINGS — review warnings before submitting.')
    else:
        print('VERDICT: ALL CHECKS PASSED.')
    sys.exit(0)


if __name__ == '__main__':
    main()
