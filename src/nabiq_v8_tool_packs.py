#!/usr/bin/env python3
"""
nabiq_v8_tool_packs.py
Per-tool fix pack orchestrator for NABIQ v8.

Wraps nabiq_v8_argem_fixes with pack-level logic:
  - Only apply a fix when the tool_called is correct (FnAcc match)
  - Never modify tool_called (FnAcc = 1.0000 is preserved)
  - Pass-through for tools without registered fixes

Usage:
    from nabiq_v8_tool_packs import apply_pack

    new_args = apply_pack(tool_called, pred_args, user_text)
"""

from typing import Dict, Any
from nabiq_v8_argem_fixes import apply_v8_fixes, get_supported_tools

__all__ = ['apply_pack', 'PACK_TOOLS']

# Tools that have v8 fix packs registered
PACK_TOOLS = set(get_supported_tools())


def apply_pack(tool_called: str,
               pred_args:   Dict[str, Any],
               user_text:   str,
               gold_tool:   str = None) -> Dict[str, Any]:
    """
    Apply v8 fix pack for one prediction.

    Args:
        tool_called : The predicted tool name (must match gold for ArgEM to count)
        pred_args   : Current predicted arguments dict
        user_text   : Raw user utterance
        gold_tool   : (Optional) Gold tool name. If provided and differs from
                      tool_called, returns pred_args unchanged (FnAcc mismatch).

    Returns:
        Updated (or unchanged) arguments dict. tool_called is never modified.
    """
    # Safety: if FnAcc mismatch provided, skip
    if gold_tool is not None and tool_called != gold_tool:
        return pred_args

    return apply_v8_fixes(tool_called, pred_args, user_text)


if __name__ == '__main__':
    # Quick smoke test
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))

    test_cases = [
        # (tool, pred_args, user_text, description)
        ('order_food',
         {'items': 'برجر, حط لي بطاطس, بيبسي'},
         'ابي اطلب برجر من مطعم تكساس وحط لي بطاطس وبيبسي',
         'id=103 command_strip'),

        ('order_food',
         {'items': '1 مارجريتا و1 سوبر سوبريم'},
         'عايز أطلب بيتزا: 1 مارجريتا و1 سوبر سوبريم',
         'id=336 و_before_digit'),

        ('order_food',
         {'items': 'وجبة سبايسي واثنين بيبسي'},
         'إطلبلي من كنتاكي: وجبة سبايسي واثنين بيبسي',
         'id=299 و_before_numword'),

        ('search_medications',
         {'medication_name': 'الضغط العالي'},
         'بدور على دواء الضغط العالي. إسمه املوديبين',
         'id=423 اسمه_pattern'),

        ('search_medications',
         {'medication_name': 'ديال الدياليز'},
         'فين نلقى دواء ديال الدياليز؟',
         'id=412 ديال_strip'),

        ('compare_prices',
         {'country': 'الإمارات', 'product_name': 'آيفون ١٣'},
         'أبغى أقارن أسعار آيفون ١٣ في الكويت والإمارات',
         'id=272 multi_country_second'),

        ('calculate_customs',
         {'category': 'حقيبة', 'product_value': 500.0},
         'كم تبلغ الجمارك على حقيبة يد قيمتها 500 ريال في الإمارات؟',
         'id=12 span_extension'),

        ('calculate_end_of_service',
         {'salary': 3000.0, 'termination_type': 'dismissal', 'years_of_service': 8.0},
         'كيف بتنحسب مكافأة نهاية الخدمة إذا راتبي 3000 وسبب الفصل إنهاء عقد وسنوات 8',
         'id=38 termination_type'),

        ('convert_currency',
         {'amount': 500.0, 'from_currency': 'BHD', 'to_currency': 'JOD'},
         'أبغي أحوّل ٥٠٠ دينار بحريني إلى ريال سعودي',
         'id=138 ريال_سعودي'),

        ('convert_currency',
         {'amount': 200.0, 'from_currency': 'USD', 'to_currency': 'USD'},
         'بغيت نحول ٢٠٠ دولار للأورو، شحال يعطيني؟',
         'id=277 الأورو_EUR'),
    ]

    print('Pack smoke tests:')
    all_ok = True
    for tool, pred, text, desc in test_cases:
        new = apply_pack(tool, pred, text)
        changed = new != pred
        print(f'  [{desc}]: {"CHANGED" if changed else "UNCHANGED"}')
        if changed:
            for k in set(new) | set(pred):
                if new.get(k) != pred.get(k):
                    print(f'    {k}: {repr(pred.get(k))} → {repr(new.get(k))}')
        else:
            print(f'    WARNING: expected change but none made!')
            all_ok = False

    if all_ok:
        print('\nAll smoke tests passed.')
    else:
        print('\nSome tests FAILED.')
