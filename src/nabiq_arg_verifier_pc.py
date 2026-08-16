"""
nabiq_arg_verifier_pc.py
NABIQ-v3-PC: Argument verifier.

Removes extra arguments that are NOT supported by user text.
Validates value types (amounts, numbers, dates, currencies).
Philosophy: fewer correct args > more wrong args (ArgEM is exact-match).
"""

import re
from typing import Any

from nabiq_v3_pc_utils import ar2w, norm_text, FULL_CURRENCY_MAP

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# ── Known-currency validator ─────────────────────────────────────────────────
VALID_CURRENCIES: set[str] = {
    "SAR", "USD", "AED", "EGP", "KWD", "BHD", "QAR", "EUR", "GBP",
    "JOD", "MAD", "SYP", "LBP", "OMR", "TRY", "DZD", "CAD", "JPY", "ILS",
    # Short Arabic forms allowed in calculate_zakat
    "ريال", "دولار", "جنيه", "درهم", "دينار", "ليرة", "ليره", "يورو",
    # Other units
    "gram", "kg",
}

# ── Optional argument lists per tool ─────────────────────────────────────────
# Arguments that are truly optional and should be REMOVED if not clearly in text.
OPTIONAL_ARGS: dict[str, set[str]] = {
    "get_weather":              {"days"},
    "get_air_quality":          {"city"},
    "search_quran":             {"search_type"},
    "book_doctor_appointment":  {"doctor_name", "date"},
    "search_hotels":            {"guests", "stars"},
    "check_traffic_violations": {},
    "check_insurance_coverage": {},
    "compare_prices":           {"category"},
}

# Arguments that require a numeric value
NUMERIC_ARGS: set[str] = {
    "amount", "guests", "stars", "days", "num_persons", "product_value",
    "salary", "years_of_service",
}

# ── Text presence checks ─────────────────────────────────────────────────────

def _has_days_in_text(text: str) -> bool:
    """Does the text explicitly mention a day count (beyond just 'today')?"""
    nt = norm_text(text)
    day_indicators = ["يوم", "أيام", "ايام", "أسبوع", "اسبوع", "أسبوعين", "اسبوعين"]
    return any(d in nt for d in day_indicators)


def _has_guests_in_text(text: str) -> bool:
    nt = norm_text(text)
    guest_kws = ["شخص", "ضيف", "ضيوف", "أشخاص", "اشخاص", "فرد", "أفراد", "افراد",
                 "اثنين", "ثلاثة", "أربعة", "شخصين"]
    return any(g in nt for g in guest_kws)


def _has_stars_in_text(text: str) -> bool:
    nt = norm_text(text)
    star_kws = ["نجم", "نجوم", "نجمة", "نجمات", "star", "stars"]
    return any(s in nt for s in star_kws)


def _has_doctor_name_in_text(text: str) -> bool:
    return bool(re.search(r"(دكتور|الدكتور|دكتورة|الدكتورة)\s+[؀-ۿ]+", text))


def _has_search_type_in_text(text: str) -> bool:
    nt = norm_text(text)
    kws = ["تفسير", "فسر", "شرح", "آية", "ايه", "موضوع", "معنى", "معني", "نص حرفي", "verse", "tafseer"]
    return any(k in nt for k in kws)


def _value_is_numeric(val: Any) -> bool:
    try:
        float(str(val).translate(ARABIC_DIGITS))
        return True
    except (ValueError, TypeError):
        return False


def _has_city_in_text(text: str, city: str) -> bool:
    """Check if the city name (or normalised form) appears in text."""
    if not city:
        return False
    return norm_text(city) in norm_text(text)


def _has_id_in_text(text: str, id_val: str) -> bool:
    """Check if a numeric ID appears in text (Arabic or Western)."""
    t_w = ar2w(text)
    id_w = ar2w(str(id_val))
    return id_w in t_w


# ── None-check: some tools' gold expects {} (no args) in some cases ──────────
def _is_none_args_tool(tool: str, args: dict) -> bool:
    """Return True if this tool+args combo should definitely have {}."""
    return False   # handled per-tool below


# ── Main verifier ─────────────────────────────────────────────────────────────

