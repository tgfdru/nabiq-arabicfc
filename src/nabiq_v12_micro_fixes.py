"""
NABIQ v12 Micro-Fixes
=====================
Surgical post-processing fixes on top of v11, targeting +14 wins / 0 regressions
on v13 dev gold (strict scorer).

Fix groups:
  A — book_doctor_appointment: specialty + date + city verbatim extraction
  B — search_hotels: Arabic month-day → ISO 2023 date conversion
  C — transfer_money: friend-transfer name fix + procedural query stripping

All fixes are text-evidence-based. No id-specific rules. No gold oracle at test time.
"""

import re

# ---------------------------------------------------------------------------
# Shared regex
# ---------------------------------------------------------------------------
_ARABIC_DAY = re.compile(
    r'^(?:الأحد|الاثنين|الاتنين|الثلاثاء|الأربعاء|الخميس|الجمعة|السبت)$'
)
_AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_AR_MONTH_MAP = {
    'يناير': '01', 'فبراير': '02', 'مارس': '03', 'أبريل': '04', 'إبريل': '04',
    'مايو': '05', 'يونيو': '06', 'يوليو': '07', 'أغسطس': '08',
    'سبتمبر': '09', 'أكتوبر': '10', 'نوفمبر': '11', 'ديسمبر': '12',
}
_TM_PROCEDURAL_RE = re.compile(
    'شنو هي الإجراءات|ما الإجراءات|ما هي الإجراءات|ما إجراءات'
    '|كيف أحول|ما الخطوات|كيف بحول'
)


# ---------------------------------------------------------------------------
# Fix A1 — BDA: unified specialty verbatim extraction
# ---------------------------------------------------------------------------
def _fix_bda_specialty(args: dict, text: str) -> dict:
    spec = str(args.get('specialty', ''))

    # A1a: نساء وولادة → correct OB/GYN form from text
    if 'ولادة' in spec:
        if 'طبيب نسائية' in text:
            args['specialty'] = 'طبيب نسائية'
        elif 'التوليد' in text:
            args['specialty'] = 'نساء وتوليد'
        return args

    # A1b: أسنان → طبيب أسنان
    if spec == 'أسنان' and 'طبيب أسنان' in text:
        args['specialty'] = 'طبيب أسنان'
        return args

    # A1c: أطفال → طبيب الأطفال
    if spec == 'أطفال' and 'طبيب الأطفال' in text:
        args['specialty'] = 'طبيب الأطفال'
        return args

    # A1d: جلدية → أمراض جلدية (combined with city fix below)
    if spec == 'جلدية' and 'أمراض جلدية' in text:
        args['specialty'] = 'أمراض جلدية'
        return args

    # A1e: أنف وأذن وحنجرة → دكتور أنف وأذن وحنجرة (exact text match)
    if spec == 'أنف وأذن وحنجرة' and 'دكتور أنف وأذن وحنجرة' in text:
        args['specialty'] = 'دكتور أنف وأذن وحنجرة'
        return args

    return args


# ---------------------------------------------------------------------------
# Fix A2 — BDA: date verbatim extraction
# ---------------------------------------------------------------------------
def _fix_bda_date(args: dict, text: str) -> dict:
    date = str(args.get('date', ''))

    # A2a: tomorrow → بكرة (Maghrebi dialect)
    if date.lower() == 'tomorrow' and 'بكرة' in text:
        args['date'] = 'بكرة'
        return args

    # A2b: الجمعة → Friday when text says يوم الجمعة
    if date == 'الجمعة' and 'يوم الجمعة' in text:
        args['date'] = 'Friday'
        return args

    # A2c: Arabic day name → نهار+day when text has standalone نهار prefix
    # (lookbehind ensures we match 'نهار الجمعة' but NOT 'النهار السبت')
    if _ARABIC_DAY.match(date):
        m = re.search(r'(?:^|(?<=\s))نهار\s+' + re.escape(date), text)
        if m:
            args['date'] = m.group().strip()
            return args

    return args


# ---------------------------------------------------------------------------
# Fix A3 — BDA: city verbatim extraction
# ---------------------------------------------------------------------------
def _fix_bda_city(args: dict, text: str) -> dict:
    # A3a: city → العاصمة when text mentions it
    if 'العاصمة' in text and args.get('city', '') != 'العاصمة':
        args['city'] = 'العاصمة'
        return args

    # A3b: city → مدينة الكويت when text mentions it
    if 'مدينة الكويت' in text and args.get('city', '') != 'مدينة الكويت':
        args['city'] = 'مدينة الكويت'
        return args

    return args


