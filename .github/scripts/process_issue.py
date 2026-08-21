#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
يحوّل Issue بوسم inbox إلى بطاقة في لوحة «مركز المعرفة».
يعمل داخل GitHub Actions. مبدأ التصميم: عند أي شك — لا تكتب شيئًا واترك الـ Issue مفتوحة
لتلتقطها المهمة المجدولة كل ساعة. الفشل الصامت ممنوع؛ كل خطأ يُعلَّق على الـ Issue.
"""
import json, os, re, sys, urllib.request, urllib.error, urllib.parse, datetime, html as htmllib

OWNER   = os.environ["GH_OWNER"]
REPO    = os.environ["GH_REPO"]
NUMBER  = int(os.environ["ISSUE_NUMBER"])
AUTHOR  = os.environ.get("ISSUE_AUTHOR", "")
BODY    = os.environ.get("ISSUE_BODY", "") or ""
GH_TOK  = os.environ["GITHUB_TOKEN"]
AKEY    = os.environ.get("ANTHROPIC_API_KEY", "").strip()
APIFY   = os.environ.get("APIFY_TOKEN", "").strip()
MODEL   = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
DATA    = "data"

def log(m): print(m, flush=True)

def gh(method, path, payload=None):
    url = "https://api.github.com" + path
    data = json.dumps(payload).encode() if payload is not None else None
    req  = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + GH_TOK, "Accept": "application/vnd.github+json",
        "User-Agent": "ai-intel-inbox", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")

def comment(msg):
    try: gh("POST", f"/repos/{OWNER}/{REPO}/issues/{NUMBER}/comments", {"body": msg})
    except Exception as e: log("comment failed: %s" % e)

def bail(msg, keep_open=True):
    """يترك الـ Issue مفتوحة ليعالجها المسار البطيء، ويشرح السبب."""
    log("BAIL: " + msg)
    comment("تعذّرت المعالجة السريعة: %s\n\nالطلب باقٍ مفتوحًا، وستلتقطه المهمة المجدولة خلال ساعة." % msg)
    sys.exit(0)

# ---------- 1) التحقق من الهوية ----------
if AUTHOR.lower() != OWNER.lower():
    log("author %s is not owner — ignoring" % AUTHOR); sys.exit(0)

# ---------- 2) استخراج الرابط والملاحظة ----------
m = re.search(r'https?://[^\s<>"\)]+', BODY)
if not m: bail("لم أجد رابطًا في الطلب")
URL = m.group(0).rstrip(".,،؛)")
note = ""
nm = re.search(r'ملاحظة عزيز:\s*(.+)', BODY, re.S)
if nm: note = nm.group(1).strip()

def host_of(u):
    h = re.sub(r'^https?://', '', u).split('/')[0].split('?')[0]
    return re.sub(r'^www\.', '', h).lower()
HOST = host_of(URL)

if HOST in ("x.com", "twitter.com", "mobile.x.com"):
    KIND = "x"
elif HOST in ("youtube.com", "youtu.be", "m.youtube.com"):
    KIND = "youtube"
elif HOST == "github.com":
    KIND = "github"
else:
    KIND = "web"

if not AKEY:
    bail("مفتاح ANTHROPIC_API_KEY غير مضبوط في أسرار المستودع")

# ---------- 3) قراءة الحالة ----------
def read_json(p, default=None):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError:
        if default is not None: return default
        raise

state    = read_json(f"{DATA}/state.json")
manifest = read_json(f"{DATA}/manifest.json")

def norm_url(u):
    """توحيد الرابط لكشف التكرار — مع **إبقاء** المعاملات المعنوية.
    قصّ ما بعد '?' كان يحوّل كل روابط يوتيوب إلى youtube.com/watch فتُعدّ كلها مكررة."""
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:
        return u.rstrip("/")
    DROP = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content",
            "si","feature","ref","ref_src","ref_url","fbclid","gclid","igshid","s","t"}
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query)
         if k.lower() not in DROP]
    q.sort()
    host = p.netloc.lower()
    if host.startswith("www."): host = host[4:]
    if host == "twitter.com": host = "x.com"
    if host == "youtu.be":
        vid = p.path.lstrip("/")
        host, path, q = "youtube.com", "/watch", [("v", vid)]
    else:
        path = p.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit(("https", host, path, urllib.parse.urlencode(q), ""))

saved = set(state.get("saved_urls") or [])
norm  = norm_url(URL)
if norm in saved:
    comment("هذا الرابط مضاف سابقًا — لم تُنشأ بطاقة مكرّرة.")
    try: gh("PATCH", f"/repos/{OWNER}/{REPO}/issues/{NUMBER}", {"state": "closed"})
    except Exception as e: log("close failed: %s" % e)
    sys.exit(0)

# ---------- 4) جلب المحتوى ----------
def fetch_text(u, limit=18000, want_raw=False):
    req = urllib.request.Request(u, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
        "Accept-Language": "ar,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=45) as r:
        rawb = r.read(2_500_000)
        enc = r.headers.get_content_charset() or "utf-8"
    raw = rawb.decode(enc, errors="replace")
    t = re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>', ' ', raw)
    title = ""
    tm = re.search(r'(?is)<title[^>]*>(.*?)</title>', t)
    if tm: title = htmllib.unescape(re.sub(r'\s+', ' ', tm.group(1))).strip()
    body = re.sub(r'(?s)<[^>]+>', ' ', t)
    body = htmllib.unescape(re.sub(r'\s+', ' ', body)).strip()
    return (title, body[:limit], raw) if want_raw else (title, body[:limit])

source_name, source_site, page_title, page_text = "", HOST, "", ""
x_data = None

if KIND == "x":
    tid = re.search(r'/status/(\d+)', URL)
    if not tid: bail("رابط X بلا معرّف تغريدة")
    if not APIFY: bail("رابط X يحتاج APIFY_TOKEN وهو غير مضبوط")
    payload = {"mode": "tweet", "tweetIds": [tid.group(1)],
               "outputVariant": "rich", "fieldStyle": "camelCase"}
    req = urllib.request.Request(
        "https://api.apify.com/v2/acts/xquik~x-tweet-scraper/run-sync-get-dataset-items?token=" + APIFY,
        data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            items = json.loads(r.read().decode())
    except Exception as e:
        bail("فشل جلب التغريدة من Apify: %s" % e)
    if not items: bail("Apify لم يُعد أي نتيجة لهذه التغريدة")
    x_data = items[0]
    a = x_data.get("author") or {}
    source_name = a.get("name") or a.get("username") or ""
    source_site = "x.com"
    page_text   = (x_data.get("noteTweet") or {}).get("text") or x_data.get("text") or ""
else:
    try:
        page_title, page_text = fetch_text(URL)
    except Exception as e:
        log("fetch failed: %s" % e)
        page_title, page_text = "", ""
    if KIND == "github":
        gm = re.match(r'https?://github\.com/([^/]+)/([^/#?]+)', URL)
        source_name = "%s/%s" % (gm.group(1), gm.group(2)) if gm else HOST
        if gm:
            for br in ("main", "master"):
                try:
                    _, rd = fetch_text("https://raw.githubusercontent.com/%s/%s/%s/README.md"
                                       % (gm.group(1), gm.group(2), br))
                    if rd: page_text = rd; break
                except Exception: pass
    elif KIND == "youtube":
        # صفحة يوتيوب تُبنى بـ JS، فقشطُ الـ HTML يعيد روابط التذييل فقط.
        # oEmbed يعطي العنوان واسم القناة بثبات وبلا JS.
        yt_title, yt_channel, yt_desc = "", "", ""
        try:
            oe = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(URL, safe="")
            with urllib.request.urlopen(urllib.request.Request(
                    oe, headers={"User-Agent": "ai-intel-bot/1.0"}), timeout=30) as r:
                o = json.loads(r.read().decode())
            yt_title   = (o.get("title") or "").strip()
            yt_channel = (o.get("author_name") or "").strip()
        except Exception as e:
            log("oembed failed: %s" % e)
        try:
            _, _, raw_html = fetch_text(URL, want_raw=True)
            dm = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', raw_html)
            if dm:
                yt_desc = json.loads('"' + dm.group(1) + '"')
        except Exception as e:
            log("yt description failed: %s" % e)
        source_name = yt_channel or "YouTube"
        page_title  = yt_title or page_title.replace(" - YouTube", "").strip()
        parts = []
        if yt_title:   parts.append("عنوان الفيديو: " + yt_title)
        if yt_channel: parts.append("القناة: " + yt_channel)
        if yt_desc:    parts.append("وصف الفيديو:\n" + yt_desc)
        else:          parts.append("(وصف الفيديو غير متاح، ولا يتوفر تفريغ نصي)")
        page_text = "\n\n".join(parts)
    else:
        cand = re.split(r'\s+[|\u2013\u2014-]\s+', page_title)[-1].strip() if page_title else ""
        source_name = (cand or HOST)[:60]

unreadable = len(page_text.strip()) < 120
# حارس: صفحة بلا عنوان وبلا نص لا تُنتج بطاقة — الطلب يبقى مفتوحًا بدل حفظ بطاقة فارغة
if unreadable and not page_title and KIND != "x":
    bail("تعذّر قراءة الصفحة: لا عنوان ولا نص. لم أُنشئ بطاقة فارغة")

# ---------- 5) التصنيف عبر Claude ----------
TAXONOMY = {
 "content_types": ['Skill','MCP','Agent','Prompt','API','Release','Feature','Tutorial','Guide','Tool',
   'Workflow','Template','SDK','Dataset','Benchmark','Research Paper','Announcement','Case Study',
   'Comparison','Opinion','Thread','Demo','Course','News','Job','Event'],
 "domains": ['AI','ML','LLM','Software Development','Coding','DevOps','Data','Analytics','Cybersecurity',
   'Robotics','Product','Design','UI','UX','Marketing','Digital Marketing','SEO','Content','Sales',
   'E-commerce','Business','Management','Operations','Customer Experience','Finance','Investment',
   'Legal','Healthcare','Medicine','Education','Research','Engineering','Automotive','Manufacturing',
   'Media','Creative','Video','Audio','Islamic','Personal Productivity','Automation'],
 "change_types": ['New Release','New Feature','Upgrade','Update','Model Update','API Update',
   'Pricing Change','New Integration','MCP Support','New Agent Feature','Beta / Preview',
   'General Availability','Deprecation','Shutdown','Research Release','Open Source','Acquisition',
   'Outage / Incident','Security']
}

PROMPT = f"""أنت محرّر «مركز المعرفة — الذكاء الاصطناعي»، لوحة عربية يملكها عزيز.
حوّل المصدر التالي إلى بطاقة عربية واحدة.

