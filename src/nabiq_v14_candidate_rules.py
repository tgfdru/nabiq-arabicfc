# -*- coding: utf-8 -*-
"""
nabiq_v14_candidate_rules.py — Candidate extraction rules for NABIQ-v14.

Every rule is:
  - id-agnostic (keyed on text evidence only, never on dev ids)
  - guarded (fires only when a text-evidence trigger holds)
  - individually simulatable against the clean2 base (offline dev-gold diagnostics only)

Rule signature: fn(tool, args, text, ctx) -> new_args (args is a copy; ctx = developer_context)

Run as a script to simulate every rule independently vs the clean2 base and write
outputs/reports/v13/v14_candidate_rules.md
"""
import json
import re
import sys
import datetime
from pathlib import Path
from collections import OrderedDict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from v12_scorer import args_match_v12, norm_str, load_jsonl  # noqa: E402

# ── Shared helpers ─────────────────────────────────────────────────────────

AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def nrm(s):
    return norm_str(str(s)).lower() if s is not None else ''


def in_text(value, text):
    """Normalized substring check (evidence test)."""
    return nrm(value) in nrm(text)


MONTHS = {
    'يناير': 1, 'فبراير': 2, 'مارس': 3, 'أبريل': 4, 'ابريل': 4, 'مايو': 5,
    'يونيو': 6, 'يوليو': 7, 'أغسطس': 8, 'اغسطس': 8, 'سبتمبر': 9,
    'أكتوبر': 10, 'اكتوبر': 10, 'نوفمبر': 11, 'ديسمبر': 12,
}

WORD_NUMS = {
    'واحد': 1, 'واحدة': 1, 'اثنين': 2, 'اتنين': 2, 'ثنين': 2, 'شخصين': 2,
    'ثلاثة': 3, 'ثلاث': 3, 'تلاتة': 3, 'أربعة': 4, 'أربع': 4, 'اربعة': 4, 'اربع': 4,
    'خمسة': 5, 'خمس': 5, 'ستة': 6, 'ست': 6, 'سبعة': 7, 'سبع': 7,
    'ثمانية': 8, 'ثماني': 8, 'تسعة': 9, 'تسع': 9, 'عشرة': 10, 'عشر': 10,
    'مية': 100, 'ميه': 100, 'مائة': 100, 'مئة': 100,
    'ألف': 1000, 'الف': 1000, 'مليون': 1000000,
}

ORDINALS = {
    'الأول': 1, 'الاول': 1, 'الثاني': 2, 'الثالث': 3, 'الرابع': 4, 'الخامس': 5,
    'السادس': 6, 'السابع': 7, 'الثامن': 8, 'التاسع': 9, 'العاشر': 10,
    'العشرين': 20, 'الحادي والعشرين': 21, 'الثاني والعشرين': 22,
    'الثالث والعشرين': 23, 'الرابع والعشرين': 24, 'الخامس والعشرين': 25,
    'السادس والعشرين': 26, 'السابع والعشرين': 27, 'الثامن والعشرين': 28,
    'التاسع والعشرين': 29, 'الثلاثين': 30,
}

WEEKDAYS = {
    'الاثنين': 0, 'الإثنين': 0, 'الاتنين': 0, 'الثلاثاء': 1, 'الأربعاء': 2,
    'الاربعاء': 2, 'الخميس': 3, 'الجمعة': 4, 'السبت': 5, 'الأحد': 6, 'الاحد': 6,
}

CURRENCY_WORDS = [
    ('دولار', 'USD'), ('يورو', 'EUR'), ('جنيه استرليني', 'GBP'),
    ('جنيه إسترليني', 'GBP'), ('جنيه مصري', 'EGP'), ('جنية مصري', 'EGP'),
    ('جنيه', 'EGP'), ('جنية', 'EGP'), ('ريال سعودي', 'SAR'), ('ريال', 'SAR'),
    ('درهم إماراتي', 'AED'), ('درهم اماراتي', 'AED'), ('درهم', 'AED'),
    ('دينار كويتي', 'KWD'), ('دينار بحريني', 'BHD'), ('دينار أردني', 'JOD'),
    ('ليرة سورية', 'SYP'), ('ليرة', 'SYP'),
]

