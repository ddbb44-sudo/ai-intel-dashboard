#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سحب تاريخي لمرة واحدة لحساب واحد — يعمل داخل GitHub Actions.

لماذا سكربت منفصل ولا نعيد استخدام daily_pull.py:
  daily_pull مثبّت على نافذة 24 ساعة ويستخدم mode=profileTweets، وهذا الوضع
  يتجاهل مُعامِلات الوقت (كما هو موثّق في daily_pull نفسه). الوضع الوحيد في
  الأكتور الذي يحترم since/until ويتحقق من كل نتيجة هو وضع البحث، فنستخدمه هنا.

ما يبقى مطابقًا لـ daily_pull حرفيًا: قوائم التصنيف (TAX)، وقواعد البرومبت،
وشكل البطاقة، وحساب engagement. الاختلاف الوحيد في البرومبت جملة واحدة تشرح
أن المنشورات تاريخية لا خلال 24 ساعة — بلا ذلك يرفض المصنّف كل شيء لقِدَمه.

المخرَج: شارد مستقل data/backfill-<handle>.json — قابل للتراجع بحذف ملف واحد.
"""
import json, os, re, sys, time, datetime, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

def envs(name, default):
    v = os.environ.get(name)
    return v.strip() if v and v.strip() else default

def envi(name, default):
    try: return int(envs(name, str(default)))
    except (TypeError, ValueError): return default

AKEY   = envs("ANTHROPIC_API_KEY", "")
APIFY  = envs("APIFY_TOKEN", "")
MODEL  = envs("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
ABASE  = envs("ANTHROPIC_BASE", "https://api.anthropic.com")
DATA   = "data"

HANDLE    = envs("BF_HANDLE", "BadwiNew")
DAYS      = envi("BF_DAYS", 60)
DROP_RT   = envs("BF_DROP_RT", "1") == "1"   # قرار عزيز: إسقاط الريتويت
MAX_PULL  = envi("BF_MAX_PULL", 400)         # سقف السحب — الحساب ينشر ~1/يوم
MAX_READ  = envi("BF_MAX_READ", 250)         # سقف التصنيف (حماية تكلفة)
MAX_CARDS = envi("BF_MAX_CARDS", 120)
BATCH     = envi("BATCH", 20)
PARALLEL  = envi("PARALLEL", 4)
POLL_MAX  = envi("POLL_MAX", 1500)

def log(m): print(m, flush=True)

T0 = time.time()
REPORT = {"status": "unknown", "error": "", "handle": HANDLE, "days": DAYS,
          "pulled": 0, "candidates": 0, "read": 0, "accepted": 0,
          "dropped": {}, "titles": [], "batches_failed": 0, "batch_errors": [],
          "cost_estimate_usd": 0.0, "duration_secs": 0}

def write_report():
    REPORT["duration_secs"] = int(time.time() - T0)
    try:
        with open("bf_report.json", "w", encoding="utf-8") as f:
            json.dump(REPORT, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log("report write failed: %s" % e)

def die(m):
    log("FATAL: " + m)
    REPORT["status"] = "failed"; REPORT["error"] = m
    write_report(); sys.exit(1)

if not AKEY:  die("ANTHROPIC_API_KEY غير مضبوط")
if not APIFY: die("APIFY_TOKEN غير مضبوط")

# §33 — نفس المفردات المعتمدة في daily_pull.py حرفيًا. لا تُعدَّل هنا وحدها.
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

state    = rj(f"{DATA}/state.json")
manifest = rj(f"{DATA}/manifest.json")

NOW = datetime.datetime.now(datetime.timezone.utc)
SINCE = NOW - datetime.timedelta(days=DAYS)

# ---------- 1) السحب عبر وضع البحث (يحترم since/until ويتحقق منهما) ----------
def _get(url, timeout=180):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return json.loads(r.read().decode())

BASE = envs("APIFY_BASE", "https://api.apify.com")
ACT  = "xquik~x-tweet-scraper"

query = "from:%s since:%s until:%s" % (
    HANDLE,
    SINCE.strftime("%Y-%m-%d_%H:%M:%S_UTC"),
    (NOW + datetime.timedelta(days=1)).strftime("%Y-%m-%d_%H:%M:%S_UTC"))
log("الاستعلام: %s" % query)

payload = {"mode": "search", "searchTerms": [query], "queryType": "Latest",
           "maxItems": MAX_PULL, "outputVariant": "rich", "fieldStyle": "camelCase"}

req = urllib.request.Request(BASE + "/v2/acts/%s/runs?token=%s" % (ACT, APIFY),
        data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        run = json.loads(r.read().decode())["data"]
except Exception as e:
    die("تعذّر بدء تشغيلة Apify: %s" % e)

rid, dsid = run["id"], run.get("defaultDatasetId")
log("تشغيلة %s بدأت" % rid)
deadline, last = time.time() + POLL_MAX, 0
while time.time() < deadline:
    time.sleep(15)
    try:
        st = _get("%s/v2/actor-runs/%s?token=%s" % (BASE, rid, APIFY))["data"]
    except Exception as e:
        log("poll error: %s" % e); continue
    got = (st.get("stats") or {}).get("itemCount")
    if got and got != last:
        last = got; log("  %d عنصرًا حتى الآن" % got)
    if st.get("status") in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
        dsid = st.get("defaultDatasetId") or dsid
        if st["status"] != "SUCCEEDED":
            die("التشغيلة انتهت بحالة %s" % st["status"])
        break
else:
    die("التشغيلة لم تنتهِ خلال %d دقيقة" % (POLL_MAX // 60))

raw, offset = [], 0
while True:
    page = _get("%s/v2/datasets/%s/items?token=%s&clean=true&limit=1000&offset=%d"
                % (BASE, dsid, APIFY, offset))
    if not page: break
    raw.extend(page); offset += len(page)
    if len(page) < 1000: break

log("سُحب %d منشورًا" % len(raw))
REPORT["pulled"] = len(raw)
if not raw: die("لم يُعد Apify أي منشور لهذا الحساب في النافذة المطلوبة")

# ---------- 2) التنظيف ----------
def parse_dt(s):
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            d = datetime.datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
        except Exception: pass
    return None

recent = set(state.get("recent_ids") or [])
cands = []
d_seen = d_reply = d_rt = d_short = d_old = d_other = 0
for t in raw:
    tid = str(t.get("id") or "")
    if not tid: continue
    a = t.get("author") or {}
    # وضع البحث قد يعيد منشورات من حسابات أخرى إن التقط الاستعلام شيئًا؛ نتحقق
    if (a.get("username") or "").lower() != HANDLE.lower(): d_other += 1; continue
    if tid in recent: d_seen += 1; continue
    if t.get("isReply"): d_reply += 1; continue
    txt = ((t.get("noteTweet") or {}).get("text") or t.get("text") or "").strip()
    if DROP_RT and txt.startswith("RT @"): d_rt += 1; continue
    if len(txt) < 40: d_short += 1; continue
    d = parse_dt(t.get("createdAt") or "")
    if not d or d < SINCE: d_old += 1; continue
    cands.append({
      "id": tid, "handle": a.get("username") or HANDLE, "name": a.get("name") or "",
      "created": d.strftime("%Y-%m-%dT%H:%M:%SZ"), "lang": t.get("lang") or "",
      "text": txt[:1400], "url": t.get("url") or "",
      "m": {"likes": t.get("likeCount"), "replies": t.get("replyCount"),
            "reposts": t.get("retweetCount"), "quotes": t.get("quoteCount"),
            "bookmarks": t.get("bookmarkCount"), "views": t.get("viewCount")},
      "q": ((t.get("quotedTweet") or {}).get("text") or "")[:400],
      "links": [u.get("expandedUrl") for u in ((t.get("entities") or {}).get("urls") or [])
                if isinstance(u, dict) and u.get("expandedUrl")][:4],
    })

REPORT["dropped"] = {"حساب آخر": d_other, "مسحوب سابقًا": d_seen, "ردود": d_reply,
                     "ريتويت": d_rt, "بلا نص كافٍ": d_short, "خارج النافذة": d_old}
REPORT["candidates"] = len(cands)
log("بعد التنظيف: %d مرشحًا — %s" % (len(cands), json.dumps(REPORT["dropped"], ensure_ascii=False)))
if not cands:
    REPORT["status"] = "nothing"; write_report()
    log("لا مرشح بعد التنظيف"); sys.exit(0)

cands.sort(key=lambda c: c["created"])          # الأقدم أولًا — ترتيب زمني للتسلسل
if len(cands) > MAX_READ:
    log("سقف القراءة: %d من %d" % (MAX_READ, len(cands)))
    cands = cands[-MAX_READ:]                    # الأحدث عند لمس السقف
REPORT["read"] = len(cands)

# ---------- 3) التصنيف — نفس قواعد daily_pull، مع سطر واحد يشرح أنها تاريخية ----------
HEAD = """أنت محرّر «مركز المعرفة — الذكاء الاصطناعي»، لوحة عربية يملكها عزيز.

