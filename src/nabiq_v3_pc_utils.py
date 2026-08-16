"""
nabiq_v3_pc_utils.py
NABIQ-v3-PC: normalization functions + direct extractors for weak tools.

All functions take (user_text, current_args, train_data) and return improved args.
They NEVER modify files or global state.
"""

import re
import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any

# ── Arabic ↔ text helpers ───────────────────────────────────────────────────
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
WESTERN_TO_AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

AR_NUMBER_WORDS = {
    "واحد": 1, "اثنين": 2, "اثنان": 2, "ثنين": 2, "ثلاثة": 3, "ثلاث": 3,
    "اربعة": 4, "أربعة": 4, "اربع": 4, "أربع": 4,
    "خمسة": 5, "خمس": 5, "ستة": 6, "ست": 6,
    "سبعة": 7, "سبع": 7, "ثمانية": 8, "ثمان": 8,
    "تسعة": 9, "تسع": 9, "عشرة": 10, "عشر": 10,
    "مية": 100, "مئة": 100, "الف": 1000, "ألف": 1000,
    "مليون": 1_000_000, "مليار": 1_000_000_000,
}

ARABIC_MONTHS = {
    "يناير": 1, "يناير": 1, "فبراير": 2, "مارس": 3,
    "أبريل": 4, "ابريل": 4, "مايو": 5, "يونيو": 6,
    "يوليو": 7, "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}


def ar2w(s: str) -> str:
    """Convert Arabic-Indic digits to Western digits."""
    return s.translate(ARABIC_DIGITS)


def norm_alef(s: str) -> str:
    return s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")


def norm_text(s: str) -> str:
    s = str(s or "").translate(ARABIC_DIGITS)
    s = re.sub(r"[ً-ٰٟ]", "", s)  # diacritics
    s = norm_alef(s)
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def extract_number_from_text(text: str) -> float | None:
    """Extract first number (Arabic or Western) from text, handling مليون/الف."""
    t = ar2w(text)
    # Try "X مليون" pattern
    m = re.search(r"(\d+(?:\.\d+)?)\s*(مليون|مليار|الف|ألف)", t)
    if m:
        n = float(m.group(1))
        mult = {"مليون": 1e6, "مليار": 1e9, "الف": 1e3, "ألف": 1e3}
        return n * mult[m.group(2)]
    # Try "مية/مئة" standalone
    if re.search(r"مية|مئة", t):
        m2 = re.search(r"(\d+(?:\.\d+)?)\s*(?:مية|مئة)", t)
        if m2:
            return float(m2.group(1)) * 100
    # Plain number
    m2 = re.search(r"\d+(?:\.\d+)?", t)
    if m2:
        return float(m2.group())
    # Arabic number words
    for word, val in sorted(AR_NUMBER_WORDS.items(), key=lambda x: -x[1]):
        if word in text:
            return float(val)
    return None


def extract_all_digit_strings(text: str) -> list[str]:
    """Extract all contiguous digit sequences (after Arabic→Western conversion), preserving leading zeros."""
    t = ar2w(text)
    return re.findall(r"\d+", t)


# ── ID-number extraction (iqama / traffic / visa) ───────────────────────────
def extract_id_number(text: str, min_len: int = 5) -> str | None:
    """
    Extract the longest numeric string from text (Arabic or Western digits).
    Preserves leading zeros.  Returns None if no sequence ≥ min_len.
    """
    t = ar2w(text)
    candidates = re.findall(r"\d+", t)
    if not candidates:
        return None
    best = max(candidates, key=len)
    return best if len(best) >= min_len else None


def extract_all_id_numbers(text: str, min_len: int = 5) -> list[str]:
    t = ar2w(text)
    return [s for s in re.findall(r"\d+", t) if len(s) >= min_len]


# ── IBAN extraction ──────────────────────────────────────────────────────────
IBAN_PATTERN = re.compile(
    r"\b([A-Z]{2}\d{2}[A-Z0-9]{1,30})\b"
)

def extract_iban(text: str) -> str | None:
    """Extract the first IBAN-like string from text (Country-code + digits/alphanumeric)."""
    m = IBAN_PATTERN.search(text)
    if m:
        return m.group(1)
    return None


# ── Currency helpers ─────────────────────────────────────────────────────────
# Short forms that MUST NOT be upgraded to ISO for calculate_zakat/transfer_money
# unless a qualifying country adjective appears.
ZAKAT_CURRENCY_PATTERNS: list[tuple[str, str]] = [
    # Specific qualified forms → ISO  (checked FIRST, longest patterns first)
    ("ريال سعودي",    "SAR"),
    ("الريال السعودي","SAR"),
    ("ريال قطري",     "QAR"),
    ("ريال عماني",    "OMR"),
    ("دولار أمريكي",  "USD"),
    ("دولار امريكي",  "USD"),
    ("الدولار الأمريكي", "USD"),
    ("جنيه مصري",     "EGP"),
    ("الجنيه المصري", "EGP"),
    ("جنيه إسترليني","GBP"),
    ("درهم إماراتي",  "AED"),
    ("درهم اماراتي",  "AED"),
    ("الدرهم الاماراتي", "AED"),
    ("درهم مغربي",    "MAD"),
    ("دينار كويتي",   "KWD"),
    ("دينار بحريني",  "BHD"),
    ("دينار أردني",   "JOD"),
    ("دينار اردني",   "JOD"),
    ("دينار جزائري",  "DZD"),
    ("ليرة سورية",    "SYP"),
    ("ليره سوريه",    "SYP"),
    ("ليرة لبنانية",  "LBP"),
    ("يورو",           "EUR"),
    ("euro",           "EUR"),
    # ISO codes already
    ("SAR", "SAR"), ("USD", "USD"), ("AED", "AED"), ("EGP", "EGP"),
    ("KWD", "KWD"), ("BHD", "BHD"), ("QAR", "QAR"), ("EUR", "EUR"),
    ("GBP", "GBP"), ("JOD", "JOD"), ("MAD", "MAD"), ("SYP", "SYP"),
    ("LBP", "LBP"), ("OMR", "OMR"),
    # Short/ambiguous → keep as-is (return the literal Arabic form)
    ("ريال",   "ريال"),
    ("دولار",  "دولار"),
    ("جنيه",   "جنيه"),
    ("درهم",   "درهم"),
    ("دينار",  "دينار"),
    ("ليرة",   "ليرة"),
    ("ليره",   "ليره"),
]

# For transfer_money and convert_currency, short forms → ISO
FULL_CURRENCY_MAP: list[tuple[str, str]] = [
    ("ريال سعودي",    "SAR"),
    ("الريال السعودي","SAR"),
    ("ريال قطري",     "QAR"),
    ("ريال عماني",    "OMR"),
    ("دولار أمريكي",  "USD"),
    ("دولار امريكي",  "USD"),
    ("الدولار الأمريكي", "USD"),
    ("جنيه مصري",     "EGP"),
    ("الجنيه المصري", "EGP"),
    ("جنيه إسترليني","GBP"),
    ("درهم إماراتي",  "AED"),
    ("درهم اماراتي",  "AED"),
    ("الدرهم الاماراتي", "AED"),
    ("درهم مغربي",    "MAD"),
    ("دينار كويتي",   "KWD"),
    ("دينار بحريني",  "BHD"),
    ("دينار أردني",   "JOD"),
    ("دينار اردني",   "JOD"),
    ("دينار جزائري",  "DZD"),
    ("ليرة سورية",    "SYP"),
    ("ليره سوريه",    "SYP"),
    ("ليرة لبنانية",  "LBP"),
    ("يورو",           "EUR"),
    ("euro",           "EUR"),
    ("sar", "SAR"), ("usd", "USD"), ("aed", "AED"), ("egp", "EGP"),
    ("kwd", "KWD"), ("bhd", "BHD"), ("qar", "QAR"), ("eur", "EUR"),
    ("gbp", "GBP"), ("jod", "JOD"), ("mad", "MAD"), ("syp", "SYP"),
    ("lbp", "LBP"), ("omr", "OMR"), ("try", "TRY"), ("dzd", "DZD"),
    ("ريال",   "SAR"),
    ("درهم",   "AED"),
    ("يورو",   "EUR"),
    ("دولار",  "USD"),
    ("جنيه",   "EGP"),
    ("دينار",  "KWD"),   # default دينار → KWD (most common ISO in train)
    ("ليرة",   "SYP"),   # default ليرة → SYP
]


def normalize_currency_zakat(text: str, current_val: str) -> str:
    """
    Field-aware currency normalization for calculate_zakat.
    Short Arabic forms (ريال, دولار, جنيه...) are KEPT as-is unless a qualifier
    (سعودي, مصري, etc.) is present in the user text.
    """
    nt = norm_text(text)
    for pattern, iso in ZAKAT_CURRENCY_PATTERNS:
        if norm_text(pattern) in nt:
            return iso
    # No match: return current value unchanged
    return current_val


def normalize_currency_full(text: str) -> str | None:
    """
    Full currency normalization (for transfer_money, convert_currency).
    Returns ISO code.
    """
    nt = norm_text(text)
    for pattern, iso in FULL_CURRENCY_MAP:
        if norm_text(pattern) in nt:
            return iso
    return None


def find_currencies_in_text(text: str) -> list[str]:
    """Return ordered list of ISO currencies found in text (left to right)."""
    found: list[tuple[int, str]] = []
    nt = norm_text(text)
    for pattern, iso in FULL_CURRENCY_MAP:
        np = norm_text(pattern)
        idx = nt.find(np)
        if idx >= 0:
            # Don't double-count the same ISO
            if not any(f[1] == iso for f in found):
                found.append((idx, iso))
    found.sort(key=lambda x: x[0])
    return [f[1] for f in found]


# ── book_doctor_appointment: specialty normalization ────────────────────────
# Strip "طبيب " or "دكتور " prefix ONLY when the stripped form is the dominant gold.
SPECIALTY_PREFIXES = re.compile(
    r"^(طبيب\s+|دكتور\s+|دكتورة\s+|طبيبة\s+|الطبيب\s+|الدكتور\s+)"
)

# Specialty synonym table → canonical gold form (derived from training distribution)
SPECIALTY_SYNONYMS: list[tuple[str, str]] = [
    # children
    ("اطفال",          "أطفال"),
    ("الاطفال",        "أطفال"),
    ("الأطفال",        "أطفال"),
    ("طب الأطفال",     "طب الأطفال"),
    ("طب الاطفال",     "طب الأطفال"),
    # heart
    ("قلب",            "قلب"),
    ("القلب",          "قلب"),
    ("قلبية",          "قلب"),
    # eyes
    ("عيون",           "عيون"),
    ("العيون",         "عيون"),
    # teeth
    ("أسنان",          "أسنان"),
    ("اسنان",          "أسنان"),
    # dermatology
    ("جلدية",          "جلدية"),
    ("الجلدية",        "جلدية"),
    ("أمراض جلدية",   "أمراض جلدية"),
    ("جلد",            "جلدية"),
    # ENT
    ("أنف وأذن وحنجرة", "أنف وأذن وحنجرة"),
    ("انف واذن وحنجره", "أنف وأذن وحنجرة"),
    ("أنف وأذن",       "أنف وأذن وحنجرة"),
    # women
    ("نساء وتوليد",    "نساء وتوليد"),
    ("نساء وولادة",    "نساء وتوليد"),
    ("النساء",         "نساء"),
    ("نسائية",         "نسائية"),
    ("نساء",           "نساء"),
    # bones
    ("عظام",           "عظام"),
    ("العظام",         "عظام"),
    # psychiatry
    ("نفسي",           "نفسي"),
    ("النفسي",         "نفسي"),
    # neurology
    ("أعصاب",          "أعصاب"),
    ("الأعصاب",        "أعصاب"),
    # internal
    ("باطنية",         "باطنية"),
    ("باطنه",          "باطنية"),
    ("باطنة",          "باطنية"),
    # gastro
    ("جهاز هضمي",      "جهاز هضمي"),
    ("الجهاز الهضمي",  "جهاز هضمي"),
    # oncology
    ("أورام",          "أورام"),
    ("الأورام",        "أورام"),
]

# Keep "دكتور أنف وأذن وحنجرة" form
KEEP_DOCTOR_PREFIX = {"أنف وأذن وحنجرة"}


def normalize_specialty(specialty: str) -> str:
    """
    Strip doctor/physician prefix when the base specialty is the dominant gold form.
    Apply synonym normalization.
    """
    if not specialty:
        return specialty

    stripped = SPECIALTY_PREFIXES.sub("", specialty).strip()

    # If stripping gives one of the KEEP forms, DON'T strip
    # (e.g. "دكتور أنف وأذن وحنجرة" → keep with the prefix for that special case)
    # But actually, training shows "أنف وأذن وحنجرة" 13x most common, "دكتور أنف" rare.
    # We strip and use the base form.

    # Synonym lookup (try stripped first, then original)
    nt_stripped = norm_text(stripped)
    for alias, canon in SPECIALTY_SYNONYMS:
        if norm_text(alias) == nt_stripped:
            return canon

    # Try original
    nt_orig = norm_text(specialty)
    for alias, canon in SPECIALTY_SYNONYMS:
        if norm_text(alias) == nt_orig:
            return canon

    # Default: return stripped version
    return stripped


# ── calculate_zakat: type normalization ──────────────────────────────────────
ZAKAT_TYPE_MAP: list[tuple[str, str]] = [
    ("gold",       ["ذهب"]),
    ("silver",     ["فضة", "فضه"]),
    ("cash",       ["مال", "اموال", "فلوس", "نقد", "نقود", "cash"]),
    ("trade",      ["تجارة", "تجاره", "عروض", "بضاعة", "بضاعه"]),
    ("crops",      ["زروع", "زرع", "محاصيل", "crops"]),
    ("fitr",       ["فطر", "fitr"]),
    ("salary",     ["راتب", "مرتب", "salary"]),
    ("livestock",  ["مواشي", "ماشية", "حيوانات", "livestock"]),
    ("realestate", ["عقارات", "عقار", "realestate"]),
    ("shares",     ["أسهم", "اسهم", "shares"]),
    ("general",    ["general"]),
]


def normalize_zakat_type(text: str, current_type: str) -> str:
    nt = norm_text(text)
    for canon, aliases in ZAKAT_TYPE_MAP:
        for alias in aliases:
            if norm_text(alias) in nt:
                return canon
    return current_type


# ── get_weather: days extraction / verification ──────────────────────────────
DAY_WORDS: dict[str, float] = {
    "اليوم": 1.0, "اليوم فقط": 1.0, "هذا اليوم": 1.0,
    "بكرة": 1.0, "غداً": 1.0, "غدا": 1.0,
    "يومين": 2.0, "يومان": 2.0,
    "ثلاثة أيام": 3.0, "3 أيام": 3.0, "ثلاث أيام": 3.0,
    "أسبوع": 7.0, "اسبوع": 7.0, "أسبوعاً": 7.0,
    "أسبوعين": 14.0, "اسبوعين": 14.0, "أسبوعان": 14.0,
}

# Patterns that indicate "only today" → no days field needed
TODAY_PATTERNS = re.compile(r"(اليوم|النهارده|هلق|هلأ|الآن|حالياً|الحين|هاليوم|هالحين)")


def extract_weather_days(text: str, current_days: float | None) -> float | None:
    """
    Re-infer days from text.
    Return None if text indicates today/now only (no explicit days).
    """
    nt = norm_text(text)

    # Explicit day-count words
    for phrase, days in sorted(DAY_WORDS.items(), key=lambda x: -len(x[0])):
        if norm_text(phrase) in nt:
            if days == 1.0 and TODAY_PATTERNS.search(text):
                return None   # "اليوم" alone → no days field
            return days

    # Number + يوم
    m = re.search(r"(\d+)\s*أيام", ar2w(text))
    if m:
        return float(m.group(1))

    # Pure "اليوم/الآن" only → no days
    if TODAY_PATTERNS.search(text) and not re.search(r"\d", ar2w(text)):
        return None

    return current_days


# ── search_quran ─────────────────────────────────────────────────────────────
QURAN_SEARCH_TYPES: list[tuple[str, str]] = [
    ("tafseer",  ["تفسير", "فسر", "شرح", "تفسيرات"]),
    ("verse",    ["آية", "ايه", "آيات", "ابحث عن آية"]),
    ("topic",    ["موضوع", "يتحدث عن", "تتحدث عن"]),
    ("meaning",  ["معنى", "معني", "معني"]),
    ("exact",    ["نص حرفي"]),
    ("word",     ["كلمة"]),
]


def extract_quran_search_type(text: str) -> str | None:
    nt = norm_text(text)
    for canon, aliases in QURAN_SEARCH_TYPES:
        for alias in aliases:
            if norm_text(alias) in nt:
                return canon
    return None


def normalize_quran_query(text: str, current_query: str) -> str:
    """
    Improve Quran query extraction: prefer text-verbatim span.
    """
    # If query contains "سورة X" and text also has that, keep it
    t_norm = norm_text(text)
    q_norm = norm_text(current_query)

    # Try to find a better span: look for "سورة X" in text
    m = re.search(r"(سورة\s+\S+)", text)
    if m and norm_text(m.group(1)) not in q_norm:
        candidate = m.group(1).strip()
        if q_norm in norm_text(candidate):
            return candidate

    # quoted text
    m2 = re.search(r"[\"'\'\"](.*?)[\"'\'\"]", text)
    if m2:
        return m2.group(1).strip()

    return current_query


# ── search_hotels: date & guests extraction ──────────────────────────────────
MONTH_AR_TO_NUM: dict[str, int] = {
    "يناير": 1, "فبراير": 2, "مارس": 3,
    "أبريل": 4, "ابريل": 4, "مايو": 5, "يونيو": 6,
    "يوليو": 7, "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}
MONTH_NUM_TO_AR_W: dict[int, str] = {   # Western-digit + Arabic month name
    1: "يناير", 2: "فبراير", 3: "مارس",
    4: "أبريل", 5: "مايو", 6: "يونيو",
    7: "يوليو", 8: "أغسطس", 9: "سبتمبر",
    10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}
MONTH_NUM_TO_AR_AR: dict[int, str] = {   # Arabic-digit + Arabic month name
    1: "يناير", 2: "فبراير", 3: "مارس",
    4: "أبريل", 5: "مايو", 6: "يونيو",
    7: "يوليو", 8: "أغسطس", 9: "سبتمبر",
    10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

# Guest phrases
GUEST_PATTERNS: list[tuple[str, float]] = [
    (r"لشخص\s*واحد|لفرد\s*واحد|لشخص\s*1", 1.0),
    (r"لشخصين|لفردين|لاثنين|لاثنان|لشخصان", 2.0),
    (r"لثلاثة\s*أشخاص|لثلاث\s*أفراد|لـ\s*3\s*أشخاص|لثلاثة\s*أفراد|لثلاثة\s*ضيوف|لثلاث", 3.0),
    (r"لأربعة\s*أشخاص|لأربع\s*أشخاص|لـ\s*4\s*أشخاص|لأربعة\s*أفراد|لأربعة\s*ضيوف|لأربعة", 4.0),
    (r"لخمسة\s*أشخاص|لخمسة\s*أفراد|لـ\s*5\s*أشخاص|لخمسة\s*ضيوف", 5.0),
    (r"لستة\s*أشخاص|لـ\s*6\s*أشخاص", 6.0),
    (r"لـ?\s*(\d+)\s*(أشخاص|ضيوف|أفراد|شخص|ضيف|فرد)", None),  # generic
]


def extract_hotel_guests(text: str) -> float | None:
    """Extract guest count from text. Return None if not explicitly mentioned."""
    t = ar2w(text)
    for pattern, fixed_val in GUEST_PATTERNS:
        if fixed_val is not None:
            if re.search(pattern, t) or re.search(pattern, text):
                return fixed_val
        else:
            m = re.search(pattern, t)
            if not m:
                m = re.search(pattern, text)
            if m:
                try:
                    return float(ar2w(m.group(1)))
                except (ValueError, IndexError):
                    pass
    return None


def _parse_date_from_text(text: str) -> list[tuple[int, int, str, str]]:
    """
    Find all date mentions in text.
    Returns list of (char_position, month_num, day_str, raw_date_span).
    day_str preserves original digit form (Arabic or Western).
    """
    dates: list[tuple[int, int, str, str]] = []
    t_w = ar2w(text)  # Western-digit version

    for month_name, month_num in MONTH_AR_TO_NUM.items():
        # Pattern: "[day] [month]" or "[month] [day]"
        # Try "D/DD month" (Western digits in text)
        for pattern in [
            rf"(\d{{1,2}})\s*{re.escape(month_name)}",
            rf"{re.escape(month_name)}\s*(\d{{1,2}})",
        ]:
            for m in re.finditer(pattern, t_w):
                day_str_w = m.group(1)
                pos = m.start()
                dates.append((pos, month_num, day_str_w, m.group()))

        # Try Arabic digits: "٣ نوفمبر"
        for m in re.finditer(
            rf"([٠-٩]{{1,2}})\s*{re.escape(month_name)}", text
        ):
            day_str_ar = m.group(1)
            day_val = int(ar2w(day_str_ar))
            pos = m.start()
            # Convert Arabic digits to western for position tracking
            dates.append((pos, month_num, ar2w(day_str_ar), m.group()))

    # Remove duplicates by position (keep first)
    seen: set[int] = set()
    unique: list[tuple[int, int, str, str]] = []
    for pos, mn, ds, raw in sorted(dates, key=lambda x: x[0]):
        if pos not in seen:
            seen.add(pos)
            unique.append((pos, mn, ds, raw))

    return unique


def _infer_year(month_num: int) -> int:
    """Infer year: training data mostly 2023/2024."""
    return 2023


def _format_date(day: str, month_num: int, gold_sample: str | None) -> str:
    """
    Format a date to match the most likely gold format.
    Uses training-data ISO majority (405/558) but also respects input form.
    """
    day_int = int(day)
    year = _infer_year(month_num)

    # Try to infer format from the gold sample passed in
    if gold_sample:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", gold_sample):
            return f"{year}-{month_num:02d}-{day_int:02d}"
        if re.match(r"^\d{2}-\d{2}-\d{4}$", gold_sample):
            return f"{day_int:02d}-{month_num:02d}-{year}"
        if re.match(r"^\d{2}-\d{2}$", gold_sample):
            return f"{day_int:02d}-{month_num:02d}"
        # Arabic format: "١ فبراير" or "1 فبراير"
        if re.search(r"[٠-٩]", gold_sample):
            # Preserve Arabic digits
            ar_day = str(day_int).translate(WESTERN_TO_AR)
            return f"{ar_day} {MONTH_NUM_TO_AR_W[month_num]}"
        if re.search(r"\d+\s+\w+", gold_sample):
            return f"{day_int} {MONTH_NUM_TO_AR_W[month_num]}"

    # Default: ISO (most common in training: 405/558)
    return f"{year}-{month_num:02d}-{day_int:02d}"


def extract_hotel_dates(
    text: str,
    current_check_in: str | None,
    current_check_out: str | None,
) -> tuple[str | None, str | None]:
    """
    Extract check_in / check_out dates from text.
    Returns (check_in, check_out).  Falls back to current values if extraction fails.
    """
    dates = _parse_date_from_text(text)

    if len(dates) < 2:
        # Try to find "من X إلى X" pattern without explicit month (same-month)
        # e.g., "من ١ إلى ٥ نوفمبر"
        t_w = ar2w(text)
        for month_name, month_num in MONTH_AR_TO_NUM.items():
            m = re.search(
                rf"من\s+(\d{{1,2}})\s+(?:إلى|الى|ل|لحد|لغاية|لغاية|حتى)\s+(\d{{1,2}})\s+{re.escape(month_name)}",
                t_w
            )
            if m:
                d1, d2 = m.group(1), m.group(2)
                fmt = _format_date(d1, month_num, current_check_in)
                fmt2 = _format_date(d2, month_num, current_check_out)
                return fmt, fmt2
            # Arabic digits version
            m2 = re.search(
                rf"من\s+([٠-٩]{{1,2}})\s+(?:إلى|الى|ل|لحد|لغاية|حتى)\s+([٠-٩]{{1,2}})\s+{re.escape(month_name)}",
                text
            )
            if m2:
                d1 = ar2w(m2.group(1))
                d2 = ar2w(m2.group(2))
                fmt = _format_date(d1, month_num, current_check_in)
                fmt2 = _format_date(d2, month_num, current_check_out)
                return fmt, fmt2

        return current_check_in, current_check_out

    # We have at least 2 date mentions
    pos1, m1, d1, raw1 = dates[0]
    pos2, m2, d2, raw2 = dates[1]

    fmt1 = _format_date(d1, m1, current_check_in)
    fmt2 = _format_date(d2, m2, current_check_out)

    return fmt1, fmt2


# ── order_food: restaurant + items extraction ────────────────────────────────
# Restaurant extraction patterns (ordered by priority)
REST_PATTERNS = [
    re.compile(r"من\s+مطعم\s+([؀-ۿ\w\s]+?)(?=[،,\.!؟\?]|$|يشمل|اطلب|يتكون|الطلب|عبارة|قائمة)"),
    re.compile(r"من\s+([؀-ۿ\w\s]+?)(?=\s*[،,\.!؟\?]|$)"),
    re.compile(r"اطلب(?:لي|لنا)?\s+\w+\s+من\s+مطعم\s+([؀-ۿ\w\s]+?)(?=[،,\.!؟\?]|$)"),
    re.compile(r"اطلب(?:لي|لنا)?\s+\w+\s+من\s+([؀-ۿ\w\s]+?)(?=[،,\.!؟\?]|$)"),
]

# Restaurant name stopwords
REST_STOPWORDS = {
    "مطعم", "طعام", "اكل", "أكل", "وجبة", "وجبات", "الطلبات", "الطلب",
    "قائمة", "قائمة الطلبات", "يشمل", "عبارة", "يتكون",
}

# Known restaurants from training (normalized → canonical)
KNOWN_RESTAURANTS: dict[str, str] = {}  # populated by load_gazetteers()


def _clean_restaurant_name(raw: str) -> str:
    """Clean up extracted restaurant name."""
    name = raw.strip()
    # Remove trailing connectors
    name = re.sub(r"\s+(و|في|على|الطلب|الطلبات|يشمل|يتكون|أضف|اضف).*$", "", name)
    # Strip trailing punctuation
    name = name.rstrip("،,. !؟?")
    return name.strip()


def extract_restaurant_from_text(
    text: str,
    known_restaurants: dict[str, str],
    v2_restaurant: str | None = None,
) -> str | None:
    """
    Extract restaurant name from user text.
    Priority: pattern match > gazetteer lookup > v2 prediction.
    """
    # 1. "من مطعم X" pattern
    m = re.search(
        r"من\s+مطعم\s+([؀-ۿa-zA-Z0-9\s]+?)(?=[،,\.!؟\?\n]|$|يشمل|الطلبات|الطلب|أبغى|عايز)",
        text
    )
    if m:
        raw = _clean_restaurant_name(m.group(1))
        if raw and len(raw) > 1:
            # Check if "مطعم X" is a known name
            nr = norm_text(raw)
            full_nr = norm_text("مطعم " + raw)
            if full_nr in known_restaurants:
                return known_restaurants[full_nr]
            if nr in known_restaurants:
                return known_restaurants[nr]
            return raw  # Return without "مطعم" prefix (most gold drops it)

    # 2. "اطلب من X" or "طلب من X"
    m2 = re.search(
        r"(?:اطلب|طلب|أطلب|اطلبلي|اطلبلنا|أطلبلي)\s+\w*\s*من\s+([؀-ۿa-zA-Z0-9\s]+?)(?=[،,\.!؟\?\n]|$)",
        text
    )
    if m2:
        raw = _clean_restaurant_name(m2.group(1))
        if raw and len(raw) > 1:
            nr = norm_text(raw)
            if nr in known_restaurants:
                return known_restaurants[nr]
            return raw

    # 3. "من X" where X is a known restaurant name
    words = text.split()
    for i, w in enumerate(words):
        if norm_text(w) == norm_text("من") and i + 1 < len(words):
            # Try 1-word, 2-word, 3-word after "من"
            for length in range(3, 0, -1):
                candidate = " ".join(words[i+1:i+1+length])
                nr = norm_text(candidate)
                if nr in known_restaurants:
                    return known_restaurants[nr]

    # 4. Scan entire text for known restaurant names
    nt = norm_text(text)
    best_match: tuple[int, str] | None = None  # (start_pos, canonical)
    for nr, canon in known_restaurants.items():
        idx = nt.find(nr)
        if idx >= 0:
            if best_match is None or idx < best_match[0]:
                best_match = (idx, canon)
    if best_match:
        return best_match[1]

    return v2_restaurant  # fall back to v2


def extract_food_items_from_text(text: str, restaurant_name: str | None = None) -> str | None:
    """
    Extract food items from text. Remove restaurant-mention span.
    """
    # Remove greetings and common leading phrases
    cleaned = text.strip()

    # Remove the restaurant mention span
    if restaurant_name:
        # Remove "من مطعم X" or "من X"
        cleaned = re.sub(
            r"من\s+مطعم\s+" + re.escape(restaurant_name), "", cleaned, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"مطعم\s+" + re.escape(restaurant_name), "", cleaned, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"من\s+" + re.escape(restaurant_name), "", cleaned, flags=re.IGNORECASE
        )

    # Items after ":"
    colon_m = re.search(r"[:]\s*(.+)$", cleaned, re.DOTALL)
    if colon_m:
        items_part = colon_m.group(1).strip()
        # Remove trailing fluff
        items_part = re.sub(r"\s+(?:من\s+مطعم|من\s+\S+).*$", "", items_part)
        items_part = items_part.strip("،,. ")
        if items_part and len(items_part) > 2:
            return items_part

    # Items after "الطلبات هي/هو/تكون" or "الطلب هو"
    m2 = re.search(r"(?:الطلبات?\s*(?:هي|هو|تكون)?|الطلب\s*(?:هو)?|قائمة[^:]*:?)\s*(.+)$", cleaned)
    if m2:
        items_part = m2.group(1).strip()
        items_part = re.sub(r"\s+من\s+.*$", "", items_part)
        items_part = items_part.strip("،,. ")
        if items_part and len(items_part) > 2:
            return items_part

    # Items after order-verb at beginning: "ابغى/عايز/أريد X من مطعم Y" → X
    m3 = re.search(
        r"(?:ابغى|أبغى|أبي|ابي|عايز|بدي|أريد|اريد|أود|اود|احتاج|نريد)\s+(.+?)(?=من\s+(?:مطعم|\S+)|$)",
        cleaned
    )
    if m3:
        items_part = m3.group(1).strip()
        # Skip if it's just a request verb like "أطلب"
        if items_part and not re.match(r"^(?:اطلب|أطلب|طلب)\s*$", items_part):
            items_part = items_part.strip("،,. ")
            if items_part and len(items_part) > 2:
                return items_part

    # "يشمل/تشمل X"
    m4 = re.search(r"يشمل\s+(.+)$|تشمل\s+(.+)$", cleaned)
    if m4:
        items_part = (m4.group(1) or m4.group(2)).strip()
        items_part = items_part.strip("،,. ")
        if items_part and len(items_part) > 2:
            return items_part

    # "أضف X" / "اضف X"
    m5 = re.search(r"(?:أضف|اضف|أضيف|اضيف)\s+(.+)$", cleaned)
    if m5:
        return m5.group(1).strip("،,. ").strip()

    # Fallback: everything after order-verb + restaurant
    # Strip common request-phrase words at start
    cleaned2 = re.sub(
        r"^(?:اطلب|أطلب|طلب|أريد|اريد|ابغى|أبغى|أبي|ابي|بدي|عايز|أود|احتاج|نريد|نطلب)\s+",
        "", cleaned
    ).strip()
    cleaned2 = re.sub(
        r"^(?:طعام|أكل|وجبة|غداء|عشاء|فطور|طعام)\s+", "", cleaned2
    ).strip()

    if cleaned2 and len(cleaned2) > 3:
        return cleaned2

    return None


# ── transfer_money: recipient_name extraction ───────────────────────────────
STOP_AFTER_NAME = re.compile(
    r"""
    \s+(?:
        في\s+\w+  |     # في [country/city]
        بالبنك   |
        برقم     |
        رقم      |
        وده\s+رقم|
        الآيبان  |
        ايبان    |
        بنك      |
        bank     |
        حساب     |
        شلون     |
        شو\s+الإجراءات
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

NAME_STOPWORDS = {
    "في", "من", "إلى", "الى", "بالبنك", "بنك", "bank", "iban", "الآيبان",
    "ايبان", "رقم", "برقم", "وده", "حساب", "شو", "شلون", "شكيف",
}


def extract_recipient_name(text: str) -> str | None:
    """
    Extract recipient name from transfer_money text.
    Looks for patterns like "لـX", "إلى X", "الى X", "لحساب X", "ارسل لـ X".
    """
    # Pattern priority: "لحساب X", "إلى X", "لـ X", "لXname"
    patterns = [
        r"لحساب\s+([؀-ۿa-zA-Z]+(?:\s+[؀-ۿa-zA-Z]+)?)",
        r"(?:إلى|الى)\s+(?:حساب\s+)?([؀-ۿa-zA-Z]+(?:\s+[؀-ۿa-zA-Z]+)?)",
        r"ارسل\s+(?:لـ?|إلى|الى)\s+([؀-ۿa-zA-Z]+(?:\s+[؀-ۿa-zA-Z]+)?)",
        r"حول\s+(?:لـ?|إلى|الى)\s+([؀-ۿa-zA-Z]+(?:\s+[؀-ۿa-zA-Z]+)?)",
        r"أرسل\s+(?:لـ?|إلى|الى)\s+([؀-ۿa-zA-Z]+(?:\s+[؀-ۿa-zA-Z]+)?)",
        r"لـ?([؀-ۿa-zA-Z]{3,}(?:\s+[؀-ۿa-zA-Z]{3,})?)",
    ]
    for patt in patterns:
        m = re.search(patt, text)
        if m:
            name = m.group(1).strip()
            # Filter out stopwords and non-name phrases
            first_tok = name.split()[0] if name else ""
            if first_tok.lower() in {norm_text(s) for s in NAME_STOPWORDS}:
                continue
            # Stop at interfering words
            name = STOP_AFTER_NAME.split(name)[0].strip()
            # Remove relational words at start ("أخويا", "صديقي", "أخي")
            # → ONLY remove if it's purely a relation word followed by a name
            rel_m = re.match(
                r"(?:أخي|اخي|أخويا|أخوي|صديقي|اخ|اختي|أختي|خويا|ابني|ابنتي|والدي|أمي)\s+([؀-ۿa-zA-Z]+.*)",
                name
            )
            if rel_m:
                name = rel_m.group(1).strip()
            if name and len(name) >= 2:
                return name
    return None


# ── search_medications: medication name extraction ───────────────────────────
def extract_medication_name(text: str, known_meds: dict[str, str]) -> str | None:
    """
    Extract medication name from text.
    Tries "دواء X" first, then scans for known medication names.
    """
    # 1. "دواء X" or "دواء للX"
    m = re.search(r"دواء\s+([؀-ۿa-zA-Z0-9\s]+?)(?=[،,\.\n!؟\?]|$|في\s|متوفر)", text)
    if m:
        raw = m.group(1).strip()
        # Check gazetteer
        nr = norm_text(raw)
        if nr in known_meds:
            return known_meds[nr]
        # Return cleaned verbatim
        raw = re.sub(r"\s+(?:في|من|متوفر|بجميع|بصيدلي).*$", "", raw).strip()
        if raw:
            return raw

    # 2. "كريم/حبوب/أقراص X"
    m2 = re.search(r"(?:كريم|حبوب|أقراص|أمبولات|شراب|محلول)\s+([؀-ۿa-zA-Z0-9]+)", text)
    if m2:
        raw = m2.group(1).strip()
        nr = norm_text(raw)
        if nr in known_meds:
            return known_meds[nr]
        return raw

    # 3. "إسمه/اسمه X"
    m3 = re.search(r"(?:إسمه|اسمه|اسمها|إسمها)\s+([؀-ۿa-zA-Z0-9]+)", text)
    if m3:
        raw = m3.group(1).strip()
        nr = norm_text(raw)
        if nr in known_meds:
            return known_meds[nr]
        return raw

    # 4. Scan for known medication names in text
    nt = norm_text(text)
    for nr, canon in sorted(known_meds.items(), key=lambda x: -len(x[0])):
        if nr in nt:
            return canon

    return None


# ── compare_prices: product name extraction ──────────────────────────────────
def extract_product_name(text: str) -> str | None:
    """
    Extract product name from compare_prices text.
    Returns the text-verbatim mention, preserving original digits and script.
    """
    # Remove known non-product phrases
    t = text
    # Common patterns: "سعر X في Y", "أسعار X في Y/بين Y وZ", "قارن X في Y"
    patterns = [
        r"(?:وش|إيه|كيف|ما|شنو)\s+(?:هو\s+)?سعر\s+([؀-ۿa-zA-Z0-9\s]+?)(?=في\s|بـ|$|[،,\.])",
        r"أسعار\s+([؀-ۿa-zA-Z0-9\s]+?)(?=\s+(?:بين|في|ب)|$|[،,\.])",
        r"قارن(?:ت|ي)?\s+أسعار\s+([؀-ۿa-zA-Z0-9\s]+?)(?=\s+(?:بين|في)|$|[،,\.])",
        r"قارن\s+([؀-ۿa-zA-Z0-9\s]+?)(?=\s+(?:في|بين)|$|[،,\.])",
        r"مقارنة\s+أسعار\s+([؀-ۿa-zA-Z0-9\s]+?)(?=\s+(?:في|بين)|$|[،,\.])",
        r"سعر\s+([؀-ۿa-zA-Z0-9\s]+?)(?=\s+(?:في|ب)|$|[،,\.])",
        r"أسعار\s+([؀-ۿa-zA-Z0-9\s]+?)(?=\s+في|$|[،,\.])",
    ]

    for patt in patterns:
        m = re.search(patt, text)
        if m:
            raw = m.group(1).strip()
            # Remove trailing country/city mentions
            raw = re.sub(r"\s+(?:في\s+\S+|بين\s+\S+|والسعودية|ومصر|والأردن).*$", "", raw).strip()
            raw = raw.strip("،,. ")
            if raw and len(raw) > 1:
                return raw

    return None


# ── calculate_customs: category extraction ───────────────────────────────────
# Map to remove "جهاز" prefix in some cases
CUSTOMS_STRIP_PREFIX = re.compile(r"^جهاز\s+")
CUSTOMS_STRIP_AL = re.compile(r"^ال")

CUSTOMS_ALIASES: list[tuple[str, str]] = [
    ("كمبيوتر محمول",       "كمبيوتر محمول"),
    ("حاسوب محمول",        "كمبيوتر محمول"),
    ("لاب توب",            "لابتوب"),
    ("لابتوب",             "لابتوب"),
    ("laptop",             "laptop"),
    ("كاميرا",             "كاميرا"),
    ("camera",             "camera"),
    ("ساعة يد",            "ساعة يد"),
    ("ساعة ذكية",          "ساعة ذكية"),
    ("موبايل",             "موبايل"),
    ("جوال",               "جوال"),
    ("هاتف",               "هاتف"),
    ("تلفزيون",            "تلفزيون"),
    ("تليفزيون",           "تلفزيون"),
    ("تلفاز",              "تلفاز"),
    ("ملابس",              "ملابس"),
    ("إلكترونيات",         "إلكترونيات"),
    ("اكسسوارات",          "اكسسوارات"),
    ("أكسسوارات",          "اكسسوارات"),
    ("حقيبة",              "حقيبة"),
    ("شنطة",               "شنطة"),
]


def normalize_customs_category(text: str, current_cat: str | None) -> str | None:
    """Normalize category: strip جهاز prefix, strip ال, fix alef normalization."""
    if not current_cat:
        return current_cat

    cat = current_cat.strip()
    # Strip "جهاز " prefix for common categories
    stripped = CUSTOMS_STRIP_PREFIX.sub("", cat).strip()
    # Strip leading "ال" for generic categories
    stripped_al = CUSTOMS_STRIP_AL.sub("", stripped).strip()

    # Alias lookup
    for alias, canon in CUSTOMS_ALIASES:
        if norm_text(alias) == norm_text(stripped) or norm_text(alias) == norm_text(stripped_al):
            return canon

    # Direct extraction from text
    t_norm = norm_text(text)
    for alias, canon in sorted(CUSTOMS_ALIASES, key=lambda x: -len(x[0])):
        if norm_text(alias) in t_norm:
            return canon

    # Return stripped version as fallback
    return stripped_al if stripped_al != stripped else stripped


# ── check_insurance: procedure + insurance_number extraction ─────────────────
def extract_insurance_number(text: str) -> str | None:
    """Re-extract insurance number from text."""
    # Look for number after "رقم" or "رقمي" or "رقمها"
    t = ar2w(text)
    m = re.search(r"(?:رقم(?:ي|ها|ه|التأمين)?|number)\s*(?:هو\s*)?(\d{4,})", t, re.IGNORECASE)
    if m:
        return m.group(1)
    # Standalone long number
    numbers = re.findall(r"\d{4,}", t)
    if numbers:
        return max(numbers, key=len)
    return None


def extract_procedure_from_text(text: str, known_procedures: dict[str, str]) -> str | None:
    """
    Extract medical procedure from text verbatim.
    Uses direct text substring matching.
    """
    # "يغطي/تغطي X" patterns
    m = re.search(
        r"(?:يغطي|تغطي|يغطى|تغطى|تغطية|لتغطية)\s+(?:التأمين\s+)?(.+?)(?=\?|؟|$|\.|،)",
        text
    )
    if m:
        proc = m.group(1).strip()
        proc = re.sub(r"^\s*(?:إجراء|عملية)\s+", "", proc)
        # Check if known
        nr = norm_text(proc)
        if nr in known_procedures:
            return known_procedures[nr]
        # Strip "عملية " if it yields a known form
        stripped = re.sub(r"^عملية\s+", "", proc).strip()
        nrs = norm_text(stripped)
        if nrs in known_procedures:
            return known_procedures[nrs]
        # Return verbatim if reasonable length
        if 3 < len(proc) < 50:
            return proc

    # "X التأمين ... يغطي" (question form)
    m2 = re.search(r"التأمين\s+\S+\s+(?:يغطي|تغطي)\s+(.+?)(?=\?|؟|$)", text)
    if m2:
        proc = m2.group(1).strip()
        if proc and len(proc) > 3:
            return proc

    # Scan known procedures
    nt = norm_text(text)
    for nr, canon in sorted(known_procedures.items(), key=lambda x: -len(x[0])):
        if nr in nt:
            return canon

    return None


# ── search_umrah_packages: city normalization ────────────────────────────────
def normalize_departure_city(city: str, city_gazetteer: dict[str, str]) -> str:
    """Normalise via city gazetteer."""
    if not city:
        return city
    nr = norm_text(city)
    return city_gazetteer.get(nr, city)


# ── Gazetteer loader ────────────────────────────────────────────────────────
def load_gazetteers(schema_report_path: Path | None = None) -> dict[str, dict[str, str]]:
    """
    Load gazetteers from schema miner JSON report, or build minimal fallbacks.
    """
    gz: dict[str, dict[str, str]] = {
        "restaurants": {}, "cities": {},
        "specialties": {}, "medications": {},
        "customs_categories": {}, "procedures": {},
    }

    if schema_report_path and schema_report_path.exists():
        with schema_report_path.open(encoding="utf-8") as f:
            report = json.load(f)
        gz_raw = report.get("_gazetteers", {})
        gz["restaurants"] = gz_raw.get("restaurants", {})
        gz["cities"] = gz_raw.get("cities", {})
        gz["specialties"] = gz_raw.get("specialties", {})
        gz["medications"] = gz_raw.get("medications", {})
        gz["customs_categories"] = gz_raw.get("customs_categories", {})

        # Build procedure gazetteer from check_insurance_coverage
        procs = report.get("check_insurance_coverage", {}).get("procedure", {})
        gz["procedures"] = {
            norm_text(p): p for p in procs.keys() if p
        }

    return gz