## قواعد غير قابلة للتفاوض
- **لا تخمّن ولا تخترع.** كل ما تكتبه مستخرج من النص المعطى فقط. لا أرقام ولا روابط ولا أسماء غير واردة فيه.
- إن كان النص ناقصًا أو غير مقروء، قُل ذلك صراحة داخل الشرح ولا تكمّل من عندك.
- العربية للشرح، والمصطلحات التقنية تبقى إنجليزية: MCP, API, Agent, Embedding, Vector Database,
  Fine-tuning, RAG, Prompt, Skill, Benchmark, Token, Context Window.
- اكتب كمحلّل لا كمسوّق: ماذا يقول المصدر، ولماذا يهم.
- عزيز أضاف هذا بنفسه، فلا يُصنَّف ضجيجًا أبدًا: `importance_tier` إما "important" أو "useful".

## المصدر
النوع: {KIND}
الرابط: {URL}
اسم المصدر: {source_name or HOST}
{"عنوان الصفحة: " + page_title if page_title else ""}
{"ملاحظة عزيز (تعليقه هو، ليست من المصدر): " + note if note else ""}

النص:
\"\"\"{page_text[:14000] if not unreadable else "(تعذّر قراءة محتوى الصفحة)"}\"\"\"

## المطلوب
أعد **JSON فقط** بلا أي نص قبله أو بعده، بهذه المفاتيح:
{{
 "arabic_title": "عنوان عربي محدّد، 6-14 كلمة، لا عناوين عامة",
 "arabic_summary": "ملخص عربي مبسّط لغير المختص، 2-4 جمل",
 "why_it_matters": "جملة أو جملتان عن الأثر الحقيقي — لا إعادة صياغة للملخص",
 "detailed_explanation": "شرح موسّع، فقرات مفصولة بسطرين. إلزامي إن كان التصنيف important.",
 "content_types": ["من القائمة المعتمدة فقط"],
 "domains": ["2-5 من القائمة المعتمدة فقط"],
 "entities": ["الشركات/المنتجات المذكورة صراحةً فقط، أو []"],
 "change_types": ["من القائمة المعتمدة فقط، أو []"],
 "importance_tier": "important أو useful",
 "glossary": [{{"term":"مصطلح","ar":"تعريف مبسّط"}}],
 "original_language": "ar أو en"
}}

