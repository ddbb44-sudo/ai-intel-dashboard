#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
«أضفتها بنفسي» = الروابط التي ألصقها عزيز فقط.

كان الفلتر يعتبر أي قيمة في added_via إضافةً يدوية، فبطاقات السحب التاريخي
(added_via = "backfill") كانت ستدخل القسم وتحمل شارة «مضافة يدويًا» — وهي ليست
كذلك: الحساب أُضيف يدويًا، أما بطاقاته فجاءت من سحب آلي.

نجعل الشرط صريحًا على 'issue' ولا نمحو قيمة 'backfill' من البيانات:
إخفاء المعلومة من الواجهة أنظف من محوها من المصدر.

آمن للتكرار؛ يتوقف دون تغيير إن لم يطابق الملف المتوقع.
"""
import sys

P = "app.js"
src = open(P, encoding="utf-8").read()

if "added_via !== 'issue'" in src:
    print("app.js: الفلتر مُصلَح مسبقًا — تخطٍّ")
    sys.exit(0)

PAIRS = [
    # ١) الفلتر
    ("      if (F.pref.includes('mine') && !i.added_via) return false;",
     "      if (F.pref.includes('mine') && i.added_via !== 'issue') return false;"),
    # ٢) الشارة على البطاقة
    ("""${i.added_via?' <span class="mine" title="أضفتها بنفسك">مضافة يدويًا</span>':''}""",
     """${i.added_via==='issue'?' <span class="mine" title="أضفتها بنفسك">مضافة يدويًا</span>':''}"""),
]

for n, (old, new) in enumerate(PAIRS, 1):
    c = src.count(old)
    if c != 1:
        print("توقّف: الموضع %d وُجد %d مرة (المتوقع 1) — لم أغيّر شيئًا." % (n, c))
        sys.exit(1)
    src = src.replace(old, new)

open(P, "w", encoding="utf-8").write(src)
print("app.js: «أضفتها بنفسي» صار للروابط الملصوقة فقط (موضعان)")