تصلك منشورات من حساب واحد على X نُشرت خلال آخر %d يومًا (أرشيف تاريخي لا أخبار
اليوم). **لا ترفض منشورًا لأنه قديم** — احكم على قيمته المعرفية في ذاتها كما لو
قرأها القارئ اليوم. أسقط ما فقد قيمته فعلًا (إعلان مقاعد دورة انتهت، عدّ تنازلي)
لا ما مضى عليه وقت وهو نافع.

## قواعد غير قابلة للتفاوض
- **أغلب المنشورات لا تستحق بطاقة.** أسقط: التهاني، النكات، الترويج الفارغ،
  الآراء بلا محتوى، الإعلانات الشخصية، وكل ما لا يضيف معرفة.
- **لا تخمّن ولا تخترع.** كل ما تكتبه مستخرج من نص المنشور فقط. لا أرقام ولا روابط
  ولا أسماء غير واردة فيه.
- العربية للشرح، والمصطلحات التقنية تبقى إنجليزية: MCP, API, Agent, Embedding,
  Vector Database, Fine-tuning, RAG, Prompt, Skill, Benchmark, Token, Context Window.
- اكتب كمحلّل لا كمسوّق: ماذا يقول المصدر، ولماذا يهم.

## المخرَج
أعد **JSON فقط**: مصفوفة فيها عنصر لكل منشور بنفس ترتيب المدخلات:
{"id":"معرّف المنشور","keep":true|false,"reason":"سبب الرفض بإيجاز إن keep=false",
 "cluster_id":null,"duplicate_of":null,
 "arabic_title":"عنوان محدّد 6-14 كلمة","arabic_summary":"2-4 جمل لغير المختص",
 "why_it_matters":"جملة أو جملتان عن الأثر الحقيقي",
 "detailed_explanation":"شرح موسّع بفقرات مفصولة بسطرين — إلزامي إن كان التصنيف important",
 "content_type":"واحد فقط","tool_types":[],"domains":[],"entities":[],"change_types":[],
 "importance_tier":"important|useful","glossary":[{"term":"","ar":""}]}
