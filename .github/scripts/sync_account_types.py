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

    # ٣) النقل
    moved = 0
    for h, a in by_acc.items():
        r = by_aut.get(h)
        if not r: continue
        if r.get("account_type") != a.get("account_type") or r.get("is_arab") != a.get("is_arab"):
            r["account_type"] = a.get("account_type")
            r["is_arab"] = a.get("is_arab")
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