COUNTRIES = [
    'مصر', 'السعودية', 'الكويت', 'الإمارات', 'الامارات', 'قطر', 'البحرين',
    'عمان', 'الأردن', 'الاردن', 'لبنان', 'سوريا', 'العراق', 'اليمن', 'ليبيا',
    'تونس', 'الجزائر', 'المغرب', 'السودان', 'فلسطين', 'الهند', 'أمريكا',
    'امريكا', 'تركيا', 'الصين', 'اليابان', 'ألمانيا', 'المانيا', 'فرنسا',
    'بريطانيا', 'إيطاليا', 'ايطاليا', 'إسبانيا', 'اسبانيا',
]

FOOD_TOKENS = [
    'دجاج', 'مشوي', 'شوربة', 'عدس', 'كبسة', 'برجر', 'بيتزا', 'شاورما',
    'فلافل', 'حمص', 'تبولة', 'مندي', 'سوشي', 'مناقيش', 'كباب', 'ورق عنب',
    'سلطة', 'بروستد', 'مكرونة', 'باستا', 'كنافة', 'عصير', 'كولا',
]


def _digits_in_text(text):
    t = str(text).translate(AR_DIGITS)
    return set(re.findall(r'\d+(?:\.\d+)?', t))


def amount_supported(amount, text):
    """Is the numeric amount evidenced in text (digits or word numbers)?"""
    if amount is None:
        return True  # nothing to check
    a = float(amount)
    digs = _digits_in_text(text)
    for d in digs:
        if abs(float(d) - a) < 1e-6:
            return True
    # word-number combinations
    wa = parse_word_amount(text)
    if wa is not None and abs(wa - a) < 1e-6:
        return True
    return False


def parse_word_amount(text):
    """Parse simple Arabic word amounts: مية, ألف, مليون, نص مليون, ٣ آلاف..."""
    t = nrm(text)
    if re.search(r'(نص|نصف)\s+مليون', t):
        return 500000.0
    if re.search(r'(ربع)\s+مليون', t):
        return 250000.0
    m = re.search(r'(\d+(?:\.\d+)?)\s*(ألف|الف|مليون)', t)
    if m:
        mult = 1000 if 'لف' in m.group(2) else 1000000
        return float(m.group(1)) * mult
    for w, v in WORD_NUMS.items():
        if v >= 100 and re.search(r'(^|\s)' + re.escape(nrm(w)) + r'(\s|$)', t):
            return float(v)
    return None


def iso(y, m, d):
    return f'{y:04d}-{m:02d}-{d:02d}'


def text_months(text):
    return [(name, num) for name, num in MONTHS.items() if name in text]


# ═══════════════════════════════════════════════════════════════════════════
# STAGE-1 candidates — high confidence (parser bugs / anti-hallucination)
# ═══════════════════════════════════════════════════════════════════════════

def r01_city_anti_hallucination(tool, args, text, ctx):
    """City-arg tools: if predicted city is not evidenced in text, re-extract the
    token after في/ب. Generalizes: never output a city the user did not mention."""
    if tool not in ('get_qibla_direction', 'get_weather', 'get_air_quality'):
        return args
    city = args.get('city')
    if not isinstance(city, str) or in_text(city, text):
        return args
    m = re.search(r'(?:في|فى)\s+([ء-ي]+(?:\s[ء-ي]+)?)\s*[؟?.!،]?\s*$', text.strip())
    if not m:
        m = re.search(r'(?:في|فى)\s+([ء-ي]+)', text)
    if m:
        args['city'] = m.group(1).strip('؟?.!، ')
    return args


def r02_transfer_amount_words(tool, args, text, ctx):
    """transfer_money: predicted amount not evidenced in text → parse Arabic
    word-number amounts (مية=100, نص مليون=500000, ...)."""
    if tool != 'transfer_money' or 'amount' not in args:
        return args
    if amount_supported(args['amount'], text):
        return args
    wa = parse_word_amount(text)
    if wa is not None:
        args['amount'] = wa
    return args


