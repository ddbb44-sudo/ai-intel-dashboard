# -*- coding: utf-8 -*-
"""تمريرة ثانية: المجال حسب الجمهور، لا حسب الموضوع فقط.

المشكلة التي عالجتها هذه التمريرة (قياس 21 أغسطس): التمريرة الأولى أعطت مجالًا
واحدًا لكل بطاقة تقريبًا (متوسط 1.12)، فسقطت بطاقات يحتاجها المصمّم أو المسوّق
لأن «موضوعها الرئيسي» شيء آخر — مثل «مهارة /animate-expo» التي صُنِّفت
«برمجة وهندسة» فقط رغم أنها عن الحركة والواجهات.

هذه التمريدة **تضيف ولا تحذف**: مجال ثانٍ واحد كحد أقصى، والمجال الأول يبقى كما هو.
"""
import json, os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taxonomy import DOMAINS
import retag   # يعيد استخدام call_api ومنطق الدفعات

SYSTEM = """أنت تكمل تصنيف بطاقات عربية عن الذكاء الاصطناعي.

كل بطاقة لها **مجال رئيسي** مُسند سلفًا. مهمتك سؤال واحد فقط:

> هل هناك مجال ثانٍ **سيبحث أهله عن هذه البطاقة فعلًا** حتى لو لم يكن موضوعها الرئيسي؟

المعيار جمهور لا موضوع. أمثلة:
- أداة توليد فيديو أو صور ← مجالها الرئيسي «فيديو وصوت»، لكن **المصمّم** يريدها → «تصميم وواجهات»
- مهارة برمجية عن الحركة والانتقالات ← رئيسيها «برمجة وهندسة»، لكنها شغل **تصميم واجهات**
- تغيير في احتساب مشاهدات يوتيوب ← يهم **صانع المحتوى** → «تسويق ومحتوى»
- نموذج لغوي جديد أرخص بعشر مرات ← يهم **صاحب العمل** → «أعمال وإدارة»

المجالات المتاحة (لا تخرج عنها):
برمجة وهندسة · أعمال وإدارة · تصميم وواجهات · تسويق ومحتوى · نماذج وLLM ·
بيانات وتحليلات · بحث وتعليم · إنتاجية شخصية · فيديو وصوت · أمن سيبراني ·
روبوتات وعتاد · صحة · إسلامي

## قيود صارمة
- **مجال واحد إضافي كحد أقصى**، وغالبًا لا شيء. `null` جواب صحيح ومتوقّع للأغلبية.
- لا تُعِد المجال الرئيسي نفسه.
- لا تُضِف مجالًا لمجرد أن الكلمة وردت. اسأل: هل من يعمل في هذا المجال يستفيد عمليًا؟
- خبر عام عن شركة ذكاء اصطناعي ليس «أعمال وإدارة» تلقائيًا.

## الرد
JSON فقط: [{"serial":124,"extra_domain":"تصميم وواجهات"}, {"serial":125,"extra_domain":null}]"""


def run_batch(cards, ix):
    lines = [json.dumps({"serial": c["serial"], "title": c.get("arabic_title"),
                         "summary": (c.get("arabic_summary") or "")[:260],
                         "primary_domain": (c.get("domains") or [None])[0],
                         "text": (c.get("original_text") or "").replace("\n", " ")[:380]},
                        ensure_ascii=False) for c in cards]
    data = retag.call_api({"model": retag.MODEL, "max_tokens": 3000, "system": SYSTEM,
                           "messages": [{"role": "user",
                                         "content": "أكمل تصنيف هذه البطاقات:\n" + "\n".join(lines)}]})
    body = data["content"][0]["text"].strip()
    if body.startswith("```"):
        body = body.split("```")[1]
        if body.startswith("json"): body = body[4:]
    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        i, j = body.find("["), body.rfind("]")
        raw = json.loads(body[i:j + 1])
    out, bad = {}, []
    valid = {c["serial"] for c in cards}
    for r in raw:
        s, d = r.get("serial"), r.get("extra_domain")
        if s not in valid or not d: continue
        if d in DOMAINS: out[s] = d
        else: bad.append(d)
    print("  دفعة %02d: +%d مجال ثانٍ من %d" % (ix + 1, len(out), len(cards)), flush=True)
    return out, bad


def main():
    if not retag.API_KEY:
        sys.exit("ANTHROPIC_API_KEY غير مضبوط — أوقفت التشغيل بلا تعديل.")
    files, cards = {}, []
    for f in sorted(glob.glob(os.path.join(retag.DATA, "*.json"))):
        if os.path.basename(f) in ("manifest.json", "state.json", "authors.json"): continue
        d = json.load(open(f, encoding="utf-8"))
        if not isinstance(d, list) or not d or "serial" not in d[0]: continue
        files[f] = d; cards += d
    print("بطاقات: %d" % len(cards), flush=True)

    B = retag.BATCH
    batches = [cards[i:i + B] for i in range(0, len(cards), B)]
    from concurrent.futures import ThreadPoolExecutor
    extra, bad, failed = {}, [], 0
    with ThreadPoolExecutor(max_workers=retag.WORKERS) as ex:
        for fu in [ex.submit(run_batch, b, i) for i, b in enumerate(batches)]:
            try:
                g, bd = fu.result(); extra.update(g); bad += bd
            except Exception as e:
                failed += 1; print("  !! فشلت دفعة: %s" % str(e)[:180], flush=True)

    added = 0
    for f, arr in files.items():
        for c in arr:
            d = extra.get(c["serial"])
            if not d: continue
            doms = c.get("domains") or []
            if d not in doms and len(doms) < 2:
                doms.append(d); c["domains"] = doms; added += 1
        json.dump(arr, open(f, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    import collections
    dm = collections.Counter(x for c in cards for x in c["domains"])
    print("\nأُضيف مجال ثانٍ إلى %d بطاقة" % added)
    if failed: print("دفعات فاشلة: %d" % failed)
    if bad: print("مجالات مرفوضة: %s" % collections.Counter(bad).most_common(8))
    print("متوسط المجالات لكل بطاقة: %.2f" % (sum(len(c["domains"]) for c in cards) / len(cards)))
    print("\nالمجال بعد التمريرة:", dict(dm.most_common()))


if __name__ == "__main__":
    main()
