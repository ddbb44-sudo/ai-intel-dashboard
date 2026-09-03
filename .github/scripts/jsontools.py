#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""أدوات JSON متسامحة — مفصولة لتُختبر بلا تشغيل خط السحب كاملًا."""
import json


def salvage(text):
    """يستخرج الكائنات المكتملة من JSON مقصوص.

    الدفعة الواحدة عشرون منشورًا؛ فقدانها كلها لأن آخر كائن انقطع خسارةٌ لا
    مبرّر لها. نمسح الأقواس ونأخذ ما أُغلق منها فقط.
    """
    out, depth, start, instr, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if instr:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': instr = False
            continue
        if ch == '"': instr = True
        elif ch == "{":
            if depth == 0: start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try: out.append(json.loads(text[start:i+1]))
                except Exception: pass
                start = None
    return [o for o in out if isinstance(o, dict) and o.get("id")]
