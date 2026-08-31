#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
يحوّل Issue بوسم `article` إلى بطاقة مقالة كاملة.

مساران:
  • نص ملصوق  — لا جلب إطلاقًا، جسم الطلب هو المقالة.
  • رابط      — جلب عادي، فإن عجز فمتصفح Apify الحقيقي.

الفرق عن process_issue.py: هذا يحفظ **المقالة كاملة مرتَّبة** لا ملخصًا،
فتُقرأ داخل اللوحة بلا رجوع للمصدر.

مبدأ ثابت: عند أي شك — لا تكتب، واترك الـIssue مفتوحة بسبب واضح.
"""
import json, os, re, sys, time, html as htmllib, urllib.request, urllib.error, datetime

OWNER  = os.environ["GH_OWNER"]
REPO   = os.environ["GH_REPO"]
NUMBER = int(os.environ["ISSUE_NUMBER"])
AUTHOR = os.environ.get("ISSUE_AUTHOR", "")
BODY   = os.environ.get("ISSUE_BODY", "") or ""
TITLE  = os.environ.get("ISSUE_TITLE", "") or ""
GH_TOK = os.environ["GITHUB_TOKEN"]

def _envs(n, d):
    v = os.environ.get(n)
    return v.strip() if v and v.strip() else d

AKEY   = _envs("ANTHROPIC_API_KEY", "")
APIFY  = _envs("APIFY_TOKEN", "")
MODEL  = _envs("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
ABASE  = _envs("ANTHROPIC_BASE", "https://api.anthropic.com")
APBASE = _envs("APIFY_BASE", "https://api.apify.com")
DATA   = "data"

MAX_INPUT = 45000     # حد النص الداخل إلى النموذج
MAX_OUT   = 16000     # المقالة الكاملة تحتاج مخرَجًا واسعًا

def log(m): print(m, flush=True)

def gh(method, path, payload=None):
    req = urllib.request.Request("https://api.github.com" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method, headers={"Authorization": "Bearer " + GH_TOK,
        "Accept": "application/vnd.github+json", "User-Agent": "ai-intel-article",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")

def comment(msg):
    try: gh("POST", "/repos/%s/%s/issues/%d/comments" % (OWNER, REPO, NUMBER), {"body": msg})
    except Exception as e: log("comment failed: %s" % e)

def bail(msg):
    log("BAIL: " + msg)
    comment("تعذّرت إضافة المقالة: %s\n\nالطلب باقٍ مفتوحًا." % msg)
    sys.exit(0)

if AUTHOR.lower() != OWNER.lower():
    log("author %s is not owner — ignoring" % AUTHOR); sys.exit(0)
if not AKEY: bail("ANTHROPIC_API_KEY غير مضبوط")

# §33 — نسخة مطابقة للقوائم المعتمدة
TAX = {
 "content_types": ['إصدار','أداة','شرح','تجربة','بحث وقياس','رأي','خبر'],
 "tool_types":    ['MCP','Skill','Agent','Plugin','Prompt','API/SDK','تطبيق','نموذج'],
 "domains": ['برمجة وهندسة','أعمال وإدارة','تصميم وواجهات','تسويق ومحتوى','نماذج وLLM',
   'بيانات وتحليلات','بحث وتعليم','إنتاجية شخصية','فيديو وصوت','أمن سيبراني',
   'روبوتات وعتاد','صحة','إسلامي'],
 "change_types": ['New Release','New Feature','Upgrade','Update','Model Update','API Update',
   'Pricing Change','New Integration','MCP Support','New Agent Feature','Beta / Preview',
   'General Availability','Deprecation','Shutdown','Research Release','Open Source','Acquisition',
   'Outage / Incident','Security']
}

def rj(p, d=None):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError:
        if d is not None: return d
        raise

# ---------- 1) نص أم رابط؟ ----------
note = ""
nm = re.search(r'ملاحظة عزيز:\s*(.+)', BODY, re.S)
if nm:
    note = nm.group(1).strip()
    BODY = BODY[:nm.start()]

body = BODY.strip()
um = re.search(r'https?://[^\s<>"\)]+', body)
# رابط فقط (لا نص حوله) = مسار الرابط. نص طويل = مسار النص ولو حوى روابط.
url_only = bool(um) and len(re.sub(r'https?://[^\s<>"\)]+', '', body).strip()) < 40

URL = um.group(0).rstrip(".,،؛)") if um else ""
source_url, source_site, page_title = "", "", ""

def clean_html(raw):
    t = re.sub(r'(?is)<(script|style|noscript|svg|nav|footer|header|aside)[^>]*>.*?</\1>', ' ', raw)
    title = ""
    tm = re.search(r'(?is)<title[^>]*>(.*?)</title>', t)
    if tm: title = htmllib.unescape(re.sub(r'\s+', ' ', tm.group(1))).strip()
    # نحافظ على حدود الفقرات قبل نزع الوسوم
    t = re.sub(r'(?i)</(p|div|h[1-6]|li|section|article|br)\s*>', '\n\n', t)
    t = re.sub(r'(?i)<br\s*/?>', '\n', t)
    b = re.sub(r'(?s)<[^>]+>', ' ', t)
    b = htmllib.unescape(b)
    b = re.sub(r'[ \t]+', ' ', b)
    b = re.sub(r'\n\s*\n\s*\n+', '\n\n', b).strip()
    return title, b

def fetch_plain(u):
    req = urllib.request.Request(u, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
        "Accept-Language": "ar,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read(3_000_000).decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    return clean_html(raw)

def fetch_browser(u):
    """متصفح حقيقي عبر أكتور Apify المجاني rag-web-browser.
    يشغّل Playwright، ينتظر المحتوى الديناميكي، ويغلق نوافذ الكوكيز."""
    if not APIFY: return "", ""
    payload = {"query": u, "maxResults": 1, "outputFormats": ["markdown"],
               "scrapingTool": "browser-playwright", "htmlTransformer": "readable",
               "removeCookieWarnings": True, "dynamicContentWaitSecs": 12,
               "requestTimeoutSecs": 90}
    try:
        req = urllib.request.Request(
            APBASE + "/v2/acts/apify~rag-web-browser/run-sync-get-dataset-items?token=" + APIFY,
            data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=240) as r:
            items = json.loads(r.read().decode())
    except Exception as e:
        log("المتصفح فشل: %s" % e); return "", ""
    if not items: return "", ""
    it = items[0] if isinstance(items, list) else items
    md = it.get("markdown") or it.get("text") or ""
    md = re.sub(r'\n\s*\n\s*\n+', '\n\n', md).strip()
    ttl = ((it.get("metadata") or {}).get("title")) or it.get("title") or ""
    return ttl, md

if url_only:
    if not URL: bail("لم أجد رابطًا صالحًا")
    source_url = URL
    source_site = re.sub(r'^https?://(www\.)?', '', URL).split('/')[0]
    log("مسار الرابط: %s" % URL)
    try:
        page_title, article_text = fetch_plain(URL)
        log("الجلب العادي: %d حرفًا" % len(article_text))
    except Exception as e:
        page_title, article_text = "", ""
        log("الجلب العادي فشل: %s" % e)

    if len(article_text) < 400:
        log("النص هزيل — أجرّب المتصفح الحقيقي…")
        t2, a2 = fetch_browser(URL)
        if len(a2) > len(article_text):
            article_text = a2
            page_title = page_title or t2
            log("المتصفح نجح: %d حرفًا" % len(article_text))

    if len(article_text) < 400:
        bail("تعذّر قراءة المقالة حتى بالمتصفح — قد تكون خلف تسجيل دخول أو اشتراك. "
             "انسخ نصها والصقه في طلب جديد بوسم `article`.")
else:
    article_text = body
    if len(article_text) < 200:
        bail("النص قصير جدًا (%d حرفًا). الصق المقالة كاملة." % len(article_text))
    if um: source_url = URL   # رابط ذُكر داخل النص = مرجع
    log("مسار النص الملصوق: %d حرفًا" % len(article_text))

article_text = article_text[:MAX_INPUT]

# ---------- 2) Claude: يرتّب المقالة كاملة ويصنّفها ----------
PROMPT = """أنت محرّر «مركز المعرفة — الذكاء الاصطناعي»، لوحة عربية يملكها عزيز.

