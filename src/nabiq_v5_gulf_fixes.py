"""
NABIQ v5 - Gulf dialect phrase maps and extraction cues.
"""
import re

CITY_CANONICAL = {
    'الاسكندرية': 'الإسكندرية',
    'اسكندرية': 'إسكندرية',
    'الاسكندريه': 'الإسكندرية',
}

def canonicalize_city(city: str) -> str:
    return CITY_CANONICAL.get(city.strip(), city)

def arabic_to_western(s: str) -> str:
    d = {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9',
         '٠':'0','١':'1','٢':'2','٣':'3','٤':'4',
         '٥':'5','٦':'6','٧':'7','٨':'8','٩':'9'}
    return ''.join(d.get(c,c) for c in s)

RELATIVE_DATE_AR_TO_EN = {
    'الأسبوع الجاي': 'next week',
    'الأسبوع المقبل': 'next week',
}

DATE_EXPRESSION_PATTERNS = [
    r'\b(الجمعة|السبت|الأحد|الاثنين|الإثنين|الثلاثاء|الأربعاء|الخميس)\b',
    r'\b(Friday|Saturday|Sunday|Monday|Tuesday|Wednesday|Thursday)\b',
    r'\b(غد[اً]?|غدًا|بكر[ةاه]|باجر|اليوم|النهارد[هة]|هذا\s+الشهر|هذه\s+الأسبوع)\b',
    r'\bبعد\s+(غد[اً]?|غدًا|بكر[ةاه]|باجر)\b',
    r'\b(الأسبوع|الاسبوع)\s+(الجاي|القادم|المقبل|الجاية)\b',
    r'\b(next|this)\s+(week|month|year)\b',
    r'\btomorrow\b', r'\btoday\b',
    r'\bafter\s+tomorrow\b',
    r'\b(يناير|فبراير|مارس|أبريل|ابريل|مايو|يونيو|يوليو|أغسطس|اغسطس|سبتمبر|أكتوبر|اكتوبر|نوفمبر|ديسمبر)\b',
    r'[٠-٩0-9]+\s*(أكتوبر|نوفمبر|ديسمبر|يناير|فبراير|مارس|مايو)',
    r'\b\d{4}-\d{2}-\d{2}\b',
    r'\b(يوم|نهار)\s+\w+',
    r'\b(الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر)\b',
    r'\bهذا\s+(الأسبوع|الشهر)\b',
]

NO_DATE_NEGATION = [
    r'دون\s+تحديد\s+تاريخ',
    r'بدون\s+تحديد\s+تاريخ',
]

def text_has_date_expression(text: str) -> bool:
    for pat in NO_DATE_NEGATION:
        if re.search(pat, text):
            return False
    for pat in DATE_EXPRESSION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False
