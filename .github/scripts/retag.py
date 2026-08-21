# -*- coding: utf-8 -*-
"""إعادة تصنيف كل البطاقات على المحاور الثلاثة المعتمدة (§33).

يُشغَّل من GitHub Actions:  python3 .github/scripts/retag.py
يقرأ كل ملفات data/*.json التي تحوي بطاقات، ويعيد كتابة ثلاثة حقول فقط:
    content_types  →  نوع واحد من CONTENT_TYPES
    tool_types     →  جديد: 0-2 من TOOL_TYPES (فقط حين يكون النوع «أداة»)
    domains        →  1-2 من DOMAINS

لا يمسّ: serial · serial_display · id · النصوص العربية · original_text ·
source_url · metrics · entities · change_types · cluster_id · التفضيلات.
"""
import json, os, sys, glob, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taxonomy import CONTENT_TYPES, TOOL_TYPES, DOMAINS, LEGACY_DOMAIN

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL   = os.environ.get("RETAG_MODEL", "claude-sonnet-4-5-20250929")
BATCH   = int(os.environ.get("RETAG_BATCH", "20"))
WORKERS = int(os.environ.get("RETAG_WORKERS", "4"))
DATA    = os.environ.get("DATA_DIR", "data")

SYSTEM = """أنت مصنِّف محتوى لمركز معرفة عربي عن الذكاء الاصطناعي.

تُعطى بطاقات، وتُعيد لكل بطاقة ثلاثة حقول فقط. لا تشرح ولا تعتذر.

## نوع المحتوى — اختر واحدًا فقط
- إصدار — منتج أو ميزة أو نموذج جديد نزل أو تحدّث
- أداة — المنشور يعرّف بشيء يمكن استخدامه (سكربت · إضافة · تطبيق · مهارة)
- شرح — خطوات أو دليل أو طريقة عمل أو prompt مشروح
- تجربة — شخص جرّب شيئًا وذكر ما حصل معه
- بحث وقياس — ورقة علمية أو benchmark أو مقارنة مقاسة بأرقام
- رأي — تحليل شخصي أو موقف أو جدل، بلا إعلان منتج
- خبر — حدث في السوق (استحواذ · تمويل · سياسة · تعطّل) لا إصدار منتج

قاعدة الترجيح: إن أعلن المنشور شيئًا جديدًا فهو «إصدار» لا «خبر».
إن كان جوهره تعليم القارئ كيف يفعل شيئًا فهو «شرح» لا «أداة».

## نوع الأداة — فقط إذا كان نوع المحتوى «أداة» أو «إصدار»، وإلا اتركها []
MCP · Skill · Agent · Plugin · Prompt · API/SDK · تطبيق · نموذج
- MCP: خادم أو موصّل MCP تحديدًا. لا تستخدمها لمجرد ذكر الكلمة.
- Skill: مهارة قابلة للتركيب داخل نموذج (مثل /animate).
- Agent: وكيل ينفّذ مهامًا بنفسه. ليست لكل ذكر لكلمة agent في سياق عام.
- Plugin: إضافة داخل برنامج قائم (VS Code · Chrome · Figma · Excel).
- Prompt: النص نفسه هو المنتج.
- API/SDK: واجهة برمجية أو مكتبة للمطورين.
- تطبيق: أداة أو موقع أو برنامج مستقل.
- نموذج: نموذج ذكاء اصطناعي (GPT · Claude · Qwen · Seedance).
اثنان كحد أقصى. إن لم تنطبق أي واحدة بوضوح، أعِد [].

## المجال — واحد رئيسي، وثانٍ فقط إن كان حاضرًا بقوة
برمجة وهندسة · أعمال وإدارة · تصميم وواجهات · تسويق ومحتوى · نماذج وLLM ·
بيانات وتحليلات · بحث وتعليم · إنتاجية شخصية · فيديو وصوت · أمن سيبراني ·
روبوتات وعتاد · صحة · إسلامي

## القاعدة الحاكمة
**الإفراط في الوسم خطأ.** الوسم الذي لا تستطيع الدفاع عنه من نص البطاقة لا يوضع.
اثنان صحيحان أفضل من خمسة أحدها خاطئ.

## الرد
JSON فقط، مصفوفة بنفس ترتيب البطاقات وبنفس عدد العناصر:
[{"serial":124,"content_type":"إصدار","tool_types":["نموذج"],"domains":["نماذج وLLM"]}]"""


def call_api(payload, tries=3):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    last = None
    for a in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = "HTTP %s: %s" % (e.code, e.read()[:300].decode("utf-8", "replace"))
            if e.code in (429, 500, 502, 503, 529):
                time.sleep(5 * (a + 1)); continue
            break
        except Exception as e:
            last = str(e); time.sleep(4 * (a + 1))
    raise RuntimeError(last)


