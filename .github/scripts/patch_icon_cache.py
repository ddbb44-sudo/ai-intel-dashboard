#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
أيقونة اللوحة + إصلاح جذري لمشكلة الذاكرة المؤقتة.

المشكلة (31 أغسطس 2026): زر المقالة ظهر ولم يعمل. السبب أن index.html يحمّل
السكربت هكذا:

    s.src = 'app.js?v=' + encodeURIComponent(man.generated_at || '1');

أي أن نسخة **الكود** مربوطة بتاريخ **البيانات**. تشغيلة install-3 غيّرت app.js
ولم تلمس البيانات، فبقي الرابط نفسه فأعاد المتصفح النسخة القديمة: الزر موجود
في index.html الجديد، والدالة غائبة من app.js القديم.

الإصلاح: بصمة محتوى app.js نفسه. أي تعديل عليه يغيّر الرابط تلقائيًا.
يجب تشغيل هذا السكربت **بعد** أي تعديل على app.js.

آمن للتكرار: يعيد حساب البصمة في كل مرة.
"""
import hashlib, re, sys, os

# ───────── ١) بصمة المحتوى ─────────
if not os.path.exists("app.js"):
    print("توقّف: app.js غير موجود"); sys.exit(1)

digest = hashlib.md5(open("app.js","rb").read()).hexdigest()[:10]

H = "index.html"
h = open(H, encoding="utf-8").read()

# نلتهم بقية السطر (بما فيه أي تعليق سابق) وإلا تراكمت التعليقات مع كل تشغيل
pat = re.compile(r"s\.src\s*=\s*'app\.js\?v=[^\n]*")
if not pat.search(h):
    print("توقّف: سطر تحميل app.js لم يطابق المتوقع — لم أغيّر شيئًا"); sys.exit(1)

new_line = ("s.src = 'app.js?v=%s';"
            "  /* بصمة محتوى app.js — تتغيّر مع كل تعديل عليه */" % digest)
h_new, n = pat.subn(new_line, h, count=1)
if n != 1:
    print("توقّف: تعذّر الاستبدال"); sys.exit(1)
stamped = ("app.js?v=%s" % digest) in h
h = h_new
print("البصمة: %s%s" % (digest, "  (لم تتغيّر)" if stamped else "  (محدَّثة)"))

# ───────── ٢) الأيقونة ─────────
if 'rel="icon"' in h:
    print("الأيقونة: مركّبة مسبقًا — تخطٍّ")
else:
    anchor = "<title>مركز المعرفة — الذكاء الاصطناعي</title>"
    if h.count(anchor) != 1:
        # لا نُفشل التشغيلة بسبب العنوان — البصمة أهم
        print("تنبيه: وسم <title> لم يطابق، لم تُضف الأيقونة")
    else:
        icons = (anchor + "\n"
          '<link rel="icon" href="favicon.ico" sizes="any">\n'
          '<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">\n'
          '<link rel="icon" type="image/png" sizes="16x16" href="favicon-16.png">\n'
          '<link rel="apple-touch-icon" href="apple-touch-icon.png">\n'
          '<link rel="manifest" href="site.webmanifest">\n'
          '<meta name="theme-color" content="#c25f3c">\n'
          '<meta name="apple-mobile-web-app-title" content="مركز المعرفة">\n'
          '<meta name="description" content="لوحة عربية ترصد أخبار الذكاء الاصطناعي وأدواته يوميًا وتصنّفها.">')
        h = h.replace(anchor, icons)
        print("الأيقونة: أُضيفت الروابط و theme-color")

open(H, "w", encoding="utf-8").write(h)

# ───────── ٣) ملف الـ manifest للجوال ─────────
if not os.path.exists("site.webmanifest"):
    import json
    man = {
      "name": "مركز المعرفة — الذكاء الاصطناعي",
      "short_name": "مركز المعرفة",
      "lang": "ar", "dir": "rtl",
      "start_url": "./", "scope": "./",
      "display": "standalone",
      "background_color": "#faf9f7",
      "theme_color": "#c25f3c",
      "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
      ]
    }
    with open("site.webmanifest", "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("site.webmanifest: أُنشئ (يتيح إضافة اللوحة لشاشة الجوال)")
else:
    print("site.webmanifest: موجود — تخطٍّ")

print("تم.")
