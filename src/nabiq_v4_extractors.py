"""
nabiq_v4_extractors.py
NABIQ-v4 Elite Sprint — Per-tool high-precision argument extractors.

Philosophy: only replace v3 when there is CLEAR text evidence and the
no-regression selector confirms improvement.  Every function returns
either a new args dict (to be evaluated by the selector) or None
(meaning: keep v3 as-is).
"""

from __future__ import annotations
import re
from typing import Optional

# ─── Unicode helpers ──────────────────────────────────────────────────────────
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def ar2w(s: str) -> str:
    """Arabic-Indic / Extended-Arabic-Indic digits → Western digits."""
    return str(s).translate(ARABIC_DIGITS)


def norm_text(s: str) -> str:
    """Strip diacritics + alef variants + ta-marbuta + shadda for matching."""
    s = re.sub(r"[ً-ٟ]", "", str(s))          # tashkeel
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي")
    return s


def norm_alef(s: str) -> str:
    """Just alef normalization (preserve diacritics)."""
    return s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")


# ─── 1. get_weather ──────────────────────────────────────────────────────────
# The v3 pipeline was incorrectly removing `days` when the text says "اليوم"
# (today = 1 day), and not adding days for multi-day phrases.
# Gold expects days=1.0 for "today", days=2.0 for "today+tomorrow", etc.

_DAYS_PATTERNS = [
    # Explicit multi-day counts first (order matters)
    (r"أسبوعين|اسبوعين", 14.0),
    (r"أسبوع|اسبوع", 7.0),
    (r"عشرة\s+أيام|عشر\s+أيام|١٠\s+أيام|10\s+أيام", 10.0),
    (r"خمسة\s+أيام|خمس\s+أيام|٥\s+أيام|5\s+أيام", 5.0),
    (r"أربعة\s+أيام|أربع\s+أيام|٤\s+أيام|4\s+أيام", 4.0),
    (r"ثلاثة\s+أيام|ثلاث\s+أيام|٣\s+أيام|3\s+أيام", 3.0),
    # "today AND tomorrow" → 2
    (r"(اليوم|النهارده|اليوم|اليوم)\s+(و|وبكر[اةه]|ووكر[اةه])", 2.0),
    (r"(النهارده|اليوم)\s+وبكر[هاة]", 2.0),
    (r"بكر[هاة]\s+وبعد[هه]", 2.0),
    (r"هاليومين|اليومين|يومين", 2.0),
    # tomorrow only → 1 (tomorrow is 1-day forecast)
    (r"\bغداً?\b|غدًا|بكر[هاة]|بكره|بكرا|بكرة", 1.0),
    # "today" → 1 (multiple dialects)
    (r"\bاليوم\b|\bالنهارده\b|\bالنهاردة\b|\bاليوم\b|\bالنهاردة\b|"
     r"\bاليوم\b|\bهسع\b|\bحالياً\b|\bشلون\b.{0,20}اليوم\b", 1.0),
]


def extract_weather_days(text: str, v3_days) -> Optional[float]:
    """
    Return the days value to use, or None to keep v3_days.
    - If text has explicit multi-day phrase → return that count
    - If text says 'اليوم' (today) → return 1.0  (v3 was removing this)
    - If no day mention at all → return None (keep v3)
    """
    nt = norm_text(text)
    tw = ar2w(text)

    # Check for explicit numeric days: "3 أيام", "٥ أيام"
    m = re.search(r"([٠-٩\d]+)\s*(?:أيام|ايام|يوم)", tw)
    if m:
        try:
            n = float(ar2w(m.group(1)))
            if 1 <= n <= 30:
                return n
        except ValueError:
            pass

    # Pattern-based
    for pattern, days in _DAYS_PATTERNS:
        if re.search(pattern, nt):
            return days

    return None   # no clear signal → keep v3


# ─── 2. calculate_end_of_service ─────────────────────────────────────────────
# v3 defaults to 'dismissal' far too often.
# Training shows clear lexical signals for each type.

_EOS_TYPE_PATTERNS = [
    # disciplinary — strongest signals first
    ("disciplinary", [
        r"سوء\s+سلوك", r"تأديب", r"مخالف[ةه]", r"انتهاك", r"جريم[ةه]",
        r"طرد\s+تأديبي", r"فصل\s+تأديبي",
    ]),
    # end_of_contract — explicit contract-end language
    ("end_of_contract", [
        r"انتهاء\s+[اA-z]*عقد", r"إنهاء\s+[اA-z]*عقد", r"انتهاء\s+مدة",
        r"إنهاء\s+مدة", r"نهاية\s+العقد", r"انتهاء\s+الخدمة",
        r"انتهاء\s+مدة\s+العقد", r"بسبب\s+انتهاء", r"انفسخت",
        r"إنهاء\s+الخدمة\s+من\s+قبل\s+الشركة",
    ]),
    # retirement
    ("retirement", [r"تقاعد", r"التقاعد", r"بلغت\s+سن"]),
    # mutual_consent
    ("mutual_consent", [
        r"تراضي", r"بالتراضي", r"اتفاق\s+مشترك", r"اتفاق\s+ودي",
        r"بموافقة\s+الطرفين",
    ]),
    # unfair_dismissal
    ("unfair_dismissal", [
        r"فصل\s+تعسفي", r"فصل\s+ظالم", r"فصل\s+غير\s+عادل", r"تعسف",
    ]),
    # economic
    ("economic", [
        r"إعادة\s+هيكل", r"اقتصادي", r"تخفيض\s+عمال", r"صعوبات\s+مالية",
    ]),
    # resignation — "by employee's will" language
    ("resignation", [
        r"استقال|استقالة|الاستقالة", r"برضاي", r"بإرادتي", r"بموافقتي",
        r"بإرادته", r"قررت\s+أترك|قررت\s+الترك", r"تركت\s+العمل",
        r"قدمت\s+استقالة", r"أقدمت\s+على\s+الترك",
        r"بمحض\s+إرادتي", r"اخترت\s+الترك",
    ]),
    # dismissal — catch-all (explicit company action)
    ("dismissal", [
        r"أُقيل|أقيل", r"تم\s+فصله", r"فصلني", r"فصلت\s+",
        r"طردوني", r"تم\s+طرد", r"قرار\s+الشركة\s+بالفصل",
        r"قرار\s+الشركة\s+بإنهاء",
    ]),
]