حين keep=false اكتف بـ id و keep و reason.

## التصنيف — ثلاثة محاور، والإفراط في الوسم خطأ
**نوع المحتوى: واحد فقط.** إن أعلن المنشور شيئًا جديدًا فهو «إصدار» لا «خبر».
إن كان جوهره تعليم القارئ كيف يفعل شيئًا فهو «شرح» لا «أداة». «خبر» للسوق:
استحواذ · تمويل · سياسة · تعطّل.

**نوع الأداة: صفر إلى اثنين، وفقط مع «أداة» أو «إصدار».** `MCP` لخادم أو موصّل MCP
تحديدًا لا لمجرد ذكر الكلمة، وكذلك `Agent`. `Plugin` لإضافة داخل برنامج قائم.
`نموذج` لنموذج ذكاء اصطناعي. إن لم تنطبق واحدة بوضوح فأعد [].

**المجال: رئيسي واحد + ثانٍ فقط إن كان جمهوره سيبحث عن البطاقة فعلًا** ولو لم تكن
موضوعها. اثنان كحد أقصى.

**القاعدة الحاكمة: الوسم الذي لا يمكن الدفاع عنه من نص المنشور لا يوضع.**

## القوائم المعتمدة (لا تخرج عنها إطلاقًا)
""" % DAYS + ("content_type (واحد): " + json.dumps(TAX['content_types'], ensure_ascii=False) + "\n"
     + "tool_types (0-2): "     + json.dumps(TAX['tool_types'],    ensure_ascii=False) + "\n"
     + "domains (1-2): "        + json.dumps(TAX['domains'],       ensure_ascii=False) + "\n"
     + "change_types: "         + json.dumps(TAX['change_types'],  ensure_ascii=False) + "\n")

def claude(prompt, max_tokens=8000):
    req = urllib.request.Request(ABASE + "/v1/messages",
        data=json.dumps({"model": MODEL, "max_tokens": max_tokens,
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"x-api-key": AKEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"}, method="POST")
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            last = "HTTP %s — %s" % (e.code, body)
            if e.code in (429, 500, 502, 503, 529):
                time.sleep(10 * (attempt + 1)); continue
            break
        except Exception as e:
            last = str(e); time.sleep(6 * (attempt + 1))
    raise RuntimeError(last or "unknown")

def clean(v, allowed): return [x for x in (v or []) if x in allowed]

def run_batch(args):
    n, part = args
    payload = [{"id": c["id"], "account": "@" + c["handle"], "date": c["created"],
                "lang": c["lang"], "metrics": c["m"], "links": c["links"],
                "text": c["text"], "quoted": c["q"]} for c in part]
    prompt = HEAD + "\n## المنشورات\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    last = ""
    for attempt in (1, 2):
        try:
            resp = claude(prompt)
            txt = "".join(b.get("text", "") for b in resp.get("content", []))
            mm = re.search(r'\[.*\]', txt, re.S)
            if not mm:
                last = "مخرَج غير قابل للقراءة"; time.sleep(5); continue
            arr = json.loads(mm.group(0))
            log("دفعة %d: %d قرارًا (محاولة %d)" % (n, len(arr), attempt))
            return n, arr, ""
        except Exception as e:
            last = str(e)[:200]
            log("دفعة %d محاولة %d فشلت: %s" % (n, attempt, last))
            time.sleep(8)
    return n, None, last

chunks = [(i//BATCH + 1, cands[i:i+BATCH]) for i in range(0, len(cands), BATCH)]
decisions, batches_failed, batch_errors = {}, 0, []
with ThreadPoolExecutor(max_workers=PARALLEL) as ex:
    for n, arr, err in ex.map(run_batch, chunks):
        if arr is None:
            batches_failed += 1; batch_errors.append("دفعة %d: %s" % (n, err)); continue
        for d in arr:
            if isinstance(d, dict) and d.get("id"): decisions[str(d["id"])] = d

REPORT["batches_failed"] = batches_failed; REPORT["batch_errors"] = batch_errors
kept = [c for c in cands if decisions.get(c["id"], {}).get("keep")]
log("قُبل %d من %d قُرئت (%d دفعة فشلت)" % (len(kept), len(cands), batches_failed))
if not kept:
    REPORT["status"] = "nothing"; write_report()
    log("لا بطاقة تستحق"); sys.exit(0)
kept = kept[:MAX_CARDS]

# ---------- 4) البطاقات ----------
def eng(m, followers=None):
    import math
    lk, rp, rt, qt, bm, vw = [(m.get(k) or 0) for k in
        ("likes","replies","reposts","quotes","bookmarks","views")]
    raw_ = lk + 2*bm + 3*rt + 2*qt + 0.5*rp
    f = followers or 5000
    return max(0, min(100, round((math.log10(raw_/max(f,500)*10000 + 1)/4.0)*100)))

serial = int(state.get("max_serial", 0))
out = []
for c in kept:
    d = decisions[c["id"]]
    _ct_raw = d.get("content_type") or d.get("content_types")
    if isinstance(_ct_raw, str): _ct_raw = [_ct_raw]
    ct  = clean(_ct_raw, TAX["content_types"])[:1]
    tl  = clean(d.get("tool_types"), TAX["tool_types"])[:2]
    dom = clean(d.get("domains"),    TAX["domains"])[:2]
    chg = clean(d.get("change_types"), TAX["change_types"])
    if not dom:
        log("تنبيه: بطاقة بلا مجال معتمد (%s) — تُترك بلا مجال بدل التخمين" % c["id"])
    tier = d.get("importance_tier") if d.get("importance_tier") in ("important","useful") else "useful"
    title = (d.get("arabic_title") or "").strip()
    summ  = (d.get("arabic_summary") or "").strip()
    if not title or not summ:
        log("تخطّي %s: بطاقة بلا عنوان أو ملخص" % c["id"]); continue
    serial += 1
    out.append({
      "id": "c%03d" % serial, "serial": serial, "serial_display": "#%06d" % serial,
      "source_type": "x", "source_url": c["url"] or ("https://x.com/%s/status/%s" % (c["handle"], c["id"])),
      "source_native_id": c["id"], "source_name": c["name"] or c["handle"], "source_site": "x.com",
      "author": c["handle"], "published_at": c["created"],
      "fetched_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
      "original_language": c["lang"] or "en", "is_arabic_source": (c["lang"] == "ar"),
      "arabic_title": title, "arabic_summary": summ,
      "detailed_explanation": d.get("detailed_explanation") or "",
      "why_it_matters": d.get("why_it_matters") or "",
      "original_text": c["text"][:1200],
      "glossary": [g for g in (d.get("glossary") or []) if isinstance(g, dict) and g.get("term")],
      "content_types": ct, "tool_types": tl, "domains": dom,
      "entities": d.get("entities") or [], "change_types": chg,
      "importance_tier": tier, "importance_score": 88 if tier == "important" else 62,
      "engagement_score": eng(c["m"]), "metrics": c["m"],
      "metrics_captured_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
      "external_links": c["links"], "quoted": ({"h": "", "x": c["q"]} if c["q"] else None),
      "cluster_id": d.get("cluster_id"), "also_reported": [],
      "thread_parts": [], "freshness": 100.0, "added_via": "backfill",
    })

if not out: die("لم تنجُ أي بطاقة بعد التحقق")

# ---------- 5) الكتابة ----------
shard = "backfill-%s.json" % HANDLE.lower()
prev  = rj(f"{DATA}/{shard}", [])
have  = {x.get("source_native_id") for x in prev}
prev.extend([o for o in out if o["source_native_id"] not in have])
json.dump(prev, open(f"{DATA}/{shard}", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if shard not in manifest.get("shards", []):
    manifest.setdefault("shards", []).append(shard)
manifest["generated_at"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
st = manifest.setdefault("stats", {})
st["cards"] = int(st.get("cards", 0)) + len(out)
json.dump(manifest, open(f"{DATA}/manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

state["max_serial"] = serial
# كل ما قُرئ يدخل recent_ids — لا المقبول فقط — كي لا تعيد تشغيلة الغد سحبه
state["recent_ids"] = sorted(set(list(recent) + [c["id"] for c in cands]))[-4000:]
lp = state.setdefault("last_id_per_account", {})
newest = max(c["id"] for c in cands)
if not lp.get(HANDLE) or newest > lp[HANDLE]: lp[HANDLE] = newest
state["updated_at"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(state, open(f"{DATA}/state.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

REPORT.update({
  "status": "ok", "accepted": len(out),
  "titles": [{"serial": r["serial_display"], "title": r["arabic_title"],
              "tier": r["importance_tier"], "url": r["source_url"]} for r in out],
  "cost_estimate_usd": round(len(cands) * 0.0028 + len(raw) * 0.00015, 3),
})
write_report()
log("تم: %d بطاقة في %s · التكلفة ≈ $%.3f"
    % (len(out), shard, REPORT["cost_estimate_usd"]))