def clean(raw, cards):
    """يطابق رد النموذج على البطاقات ويرفض أي وسم خارج المفردات المعلنة."""
    by_serial = {c["serial"]: c for c in cards}
    out, rejected = {}, []
    for row in raw:
        s = row.get("serial")
        if s not in by_serial:
            continue
        ct = row.get("content_type")
        if ct not in CONTENT_TYPES:
            rejected.append(("content_type", ct)); ct = None
        tools = []
        for t in (row.get("tool_types") or [])[:2]:
            if t in TOOL_TYPES: tools.append(t)
            else: rejected.append(("tool_type", t))
        doms = []
        for d in (row.get("domains") or [])[:2]:
            if d in DOMAINS:
                doms.append(d)
            elif d in LEGACY_DOMAIN and LEGACY_DOMAIN[d]:
                doms.append(LEGACY_DOMAIN[d])          # شبكة أمان
            else:
                rejected.append(("domain", d))
        if ct:
            out[s] = {"content_types": [ct], "tool_types": tools,
                      "domains": list(dict.fromkeys(doms))[:2]}
    return out, rejected


def run_batch(cards, ix):
    lines = []
    for c in cards:
        txt = (c.get("original_text") or "").replace("\n", " ")[:500]
        lines.append(json.dumps({
            "serial": c["serial"], "author": c.get("author"),
            "title": c.get("arabic_title"), "summary": (c.get("arabic_summary") or "")[:300],
            "text": txt}, ensure_ascii=False))
    payload = {"model": MODEL, "max_tokens": 4000, "system": SYSTEM,
               "messages": [{"role": "user", "content":
                             "صنّف هذه البطاقات:\n" + "\n".join(lines)}]}
    data = call_api(payload)
    body = data["content"][0]["text"].strip()
    if body.startswith("```"):
        body = body.split("```")[1]
        if body.startswith("json"): body = body[4:]
    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        i, j = body.find("["), body.rfind("]")
        raw = json.loads(body[i:j + 1])
    got, rej = clean(raw, cards)
    print("  دفعة %02d: %d/%d بطاقة" % (ix + 1, len(got), len(cards)), flush=True)
    return got, rej


def main():
    if not API_KEY:
        sys.exit("ANTHROPIC_API_KEY غير مضبوط — أوقفت التشغيل بلا تعديل.")

    files, cards = {}, []
    for f in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        if os.path.basename(f) in ("manifest.json", "state.json", "authors.json"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        if not isinstance(d, list) or not d or "serial" not in d[0]:
            continue
        files[f] = d
        cards += d
    print("ملفات: %d — بطاقات: %d" % (len(files), len(cards)), flush=True)
    if not cards: sys.exit("لا بطاقات.")

    batches = [cards[i:i + BATCH] for i in range(0, len(cards), BATCH)]
    print("دفعات: %d × %d بطاقة، %d بالتوازي" % (len(batches), BATCH, WORKERS), flush=True)

    tags, rejected, failed = {}, [], 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(run_batch, b, i) for i, b in enumerate(batches)]
        for fu in futs:
            try:
                got, rej = fu.result(); tags.update(got); rejected += rej
            except Exception as e:
                failed += 1
                print("  !! فشلت دفعة: %s" % str(e)[:200], flush=True)

    print("\nصُنِّف: %d من %d" % (len(tags), len(cards)))
    if failed:  print("دفعات فاشلة: %d — بطاقاتها بقيت بوسومها القديمة" % failed)
    if rejected:
        from collections import Counter
        print("وسوم مرفوضة (خارج المفردات المعلنة): %d" % len(rejected))
        for k, n in Counter(rejected).most_common(12):
            print("   %s = %r × %d" % (k[0], k[1], n))

    changed_files = 0
    for f, arr in files.items():
        touched = False
        for c in arr:
            t = tags.get(c["serial"])
            if not t: continue
            if (c.get("content_types") != t["content_types"]
                    or c.get("domains") != t["domains"]
                    or c.get("tool_types") != t["tool_types"]):
                touched = True
            c["content_types"] = t["content_types"]
            c["tool_types"]    = t["tool_types"]
            c["domains"]       = t["domains"]
        for c in arr:
            c.setdefault("tool_types", [])      # الحقل موجود دائمًا حتى للفاشلة
        if touched: changed_files += 1
        json.dump(arr, open(f, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
    print("ملفات مُحدَّثة: %d" % changed_files)

    from collections import Counter
    ct = Counter(x for c in cards for x in c.get("content_types", []))
    tt = Counter(x for c in cards for x in c.get("tool_types", []))
    dm = Counter(x for c in cards for x in c.get("domains", []))
    print("\nنوع المحتوى:", dict(ct.most_common()))
    print("نوع الأداة:", dict(tt.most_common()))
    print("المجال:", dict(dm.most_common()))
    for name, used, declared in (("نوع المحتوى", ct, CONTENT_TYPES),
                                 ("نوع الأداة", tt, TOOL_TYPES),
                                 ("المجال", dm, DOMAINS)):
        zero = [x for x in declared if x not in used]
        if zero: print("%s — بعدّ صفر: %s" % (name, " · ".join(zero)))


if __name__ == "__main__":
    main()