القوائم المعتمدة (لا تخرج عنها إطلاقًا):
content_types: {json.dumps(TAXONOMY['content_types'], ensure_ascii=False)}
domains: {json.dumps(TAXONOMY['domains'], ensure_ascii=False)}
change_types: {json.dumps(TAXONOMY['change_types'], ensure_ascii=False)}
"""

ABASE = os.environ.get("ANTHROPIC_BASE", "https://api.anthropic.com")
req = urllib.request.Request(ABASE + "/v1/messages",
    data=json.dumps({"model": MODEL, "max_tokens": 3000,
                     "messages": [{"role": "user", "content": PROMPT}]}).encode(),
    headers={"x-api-key": AKEY, "anthropic-version": "2023-06-01",
             "content-type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    bail("فشل نداء Claude: HTTP %s — %s" % (e.code, e.read().decode()[:300]))
except Exception as e:
    bail("فشل نداء Claude: %s" % e)

txt = "".join(b.get("text", "") for b in resp.get("content", []))
jm = re.search(r'\{.*\}', txt, re.S)
if not jm: bail("لم أستطع قراءة مخرَج Claude كـ JSON")
try:
    card = json.loads(jm.group(0))
except Exception as e:
    bail("مخرَج Claude ليس JSON صالحًا: %s" % e)

def clean(vals, allowed):
    return [v for v in (vals or []) if v in allowed]
card["content_types"] = clean(card.get("content_types"), TAXONOMY["content_types"])
card["domains"]       = clean(card.get("domains"),       TAXONOMY["domains"])
card["change_types"]  = clean(card.get("change_types"),  TAXONOMY["change_types"])
if not card.get("arabic_title") or not card.get("arabic_summary"):
    bail("البطاقة الناتجة ناقصة العنوان أو الملخص")
if card.get("importance_tier") not in ("important", "useful"):
    card["importance_tier"] = "useful"
if not card["domains"]: card["domains"] = ["AI"]

# ---------- 6) بناء السجل ----------
now    = datetime.datetime.now(datetime.timezone.utc)
serial = int(state.get("max_serial", 0)) + 1
cid    = "c%03d" % serial

if KIND == "x" and x_data:
    a = x_data.get("author") or {}
    author = a.get("username") or HOST
    pub = x_data.get("createdAt") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        pub = datetime.datetime.strptime(pub, "%a %b %d %H:%M:%S %z %Y").strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception: pass
    metrics = {"likes": x_data.get("likeCount"), "replies": x_data.get("replyCount"),
               "reposts": x_data.get("retweetCount"), "quotes": x_data.get("quoteCount"),
               "bookmarks": x_data.get("bookmarkCount"), "views": x_data.get("viewCount")}
    original_text = page_text[:1200]
else:
    author, pub, metrics, original_text = HOST, now.strftime("%Y-%m-%dT%H:%M:%SZ"), {}, ""

de = card.get("detailed_explanation") or ""
if unreadable:
    de = ("تعذّر فتح محتوى الصفحة ولم يُقرأ؛ ما ورد أعلاه مبنيّ على العنوان والرابط فقط."
          + ("\n\n" + de if de else ""))
if note:
    de = (de + "\n\n" if de else "") + "ملاحظة عزيز: " + note

rec = {
 "id": cid, "serial": serial, "serial_display": "#%06d" % serial,
 "source_type": KIND, "source_url": URL, "source_native_id": None,
 "source_name": source_name or HOST, "source_site": source_site,
 "author": author, "published_at": pub, "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
 "original_language": card.get("original_language", "en"),
 "is_arabic_source": card.get("original_language") == "ar",
 "arabic_title": card["arabic_title"], "arabic_summary": card["arabic_summary"],
 "detailed_explanation": de, "why_it_matters": card.get("why_it_matters", ""),
 "original_text": original_text,
 "glossary": [g for g in (card.get("glossary") or []) if isinstance(g, dict) and g.get("term")],
 "content_types": card["content_types"], "domains": card["domains"],
 "entities": card.get("entities") or [], "change_types": card["change_types"],
 "importance_tier": card["importance_tier"],
 "importance_score": 88 if card["importance_tier"] == "important" else 62,
 "engagement_score": 0, "metrics": metrics,
 "metrics_captured_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
 "external_links": [], "quoted": None, "cluster_id": None,
 "also_reported": [], "thread_parts": [], "freshness": 100.0,
 "added_via": "issue",
}

# ---------- 7) الكتابة ----------
day   = now.strftime("%Y-%m-%d")
shard = f"inbox-{day}.json"
items = read_json(f"{DATA}/{shard}", default=[])
items.append(rec)
with open(f"{DATA}/{shard}", "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=1)

if shard not in manifest.get("shards", []):
    manifest.setdefault("shards", []).append(shard)
manifest["generated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
st = manifest.setdefault("stats", {})
st["cards"] = int(st.get("cards", 0)) + 1
st["fetched_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
with open(f"{DATA}/manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)

state["max_serial"] = serial
state.setdefault("saved_urls", []).append(norm)
state["updated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
with open(f"{DATA}/state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=1)

with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
    f.write("CARD_ID=%s\nCARD_SERIAL=%s\nCARD_TITLE=%s\n"
            % (cid, rec["serial_display"], rec["arabic_title"].replace("\n", " ")))
log("card %s built: %s" % (rec["serial_display"], rec["arabic_title"]))
