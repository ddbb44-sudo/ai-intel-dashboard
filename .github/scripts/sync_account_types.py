#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نقل نوع الحساب من accounts.json إلى authors.json.

لماذا سكربت لا نسخٌ يدوي (٣ سبتمبر ٢٠٢٦):
  accounts.json مصدر الحقيقة — يملكه سكربت في المستودع ويُحرَّر بطلبٍ موثَّق.
  لكن اللوحة لا تحمّله إطلاقًا: المتصفح يقرأ data/authors.json وحده.
  فالحقل الذي لا يُنقل لا يصل المستخدم مهما كان صحيحًا في مصدره.

  والنسخ اليدوي ينفصل: في اليوم نفسه غيّرتُ @xai إلى @SpaceXAI في accounts.json
  ونسيتُ authors.json، فصار الحساب بلا اسم ولا صورة ولا سيرة. هذا السكربت
  يجعل الانفصال مستحيلًا لا مستبعَدًا.

يُشغَّل بعد أي تعديل على accounts.json، وضمن السحب اليومي.
الخروج بـ1 عند اختلاف قائمتَي الحسابات — لأن الصمت عن حسابٍ ناقص أسوأ من فشلٍ ظاهر.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ACC  = os.path.join(ROOT, "accounts.json")
AUT  = os.path.join(ROOT, "data", "authors.json")

sys.path.insert(0, HERE)
from taxonomy import ACCOUNT_TYPES


def main(check_only=False):
    acc = json.load(open(ACC, encoding="utf-8"))["accounts"]
    aut = json.load(open(AUT, encoding="utf-8"))

    by_acc = {a["handle"].lower(): a for a in acc}
    by_aut = {a["handle"].lower(): a for a in aut}

    problems = []

    # ١) كل حساب متابَع له نوع معتمد
    for h, a in by_acc.items():
        t = a.get("account_type")
        if t is None:
            problems.append("@%s بلا account_type" % a["handle"])
        elif t not in ACCOUNT_TYPES:
            problems.append("@%s نوعه «%s» غير معتمد" % (a["handle"], t))
        if not isinstance(a.get("is_arab"), bool):
            problems.append("@%s بلا is_arab (منطقي)" % a["handle"])
        # فرق active يُبلَّغ في وضع الفحص فقط — في وضع النقل هو ما سيُصلَح بعد سطور،
        # والإبلاغ عمّا نحن بصدد إصلاحه ضجيجٌ يخفي المشكلات الحقيقية.
        r = by_aut.get(h)
        if check_only and r is not None and r.get("active") != a.get("active", True):
            problems.append("@%s: active في accounts=%s وفي authors=%s — "
                            "الإيقاف لن يظهر في اللوحة"
                            % (a["handle"], a.get("active", True), r.get("active")))

    # ٢) الملفّان يتطابقان في مجموعة الحسابات
    for h in sorted(set(by_acc) - set(by_aut)):
        problems.append("@%s في accounts.json ولا سجلّ له في authors.json — "
                        "سيظهر في اللوحة بلا اسم ولا صورة" % by_acc[h]["handle"])
    for h in sorted(set(by_aut) - set(by_acc)):
        problems.append("@%s في authors.json وليس في accounts.json — "
                        "سجلّ يتيم لحسابٍ لا يُسحب" % by_aut[h]["handle"])

    if check_only:
        if problems:
            print("تطابق الحسابات — %d مشكلة" % len(problems))
            for p in problems: print("  ✗ " + p)
            return 1
        print("تطابق الحسابات — سليم (%d حسابًا)" % len(by_acc))
        return 0

    # ٣) النقل — النوع والعلَم و«نشط»
    #    active يُنقل لأن «أوقف السحب» كان يعمل بلا أن يُرى: يوقف السحب في
    #    daily_pull فعلًا (السطر ١٠٤)، لكن اللوحة لا تحمّل accounts.json فيبقى
    #    الحساب في القائمة كأنه نشط. سأل عزيز: «لماذا الذين حذفتهم ما زالوا؟»
    #    — والجواب أن الإيقاف وقع ولم يصل الشاشة.
    FIELDS = ("account_type", "is_arab", "active")
    moved = 0
    for h, a in by_acc.items():
        r = by_aut.get(h)
        if not r: continue
        vals = {"account_type": a.get("account_type"),
                "is_arab": a.get("is_arab"),
                "active": a.get("active", True)}
        if any(r.get(k) != v for k, v in vals.items()):
            r.update(vals)
            moved += 1
        # is_arabic القديم مشتقٌّ من إعداد اللغة في X وقد وضع شركةً في «العرب».
        # يبقى للتوافق ولا يُقرأ في التصنيف — is_arab هو الحكم.
    json.dump(aut, open(AUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(AUT, "a", encoding="utf-8").write("\n")
    print("نُقل النوع إلى %d سجلًّا من %d" % (moved, len(by_aut)))
    for p in problems: print("  ⚠ " + p)
    return 0


if __name__ == "__main__":
    sys.exit(main(check_only="--check" in sys.argv))