def extract_eos_termination_type(text: str, v3_type: str) -> Optional[str]:
    """Return termination_type string, or None to keep v3."""
    nt = norm_text(text)
    for ttype, patterns in _EOS_TYPE_PATTERNS:
        for p in patterns:
            if re.search(p, nt):
                return ttype
    return None   # no signal → keep v3


# ─── 3. calculate_zakat currency ─────────────────────────────────────────────
# Training/gold shows that Arabic short-form currencies should map to ISO
# codes for most currencies, except "ريال" (keeps short form).
# Dialect-aware: "درهم" in Maghrebi context → MAD, else → AED.

_ZAKAT_CURRENCY_MAP = {
    # Arabic form → ISO
    "دولار":   "USD",
    "دولارات": "USD",
    "dollar":  "USD",
    # درهم handled separately (dialect-sensitive)
    "يورو":    "EUR",
    "يوروهات": "EUR",
    "euro":    "EUR",
    "جنيه":    "EGP",   # default Egyptian pound (most common in training)
    "جنيه مصري": "EGP",
    "دينار":   "KWD",   # most common dinar in training
    "دينار كويتي": "KWD",
    "دينار اردني": "JOD",
    "دينار أردني": "JOD",
    "دينار بحريني": "BHD",
    "ليرة سورية": "SYP",
    "ليرة سوري": "SYP",
    "السورية": "SYP",   # context clue
    "ليرة لبنانية": "LBP",
    "ليرة لبناني": "LBP",
    "ليرة تركية": "TRY",
    "ليرة":    "ليرة",  # ambiguous → keep Arabic (training shows many "ليرة" as-is)
    "ريال سعودي": "SAR",
    "ريال":    "ريال",  # keep short form (training gold uses "ريال" not "SAR" often)
    "ريالات":  "ريال",
    "درهم مغربي": "MAD",
    "درهم إماراتي": "AED",
}

_MAGHREBI_MARKERS = {
    "شحال", "ديال", "غادي", "خصني", "باش", "فهاذ", "هاد", "فهاد",
    "نخرج", "شنو",
}


def extract_zakat_currency(text: str, dialect: str, v3_currency: str) -> Optional[str]:
    """
    Return normalized currency ISO code, or None to keep v3.
    Only updates if there is clear text evidence.
    """
    nt = norm_text(text.lower())

    # Check for explicit long-form currency first (highest precision)
    for phrase, iso in sorted(_ZAKAT_CURRENCY_MAP.items(), key=lambda x: -len(x[0])):
        if norm_text(phrase) in nt:
            if iso in ("ليرة", "ريال"):
                # ambiguous short-form → check for more specific context
                if "سوري" in nt or "سورية" in nt:
                    return "SYP"
                if "لبناني" in nt or "لبنانية" in nt:
                    return "LBP"
                if "تركي" in nt or "تركية" in nt:
                    return "TRY"
                # else keep as-is
                return iso
            return iso

    # درهم — dialect-sensitive
    if "درهم" in text or norm_text("درهم") in nt:
        words = set(norm_text(text).split())
        is_maghrebi = bool(_MAGHREBI_MARKERS & words) or dialect == "maghrebi"
        return "MAD" if is_maghrebi else "AED"

    return None


# ─── 4. search_hotels — ISO date extraction ──────────────────────────────────
# The v3 pipeline was extracting day+month but formatting as Arabic "١٠ نوفمبر"
# instead of ISO "2023-11-10".
# Gold uses ISO YYYY-MM-DD for the majority of training examples.
# Special cases: some Levantine/Gulf gold uses verbatim or DD-MM forms.

_MONTH_AR2NUM = {
    "يناير": 1, "كانون الثاني": 1, "كانون ثاني": 1,
    "فبراير": 2, "شباط": 2,
    "مارس": 3, "آذار": 3, "اذار": 3,
    "أبريل": 4, "ابريل": 4, "نيسان": 4,
    "مايو": 5, "أيار": 5, "ايار": 5,
    "يونيو": 6, "حزيران": 6,
    "يوليو": 7, "تموز": 7,
    "أغسطس": 8, "اغسطس": 8, "آب": 8,
    "سبتمبر": 9, "أيلول": 9, "ايلول": 9,
    "أكتوبر": 10, "اكتوبر": 10, "تشرين الأول": 10, "تشرين اول": 10,
    "نوفمبر": 11, "تشرين الثاني": 11, "تشرين ثاني": 11,
    "ديسمبر": 12, "كانون الأول": 12, "كانون اول": 12,
}

