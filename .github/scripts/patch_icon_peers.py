#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إصلاح أزرار الشريط العلوي: تصادم اسم + أقران غير متكافئين.

العطل (1 سبتمبر 2026، رصده عزيز بالعين): أيقونة «أضف مقالة» تبدو أصغر وأبهت
من إخوتها. السبب أن زرها كُتب `class="iconbtn artbtn"`، و`.artbtn` صارت
لاحقًا فئة زرّ الرابط داخل المقالة (display:flex · padding:11px 14px)،
فانسكبت على زر الشريط. والحاوية بقيت 36×36 فلم يكشفه قياسي — كشفته عينه.

وأثناء الإصلاح كشف الفحص الآلي تفاوتًا ثالثًا: زر «+» بمقاس 17 بينما
إخوته 16.

آمن للتكرار.
"""
import re, sys

H = "index.html"
h = open(H, encoding="utf-8").read()
changed = []

# ── 1) فكّ التصادم: الزر يصير قرينًا كامل التكافؤ لإخوته ──
old = 'class="iconbtn artbtn" onclick="openArticle()"'
new = 'class="iconbtn hb" onclick="openArticle()"'
if old in h:
    h = h.replace(old, new)
    changed.append("زر المقالة: iconbtn artbtn ← iconbtn hb (فُكَّ التصادم)")
elif new in h:
    print("زر المقالة: مُصلَح مسبقًا")
else:
    print("توقّف: زر المقالة لم يطابق — لم أغيّر شيئًا"); sys.exit(1)

# ── 2) توحيد مقاس الأيقونات: الأقران المتكافئون لا يختلف مقاسهم ──
hdr_m = re.search(r'(?is)<header.*?</header>', h)
if hdr_m:
    hdr = hdr_m.group(0)
    fixed = re.sub(r'(<button class="iconbtn[^"]*"[^>]*>\s*<svg )width="17" height="17"',
                   r'\1width="16" height="16"', hdr)
    if fixed != hdr:
        h = h.replace(hdr, fixed)
        changed.append("زر +: أيقونة 17×17 ← 16×16 لتطابق إخوتها")

open(H, "w", encoding="utf-8").write(h)
print("تم. " + (" · ".join(changed) if changed else "لا تغيير"))