وصلتك **مقالة كاملة** اختارها عزيز بنفسه. مهمتك أن تخرجها في بطاقة تُقرأ داخل
اللوحة **دون الحاجة للرجوع إلى المصدر**.

## قواعد غير قابلة للتفاوض
- **لا تلخّص المقالة ولا تحذف أفكارها.** أعد عرض محتواها كاملًا مرتَّبًا: فقرات
  واضحة، وعناوين فرعية تسبقها `## `، وقوائم حيث يناسب. احذف فقط ضجيج الصفحة
  (إعلانات · روابط تنقّل · دعوات اشتراك · تعليقات).
- إن كانت المقالة بالإنجليزية فانقلها إلى **عربية سليمة** — نقلًا أمينًا لا ترجمة
  حرفية، والمصطلحات التقنية تبقى إنجليزية: MCP, API, Agent, RAG, Prompt, Skill,
  Benchmark, Token, Context Window, Fine-tuning, Embedding.
- إن كانت عربية أصلًا فاحتفظ بصياغة الكاتب وحسّن التنسيق فقط.
- **لا تخترع.** لا رقم ولا اسم ولا رابط ولا استنتاج غير موجود في النص. إن كان
  النص ناقصًا أو مبتورًا فقل ذلك في نهاية `detailed_explanation` بجملة صريحة.
