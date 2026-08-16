"""
NABIQ v5 - High-precision tool-specific argument extractors.
Safety: keep v4 unless clear text evidence + high confidence.
"""
import re
import sys
from pathlib import Path
from typing import Optional, Dict

sys.path.insert(0, str(Path(__file__).parent))
from nabiq_v5_gulf_fixes import arabic_to_western, canonicalize_city, text_has_date_expression

# ── ORDER_FOOD items extractor ────────────────────────────────────────────────
_ITEMS_CMD_PREFIX_PATTERNS = [
    r'^أن\s+(أطلب|اطلب)\s+(طعام|أكل|أكلة|وجبة\s+\w+)?\s*(يشمل|وهو|وهي)?\s*',
    r'^(بغيت|ابغى|أبغى)\s+(اطلب|أطلب)\s+(أكل|طعام|أكلة)?\s*[،,.]?\s*(جيب\s+لي|اطلب\s+لي|أطلب\s+لي)?\s*',
    r'^(أطلب|اطلب)\s+(أكل|طعام|أكلة)\s*[،,.]\s*\w+\s+بتكون\s+',
    r'^(أطلب|اطلب)\s+(أكل|طعام|أكلة)\s*[،,.\s]+\s*(عايز|ودي|ابي|أبي|ابغى|أبغى)\s+',
    r'^(أطلب|اطلب)\s+(أكل|طعام|أكلة)\s*[،,.]\s*(أقدر|بقدر)\s+\w+\s+',
    r'^(أطلب|اطلب)\s+(أكل|طعام|أكلة|وجبة\s+غداء|وجبة\s+\w+)\s*[،,\.]\s+',
    r'^طلب\s+(وجبة|أكل|طعام)\s+\w+\s*[،,]\s*(أضف|أضف\s+لي)?\s*',
    r'^اطلب\s*[،,]\s*(ابغى|أبغى|ابي|أبي|عايز|ودي)\s+',
    r'^(أطلب|اطلب)\s+(?!(أكل|طعام|أكلة|وجبة|لي|لنا))',
    r'^(محتاج|عايز|أريد|أود|ودي)\s+(أطلب|اطلب|أن\s+أطلب)\s+(أكل|طعام|أكلة)?\s*[،,.]?\s*',
    r'^طلب\s+(?!\d)',
    r'^(لي|لنا)\s+',
]

_NUMERAL_STARTS = re.compile(
    r'^[٠-٩0-9]|^(اثنين|ثلاثة|أربعة|خمسة|ستة|سبعة|ثمانية|تسعة|عشرة|'
    r'واحد|وحدة|نص|نصف|ربع|كيلو|حبة|طبق|صحن|قطعة|وجبة)'
)

def _strip_items_prefix(items: str):
    s = items.strip()
    for pat in _ITEMS_CMD_PREFIX_PATTERNS:
        m = re.match(pat, s)
        if m and m.end() < len(s):
            return s[m.end():].strip(), True
    return s, False

def _split_items(items: str) -> str:
    if _NUMERAL_STARTS.match(items):
        return items
    parts = re.split(r'[،,]\s*|\s+و\s*', items)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return items
    if len(parts) == 1:
        return parts[0]
    if any(len(p) < 2 for p in parts):
        return items
    return ', '.join(parts)

def fix_order_food_items(v4_items: str, text: str) -> Optional[str]:
    if not v4_items:
        return None
    stripped, had_prefix = _strip_items_prefix(v4_items)
    if not had_prefix:
        return None
    result = _split_items(stripped)
    if result == v4_items or not result or len(result) > len(v4_items):
        return None
    return result

# ── BOOK_DOCTOR_APPOINTMENT ───────────────────────────────────────────────────
def fix_book_doctor_args(v4_args: Dict, text: str) -> Optional[Dict]:
    args = dict(v4_args)
    changed = False

    # Fix 1: remove spurious date (text has NO date expression)
    if 'date' in args and not text_has_date_expression(text):
        del args['date']
        changed = True

    # Fix 2: الأسبوع الجاي → next week
    if 'date' in args:
        dv = args['date']
        if dv in ('الأسبوع الجاي', 'الاسبوع الجاي', 'الأسبوع المقبل'):
            if re.search(r'الأسبوع\s+الجاي|الاسبوع\s+الجاي|الأسبوع\s+المقبل', text):
                args['date'] = 'next week'
                changed = True

    # Fix 3 removed: "the day after tomorrow" -> "after tomorrow" is inconsistent in gold

    # Fix 4: بعد باجر (Gulf tomorrow-after)
    if 'date' in args and re.search(r'بعد\s+باجر', text):
        if args['date'] != 'بعد باجر':
            args['date'] = 'بعد باجر'
            changed = True

    # Fix 5: city hamza normalization
    if 'city' in args:
        c = canonicalize_city(args['city'])
        if c != args['city']:
            args['city'] = c
            changed = True

    return args if changed else None