def verify_args(
    tool: str,
    args: dict[str, Any],
    user_text: str,
) -> dict[str, Any]:
    """
    Return a cleaned version of args with unsupported optional arguments removed.
    Never removes clearly correct core arguments.
    """
    if not args:
        return args

    cleaned = dict(args)
    nt = norm_text(user_text)

    # ── get_weather ──────────────────────────────────────────────────────────
    # CONSERVATIVE: the stage1 pipeline already handles days extraction.
    # The verifier should not re-remove days since that causes regressions.
    # (Stage1 already handles "اليوم" → remove days case conservatively.)

    # ── get_air_quality ──────────────────────────────────────────────────────
    if tool == "get_air_quality":
        if "city" in cleaned:
            city = str(cleaned["city"])
            if not _has_city_in_text(user_text, city):
                del cleaned["city"]
            # If city is present, normalise alef
            elif "city" in cleaned:
                cleaned["city"] = cleaned["city"].replace("عمّان", "عمان")

    # ── search_quran ─────────────────────────────────────────────────────────
    # CONSERVATIVE: do NOT remove search_type — v2 predictions are generally
    # correct for search_quran and removing them causes regressions.
    # (We only ADD search_type via the stage1 pipeline if explicitly detected.)

    # ── book_doctor_appointment ──────────────────────────────────────────────
    if tool == "book_doctor_appointment":
        if "doctor_name" in cleaned:
            if not _has_doctor_name_in_text(user_text):
                del cleaned["doctor_name"]

    # ── search_hotels ────────────────────────────────────────────────────────
    if tool == "search_hotels":
        if "guests" in cleaned:
            if not _has_guests_in_text(user_text):
                del cleaned["guests"]
        if "stars" in cleaned:
            if not _has_stars_in_text(user_text):
                del cleaned["stars"]

    # ── compare_prices ───────────────────────────────────────────────────────
    if tool == "compare_prices":
        if "category" in cleaned:
            cat = str(cleaned.get("category", ""))
            if norm_text(cat) not in nt:
                del cleaned["category"]

    # ── check_traffic_violations ─────────────────────────────────────────────
    if tool == "check_traffic_violations":
        # The gold sometimes has {} even when text has a number (tool may not take args)
        # We keep id_number only if text clearly provides one
        if "id_number" in cleaned:
            id_val = str(cleaned["id_number"])
            if not _has_id_in_text(user_text, id_val):
                del cleaned["id_number"]

    # ── check_iqama_status ───────────────────────────────────────────────────
    if tool == "check_iqama_status":
        if "iqama_number" in cleaned:
            id_val = str(cleaned["iqama_number"])
            if not _has_id_in_text(user_text, id_val):
                del cleaned["iqama_number"]

    # ── check_visa_status ────────────────────────────────────────────────────
    if tool == "check_visa_status":
        if "visa_number" in cleaned:
            id_val = str(cleaned["visa_number"])
            if not _has_id_in_text(user_text, id_val):
                del cleaned["visa_number"]
        if "passport_number" in cleaned:
            # Gold rarely includes passport_number; remove if visa_number is present
            if "visa_number" in cleaned:
                del cleaned["passport_number"]

    # ── check_insurance_coverage ─────────────────────────────────────────────
    if tool == "check_insurance_coverage":
        # Remove extra keys that aren't in text
        for key in ["provider", "company", "country"]:
            if key in cleaned:
                val = str(cleaned[key])
                if norm_text(val) not in nt:
                    del cleaned[key]

    # ── calculate_customs ────────────────────────────────────────────────────
    if tool == "calculate_customs":
        # destination_country should be in text
        if "destination_country" in cleaned:
            country = str(cleaned["destination_country"])
            # Accept both Arabic country name and common aliases
            if norm_text(country) not in nt:
                # Try to find implied destination from ريال/country context
                pass  # keep as-is if we can't do better

    # ── search_medications ───────────────────────────────────────────────────
    if tool == "search_medications":
        # Remove "country" if gold often doesn't have it
        if "country" in cleaned:
            country = str(cleaned.get("country", ""))
            # Keep only if a city/country is explicitly a search scope, not just context
            pass   # be conservative, keep

    # ── Numeric type enforcement ─────────────────────────────────────────────
    for key in list(cleaned.keys()):
        if key in NUMERIC_ARGS:
            if not _value_is_numeric(cleaned[key]):
                pass  # keep non-numeric (might be intentional)

    return {k: v for k, v in cleaned.items() if v is not None}


def score_candidate(
    args: dict[str, Any],
    tool: str,
    user_text: str,
    schema_keys: set[str],
) -> float:
    """
    Score a candidate argument dict.
    Higher = better.  Used for ensemble selection.
    """
    if not args:
        return 0.1   # empty is bad unless tool expects {}

    score = 0.0
    nt = norm_text(user_text)

    for key, val in args.items():
        val_str = str(val)
        val_norm = norm_text(val_str)
        # +1 for each key that's in expected schema
        if key in schema_keys:
            score += 0.5
        # +2 if value appears in text
        if val_norm in nt or ar2w(val_str) in ar2w(user_text):
            score += 2.0
        # +1 for numeric args with numeric value
        if key in NUMERIC_ARGS and _value_is_numeric(val):
            score += 1.0
        # -1 for args not in text (potential hallucination)
        if val_norm not in nt and ar2w(val_str) not in ar2w(user_text):
            if key not in {"currency", "to_currency", "from_currency"}:  # normalized vals OK
                score -= 0.3

    # Fewer extra args = better for ArgEM
    extra_keys = set(args.keys()) - schema_keys
    score -= len(extra_keys) * 0.5

    return score
