"""
normalization_maps_v2_pc.py
Canonical-form lookup tables derived from data/processed_latest/train_processed.jsonl.

Rules:
- Currency codes: ISO-3 (SAR, USD, AED, EGP, KWD, BHD, QAR, EUR, GBP, JOD, MAD, SYP, LBP, OMR, TRY, DZD)
- Language codes: ISO-2 (en, fr, es, de, it, ar, zh, ja, tr, ko, fa)
- Zakat types: English (cash, gold, silver, trade, fitr, crops, salary, livestock)
- Termination types: English (resignation, dismissal, end_of_contract, unfair_dismissal,
                               retirement, disciplinary, economic, mutual_consent)
- Search Quran types: English (verse, tafseer, topic, meaning, exact, word, any)
- Country names: Arabic (مصر, الإمارات, السعودية, الكويت, الأردن, قطر, ...)
"""

# ── Currency → ISO-3 ───────────────────────────────────────────────────────────
# Each entry: (canonical_ISO, [alias_substrings_lowercased_normalised])
# Ordered longest alias first so we don't partially match short words.
CURRENCY_TO_ISO: list[tuple[str, list[str]]] = [
    ("SAR", ["sar", "ريال سعودي", "riyal", "ر.س"]),
    ("USD", ["usd", "دولار أمريكي", "دولار امريكي", "الدولار الأمريكي", "dollar"]),
    ("AED", ["aed", "درهم إماراتي", "درهم اماراتي", "الدرهم الاماراتي"]),
    ("EGP", ["egp", "جنيه مصري", "الجنيه المصري"]),
    ("KWD", ["kwd", "دينار كويتي"]),
    ("BHD", ["bhd", "دينار بحريني"]),
    ("QAR", ["qar", "ريال قطري"]),
    ("EUR", ["eur", "يورو", "euro", "€"]),
    ("GBP", ["gbp", "جنيه إسترليني", "جنيه استرليني", "sterling"]),
    ("JOD", ["jod", "دينار أردني", "دينار اردني"]),
    ("MAD", ["mad", "درهم مغربي"]),
    ("SYP", ["syp", "ليرة سورية", "ليره سوريه"]),
    ("LBP", ["lbp", "ليرة لبنانية", "ليره لبنانيه"]),
    ("OMR", ["omr", "ريال عماني"]),
    ("TRY", ["try", "ليرة تركية", "ليره تركيه"]),
    ("DZD", ["dzd", "دينار جزائري"]),
    ("CAD", ["cad", "دولار كندي"]),
    ("JPY", ["jpy", "ين ياباني"]),
    ("ILS", ["ils", "شيكل", "شيقل"]),
    # Short/ambiguous forms — only if nothing more specific matched
    ("SAR", ["ريال"]),
    ("USD", ["دولار"]),
    ("AED", ["درهم"]),
    ("EGP", ["جنيه"]),
    ("JOD", ["دينار"]),
    ("SYP", ["ليرة", "ليره"]),
]

# ── Language → ISO-2 ───────────────────────────────────────────────────────────
LANGUAGE_TO_ISO: list[tuple[str, list[str]]] = [
    ("en", ["english", "انجليزي", "إنجليزي", "انجليزية", "إنجليزية", "للإنجليزية", "للانجليزية", " en "]),
    ("fr", ["french", "français", "فرنسي", "فرنساوي", "فرنسية", "للفرنسية"]),
    ("es", ["spanish", "español", "اسباني", "إسباني", "اسبانية", "إسبانية"]),
    ("de", ["german", "deutsch", "ألماني", "الماني", "ألمانية", "المانية"]),
    ("it", ["italian", "italiano", "إيطالي", "ايطالي", "إيطالية", "ايطالية"]),
    ("ar", ["arabic", "عربي", "عربية", "للعربية"]),
    ("zh", ["chinese", "mandarin", "صيني", "صينية"]),
    ("ja", ["japanese", "ياباني", "يابانية"]),
    ("tr", ["turkish", "تركي", "تركية"]),
    ("ko", ["korean", "كوري", "كورية"]),
    ("fa", ["persian", "farsi", "فارسي", "فارسية"]),
    ("pt", ["portuguese", "برتغالي", "برتغالية"]),
    ("ru", ["russian", "روسي", "روسية"]),
    ("nl", ["dutch", "هولندي", "هولندية"]),
    ("pl", ["polish", "بولندي", "بولندية"]),
]