# ── TRANSFER_MONEY ────────────────────────────────────────────────────────────
def fix_transfer_money_args(v4_args: Dict, text: str) -> Optional[Dict]:
    """
    ONLY safe fix: AED -> درهم when text says 'درهم' (not 'درهم مغربي').
    All other currencies (SAR, BHD, EGP, etc.) use ISO in gold even when
    Arabic form appears in text — converting causes regressions.
    """
    args = dict(v4_args)
    if args.get('currency') == 'AED':
        if re.search(r'درهم', text) and not re.search(r'درهم\s+مغربي', text):
            args['currency'] = 'درهم'
            return args
    return None

# ── SEARCH_HOTELS ─────────────────────────────────────────────────────────────
def fix_search_hotels_args(v4_args: Dict, text: str) -> Optional[Dict]:
    args = dict(v4_args)
    if 'city' in args:
        c = canonicalize_city(args['city'])
        if c != args['city']:
            args['city'] = c
            return args
    return None

# ── DISPATCH ──────────────────────────────────────────────────────────────────
def apply_v5_fixes(tool: str, v4_args: Dict, text: str) -> Optional[Dict]:
    if tool == 'order_food':
        items = v4_args.get('items')
        if items:
            new_items = fix_order_food_items(items, text)
            if new_items and new_items != items:
                new_args = dict(v4_args)
                new_args['items'] = new_items
                return new_args
        return None
    elif tool == 'book_doctor_appointment':
        return fix_book_doctor_args(v4_args, text)
    elif tool == 'transfer_money':
        return fix_transfer_money_args(v4_args, text)
    elif tool == 'search_hotels':
        return fix_search_hotels_args(v4_args, text)
    return None

if __name__ == '__main__':
    tests = [
        ('order_food', {'items': 'أطلب أكل ، عايز كباب و2 كفتة', 'restaurant': 'المحروسة'},
         'عايز أطلب أكل من المحروسة، عايز كباب و2 كفتة', 'items', 'كباب, 2 كفتة'),
        ('order_food', {'items': 'شيش طاووق وكوكاكولا', 'restaurant': 'x'},
         'اطلب شيش طاووق وكوكاكولا', 'items', None),  # no prefix -> no change
        ('book_doctor_appointment', {'city': 'جدة', 'specialty': 'أطفال', 'date': 'tomorrow'},
         'ابي احجز موعد عند دكتور أطفال في جدة', 'date', None),  # date removed
        ('book_doctor_appointment', {'city': 'إسكندرية', 'date': 'tomorrow', 'specialty': 'أطفال'},
         'ممكن أحجز موعد مع دكتور أطفال في إسكندرية بكره؟', 'date', 'tomorrow'),  # بكره = date present
        ('book_doctor_appointment', {'city': 'القاهرة', 'date': 'the day after tomorrow', 'specialty': 'عيون'},
         'أريد حجز موعد لزيارة طبيب عيون في القاهرة بعد غد', 'date', 'the day after tomorrow'),  # no change
        ('book_doctor_appointment', {'city': 'المنصورة', 'specialty': 'قلب', 'date': 'الأسبوع الجاي'},
         'ممكن أحجز مع دكتور قلب في المنصورة الأسبوع الجاي', 'date', 'next week'),
        ('transfer_money', {'amount': 2000.0, 'currency': 'SAR', 'recipient_name': 'محمد'},
         'أحول ٢٠٠٠ ريال سعودي لمحمد', 'currency', 'SAR'),  # SAR stays
        ('transfer_money', {'amount': 1000.0, 'currency': 'AED'},
         'أبي أحول ١٠٠٠ درهم لحساب عيسى', 'currency', 'درهم'),  # AED->درهم
        ('search_hotels', {'city': 'الاسكندرية', 'check_in': '2023-10-25'},
         'فندق في الإسكندرية', 'city', 'الإسكندرية'),
    ]
    print('=== V5 Extractor Smoke Tests ===')
    all_pass = True
    for i, (tool, v4_args, text, field, expected) in enumerate(tests):
        result = apply_v5_fixes(tool, v4_args, text)
        if result is None:
            got = v4_args.get(field)  # unchanged
        else:
            got = result.get(field)
        ok = got == expected
        if not ok:
            all_pass = False
        print(f'  [{"✓" if ok else "✗"}] Test {i+1}: got={got!r} expected={expected!r}')
    print(f'\n{"ALL PASS" if all_pass else "SOME FAILED"}')
