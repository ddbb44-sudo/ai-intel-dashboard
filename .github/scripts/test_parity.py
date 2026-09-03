#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تطابق daily_pull.py و backfill_account.py.

العطل الذي وُلد منه (٣ سبتمبر ٢٠٢٦): السكربتان نسختان من منطق واحد، ويصرّح
backfill في ترويسته أن التصنيف والبرومبت وشكل البطاقة «تبقى مطابقة حرفيًا».
لكن إصلاحين وقعا في daily_pull ولم يُنقلا:

  · رفع سقف مخرَج التصنيف من ٨٠٠٠ إلى ٢٤٠٠٠ توكن
  · دالة salvage لإنقاذ الكائنات المكتملة من JSON مقصوص

فأخفقت أول تشغيلة سحب تاريخي بسبعِ دفعات، كلها «Expecting ',' delimiter»
عند ~١٣٠٠٠ حرف — أي قصٌّ لا عطل نموذج. والنتيجة صفر بطاقة **بتشغيلة خضراء**.

القاعدة: نسختان تتباعدان بصمت أسوأ من واحدة. هذه الفحوص تكسر التشغيلة
عند أول تباعد بدل أن يُكتشف بعد تشغيلة فاشلة صامتة.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = open(os.path.join(HERE, "daily_pull.py"), encoding="utf-8").read()
B = open(os.path.join(HERE, "backfill_account.py"), encoding="utf-8").read()

ok = fail = 0

def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  ✓ " + name)
    else:
        fail += 1; print("  ✗ " + name + (" — " + detail if detail else ""))


def tax_list(src, key):
    m = re.search(r'"%s":\s*(\[.*?\])' % key, src, re.S)
    return re.sub(r"\s+", "", m.group(1)) if m else None


# ── قوائم التصنيف ────────────────────────────────────────────────────────
for key in ("content_types", "tool_types", "domains", "change_types",
            "audience_topics", "user_tools"):
    a, b = tax_list(D, key), tax_list(B, key)
    check("TAX['%s'] متطابقة" % key, a is not None and a == b,
          "daily=%s · backfill=%s" % (
              "غائبة" if a is None else "موجودة",
              "غائبة" if b is None else "موجودة"))


# ── قاعدة المحور الحاكم في نصّ التصنيف ───────────────────────────────────
K, E = "## التصنيف — المحور الحاكم أولًا", "## بقية المحاور"
if K in D and K in B and E in D and E in B:
    check("قاعدة المحور متطابقة حرفيًا",
          D[D.index(K):D.index(E)] == B[B.index(K):B.index(E)])
else:
    check("قاعدة المحور موجودة في الاثنين", False,
          "daily=%s · backfill=%s" % (K in D, K in B))


# ── سقف مخرَج التصنيف ────────────────────────────────────────────────────
# الافتراضي ٨٠٠٠ يقصّ المخرَج في منتصف JSON — يجب تجاوزه صراحةً في الاثنين.
def cap(src):
    # الاستدعاء لا التعريف: `def claude(prompt, max_tokens=8000)` يطابق النمط
    # نفسه، وهو الافتراضي المراد تجاوزه — فيُستثنى صراحةً.
    for m in re.finditer(r"(?<!def )claude\(prompt,\s*max_tokens=(\d+)\)", src):
        return int(m.group(1))
    return None

ca, cb = cap(D), cap(B)
check("سقف التصنيف مرفوع في daily_pull", ca is not None and ca >= 24000, "القيمة %s" % ca)
check("سقف التصنيف مرفوع في backfill",   cb is not None and cb >= 24000, "القيمة %s" % cb)
check("السقفان متساويان", ca == cb, "daily=%s · backfill=%s" % (ca, cb))


# ── إنقاذ JSON المقصوص ───────────────────────────────────────────────────
for name, src in (("daily_pull", D), ("backfill_account", B)):
    check("%s يستعمل salvage" % name,
          "from jsontools import salvage" in src and "salvage(" in src)


# ── الحقل الحاكم في البطاقة ──────────────────────────────────────────────
for name, src in (("daily_pull", D), ("backfill_account", B)):
    check("%s يكتب audience_topic في البطاقة" % name,
          '"audience_topic": _top' in src)
    check("%s يردّ القيمة الشاذّة إلى «عالم AI عام»" % name,
          '_top = "عالم AI عام"' in src)


print("\nنجح %d · فشل %d" % (ok, fail))
sys.exit(1 if fail else 0)