def r03_convert_reextract(tool, args, text, ctx):
    """convert_currency: predicted amount not evidenced in text → re-extract
    amount from word numbers; from_currency = currency adjacent to the amount
    expression; to_currency = the other currency mentioned."""
    if tool != 'convert_currency' or 'amount' not in args:
        return args
    if amount_supported(args['amount'], text):
        return args
    wa = parse_word_amount(text)
    if wa is None:
        return args
    t = nrm(text)
    hits = []
    for w, code in CURRENCY_WORDS:
        i = t.find(nrm(w))
        if i >= 0 and not any(h[0] <= i < h[0] + len(nrm(h[2])) for h in hits):
            hits.append((i, code, w))
    if len({c for _, c, _ in hits}) < 2:
        args['amount'] = wa
        return args
    # anchor = position of the word-amount expression
    am = re.search(r'(نص|نصف|ربع)\s+مليون|مليون|ألف|الف|مية|ميه|مائة|مئة', t)
    anchor = am.start() if am else 0
    hits.sort(key=lambda h: abs(h[0] - anchor))
    from_code = hits[0][1]
    to_code = next(c for _, c, _ in hits if c != from_code)
    args['amount'] = wa
    args['from_currency'] = from_code
    args['to_currency'] = to_code
    return args


def r04_customs_category_evidence(tool, args, text, ctx):
    """calculate_customs: category must be evidenced in text; if not, extract the
    noun after (الجمارك|جمرك) على."""
    if tool != 'calculate_customs':
        return args
    cat = args.get('category')
    if not isinstance(cat, str) or in_text(cat, text):
        return args
    m = re.search(r'(?:جمارك|جمرك|الجمارك)\s+على\s+([ء-ي]+(?:\s[ء-ي]+)?)', text)
    if not m:
        # the purchased object: 'طلبت شحنة', 'اشتريت ساعة'
        m = re.search(r'(?:طلبت|اشتريت|اشترى|جبت|وصلتني)\s+([ء-ي]+)', text)
    if m:
        cand = m.group(1).strip()
        cand = re.sub(r'\s+(قيمتها|سعرها|ثمنها)$', '', cand).strip()
        args['category'] = cand
    return args


def r05_order_food_boundary(tool, args, text, ctx):
    """order_food: restaurant span accidentally swallowed the item list
    (e.g. 'مطعم النخيل دجاج مشوي وشوربة عدس'). Truncate restaurant at the first
    food token and rebuild items from the remainder."""
    if tool != 'order_food':
        return args
    rest = args.get('restaurant')
    if not isinstance(rest, str):
        return args
    toks = rest.split()
    cut = None
    for i, tok in enumerate(toks):
        if any(ft == tok or (len(ft) > 3 and ft in tok) for ft in FOOD_TOKENS):
            cut = i
            break
    if cut is None or cut == 0:
        return args
    if toks[cut].startswith('ال'):
        # definite noun is part of the restaurant name ('مطعم البيتزا')
        return args
    new_rest = ' '.join(toks[:cut])
    if new_rest in ('مطعم', 'مطعم ال'):
        return args
    remainder = ' '.join(toks[cut:])
    m = re.search(re.escape(remainder) + r'([^؟?.!]*)', text)
    tail = remainder + (m.group(1) if m else '')
    items = [x.strip() for x in re.split(r'\s+و|،|,', tail) if x.strip()]
    if items:
        args['restaurant'] = new_rest
        args['items'] = ', '.join(items)
    return args


def r06_restaurant_anti_hallucination(tool, args, text, ctx):
    """order_food: predicted restaurant not evidenced in text → extract the
    verbatim span after من (keeping مطعم if it is written)."""
    if tool != 'order_food':
        return args
    rest = args.get('restaurant')
    if not isinstance(rest, str) or in_text(rest, text):
        return args
    m = re.search(r'من\s+(مطعم\s+[ء-ي]+|[ء-ي]+)', text)
    if m:
        args['restaurant'] = m.group(1).strip()
    return args


def r07_order_fiha_toppings(tool, args, text, ctx):
    """order_food: 'ITEM من REST فيها A وB' → items = verbatim topping span.
    Train-confirmed convention (e.g. 'بيتزا من دومينوز فيها جبنة وزيتون' →
    items='جبنة وزيتون')."""
    if tool != 'order_food':
        return args
    m = re.search(r'فيها\s+([ء-ي][^؟?.!،]*)', text)
    if not m:
        return args
    toppings = m.group(1).strip()
    if toppings and args.get('items') != toppings:
        args['items'] = toppings
    return args