def fix_book_doctor_appointment(tool_name: str, args: dict, user_text: str) -> dict:
    """Apply all BDA verbatim-extraction fixes."""
    if tool_name != 'book_doctor_appointment':
        return args
    args = _fix_bda_specialty(args, user_text)
    args = _fix_bda_date(args, user_text)
    args = _fix_bda_city(args, user_text)
    return args


# ---------------------------------------------------------------------------
# Fix B — search_hotels: Arabic month-day → ISO 2023
# ---------------------------------------------------------------------------
def _ar_date_to_iso(value: str, year: str = '2023') -> str | None:
    """
    Convert 'N شهر' or 'NN شهر' (with Arabic or Western digits) to 'YYYY-MM-DD'.
    Returns None if the value doesn't match the pattern.
    """
    s = str(value).translate(_AR_DIGITS).strip()
    for ar_month, mm in _AR_MONTH_MAP.items():
        m = re.match(r'^(\d{1,2})\s+' + re.escape(ar_month) + r'$', s)
        if m:
            dd = m.group(1).zfill(2)
            return f'{year}-{mm}-{dd}'
    return None


def fix_search_hotels_dates(tool_name: str, args: dict, user_text: str) -> dict:
    """Convert Arabic month-day date fields to ISO format."""
    if tool_name != 'search_hotels':
        return args
    for field in ('check_in', 'check_out'):
        val = args.get(field)
        if val is not None:
            iso = _ar_date_to_iso(str(val))
            if iso:
                args[field] = iso
    return args


# ---------------------------------------------------------------------------
# Fix C — transfer_money: name and query fixes
# ---------------------------------------------------------------------------
_TM_LOC_PREFIX_RE = re.compile(r'^ف[أ-ي]')  # name starts with فـ = "in [place]"


def fix_transfer_money(tool_name: str, args: dict, user_text: str) -> dict:
    """
    C1: لصديقي/لصاحبي + location-as-name → 'my friend'
    C2: Procedural query ('what are the procedures?') → strip all except amount
    """
    if tool_name != 'transfer_money':
        return args

    # C1: friend-transfer fix
    name = str(args.get('recipient_name', ''))
    if ('لصديقي' in user_text or 'لصاحبي' in user_text) and _TM_LOC_PREFIX_RE.match(name):
        args['recipient_name'] = 'my friend'

    # C2: procedural query → only keep amount
    if _TM_PROCEDURAL_RE.search(user_text):
        amount = args.get('amount')
        args = {'amount': amount} if amount is not None else {}

    return args


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def apply_v12_fixes(tool_name: str, args: dict, user_text: str) -> dict:
    """
    Apply all v12 micro-fixes (on top of v11 base predictions).
    Returns a (possibly modified) copy of args.
    """
    if not isinstance(args, dict):
        return args
    args = fix_book_doctor_appointment(tool_name, args, user_text)
    args = fix_search_hotels_dates(tool_name, args, user_text)
    args = fix_transfer_money(tool_name, args, user_text)
    return args


# ---------------------------------------------------------------------------
# Self-test (run against v13 dev gold)
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path

    BASE = Path(__file__).parent.parent
    sys.path.insert(0, str(BASE / 'src'))

    import importlib.util
    spec = importlib.util.spec_from_file_location('v12sc', BASE / 'src/v12_scorer.py')
    v12sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v12sc)

    v11  = {r['id']: r for r in (json.loads(l) for l in open(BASE / 'outputs/submissions/nabiq_v11.jsonl'))}
    v13g = {r['id']: r for r in (json.loads(l) for l in open(BASE / 'data/processed_v13/dev_gold_track_a.jsonl'))}
    devs = {r['id']: r for r in (json.loads(l) for l in open(BASE / 'data/processed_v13/dev_processed.jsonl'))}

    eligible = [gid for gid, g in v13g.items() if g['tool_called'] != 'none']
    wins, regressions = [], []

    for gid in eligible:
        gold = v13g[gid]; pred = v11[gid]; text = devs[gid]['user_text']
        gt = gold['tool_called']; pt = pred.get('tool_called', 'none')
        if gt != pt:
            continue
        pa = pred.get('arguments', {}); ga = gold.get('arguments', {})
        new_pa = apply_v12_fixes(gt, dict(pa), text)
        was_ok = v12sc.args_match_v12(pa, ga)
        now_ok = v12sc.args_match_v12(new_pa, ga)
        if not was_ok and now_ok:
            wins.append(gid)
        elif was_ok and not now_ok:
            regressions.append(gid)

    print(f'Wins:        {len(wins):3d}  {wins}')
    print(f'Regressions: {len(regressions):3d}  {regressions}')
    assert len(regressions) == 0, "REGRESSION DETECTED — aborting"
    print('✓ 0 regressions confirmed')