- **هذه المقالة مقبولة حتمًا** — عزيز اختارها. لا تحكم عليها ولا ترفضها.

## المخرَج
أعد **JSON فقط**، كائنًا واحدًا:
{"arabic_title":"عنوان محدّد 6-14 كلمة",
 "arabic_summary":"2-4 جمل تلخّص المقالة لغير المختص",
 "why_it_matters":"جملة أو جملتان عن الأثر الحقيقي",
 "detailed_explanation":"**المقالة كاملة** مرتَّبة بالعربية. الفقرات مفصولة بسطرين. العناوين الفرعية تبدأ بـ##",
 "original_language":"ar أو en",
 "source_name":"اسم الموقع أو الكاتب إن ظهر في النص، وإلا اتركه فارغًا",
 "content_type":"واحد فقط","tool_types":[],"domains":[],"entities":[],"change_types":[],
 "importance_tier":"important أو useful",
 "glossary":[{"term":"مصطلح إنجليزي","ar":"شرحه بالعربية"}]}

## التصنيف — والإفراط في الوسم خطأ
**نوع المحتوى: واحد فقط.** مقالة تشرح كيف تفعل شيئًا = «شرح». تحلّل أو تبدي
موقفًا = «رأي». تعرض دراسة أو قياسًا = «بحث وقياس». تعلن جديدًا = «إصدار».
**نوع الأداة: صفر إلى اثنين**، وفقط إن كانت المقالة عن أداة بعينها.
**المجال: واحد أو اثنان.** الوسم الذي لا يمكن الدفاع عنه من النص لا يوضع.