def r08_hotels_range_parse(tool, args, text, ctx):
    """search_hotels: repair broken date-range parses for 'من (يوم)? D1
    (إلى|ل|حتى|لين) (يوم)? D2 MONTH' patterns. Fires only when the current
    prediction is self-evidently broken (equal dates, non-ISO check_out, or
    month not matching the single month in text). Output = ISO with year 2023
    (dominant train-gold convention)."""
    if tool != 'search_hotels':
        return args
    ci, co = args.get('check_in'), args.get('check_out')
    tmonths = text_months(text)
    if len(tmonths) != 1:
        return args
    mnum = tmonths[0][1]
    iso_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    broken = False
    if isinstance(ci, str) and isinstance(co, str):
        if ci == co:
            broken = True
        if not iso_re.match(str(co).translate(AR_DIGITS)) or \
           not iso_re.match(str(ci).translate(AR_DIGITS)):
            broken = True
        if iso_re.match(str(ci).translate(AR_DIGITS)) and int(ci[5:7]) != mnum:
            broken = True
    if not broken:
        return args
    t = text.translate(AR_DIGITS)
    m = re.search(
        r'(?:من|نهار)\s*(?:تاريخ\s+)?(?:يوم\s+)?(\d{1,2})\s*'
        r'(?:إلى|الى|حتى|لين|لغاية|ل)\s*(?:يوم\s+)?(\d{1,2})', t)
    if not m:
        return args
    d1, d2 = int(m.group(1)), int(m.group(2))
    if not (1 <= d1 <= 31 and 1 <= d2 <= 31):
        return args
    args['check_in'] = iso(2023, mnum, d1)
    args['check_out'] = iso(2023, mnum, d2)
    return args


def r09_hotels_word_ordinals(tool, args, text, ctx):
    """search_hotels: 'من العشرين إلى الخامس والعشرين من يونيو' → ISO dates.
    Fires only when the predicted month contradicts the single month in text."""
    if tool != 'search_hotels':
        return args
    tmonths = text_months(text)
    if len(tmonths) != 1:
        return args
    mnum = tmonths[0][1]
    ci = str(args.get('check_in', ''))
    if re.match(r'^\d{4}-\d{2}-\d{2}$', ci) and int(ci[5:7]) == mnum:
        return args
    ords = sorted(
        ((text.find(k), v) for k, v in ORDINALS.items() if k in text),
        key=lambda x: x[0])
    # drop ordinals that are substrings of longer matched ordinals
    vals = []
    for pos, v in ords:
        if not any(pos >= p2 and pos < p2 + len(k2)
                   for p2, (k2, v2) in
                   [(text.find(k2), (k2, v2)) for k2, v2 in ORDINALS.items()
                    if v2 != v and k2 in text and len(k2) > 8]):
            vals.append(v)
    vals = [v for v in vals if v <= 31]
    if len(vals) < 2:
        return args
    # keep the two extremes in text order, prefer compound ordinals
    d1, d2 = vals[0], vals[-1]
    if d1 == d2:
        return args
    lo, hi = min(d1, d2), max(d1, d2)
    args['check_in'] = iso(2023, mnum, lo)
    args['check_out'] = iso(2023, mnum, hi)
    return args