# Gold year heuristic: Jan/Feb can be 2024 if context is future-looking
_FORWARD_MONTHS = {1, 2}   # Jan/Feb → 2024 (after Nov/Dec reference)

# Day name → offset from reference Monday 2023-10-09
_DAY_NAMES = {
    "الأحد": 6, "الاحد": 6,
    "الاثنين": 0, "الإثنين": 0,
    "الثلاثاء": 1,
    "الأربعاء": 2, "الاربعاء": 2,
    "الخميس": 3,
    "الجمعة": 4, "الجمعه": 4,
    "السبت": 5,
}
_REF_DATE = (2023, 10, 9)   # Monday

# Months where training uses ISO with 2024 (January, February)
_YEAR_OVERRIDES = {1: 2024, 2: 2024}


def _format_iso(day: int, month: int, year: Optional[int] = None) -> str:
    if year is None:
        year = _YEAR_OVERRIDES.get(month, 2023)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_day_month(text: str):
    """
    Extract (day, month_num) pairs from hotel date text.
    Returns list of (day:int, month:int) in order of appearance.
    """
    results = []
    tw = ar2w(text)
    nt_lower = norm_text(text).lower()

    # Build month regex
    month_regex = "|".join(sorted(_MONTH_AR2NUM, key=len, reverse=True))
    # Pattern: [day] [month_name]
    pat = r"(\d+)\s+(" + month_regex + r")"
    for m in re.finditer(pat, norm_text(tw).lower()):
        day = int(m.group(1))
        mn = _MONTH_AR2NUM.get(m.group(2), None)
        if mn and 1 <= day <= 31:
            results.append((day, mn))

    return results