## القوائم المعتمدة (لا تخرج عنها إطلاقًا)
""" + ("content_type: " + json.dumps(TAX['content_types'], ensure_ascii=False) + "\n"
     + "tool_types: "   + json.dumps(TAX['tool_types'],    ensure_ascii=False) + "\n"
     + "domains: "      + json.dumps(TAX['domains'],       ensure_ascii=False) + "\n"
     + "change_types: " + json.dumps(TAX['change_types'],  ensure_ascii=False) + "\n")

def claude(prompt, max_tokens):
    req = urllib.request.Request(ABASE + "/v1/messages",
        data=json.dumps({"model": MODEL, "max_tokens": max_tokens,
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"x-api-key": AKEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"}, method="POST")
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = "HTTP %s — %s" % (e.code, e.read().decode()[:300])
            if e.code in (429,500,502,503,529): time.sleep(10*(attempt+1)); continue
            break
        except Exception as e:
            last = str(e); time.sleep(6*(attempt+1))
    raise RuntimeError(last or "unknown")

payload = json.dumps({
    "title_hint": re.sub(r'^\s*مقالة:\s*', '', TITLE).strip(),
    "url": source_url, "text": article_text}, ensure_ascii=False)

try:
    resp = claude(PROMPT + "\n\n## المقالة\n" + payload, MAX_OUT)
except Exception as e:
    bail("فشل التصنيف: %s" % str(e)[:250])

txt = "".join(b.get("text","") for b in resp.get("content", []))
stop = resp.get("stop_reason")
mm = re.search(r'\{.*\}', txt, re.S)
if not mm:
    bail("مخرَج النموذج غير قابل للقراءة%s" % (" (بلغ الحد الأقصى للطول)" if stop=="max_tokens" else ""))
try:
    card = json.loads(mm.group(0))
except Exception as e:
    bail("مخرَج النموذج ليس JSON سليمًا: %s" % str(e)[:150])

def clean(v, allowed): return [x for x in (v or []) if x in allowed]

title = (card.get("arabic_title") or "").strip()
summ  = (card.get("arabic_summary") or "").strip()
full  = (card.get("detailed_explanation") or "").strip()
if not title or not full:
    bail("النموذج لم يُعد عنوانًا أو نص مقالة")
if stop == "max_tokens":
    full += "\n\n— بلغت المقالة الحد الأقصى للمعالجة وقد تكون مبتورة في آخرها."

_ct = card.get("content_type") or card.get("content_types")
if isinstance(_ct, str): _ct = [_ct]
ct  = clean(_ct, TAX["content_types"])[:1] or ["شرح"]
tl  = clean(card.get("tool_types"), TAX["tool_types"])[:2]
dom = clean(card.get("domains"),    TAX["domains"])[:2]
chg = clean(card.get("change_types"), TAX["change_types"])
tier = card.get("importance_tier") if card.get("importance_tier") in ("important","useful") else "useful"
lang = "ar" if card.get("original_language") == "ar" else "en"

if note:
    full += "\n\n## ملاحظة عزيز\n\n" + note

# ---------- 3) الكتابة ----------
state    = rj(f"{DATA}/state.json")
manifest = rj(f"{DATA}/manifest.json")
now = datetime.datetime.now(datetime.timezone.utc)
serial = int(state.get("max_serial", 0)) + 1
cid = "c%03d" % serial

rec = {
 "id": cid, "serial": serial, "serial_display": "#%06d" % serial,
 "source_type": "article", "source_url": source_url, "source_native_id": None,
 "source_name": (card.get("source_name") or source_site or "مقالة ملصوقة")[:60],
 "source_site": source_site, "author": card.get("source_name") or source_site or "—",
 "published_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
 "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
 "original_language": lang, "is_arabic_source": lang == "ar",
 "arabic_title": title, "arabic_summary": summ,
 "detailed_explanation": full,
 "why_it_matters": (card.get("why_it_matters") or "").strip(),
 "original_text": article_text[:20000],
 "glossary": [g for g in (card.get("glossary") or []) if isinstance(g, dict) and g.get("term")],
 "content_types": ct, "tool_types": tl, "domains": dom,
 "entities": card.get("entities") or [], "change_types": chg,
 "importance_tier": tier, "importance_score": 88 if tier == "important" else 62,
 "engagement_score": 0, "metrics": {},
 "metrics_captured_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
 "external_links": [], "quoted": None, "cluster_id": None,
 "also_reported": [], "thread_parts": [], "freshness": 100.0,
 # 'issue' لا 'article': كل ما يضيفه عزيز بيده يظهر في «أضفتها بنفسي»
 "added_via": "issue",
}

day   = now.strftime("%Y-%m-%d")
shard = f"article-{day}.json"
items = rj(f"{DATA}/{shard}", [])
items.append(rec)
with open(f"{DATA}/{shard}", "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=1)

if shard not in manifest.get("shards", []):
    manifest.setdefault("shards", []).append(shard)
manifest["generated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
st = manifest.setdefault("stats", {})
st["cards"] = int(st.get("cards", 0)) + 1
with open(f"{DATA}/manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)

state["max_serial"] = serial
state["updated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
with open(f"{DATA}/state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=1)

with open("article_result.md", "w", encoding="utf-8") as f:
    f.write("أُضيفت المقالة **%s** — %s\n\n" % (rec["serial_display"], title))
    f.write("- الطول بعد الترتيب: **%d حرفًا**\n" % len(full))
    f.write("- المصدر: %s\n" % (source_url or "نص ملصوق"))
    f.write("- التصنيف: %s%s · %s\n\n" % (
        " · ".join(ct), (" · " + " · ".join(tl)) if tl else "", " · ".join(dom) or "بلا مجال"))
    f.write("https://ddbb44-sudo.github.io/ai-intel-dashboard/#/c/%s\n" % cid)

with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
    f.write("ART_ID=%s\nART_SERIAL=%s\n" % (cid, rec["serial_display"]))

log("تمت: %s — %s (%d حرفًا)" % (rec["serial_display"], title, len(full)))
