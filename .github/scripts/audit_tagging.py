#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تدقيق وسم المحاور — يُشغَّل قبل إعادة وسم التاريخ.

لماذا وُلد (٥ سبتمبر ٢٠٢٦): كانت خطة إعادة الوسم تشترط أن يفحص عزيز
التصنيف بعينه أولًا. فقال — محقًّا — إن هذا الفحص عملٌ منهجيّ من عمل
المساعد لا من عمله. فصار أداةً تُشغَّل بدل وعدٍ يُتذكَّر.

ما يمسكه: **مخالفات القاعدة** لا أخطاء الحكم. أي ما يمكن إثباته من نصّ
البطاقة نفسها مقابل القوائم المعتمدة. الحالات الملتبسة يبقى فيها الحكم
لعزيز، وتُعرض عليه عيّنة صراحةً.

الأصل: أُجري هذا الفحص يدويًّا على سحبة ٤ سبتمبر فأمسك خطأين حقيقيين —
Respan صُنّفت «أداة يستعملها» وليست في قائمة الأدوات، وانقطاع Grok صُنّف
«خارج الاهتمام» والتعطّل مستثنى صراحةً في القاعدة. وأُصلح سببهما بتشديد
الحدّين في نصّ التصنيف.

  python audit_tagging.py                  # كل البطاقات الموسومة
  python audit_tagging.py 2026-09-05       # يوم بعينه فأحدث
"""
import json, os, re, sys, glob, collections, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from taxonomy import AUDIENCE_TOPICS, BUILD_TARGETS, USER_TOOLS

# قائمة المرفوض الثمانية — «خارج الاهتمام» قائمة مغلقة لا حكم عام على قلّة الأهمية
REJECT = re.compile(r"استحواذ|تمويل|جولة استثمار|تقييم شرك|أسهم|اكتتاب|بورصة|"
                    r"دعوى|قضائي|تعيين|استقال|مجلس الإدارة|صراع|"
                    r"acquisition|funding|ipo\b|lawsuit|valuation", re.I)
# التعطّل والتسعير وأمن الأداة مستثناة صراحةً فترتفع
EXEMPT = re.compile(r"تعطّل|تعطل|انقطاع|توقّف الخدمة|outage|downtime|"
                    r"تسعير|سعر|تكلفة|pricing|ثغرة|اختراق|أمن", re.I)
SKILL  = re.compile(r"\bskill\b|skills|سكيل|مهارة|مهارات|/[a-z-]+\b", re.I)
TOOLS  = [t.lower() for t in USER_TOOLS]


def blob(c):
    e = " ".join(x for x in (c.get("entities") or []) if isinstance(x, str))
    return " ".join([c.get("arabic_title") or "", c.get("arabic_summary") or "",
                     c.get("why_it_matters") or "", e,
                     " ".join(c.get("tool_types") or [])]).lower()


def load(since=None):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "*.json"))):
        if os.path.basename(f) in ("manifest.json", "state.json", "authors.json"):
            continue
        try: d = json.load(open(f, encoding="utf-8"))
        except Exception: continue
        if not isinstance(d, list): continue
        for c in d:
            if not isinstance(c, dict) or "arabic_title" not in c: continue
            if since and (c.get("published_at") or "")[:10] < since: continue
            out.append(c)
    return out


def main(since=None):
    cards = load(since)
    tagged = [c for c in cards if c.get("audience_topic")]
    print("البطاقات%s: %d  ·  موسومة بالموضوع: %d"
          % (" منذ " + since if since else "", len(cards), len(tagged)))
    if not tagged:
        print("لا بطاقة موسومة — لا شيء يُدقَّق."); return 0

    issues = []

    for c in tagged:
        b, t = blob(c), c["audience_topic"]
        ttl = c["arabic_title"][:66]

        if t not in AUDIENCE_TOPICS:
            issues.append(("درجة غير معتمدة", t, ttl)); continue

        # ١) «أداة يستعملها» تشترط أداةً مذكورة بالاسم في القائمة — قاعدة حرفية لا استنتاجية
        if t == "أداة يستعملها" and not any(x in b for x in TOOLS):
            issues.append(("«أداة يستعملها» بلا أداة من القائمة", "", ttl))

        # ٢) «خارج الاهتمام» قائمة مغلقة، والتعطّل والتسعير مستثنيان فيرتفعان
        if t == "خارج الاهتمام":
            if not REJECT.search(b):
                issues.append(("«خارج الاهتمام» بلا سبب من الثمانية", "", ttl))
            elif EXEMPT.search(b):
                issues.append(("«خارج الاهتمام» وفيها مستثنًى (تعطّل/تسعير/أمن)", "", ttl))

        # ٣) «سكيل» تشترط ذكرًا للسكيل
        if t == "سكيل" and not SKILL.search(b):
            issues.append(("«سكيل» بلا ذكر لسكيل", "", ttl))

        # ٤) ما يذكر سكيلًا صراحةً ولم يُصنَّف سكيلًا — الأعلى يفوز
        if t in ("نموذج", "عالم AI عام") and re.search(r"\bskill\b|سكيل\b", b):
            issues.append(("يذكر سكيلًا ولم يُصنَّف «سكيل»", t, ttl))

        bt = c.get("build_target")
        if bt is not None and bt not in BUILD_TARGETS:
            issues.append(("build_target غير معتمد", str(bt), ttl))

    print()
    if issues:
        g = collections.Counter(i[0] for i in issues)
        print("مخالفات القاعدة: %d من %d (%.0f%%)" % (len(issues), len(tagged),
                                                      len(issues)/len(tagged)*100))
        for k, n in g.most_common(): print("  · %-46s %d" % (k, n))
        print()
        for kind, extra, ttl in issues[:25]:
            print("  ✗ [%s]%s" % (kind, " ← " + extra if extra else ""))
            print("      %s" % ttl)
    else:
        print("مخالفات القاعدة: صفر ✓")

    print()
    print("=== التوزيع ===")
    d = collections.Counter(c["audience_topic"] for c in tagged)
    for k in AUDIENCE_TOPICS:
        print("  %-16s %4d" % (k, d.get(k, 0)))

    print()
    print("=== عيّنة عشوائية للحكم بالعين (ما لا يمسكه فحصٌ آليّ) ===")
    random.seed(0)
    for c in random.sample(tagged, min(8, len(tagged))):
        print("  [%s] %s" % (c["audience_topic"], c["arabic_title"][:70]))

    return 1 if issues else 0


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("-")]
    sys.exit(main(a[0] if a else None))