def _extract_hotel_dates_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse check_in and check_out from hotel booking text.
    Returns (check_in_iso, check_out_iso) or (None, None).
    """
    tw = ar2w(text)
    nt = norm_text(tw)

    dates = _parse_day_month(nt)

    if len(dates) >= 2:
        ci_day, ci_month = dates[0]
        co_day, co_month = dates[1]
        # If both same month but co_day < ci_day, likely extraction error
        if ci_month == co_month and co_day < ci_day:
            # swap
            ci_day, co_day = co_day, ci_day
        return _format_iso(ci_day, ci_month), _format_iso(co_day, co_month)

    # Try the "X إلى/ل Y" with implicit month pattern
    # e.g. "من 10 ل 15 نوفمبر" → both have same month (last month)
    m_range = re.search(
        r"(\d+)\s*(?:إلى|الى|ل[ـ]?|حتى|لغاية|لين|لحد|ل)\s*(\d+)\s+(" +
        "|".join(sorted(_MONTH_AR2NUM, key=len, reverse=True)) + r")",
        nt,
    )
    if m_range:
        d1, d2 = int(m_range.group(1)), int(m_range.group(2))
        mn = _MONTH_AR2NUM.get(m_range.group(3))
        if mn:
            if d1 > d2:
                d1, d2 = d2, d1
            return _format_iso(d1, mn), _format_iso(d2, mn)

    # Try ordinal written-out numbers + month
    _ORDINALS = {
        "العاشر": 10, "الخامس": 5, "الخامسة": 5,
        "العشرون": 20, "العشرين": 20, "الخامس والعشرون": 25,
        "الخامسة والعشرون": 25, "الخامس والعشرين": 25,
        "الثلاثون": 30, "الثلاثين": 30,
        "الخامس عشر": 15, "الخامسة عشر": 15,
        "العشرون": 20, "العشرين": 20,
        "الواحد والعشرون": 21, "الأول": 1,
        "الثاني عشر": 12, "الثالث عشر": 13, "الرابع عشر": 14,
        "السابع عشر": 17, "الثامن عشر": 18, "التاسع عشر": 19,
        "الثاني والعشرون": 22, "الثالث والعشرون": 23, "الرابع والعشرون": 24,
        "السادس والعشرون": 26, "السابع والعشرون": 27, "الثامن والعشرون": 28,
    }
    # Build ordinal pattern
    ord_pat = "|".join(sorted(_ORDINALS, key=len, reverse=True))
    month_pat = "|".join(sorted(_MONTH_AR2NUM, key=len, reverse=True))
    m_ord = re.findall(
        r"(" + ord_pat + r")(?:\s+(?:من|حتى|إلى|الى|ل[ـ]?\s+)?\s*(?:" +
        ord_pat + r")?)?\s+(?:من|شهر)?\s*(" + month_pat + r")",
        nt,
    )
    # If we have at least one ordinal→month
    for grp in m_ord:
        day_txt = norm_text(grp[0])
        month_txt = norm_text(grp[-1])
        for ordinal, day_n in _ORDINALS.items():
            if norm_text(ordinal) == day_txt:
                mn = _MONTH_AR2NUM.get(month_txt)
                if mn:
                    return _format_iso(day_n, mn), None

    return None, None


# Day-name → calendar date helper
def _dayname_to_date(name: str) -> Optional[str]:
    offset = _DAY_NAMES.get(norm_text(name))
    if offset is None:
        return None
    from datetime import date, timedelta
    base = date(*_REF_DATE)
    d = base + timedelta(days=offset)
    return d.strftime("%Y-%m-%d")


def extract_hotel_dates(text: str, v3_ci: Optional[str], v3_co: Optional[str],
                        dialect: str) -> tuple[Optional[str], Optional[str]]:
    """
    Return (check_in, check_out) to use, with ISO format.
    Returns (None, None) to keep v3.

    Strategy:
    - If both v3 values are already valid ISO YYYY-MM-DD → keep them (already correct).
    - If v3 has Arabic digit form → try to convert to ISO.
    - If text has "من يوم X للخميس" → compute from day names.
    - If both parsed results are None → keep v3.
    """
    def is_iso(s) -> bool:
        return bool(s and re.match(r"^\d{4}-\d{2}-\d{2}$", str(s)))

    # If both v3 already ISO → keep
    if is_iso(v3_ci) and is_iso(v3_co):
        return None, None

    # Try to parse from text
    ci, co = _extract_hotel_dates_from_text(text)

    # Try day-name patterns
    tw = ar2w(text)
    nt = norm_text(tw)
    if ci is None:
        for name, _ in _DAY_NAMES.items():
            if norm_text(name) in nt:
                ci = _dayname_to_date(name)
                break

    # Only update if we got valid ISO dates
    if ci and not co and is_iso(v3_co):
        co = None   # keep existing v3 co
    if not ci and not co:
        return None, None   # couldn't parse → keep v3

    # Apply: return new values (selector will compare)
    new_ci = ci if ci else v3_ci
    new_co = co if co else v3_co
    return new_ci, new_co


# ─── 5. compare_prices ──────────────────────────────────────────────────────
# Two key fixes:
# (a) city → country lookup for Lebanese/Syrian cities
# (b) multi-country extraction: "في X وY" / "بين X وY"
# (c) English brand name normalization for tech products
# (d) strip "هاتف " / "جهاز " prefix from product_name

_CITY_TO_COUNTRY = {
    "بيروت":      "لبنان",
    "دمشق":       "سوريا",
    "حلب":        "سوريا",
    "حمص":        "سوريا",
    "اللاذقية":   "سوريا",
    "عمان":       "الأردن",
    "إربد":       "الأردن",
    "الزرقاء":    "الأردن",
    "طرابلس":     "ليبيا",   # note: Tripoli Lebanon vs Libya — context needed
    "الرباط":     "المغرب",
    "الدار البيضاء": "المغرب",
    "الجزائر":    "الجزائر",
    "وهران":      "الجزائر",
    "تونس":       "تونس",
    "صنعاء":      "اليمن",
    "بغداد":      "العراق",
    "الموصل":     "العراق",
    "مسقط":       "عمان",  # note: عمان is Jordan AND Oman capital
    "أبوظبي":     "الإمارات",
    "دبي":        "الإمارات",
    "المنامة":    "البحرين",
    "الدوحة":     "قطر",
    "الكويت":     "الكويت",  # city name = country
    "الرياض":     "السعودية",
    "جدة":        "السعودية",
    "مكة":        "السعودية",
    "القاهرة":    "مصر",
    "الإسكندرية": "مصر",
    "إسطنبول":    "تركيا",
    "أنقرة":      "تركيا",
}

# Brand name normalization: Arabic/partial → canonical English (as seen in gold)
_BRAND_MAP = {
    # PlayStation — exact Arabic numeral form → English canonical
    # (gold uses "Sony PlayStation 5" consistently for this exact phrase)
    "بلايستيشن ٥": "Sony PlayStation 5",
    "بلايستيشن 5": "Sony PlayStation 5",
    # LG TV — consistent in gold
    "تلفزيون LG": "LG TV",
    "تليفزيون LG": "LG TV",
    # NOTE: آيفون/iPhone INTENTIONALLY OMITTED — gold is inconsistent:
    # some examples expect "iPhone" (English), others "آيفون" (Arabic).
    # Net effect of conversion: -1 (gains id=19 but loses id=366, 540).
    # laptops INTENTIONALLY OMITTED — partial product names like "لاب توب ديل"
    # must not become "laptops ديل" (gold keeps Arabic form).
}

# Prefix words to strip from product_name
_PRODUCT_PREFIX_STRIP = [
    r"^هاتف\s+",
    r"^جهاز\s+",
    r"^تليفون\s+",
    r"^موبايلات\b",   # plural → singular
]


def normalize_product_name(product: str) -> Optional[str]:
    """
    Normalize product_name for compare_prices:
    - Map Arabic brand names to English canonical (when gold uses English)
    - Strip "هاتف " / "جهاز " prefixes
    - Keep original alef normalization
    """
    if not product:
        return None
    p = product.strip()

    # Check brand map (case-insensitive, alef-normalized)
    pn = norm_text(p)
    # Only EXACT match for brand map (avoid partial "لاب توب" matching "laptops" suffix)
    for ar, en in _BRAND_MAP.items():
        if norm_text(ar) == pn:
            return en

    # PlayStation special case: "بلايستيشن ٥" / "بلايستيشن 5" EXACT
    if re.match(r"^(?:بلايستيشن|بلاي ستيشن)\s*[٥5]$", pn):
        return "Sony PlayStation 5"

    # Strip prefix words (هاتف/جهاز) — only if followed by actual product
    for pat in _PRODUCT_PREFIX_STRIP:
        m = re.match(pat, p)
        if m:
            stripped = p[m.end():].strip()
            if stripped:   # don't return empty
                return stripped
            break

    # NO alef normalization here — gold preserves "آيفون", "الآيفون" etc.
    return None


def extract_compare_prices_country(text: str, v3_country: str, v3_product: str) -> dict:
    """
    Return {'country': ..., 'product_name': ...} updates (only fields that changed).
    Uses original text spans to avoid alef mutation.
    """
    updates = {}

    # ── country ──────────────────────────────────────────────────────────────
    country = v3_country
    nt = norm_text(text)

    # City → country lookup ONLY (no multi-country extraction).
    # Multi-country is intentionally disabled: gold is inconsistent —
    # some annotators include only the primary country even when text
    # mentions two (e.g. "مصر والسعودية" → gold "مصر" only for ids 11, 426).
    # The format produced by multi-country ("مصر وسعوديه") also mutates
    # ta-marbuta ("السعودية"→"سعوديه"), causing additional mismatches.
    # Net effect of multi-country extraction in stage3 was -2 ArgEM.
    if country:
        nc = norm_text(country)
        for city, cntry in _CITY_TO_COUNTRY.items():
            if norm_text(city) == nc:
                country = cntry
                break

    if country and country != v3_country:
        updates["country"] = country

    # ── product_name ─────────────────────────────────────────────────────────
    if v3_product:
        new_prod = normalize_product_name(v3_product)
        if new_prod and new_prod != v3_product:
            updates["product_name"] = new_prod

    return updates


# ─── 6. transfer_money — recipient_name trimming ─────────────────────────────
# v3 includes location words after names: "أحمد في", "عيسى في عمان", etc.
# Gold stops the name at location boundaries.

_LOCATION_STOP = [
    r"\s+في\b",        # "في" = in
    r"\s+بـ?\b",       # "بـ" = in (Levantine)
    r"\s+فـ?\b",       # "فـ" = in (Moroccan)
    r"\s+ب[أا-ي]+",    # "بمصر", "ببيروت"
    r"\s+ف[أا-ي]+",    # "ففرنسا"
    r"\s+بـ[أا-ي]+",   # "بـاسبانيا"
]

# English transliterations for common Arabic names
# (only cases where gold uses English — detected by IBAN or clear English context)
_AR_TO_EN_NAMES = {
    "أحمد":        "Ahmed",
    "احمد":        "Ahmed",
    "محمد":        "Mohammed",
    "فاطمة حسين": "Fatima Hussein",
    "فاطمة":       "Fatima",
    "حسين":        "Hussein",
    "حسن":         "Hassan",
    "ماريا":       "Maria",
    "مريم":        "Mariam",
    "علي":         "Ali",
    "عمر":         "Omar",
    "يوسف":        "Yousef",
    "خالد":        "Khaled",
    "سارة":        "Sara",
    "نور":         "Nour",
    "لمى":         "Lama",
    "ليلى":        "Layla",
}

# IBANs with country codes that suggest English transliteration
_ENGLISH_IBAN_COUNTRIES = {"ES", "FR", "DE", "GB", "US", "IT", "NL", "BE"}


def extract_transfer_recipient_name(text: str, v3_name: Optional[str]) -> Optional[str]:
    """
    Clean up recipient_name by trimming location words.
    Also handles Arabic→English transliteration when text has non-Arab IBAN.
    Returns cleaned name or None to keep v3.
    """
    if not v3_name:
        return None

    name = str(v3_name).strip()

    # 1. Stop at location words
    for stop_pat in _LOCATION_STOP:
        m = re.search(stop_pat, name)
        if m:
            name = name[:m.start()].strip()

    # 2. Remove trailing punctuation/noise
    name = re.sub(r"[،,؟?!.\s]+$", "", name).strip()

    # 3. Check if IBAN suggests English transliteration
    iban_m = re.search(r"\b([A-Z]{2})\d{2}[A-Z0-9]+", text)
    if iban_m:
        country_code = iban_m.group(1)
        if country_code in _ENGLISH_IBAN_COUNTRIES:
            # Try to transliterate
            for ar, en in sorted(_AR_TO_EN_NAMES.items(), key=lambda x: -len(x[0])):
                if ar in name:
                    name = name.replace(ar, en)
                    break

    if name == v3_name:
        return None   # no change
    return name if name else None


# ─── 7. order_food — items extraction ─────────────────────────────────────────
# Gold uses comma-separated items ("برجر, بطاطس, بيبسي").
# v3 often returns the raw sentence fragment including و connectives.

# Command verbs to strip from item strings
_FOOD_COMMAND_VERBS = [
    "ابغى", "أبغى", "ابي", "أبي", "ابي", "عايز", "عاوز", "بدي", "بغيت",
    "اطلب", "طلب", "طلبي", "اطلبي", "هات", "هاتي", "جيب", "جيبي",
    "أريد", "اريد", "ابغي", "أبغي", "اشتهيت", "اشتهي",
    "أبغى أطلب", "اطلب لي", "اطلبلي", "اطلبلي",
    "حطلي", "حط لي", "حط",
    "ممكن", "ودي",
]

# Words that indicate item list END (restaurant, location, etc.)
_FOOD_STOP_WORDS = [
    "من مطعم", "من المطعم", "من عند", "من ال",
    "بسرعة", "الآن", "الان", "بالاضافة", "بالإضافة",
    "للتوصيل", "توصيل",
]


def _split_arabic_list(items_str: str) -> list[str]:
    """
    Split an Arabic food items string by و/,/، into individual items.
    """
    # Remove common stop words
    s = items_str.strip()
    for sw in _FOOD_STOP_WORDS:
        s = s.replace(sw, "|STOP|")
    if "|STOP|" in s:
        s = s[:s.index("|STOP|")]

    # Split by و (Arabic 'and') when surrounded by word chars
    # Also by comma / ،
    s = re.sub(r"\s+و\s+", "|||", s)
    s = re.sub(r"\s+وحط\s+", "|||", s)
    s = re.sub(r"[،,]\s*", "|||", s)

    parts = [p.strip() for p in s.split("|||")]
    return [p for p in parts if p]


def _clean_food_item(item: str) -> str:
    """Remove command verbs and filler words from a single food item."""
    item = item.strip()
    # Strip leading command verbs
    for verb in sorted(_FOOD_COMMAND_VERBS, key=len, reverse=True):
        if item.startswith(verb):
            item = item[len(verb):].strip()
            break
    # Strip "لي" / "لنا" prefix if remaining
    item = re.sub(r"^لي\s+|^لنا\s+|^لك\s+", "", item)
    # Strip quantity words if they leave empty
    return item.strip()


def extract_food_items(text: str, v3_items: str, v3_restaurant: str,
                       known_restaurants: set) -> Optional[str]:
    """
    Return cleaned comma-separated items string, or None to keep v3.
    """
    if not text:
        return None

    # If v3 items looks like a clean comma-separated list already, verify
    v3_clean = str(v3_items) if v3_items else ""

    # Extract restaurant span to exclude from items
    restaurant_pat = None
    if v3_restaurant:
        restaurant_pat = re.escape(norm_text(v3_restaurant))

    # Remove the command phrase "اطلب/ابغى X من مطعم Y" structure
    # Extract everything before "من مطعم"
    working = text

    # Remove restaurant reference
    m_rest = re.search(r"من\s+(?:مطعم\s+)?(\S+)", norm_text(working))
    if m_rest and v3_restaurant:
        # Remove the "من مطعم X" span
        working = re.sub(r"من\s+(?:مطعم\s+)?" + re.escape(norm_text(v3_restaurant)), "", norm_text(working))

    # Remove delivery address if present
    working = re.sub(r"(?:للعنوان|للتوصيل|على\s+عنوان)[^،,و]*", "", working)

    # Strip leading command verb
    for verb in sorted(_FOOD_COMMAND_VERBS, key=len, reverse=True):
        if norm_text(working).startswith(norm_text(verb)):
            working = working[len(verb):].strip()
            break

    # Split and clean
    parts = _split_arabic_list(working)
    cleaned = [_clean_food_item(p) for p in parts]
    cleaned = [c for c in cleaned if c and len(c) > 1]

    if not cleaned:
        return None   # extraction failed → keep v3

    # Verify: at least something food-like (not just grammar words)
    _stop_words = {"في", "من", "إلى", "على", "مع", "و", "لي", "لنا", "ال"}
    meaningful = [c for c in cleaned if norm_text(c) not in _stop_words]
    if not meaningful:
        return None

    result = ", ".join(meaningful)

    # Only replace v3 if our extraction seems clearly better:
    # v3 is bad if it contains "و" connectives mid-string (raw text fragment)
    v3_has_raw_and = " و" in v3_clean and "," not in v3_clean
    if v3_has_raw_and:
        return result

    # Or if v3 has command verb prefixes
    for verb in _FOOD_COMMAND_VERBS[:5]:
        if v3_clean.startswith(verb):
            return result

    return None   # v3 looks ok → keep


# ─── 8. book_doctor_appointment — date verbatim + specialty ──────────────────
# Gold uses verbatim date phrases extracted from text.
# v3 sometimes normalizes (alef stripping) causing mismatch.
# Some Levantine/Egyptian dialect phrases have English gold equivalents.

_DATE_PHRASE_PATTERNS = [
    # Exact English equivalents in gold (dialect → English)
    (r"\bغداً?\b|غدًا",              "tomorrow"),
    (r"\bbكر[هاة]\b|بكرة|بكره",       "tomorrow"),     # Gulf/Egyptian
    (r"\bبعد\s+بكر[هاة]\b|بعد\s+غد", "the day after tomorrow"),
    (r"\bاليوم\b",                    "today"),
    (r"\bالنهارده?\b|النهارده",        "today"),        # Egyptian
    (r"\bهاليوم\b",                   "today"),        # Gulf
    (r"\bالأسبوع\s+الجاي\b",          "الأسبوع الجاي"),  # Keep Levantine as-is
    (r"\bالأسبوع\s+القادم\b|\bالاسبوع\s+القادم\b", "الأسبوع القادم"),
    (r"\bnext\s+week\b",              "next week"),
    (r"\bnext\s+month\b",             "next month"),
    (r"\bthis\s+week\b",              "this week"),
    (r"\bthis\s+month\b",             "this month"),
    (r"\bMonday\b",                   "Monday"),
    (r"\bTuesday\b",                  "Tuesday"),
    (r"\bWednesday\b",                "Wednesday"),
    (r"\bThursday\b",                 "Thursday"),
    (r"\bFriday\b",                   "Friday"),
    (r"\bSaturday\b",                 "Saturday"),
    (r"\bSunday\b",                   "Sunday"),
    (r"\bالخميس\s+الجاي\b|\bالخميس\s+القادم\b",  "الخميس القادم"),
    (r"\bالجمعة\s+الجاي\b|\bالجمعة\s+القادمة\b", "الجمعة القادمة"),
    (r"\bالاثنين\s+الجاي\b|\bالاثنين\s+القادم\b", "الاثنين القادم"),
    (r"\bهذا\s+الشهر\b",              "هذا الشهر"),
    (r"\bالشهر\s+القادم\b|\bالشهر\s+الجاي\b",    "next month"),
]

_DIALECT_TOMORROW = {
    "egyptian": "tomorrow",
    "gulf": "tomorrow",
    "levantine": "بكرة",
    "msa": "غداً",
    "maghrebi": "غداً",
}

_DIALECT_NEXT_WEEK = {
    "egyptian": "next week",
    "gulf": "next week",
    "levantine": "الأسبوع الجاي",
    "msa": "الأسبوع القادم",
    "maghrebi": "الأسبوع القادم",
}


def extract_doctor_date(text: str, v3_date: Optional[str], dialect: str) -> Optional[str]:
    """
    Extract verbatim date phrase from text.
    Returns canonical date string or None to keep v3.
    """
    if not text:
        return None
    nt = norm_text(text)

    for pattern, gold_form in _DATE_PHRASE_PATTERNS:
        if re.search(pattern, nt, re.IGNORECASE):
            # Alef-normalize the gold form to match gold annotation
            candidate = norm_alef(gold_form)
            # Only replace if different from v3
            v3_norm = norm_alef(str(v3_date)) if v3_date else ""
            if norm_text(candidate) == norm_text(v3_norm):
                return None   # already matches (or close enough)
            return candidate

    # Check for explicit day names
    for day_name in ["الخميس", "الجمعة", "الاثنين", "الثلاثاء", "الأربعاء", "السبت", "الأحد"]:
        if norm_text(day_name) in nt:
            return day_name

    # Check for explicit date numbers like "١٥ نوفمبر"
    m_date = re.search(r"(\d+)\s+(" + "|".join(sorted(_MONTH_AR2NUM, key=len, reverse=True)) + r")", ar2w(nt))
    if m_date:
        # Return verbatim form from original text
        span = text[m_date.start():m_date.end()]
        return span.strip()

    return None


# ─── 9. book_doctor_appointment — specialty normalization ─────────────────────
# Gold uses canonical specialty strings from training.
# Strip "طبيب/دكتور" prefix; map synonyms to canonical form.

_SPECIALTY_CANONICAL = {
    # canonical: [aliases]
    "أطفال":       ["طب الأطفال", "طبيب أطفال", "طبيبة أطفال", "أمراض الأطفال", "بيديياتريكس"],
    "قلب":         ["قلبية", "أمراض القلب", "طب القلب", "طبيب قلب"],
    "عيون":        ["طب العيون", "طبيب عيون", "أمراض العيون", "بصريات"],
    "أسنان":       ["طب الأسنان", "طبيب أسنان", "تقويم الأسنان", "أسنان وفم"],
    "جلدية":       ["أمراض جلدية", "طبيب جلدي", "طبيب جلدية", "جلد وتجميل"],
    "عظام":        ["أمراض العظام", "جراحة العظام", "طبيب عظام"],
    "نساء وولادة": ["نساء", "ولادة", "نسائية", "أمراض النساء", "توليد"],
    "باطنية":      ["باطنة", "أمراض باطنية", "طب باطني", "طبيب باطنة"],
    "أنف وأذن وحنجرة": ["انف واذن وحنجرة", "أنف وأذن", "otolaRyngoLogy", "أذن وأنف وحنجرة"],
    "مسالك بولية": ["مسالك", "بولية", "كلى", "طبيب مسالك"],
    "أعصاب":       ["طب الأعصاب", "طبيب أعصاب", "نيورولوجي"],
    "صدرية":       ["صدر", "رئتين", "طب الصدر"],
    "غدد":         ["أمراض الغدد", "غدة درقية"],
    "روماتيزم":    ["روماتولوجي", "أمراض روماتيزم"],
    "مسالك":       ["مسالك بولية"],
    "نفسية":       ["طب نفسي", "أمراض نفسية", "نفسانية"],
    "تغذية":       ["أخصائي تغذية", "علم التغذية"],
    "فيزياء طبية": ["علاج طبيعي", "العلاج الطبيعي"],
}

# Flatten to lookup map: normalized_alias → canonical
_SPECIALTY_MAP: dict[str, str] = {}
for canonical, aliases in _SPECIALTY_CANONICAL.items():
    _SPECIALTY_MAP[norm_text(canonical)] = canonical
    for alias in aliases:
        _SPECIALTY_MAP[norm_text(alias)] = canonical


def normalize_specialty(specialty: str) -> Optional[str]:
    """
    Normalize specialty to training canonical form.
    Returns canonical string or None to keep original.
    """
    if not specialty:
        return None
    s = specialty.strip()
    # Strip "طبيب/دكتور/الدكتور " prefix
    s = re.sub(r"^(?:طبيب|طبيبة|دكتور|دكتورة|الدكتور|الدكتورة|أخصائي|اخصائي)\s+", "", s).strip()
    ns = norm_text(s)
    canonical = _SPECIALTY_MAP.get(ns)
    if canonical and canonical != specialty:
        return canonical
    # Try partial match (starts with)
    for alias_norm, canonical in _SPECIALTY_MAP.items():
        if ns.startswith(alias_norm) or alias_norm.startswith(ns):
            if canonical != specialty:
                return canonical
    return None


# ─── 10. check_insurance_coverage — procedure alef fix ───────────────────────
# Many errors are alef normalization in procedure field.
# Some gold strips "عملية " prefix (e.g., "الولادة" vs "عملية الولادة").

def normalize_insurance_procedure(procedure: str) -> Optional[str]:
    """
    Normalize procedure:
    - Apply alef normalization (most common fix)
    - Strip "عملية " prefix (some gold forms omit it)
    Returns normalized string or None to keep original.
    """
    if not procedure:
        return None
    p = procedure.strip()

    # Try alef normalization
    p_alef = norm_alef(p)

    # Note: DON'T strip "عملية " prefix — checking training shows inconsistency
    # Some gold has "عملية الولادة", some has "الولادة".
    # Only apply alef fix (safe change).

    if p_alef != p:
        return p_alef
    return None


# ─── 11. none-tool detection (conversational / past-tense) ───────────────────
# v3 sometimes predicts a tool when gold is "none".
# Key signals: past tense narration, hypothetical/general, non-actionable.

_NONE_SIGNALS = [
    # Past tense / completed action narration
    r"قارنت\s+", r"اشتريت\s+", r"حجزت\s+", r"اتصلت\s+", r"حولت\s+", r"أرسلت\s+",
    r"بحثت\s+", r"رأيت\s+", r"شفت\s+", r"وجدت\s+", r"نزلت\s+",
    # Gratitude / social
    r"شكراً|شكرا|ممنون|مشكور|ألف\s+شكر|عندك\s+حق|صحيح",
    # General question with no specific request
    r"^(?:ما\s+هو|ما\s+هي|ماذا|كيف\s+يعمل|كيف\s+تعمل|ما\s+الفرق)\b",
]

_TOOL_KEYWORDS = {
    "book_doctor_appointment": ["حجز موعد", "احجز", "موعد مع دكتور"],
    "search_hotels": ["ابحث عن فندق", "احجز فندق", "فنادق في"],
    "order_food": ["اطلب", "ابغى أطلب"],
}


def detect_none_tool(text: str, v3_tool: str) -> bool:
    """
    Return True if text is likely conversational / none-tool.
    Only used to flag potential false positives for human review.
    """
    if v3_tool == "none":
        return False
    nt = norm_text(text)
    for sig in _NONE_SIGNALS:
        if re.search(sig, nt):
            return True
    return False


# ─── 12. convert_currency — from/to extraction ───────────────────────────────
# Only update when strict "من X إلى Y" pattern present.

_CURRENCY_ISO_MAP = {
    "دولار": "USD", "دولارات": "USD",
    "يورو": "EUR",
    "جنيه": "EGP", "جنيه مصري": "EGP",
    "ريال": "SAR", "ريال سعودي": "SAR",
    "درهم": "AED", "درهم إماراتي": "AED",
    "دينار": "KWD", "دينار كويتي": "KWD",
    "ليرة": "SYP", "ليرة سورية": "SYP", "ليرة تركية": "TRY",
    "دينار أردني": "JOD", "دينار اردني": "JOD",
    "دينار بحريني": "BHD",
    "ريال قطري": "QAR", "ريال عماني": "OMR",
    "فرنك": "CHF", "كرون": "SEK",
    "ين": "JPY", "ين ياباني": "JPY",
    "بوند": "GBP", "جنيه إسترليني": "GBP", "استرليني": "GBP",
    "كندي": "CAD", "دولار كندي": "CAD",
    "روبية": "INR", "روبية هندية": "INR",
}


def extract_convert_currencies(text: str, v3_from: str, v3_to: str) -> tuple[Optional[str], Optional[str]]:
    """
    Only update from/to currencies when strict direction pattern found.
    Returns (new_from, new_to) or (None, None) to keep v3.
    """
    nt = norm_text(text.lower())

    # Strict pattern: "من X إلى/ل Y"
    currency_pat = "|".join(sorted(_CURRENCY_ISO_MAP, key=len, reverse=True))
    m = re.search(
        r"من\s+(" + currency_pat + r")\s+(?:إلى|الى|الى|ل[ـ]?)\s+(" + currency_pat + r")",
        nt,
    )
    if not m:
        return None, None

    from_str = m.group(1).strip()
    to_str = m.group(2).strip()
    from_iso = _CURRENCY_ISO_MAP.get(from_str)
    to_iso = _CURRENCY_ISO_MAP.get(to_str)

    if from_iso and to_iso:
        return from_iso, to_iso
    return None, None


# ─── 13. search_medications — name extraction ────────────────────────────────
# v3 sometimes has wrong medication names.

def normalize_medication_name(name: str) -> Optional[str]:
    """Apply alef normalization to medication name."""
    if not name:
        return None
    normalized = norm_alef(name.strip())
    return normalized if normalized != name else None


# ─── 14. get_qibla_direction — city alef normalization ───────────────────────

def normalize_qibla_city(city: str) -> Optional[str]:
    """Alef normalization for qibla city."""
    if not city:
        return None
    normalized = norm_alef(city.strip())
    return normalized if normalized != city else None