# ── Zakat type → English ───────────────────────────────────────────────────────
ZAKAT_TYPE_MAP: list[tuple[str, list[str]]] = [
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

# ── Termination type → English ─────────────────────────────────────────────────
TERMINATION_TYPE_MAP: list[tuple[str, list[str]]] = [
    ("resignation",      ["استقال", "استقالة", "استقاله", "resignation", "بإرادت", "إرادة الموظف", "اراده الموظف"]),
    ("dismissal",        ["فصل", "طرد", "إنهاء خدمات", "dismissal", "terminated", "فصله", "صرفه"]),
    ("end_of_contract",  ["انتهاء عقد", "انهاء عقد", "إنهاء عقد", "end_of_contract", "انتهاء العقد", "انقضاء"]),
    ("unfair_dismissal", ["تعسف", "unfair", "فصل تعسفي"]),
    ("retirement",       ["تقاعد", "retirement", "بلوغ سن التقاعد"]),
    ("disciplinary",     ["تأديب", "disciplinary", "مخالفة", "سوء سلوك"]),
    ("economic",         ["تقليص", "economic", "اقتصادي", "هيكلة", "استغناء"]),
    ("mutual_consent",   ["اتفاق", "تراضي", "mutual", "تفاهم متبادل"]),
]

# ── Search Quran type → English ────────────────────────────────────────────────
QURAN_SEARCH_TYPE_MAP: list[tuple[str, list[str]]] = [
    ("verse",    ["آية", "ايه", "verse"]),
    ("tafseer",  ["تفسير", "فسر", "شرح", "tafseer"]),
    ("topic",    ["موضوع", "topic"]),
    ("meaning",  ["معنى", "معني", "meaning"]),
    ("exact",    ["exact", "نص حرفي"]),
    ("word",     ["كلمة", "word"]),
    ("any",      ["any"]),
]

# ── Country name → Arabic ──────────────────────────────────────────────────────
COUNTRY_TO_ARABIC: list[tuple[str, list[str]]] = [
    ("مصر",          ["egypt", "مصر"]),
    ("الإمارات",     ["uae", "united arab emirates", "emirates", "الإمارات", "الامارات"]),
    ("السعودية",     ["saudi", "ksa", "السعودية", "المملكة العربية السعودية"]),
    ("الكويت",       ["kuwait", "الكويت"]),
    ("الأردن",       ["jordan", "الأردن", "الاردن"]),
    ("قطر",          ["qatar", "قطر"]),
    ("البحرين",      ["bahrain", "البحرين"]),
    ("لبنان",        ["lebanon", "لبنان"]),
    ("سوريا",        ["syria", "سوريا"]),
    ("المغرب",       ["morocco", "المغرب"]),
    ("تونس",         ["tunisia", "تونس"]),
    ("الجزائر",      ["algeria", "الجزائر"]),
    ("العراق",       ["iraq", "العراق"]),
    ("فلسطين",       ["palestine", "فلسطين"]),
    ("اليمن",        ["yemen", "اليمن"]),
    ("ليبيا",        ["libya", "ليبيا"]),
    ("السودان",      ["sudan", "السودان"]),
    ("عمان",         ["oman", "عُمان", "عمان"]),
    ("تركيا",        ["turkey", "türkiye", "تركيا"]),
    ("أمريكا",       ["america", "usa", "united states", "أمريكا", "امريكا"]),
    ("بريطانيا",     ["uk", "britain", "england", "بريطانيا"]),
    ("ألمانيا",      ["germany", "deutschland", "ألمانيا", "المانيا"]),
    ("فرنسا",        ["france", "فرنسا"]),
    ("الصين",        ["china", "الصين"]),
    ("اليابان",      ["japan", "اليابان"]),
    ("الهند",        ["india", "الهند"]),
    ("باكستان",      ["pakistan", "باكستان"]),
    ("إيران",        ["iran", "إيران", "ايران"]),
]