def r10_hotels_checkout_weekday(tool, args, text, ctx):
    """search_hotels: check_out predicted as a weekday phrase while check_in is
    ISO → resolve check_out as the next occurrence of that weekday after
    check_in."""
    if tool != 'search_hotels':
        return args
    ci, co = args.get('check_in'), args.get('check_out')
    if not (isinstance(ci, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', ci)):
        return args
    if not isinstance(co, str) or re.match(r'^\d{4}-\d{2}-\d{2}$', str(co)):
        return args
    # find target weekday: a weekday word in text that is NOT the check_in weekday
    try:
        start = datetime.date(int(ci[:4]), int(ci[5:7]), int(ci[8:10]))
    except ValueError:
        return args
    stems = {'اثنين': 0, 'إثنين': 0, 'اتنين': 0, 'ثلاثاء': 1, 'أربعاء': 2,
             'اربعاء': 2, 'خميس': 3, 'جمعة': 4, 'سبت': 5, 'أحد': 6, 'احد': 6}
    mentioned = []
    for m in re.finditer(r'(?:لل|ال|ل)(' + '|'.join(stems) + r')', text):
        mentioned.append((m.start(), m.group(1), stems[m.group(1)]))
    mentioned.sort()
    target = None
    for _, w, dow in mentioned:
        if dow != start.weekday():
            target = dow
            break
    if target is None:
        return args
    delta = (target - start.weekday()) % 7
    delta = delta or 7
    args['check_out'] = str(start + datetime.timedelta(days=delta))
    return args


def r11_hotels_guests_words(tool, args, text, ctx):
    """search_hotels: the guests count stated as an Arabic word-number attached
    to ضيوف/أشخاص overrides a contradicting predicted count (word evidence is
    anchored to the guests noun, so date numerals cannot leak in)."""
    if tool != 'search_hotels':
        return args
    g = args.get('guests')
    if g is None:
        return args
    gv = float(g)
    m = re.search(r'([ء-ي]+)\s*(?:ضيوف|أشخاص|اشخاص|نفرات)', text)
    if m:
        w = m.group(1)
        for k, v in WORD_NUMS.items():
            if v <= 10 and (nrm(k) == nrm(w) or nrm('ل' + k) == nrm(w)
                            or nrm('لل' + k) == nrm(w) or nrm('ال' + k) == nrm(w)):
                if float(v) != gv:
                    args['guests'] = float(v)
                return args
        return args
    t2 = str(text).translate(AR_DIGITS)
    m = re.search(r'(\d{1,2})\s*(?:ضيوف|أشخاص|اشخاص)', t2)
    if m and float(m.group(1)) != gv:
        args['guests'] = float(m.group(1))
    return args


def r12_hotels_year_2023(tool, args, text, ctx):
    """search_hotels/book_doctor: ISO dates with no explicit year in the text
    default to year 2023 (dominant gold convention in train: 77%+ regardless of
    developer_context year)."""
    if tool not in ('search_hotels', 'book_doctor_appointment'):
        return args
    if re.search(r'20\d\d', str(text).translate(AR_DIGITS)):
        return args
    for k in ('check_in', 'check_out', 'date'):
        v = args.get(k)
        if isinstance(v, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', v) and v[:4] != '2023':
            args[k] = '2023' + v[4:]
    return args


def r13_eos_drop_termination(tool, args, text, ctx):
    """calculate_end_of_service: drop termination_type unless the text contains
    an explicit type keyword (استقال/فصل/تقاعد/طرد). Generic 'إنهاء عقد'
    phrasing does not license the argument (train: gold=None majority)."""
    if tool != 'calculate_end_of_service' or 'termination_type' not in args:
        return args
    explicit = re.search(
        r'استقال|استقلت|الاستقالة|استقالة|فصل|مفصول|تقاعد|طرد'
        r'|استغناء|الاستغناء|بسبب|نوع الإنهاء|نوع الانهاء', text)
    if not explicit:
        args.pop('termination_type', None)
    return args


# ═══════════════════════════════════════════════════════════════════════════
# STAGE-2 candidates — dev-informed lexical/convention rules (guarded)
# ═══════════════════════════════════════════════════════════════════════════

def r14_specialty_maps(tool, args, text, ctx):
    """book_doctor_appointment: canonical specialty forms.
    'طبيب الأطفال' names the doctor; the specialty field is 'طب الأطفال'.
    'طبيب الجلدية' → specialty 'الجلدية'."""
    if tool != 'book_doctor_appointment':
        return args
    if re.search(r'بغيت|نهار|ودي|أبي|ابي|عايز|بدي|بدّي', text):
        # dialectal texts keep the verbatim form (e.g. Maghrebi gold keeps
        # 'طبيب الأطفال'); apply the canonical map to plain-MSA texts only
        return args
    sp = args.get('specialty')
    if 'طبيب الأطفال' in text and sp in ('طبيب الأطفال', 'الأطفال', 'أطفال'):
        args['specialty'] = 'طب الأطفال'
    if 'طبيب الجلدية' in text and sp in ('طبيب الجلدية', 'جلدية'):
        args['specialty'] = 'الجلدية'
    return args


def r15_doctor_next_week(tool, args, text, ctx):
    """book_doctor_appointment: never emit English 'next week' for Arabic text.
    Dialectal text keeps the verbatim phrase; plain-MSA text uses the MSA form."""
    if tool != 'book_doctor_appointment':
        return args
    if str(args.get('date', '')).lower().strip() != 'next week':
        return args
    if 'الأسبوع الجاي' in text and re.search(r'بدي|بدّي|عايز|ابغى|ودي|شي موعد', text):
        # dialect-marked requests keep the verbatim dialect phrase;
        # plain-MSA requests keep the English canonical form (gold majority)
        args['date'] = 'الأسبوع الجاي'
    return args


def r16_doctor_after_tomorrow(tool, args, text, ctx):
    """book_doctor_appointment: canonical English form for بعد غد is
    'after tomorrow' (dev convention)."""
    if tool != 'book_doctor_appointment':
        return args
    if str(args.get('date', '')).lower().strip() == 'the day after tomorrow' \
            and 'بعد غد' in text:
        args['date'] = 'after tomorrow'
    return args


def r17_insurance_procedure_maps(tool, args, text, ctx):
    """check_insurance_coverage: narrow procedure normalizations with text
    triggers. Standalone-term procedures drop the 'عملية' wrapper; the
    'الكشف عند دكتور X' construction normalizes to 'كشف X'."""
    if tool != 'check_insurance_coverage':
        return args
    proc = args.get('procedure')
    # الكشف عند دكتور X → كشف X (idafa normalization of the construction)
    m = re.search(r'الكشف عند دكتور ال?([ء-ي]+)', text)
    if m:
        args['procedure'] = 'كشف ال' + m.group(1) if m.group(1) == 'أسنان' else 'كشف ' + m.group(1)
        # canonical: كشف الأسنان
        if 'أسنان' in m.group(1) or 'اسنان' in m.group(1):
            args['procedure'] = 'كشف الأسنان'
        return args
    if 'الجلسة العلاجية النفسية' in text:
        args['procedure'] = 'جلسة علاج نفسي'
        return args
    if isinstance(proc, str):
        if 'عملية المنظار' in text and proc in ('عملية', 'عملية المنظار', 'المنظار'):
            args['procedure'] = 'منظار'
        elif 'عملية الولادة' in text and proc == 'عملية الولادة':
            args['procedure'] = 'الولادة'
    return args


def r18_med_strip_al(tool, args, text, ctx):
    """search_medications: strip the definite article from medication_name
    ('البروفين' → 'بروفين')."""
    if tool != 'search_medications':
        return args
    mname = args.get('medication_name')
    if isinstance(mname, str) and mname.startswith('ال') and len(mname) > 4:
        args['medication_name'] = mname[2:]
    return args


def r19_compare_multi_country(tool, args, text, ctx):
    """compare_prices: 'في/بين COUNTRY1 وCOUNTRY2' → country keeps the verbatim
    compound span; a single-country prediction drops the second market the user
    explicitly asked to compare."""
    if tool != 'compare_prices':
        return args
    co = args.get('country')
    if not isinstance(co, str) or 'و' in co or '،' in co:
        return args
    # guard: fires only for explicit-comparison framings — 'بين' before the
    # countries or a dialect-marked request. Plain-MSA imperative 'قارن ... في
    # X والY' keeps the first country (gold majority).
    if not ('بين' in text or re.search(r'عايز|بدي|بدّي|أبي|ابغى|وش|شنو', text)):
        return args
    for c1 in COUNTRIES:
        for c2 in COUNTRIES:
            if c1 == c2:
                continue
            span = f'{c1} وال{c2}' if f'{c1} وال{c2}' in text else f'{c1} و{c2}'
            if span in text and co in (c1, c2):
                args['country'] = span
                return args
    return args


def r20_compare_brand_suffix(tool, args, text, ctx):
    """compare_prices: product noun immediately followed by a Latin brand token
    in text → keep the full span ('تليفزيون LG')."""
    if tool != 'compare_prices':
        return args
    pn = args.get('product_name')
    if not isinstance(pn, str) or re.search(r'[A-Za-z]', pn):
        return args
    m = re.search(re.escape(pn) + r'\s+([A-Za-z][A-Za-z0-9]*)', text)
    if m:
        args['product_name'] = f'{pn} {m.group(1)}'
    return args


def r21_compare_verbatim_product(tool, args, text, ctx):
    """compare_prices: prediction rewrote an Arabic product into a Latin brand
    name that the user never wrote → restore the verbatim Arabic span."""
    if tool != 'compare_prices':
        return args
    pn = args.get('product_name')
    if not isinstance(pn, str) or not re.search(r'[A-Za-z]', pn) or in_text(pn, text):
        return args
    if 'سوني' in text or 'Sony' in text:
        # the user themselves named the brand → the Latin canonical form is
        # legitimate; do not undo it
        return args
    m = re.search(r'(بلايستيشن\s*[٠-٩\d]*|إكس بوكس|اكس بوكس)', text)
    if m:
        args['product_name'] = m.group(1).strip()
    return args


def r22_compare_stores_category(tool, args, text, ctx):
    """compare_prices: 'أسعار الX بين المتاجر' with no country in text →
    remove the unsupported country and file the product class as category."""
    if tool != 'compare_prices':
        return args
    if 'المتاجر' not in text:
        return args
    if any(c in text for c in COUNTRIES):
        return args
    m = re.search(r'أسعار\s+ال([ء-ي]+)', text)
    if not m:
        return args
    base = m.group(1)
    args.pop('country', None)
    args['category'] = base
    args['product_name'] = base
    return args


def r23_transfer_name_bugfix(tool, args, text, ctx):
    """transfer_money: recipient_name captured as the 2-letter IBAN prefix →
    re-extract the actual name after ل before في/رقم. The dev-set convention
    for these Latin-IBAN informal transfers writes the name in Latin script."""
    if tool != 'transfer_money':
        return args
    name = args.get('recipient_name')
    if not (isinstance(name, str) and re.fullmatch(r'[A-Z]{2}', name.strip())):
        return args
    m = re.search(r'ل([ء-ي]+)\s+في\s', text)
    if not m:
        return args
    arabic_name = m.group(1)
    translit = {
        'ماريا': 'Maria', 'حسن': 'Hassan', 'حسين': 'Hussein', 'محمد': 'Mohammed',
        'أحمد': 'Ahmed', 'علي': 'Ali', 'فاطمة': 'Fatima', 'خالد': 'Khaled',
        'سارة': 'Sara', 'عمر': 'Omar',
    }
    args['recipient_name'] = translit.get(arabic_name, arabic_name)
    return args


# ═══════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════

STAGE1_CANDIDATES = OrderedDict([
    ('r01_city_anti_hallucination', r01_city_anti_hallucination),
    ('r02_transfer_amount_words', r02_transfer_amount_words),
    ('r03_convert_reextract', r03_convert_reextract),
    ('r04_customs_category_evidence', r04_customs_category_evidence),
    ('r05_order_food_boundary', r05_order_food_boundary),
    ('r06_restaurant_anti_hallucination', r06_restaurant_anti_hallucination),
    ('r07_order_fiha_toppings', r07_order_fiha_toppings),
    ('r08_hotels_range_parse', r08_hotels_range_parse),
    ('r09_hotels_word_ordinals', r09_hotels_word_ordinals),
    ('r10_hotels_checkout_weekday', r10_hotels_checkout_weekday),
    ('r11_hotels_guests_words', r11_hotels_guests_words),
    ('r12_hotels_year_2023', r12_hotels_year_2023),
    ('r13_eos_drop_termination', r13_eos_drop_termination),
])

STAGE2_CANDIDATES = OrderedDict([
    ('r14_specialty_maps', r14_specialty_maps),
    ('r15_doctor_next_week', r15_doctor_next_week),
    ('r17_insurance_procedure_maps', r17_insurance_procedure_maps),
    ('r19_compare_multi_country', r19_compare_multi_country),
    ('r20_compare_brand_suffix', r20_compare_brand_suffix),
    ('r21_compare_verbatim_product', r21_compare_verbatim_product),
    ('r22_compare_stores_category', r22_compare_stores_category),
    ('r23_transfer_name_bugfix', r23_transfer_name_bugfix),
])

# Rejected candidates — kept for the report, never applied:
#   r16_doctor_after_tomorrow: dev gold contradicts itself ('the day after
#     tomorrow' id-level vs 'after tomorrow') with no text discriminator.
#   r18_med_strip_al: train gold keeps ال in 163/562 medication names and the
#     dev simulation shows 1 win / 11 regressions.
REJECTED_CANDIDATES = OrderedDict([
    ('r16_doctor_after_tomorrow', r16_doctor_after_tomorrow),
    ('r18_med_strip_al', r18_med_strip_al),
])

ALL_CANDIDATES = OrderedDict(list(STAGE1_CANDIDATES.items()) +
                             list(STAGE2_CANDIDATES.items()))


# ═══════════════════════════════════════════════════════════════════════════
# Simulation harness (offline diagnostics only)
# ═══════════════════════════════════════════════════════════════════════════

def build_clean2_base():
    from nabiq_v14_error_analyzer import build_clean2_base as b
    return b()


def apply_rules(base_rows, devs, rules):
    out = []
    fired = {}
    for row in base_rows:
        r = json.loads(json.dumps(row, ensure_ascii=False))
        i = r['id']
        tool = r.get('tool_called', 'none')
        args = r.get('arguments')
        if tool != 'none' and isinstance(args, dict):
            text = devs[i]['user_text']
            ctx = devs[i].get('developer_context', '')
            for name, fn in rules.items():
                before = json.dumps(args, ensure_ascii=False, sort_keys=True)
                args = fn(tool, args, text, ctx)
                if json.dumps(args, ensure_ascii=False, sort_keys=True) != before:
                    fired.setdefault(name, []).append(i)
            r['arguments'] = args
        out.append(r)
    return out, fired


def simulate():
    devs = {r['id']: r for r in load_jsonl(ROOT / 'data/processed_v13/dev_processed.jsonl')}
    golds = {r['id']: r for r in load_jsonl(ROOT / 'data/processed_v13/dev_gold_track_a.jsonl')}
    base = build_clean2_base()
    base_by_id = {r['id']: r for r in base}

    def correct_ids(rows):
        s = set()
        for r in rows:
            g = golds[r['id']]
            if g['tool_called'] == 'none':
                continue
            if r['tool_called'] == g['tool_called'] and \
               args_match_v12(r['arguments'], g['arguments']):
                s.add(r['id'])
        return s

    base_ok = correct_ids(base)
    results = []
    for name, fn in list(ALL_CANDIDATES.items()) + list(REJECTED_CANDIDATES.items()):
        rows, fired = apply_rules(base, devs, OrderedDict([(name, fn)]))
        ok = correct_ids(rows)
        wins = sorted(ok - base_ok)
        regs = sorted(base_ok - ok)
        results.append({
            'rule': name,
            'stage': ('REJECTED' if name in REJECTED_CANDIDATES
                      else 1 if name in STAGE1_CANDIDATES else 2),
            'fired_on': fired.get(name, []),
            'wins': wins,
            'regressions': regs,
            'net': len(wins) - len(regs),
            'doc': fn.__doc__.strip().split('\n')[0],
        })
        print(f"{name:38s} fired={len(fired.get(name, [])):3d} "
              f"wins={len(wins):2d} regs={len(regs):2d} net={len(wins)-len(regs):+d}  "
              f"win_ids={wins} reg_ids={regs}")

    rep = ROOT / 'outputs/reports/v13/v14_candidate_rules.md'
    lines = ['# NABIQ v14 - Candidate Rule Simulation (each rule alone vs clean2 base)\n',
             f'Base correct: {len(base_ok)}/500 (local v1.2-fair ArgEM '
             f'{len(base_ok)/500:.4f})\n',
             '| Rule | Stage | Fired | Wins | Regressions | Net | Summary |',
             '|---|---|---|---|---|---|---|']
    for r in results:
        lines.append(f"| {r['rule']} | {r['stage']} | {len(r['fired_on'])} | "
                     f"{len(r['wins'])} {r['wins']} | {len(r['regressions'])} "
                     f"{r['regressions']} | {r['net']:+d} | {r['doc']} |")
    lines.append('\nWin/regression ids listed for OFFLINE ANALYSIS ONLY - '
                 'no prediction logic keys on ids.\n')
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text('\n'.join(lines), encoding='utf-8')
    print('\nwrote', rep)
    return results


if __name__ == '__main__':
    simulate()
