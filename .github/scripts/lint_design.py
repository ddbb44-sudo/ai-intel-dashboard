#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحوص ميكانيكية للوحة — ما لا يمسكه نثرُ design.md.

مبدأ التقسيم (مقتبس من Vercel، وهو أهم ما في منهجهم): كل إصلاح يذهب إلى طبقته.
الحكم والذوق ← نصٌّ في design.md. القيمة المتكررة ← متغيّر CSS. أما المخالفة
الميكانيكية ← فحصٌ برمجي هنا، لأن القاعدة النثرية التي لا يمكن التحقق منها
تُهمَل بصمت بعد أسابيع.

كل فحص أدناه وُلد من عطل وقع فعلًا. لا فحص استباقي بلا سبب.

يخرج بـ1 عند أي مخالفة، فتفشل التشغيلة بصوت عالٍ.
"""
import re, sys, os

FAIL = []
WARN = []

H = "index.html"
A = "app.js"
html = open(H, encoding="utf-8").read() if os.path.exists(H) else ""
appjs = open(A, encoding="utf-8").read() if os.path.exists(A) else ""

# CSS المعرّف داخل index.html
css_classes = set(re.findall(r'\.([A-Za-z][\w-]*)\s*[{,:]', html))
compound = set(re.findall(r'\.([A-Za-z][\w-]*)\.([A-Za-z][\w-]*)', html))


# ── فحص 1: مُعدِّل يتسرّب ────────────────────────────────────────────────
# العطل (1 سبتمبر 2026): زر «أضف مقالة» كُتب class="iconbtn artbtn"، و.artbtn
# كانت معرّفة لغرض آخر تمامًا (زر رابط داخل المقالة) بـ display:flex و
# padding:11px 14px. فانسكبت على زر الشريط وسحقت أيقونته. لم يكن .iconbtn.artbtn
# معرّفًا أصلًا — أي أن الاسم كان زينة، والتصادم كان حتميًا.
for m in re.finditer(r'class="iconbtn\s+([A-Za-z][\w-]*)"', html):
    mod = m.group(1)
    if mod in css_classes and ("iconbtn", mod) not in compound:
        FAIL.append(
            "مُعدِّل يتسرّب: الزر يستخدم `iconbtn %s`، و`.%s` معرّفة وحدها لغرض آخر "
            "بينما `.iconbtn.%s` غير معرّفة. أنماط `.%s` ستنسكب على الزر."
            % (mod, mod, mod, mod))


# ── فحص 2: الأقران المتكافئون ───────────────────────────────────────────
# «الأقران المتكافئون يتشاركون الدور والحجم — لا تُكبّر واحدًا أبدًا.»
# أزرار الشريط العلوي أقران: أي اختلاف في مقاس الأيقونة يُرى فورًا بالعين.
hdr = re.search(r'(?is)<header.*?</header>', html)
if hdr:
    sizes = {}
    for m in re.finditer(r'<button class="iconbtn[^"]*"[^>]*title="([^"]*)"[^>]*>\s*'
                         r'<svg width="(\d+)" height="(\d+)"', hdr.group(0)):
        sizes.setdefault((m.group(2), m.group(3)), []).append(m.group(1))
    if len(sizes) > 1:
        common = max(sizes, key=lambda k: len(sizes[k]))
        for size, titles in sizes.items():
            if size == common: continue
            WARN.append("أقران غير متكافئين: %s مقاسه %sx%s بينما الأغلب %sx%s."
                        % ("، ".join(titles), size[0], size[1], common[0], common[1]))


# ── فحص 3: تصادم أسماء بين الشريط والمقالة ──────────────────────────────
# نفس عطل 1 سبتمبر بصيغته العامة: اسم فئة يُستعمل في مكانين لا علاقة بينهما.
if hdr and appjs:
    hdr_classes = set()
    for m in re.finditer(r'class="([^"]+)"', hdr.group(0)):
        hdr_classes.update(m.group(1).split())
    # الفئات التي يولّدها عارض المقالة
    art_block = appjs[appjs.find("function artInline"): appjs.find("function richText")] \
                if "function artInline" in appjs else ""
    art_classes = set(re.findall(r'class="([A-Za-z][\w-]*)"', art_block))
    shared = (hdr_classes & art_classes) - {"iconbtn"}
    for c in sorted(shared):
        FAIL.append("تصادم أسماء: `.%s` مستعملة في الشريط العلوي وفي عارض المقالة معًا." % c)


# ── فحص 4: تعريف مكرّر لنفس المُحدِّد ────────────────────────────────────
# تعريفان لنفس الاسم خارج media query = أحدهما يُلغي الآخر صامتًا.
body_css = re.sub(r'(?s)@media[^{]*\{.*?\n\}', '', html)
seen = {}
for m in re.finditer(r'(?m)^\.([A-Za-z][\w-]*)\s*\{', body_css):
    seen.setdefault(m.group(1), 0)
    seen[m.group(1)] += 1
for name, n in seen.items():
    if n > 1:
        WARN.append("`.%s` معرّفة %d مرات خارج media query — قد يُلغي أحدها الآخر." % (name, n))


# ── فحص 5: بصمة app.js ──────────────────────────────────────────────────
# العطل (٣ سبتمبر ٢٠٢٦): index.html يحمّل `app.js?v=<بصمة>` لكسر المخبأ، والبصمة
# تُحدَّث يدويًا. عُدِّل app.js ثلاث مرات دون تحديثها، فكان الزائر العائد يأخذ
# نسخة قديمة ولا يرى التعديل — عطل صامت تمامًا: لا خطأ ولا تحذير، والصفحة تعمل.
import hashlib
_m = re.search(r"app\.js\?v=([0-9a-f]+)", html)
if not _m:
    FAIL.append("لا بصمة لـ app.js في index.html — المخبأ سيقدّم نسخة قديمة بعد كل تعديل.")
elif os.path.exists(A):
    _real = hashlib.sha256(open(A, "rb").read()).hexdigest()[:len(_m.group(1))]
    if _real != _m.group(1):
        FAIL.append("بصمة app.js قديمة: index.html يطلب `%s` والمحتوى `%s`. "
                    "حدّثها وإلا لن يرى الزائر العائد التعديل." % (_m.group(1), _real))


# ── فحص 6: ملفات الأيقونات التي يطلبها المانيفست ────────────────────────
# العطل نفسه من نوع آخر: المانيفست كان يشير إلى icon-192.png و icon-512.png
# وهما غير موجودين، فتُطلبان في كل فتحة وتُردّان 404 بلا أثر يراه أحد.
if os.path.exists("site.webmanifest"):
    import json as _json
    try:
        _man = _json.load(open("site.webmanifest", encoding="utf-8"))
        for _ic in _man.get("icons", []):
            if not os.path.exists(_ic.get("src", "")):
                FAIL.append("المانيفست يطلب `%s` وهو غير موجود — 404 في كل فتحة." % _ic.get("src"))
    except Exception as _e:
        FAIL.append("site.webmanifest غير صالح: %s" % _e)


# ── التقرير ─────────────────────────────────────────────────────────────
print("فحص التصميم — %d مخالفة · %d تنبيه" % (len(FAIL), len(WARN)))
for x in FAIL: print("  ✗ " + x)
for x in WARN: print("  ⚠ " + x)
if not FAIL and not WARN:
    print("  ✓ لا مخالفات")

sys.exit(1 if FAIL else 0)
