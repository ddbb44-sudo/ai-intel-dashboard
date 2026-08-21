#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
السحب اليومي للوحة «مركز المعرفة» — يعمل داخل GitHub Actions، لا يحتاج جهاز عزيز
ولا موصّلات ولا جلسة Claude.

المسار: Apify (آخر 24 ساعة من الحسابات النشطة) ← تنظيف ← تصنيف عبر Claude API
        ← بطاقات عربية ← commit.

مبدأ التصميم: عند أي شك — لا تكتب. والسقوف تُعلَن ولا تُخفى.
"""
import json, os, re, sys, time, datetime, urllib.request, urllib.error, urllib.parse

AKEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()
APIFY = os.environ.get("APIFY_TOKEN", "").strip()
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
ABASE = os.environ.get("ANTHROPIC_BASE", "https://api.anthropic.com")
DATA  = "data"

# سقوف معلنة — تُذكر في التقرير دائمًا
WINDOW_HOURS   = int(os.environ.get("WINDOW_HOURS", "24"))
PER_ACCOUNT    = int(os.environ.get("PER_ACCOUNT", "25"))
MAX_READ       = int(os.environ.get("MAX_READ", "150"))     # أقصى ما يُعرض على النموذج
MAX_CARDS      = int(os.environ.get("MAX_CARDS", "40"))
BATCH          = int(os.environ.get("BATCH", "20"))
HANDLE_CHUNK   = 20

def log(m): print(m, flush=True)
def die(m):
    log("FATAL: " + m)
    with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
        f.write("DAILY_ERROR=%s\n" % m.replace("\n", " ")[:300])
    sys.exit(0)   # لا نُفشل الـ workflow: نُبلغ ونخرج بلا كتابة

if not AKEY:  die("ANTHROPIC_API_KEY غير مضبوط")
if not APIFY: die("APIFY_TOKEN غير مضبوط")

TAX = {
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

def rj(p, d=None):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError:
        if d is not None: return d
        raise

accounts = rj("accounts.json")
state    = rj(f"{DATA}/state.json")
manifest = rj(f"{DATA}/manifest.json")

handles = [a["handle"] for a in accounts.get("accounts", []) if a.get("active", True)]
if not handles: die("لا حسابات نشطة في accounts.json")
log("accounts: %d نشطًا" % len(handles))

# ---------- 1) السحب ----------
def apify_profiles(hs):
    payload = {"mode": "profileTweets", "twitterHandles": hs,
               "maxItemsPerTarget": PER_ACCOUNT,
               "outputVariant": "rich", "fieldStyle": "camelCase"}
    base = os.environ.get("APIFY_BASE", "https://api.apify.com")
    url = (base + "/v2/acts/xquik~x-tweet-scraper/"
           "run-sync-get-dataset-items?token=" + APIFY)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
            method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())

raw, failed_chunks = [], 0
for i in range(0, len(handles), HANDLE_CHUNK):
    chunk = handles[i:i+HANDLE_CHUNK]
    try:
        got = apify_profiles(chunk)
        raw.extend(got)
        log("apify chunk %d: %d حسابًا ← %d منشورًا" % (i//HANDLE_CHUNK + 1, len(chunk), len(got)))
    except Exception as e:
        failed_chunks += 1
        log("apify chunk %d FAILED: %s" % (i//HANDLE_CHUNK + 1, e))
    time.sleep(2)

if not raw: die("Apify لم يُعد أي منشور (فشل %d دفعة)" % failed_chunks)
log("إجمالي المسحوب: %d" % len(raw))

# ---------- 2) التنظيف ----------
NOW = datetime.datetime.now(datetime.timezone.utc)
CUT = NOW - datetime.timedelta(hours=WINDOW_HOURS)

def parse_dt(s):
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            d = datetime.datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
        except Exception: pass
    return None

recent = set(state.get("recent_ids") or [])
cands, drop_old, drop_reply, drop_seen, drop_empty = [], 0, 0, 0, 0
for t in raw:
    tid = str(t.get("id") or "")
    if not tid: continue
    if tid in recent: drop_seen += 1; continue
    if t.get("isReply"): drop_reply += 1; continue
    txt = ((t.get("noteTweet") or {}).get("text") or t.get("text") or "").strip()
    if len(txt) < 40: drop_empty += 1; continue
    d = parse_dt(t.get("createdAt") or "")
    if not d or d < CUT: drop_old += 1; continue     # الأكتور يتجاهل مُعامِلات الوقت — نرشّح هنا
    a = t.get("author") or {}
    cands.append({
      "id": tid, "handle": a.get("username") or "", "name": a.get("name") or "",
      "created": d.strftime("%Y-%m-%dT%H:%M:%SZ"), "lang": t.get("lang") or "",
      "text": txt[:1400], "url": t.get("url") or "",
      "m": {"likes": t.get("likeCount"), "replies": t.get("replyCount"),
            "reposts": t.get("retweetCount"), "quotes": t.get("quoteCount"),
            "bookmarks": t.get("bookmarkCount"), "views": t.get("viewCount")},
      "q": ((t.get("quotedTweet") or {}).get("text") or "")[:400],
      "links": [u.get("expandedUrl") for u in ((t.get("entities") or {}).get("urls") or [])
                if isinstance(u, dict) and u.get("expandedUrl")][:4],
    })

log("بعد التنظيف: %d مرشحًا (خارج النافذة %d · ردود %d · مقروء سابقًا %d · بلا نص %d)"
    % (len(cands), drop_old, drop_reply, drop_seen, drop_empty))
if not cands:
    with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
        f.write("DAILY_NOTHING=1\n")
    log("لا جديد اليوم"); sys.exit(0)

# ترتيب بالتفاعل ثم قصّ عند السقف — والسقف يُعلَن
cands.sort(key=lambda c: -( (c["m"].get("likes") or 0) + 2*(c["m"].get("bookmarks") or 0)
                            + 3*(c["m"].get("reposts") or 0) ))
capped = max(0, len(cands) - MAX_READ)
cands = cands[:MAX_READ]

# ---------- 3) التصنيف ----------
HEAD = """أنت محرّر «مركز المعرفة — الذكاء الاصطناعي»، لوحة عربية يملكها عزيز.
تصلك منشورات من X خلال آخر 24 ساعة. احكم على كل واحد، واكتب بطاقة عربية لما يستحق فقط.

## قواعد غير قابلة للتفاوض
- **أغلب المنشورات لا تستحق بطاقة.** النسبة التاريخية للقبول ≈ 40٪. أسقط: التهاني، النكات،
  الترويج الفارغ، الآراء بلا محتوى، الإعلانات الشخصية، وكل ما لا يضيف معرفة.
- **لا تخمّن ولا تخترع.** كل ما تكتبه مستخرج من نص المنشور فقط. لا أرقام ولا روابط ولا أسماء
  غير واردة فيه.
- العربية للشرح، والمصطلحات التقنية تبقى إنجليزية: MCP, API, Agent, Embedding, Vector Database,
  Fine-tuning, RAG, Prompt, Skill, Benchmark, Token, Context Window.
- اكتب كمحلّل لا كمسوّق: ماذا يقول المصدر، ولماذا يهم.
- خبر واحد نقلته عدة حسابات = بطاقة واحدة فقط، وأعطِ الباقي نفس `cluster_id` مع `keep:false`
  و`duplicate_of` يحمل معرّف المنشور الذي أبقيته.

## المخرَج
أعد **JSON فقط**: مصفوفة فيها عنصر لكل منشور بنفس ترتيب المدخلات:
{"id":"معرّف المنشور","keep":true|false,"reason":"سبب الرفض بإيجاز إن keep=false",
 "cluster_id":null,"duplicate_of":null,
 "arabic_title":"عنوان محدّد 6-14 كلمة","arabic_summary":"2-4 جمل لغير المختص",
 "why_it_matters":"جملة أو جملتان عن الأثر الحقيقي",
 "detailed_explanation":"شرح موسّع بفقرات مفصولة بسطرين — إلزامي إن كان التصنيف important",
 "content_types":[],"domains":[],"entities":[],"change_types":[],
 "importance_tier":"important|useful","glossary":[{"term":"","ar":""}]}
حين keep=false اكتف بـ id و keep و reason (و duplicate_of/cluster_id إن كان تكرارًا).

## القوائم المعتمدة (لا تخرج عنها)
""" + ("content_types: " + json.dumps(TAX['content_types'], ensure_ascii=False) + "\n"
     + "domains: "       + json.dumps(TAX['domains'],       ensure_ascii=False) + "\n"
     + "change_types: "  + json.dumps(TAX['change_types'],  ensure_ascii=False) + "\n")

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

decisions, batches_failed = {}, 0
for i in range(0, len(cands), BATCH):
    part = cands[i:i+BATCH]
    payload = [{"id": c["id"], "account": "@" + c["handle"], "date": c["created"],
                "lang": c["lang"], "metrics": c["m"], "links": c["links"],
                "text": c["text"], "quoted": c["q"]} for c in part]
    try:
        resp = claude(HEAD + "\n## المنشورات\n" + json.dumps(payload, ensure_ascii=False, indent=1))
    except Exception as e:
        batches_failed += 1; log("batch %d FAILED: %s" % (i//BATCH + 1, e)); continue
    txt = "".join(b.get("text", "") for b in resp.get("content", []))
    mm = re.search(r'\[.*\]', txt, re.S)
    if not mm:
        batches_failed += 1; log("batch %d: مخرَج غير قابل للقراءة" % (i//BATCH + 1)); continue
    try:
        arr = json.loads(mm.group(0))
    except Exception as e:
        batches_failed += 1; log("batch %d: JSON غير صالح — %s" % (i//BATCH + 1, e)); continue
    for d in arr:
        if isinstance(d, dict) and d.get("id"): decisions[str(d["id"])] = d
    log("batch %d: %d قرارًا" % (i//BATCH + 1, len(arr)))

kept = [c for c in cands if decisions.get(c["id"], {}).get("keep")]
log("قُبل %d من %d قُرئت (%d دفعة فشلت)" % (len(kept), len(cands), batches_failed))
if not kept:
    with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
        f.write("DAILY_NOTHING=1\n")
    log("لا بطاقة تستحق اليوم"); sys.exit(0)

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
out, dup_merged = [], 0
for c in kept:
    d = decisions[c["id"]]
    ct  = clean(d.get("content_types"),  TAX["content_types"])
    dom = clean(d.get("domains"),        TAX["domains"]) or ["AI"]
    chg = clean(d.get("change_types"),   TAX["change_types"])
    tier = d.get("importance_tier") if d.get("importance_tier") in ("important","useful") else "useful"
    title = (d.get("arabic_title") or "").strip()
    summ  = (d.get("arabic_summary") or "").strip()
    if not title or not summ:
        log("تخطّي %s: بطاقة بلا عنوان أو ملخص" % c["id"]); continue
    serial += 1
    others = [o for o in cands
              if decisions.get(o["id"], {}).get("duplicate_of") == c["id"] and o["id"] != c["id"]]
    dup_merged += len(others)
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
      "content_types": ct, "domains": dom, "entities": d.get("entities") or [], "change_types": chg,
      "importance_tier": tier, "importance_score": 88 if tier == "important" else 62,
      "engagement_score": eng(c["m"]), "metrics": c["m"],
      "metrics_captured_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
      "external_links": c["links"], "quoted": ({"h": "", "x": c["q"]} if c["q"] else None),
      "cluster_id": d.get("cluster_id"),
      "also_reported": [{"author": o["handle"],
                         "url": o["url"] or ("https://x.com/%s/status/%s" % (o["handle"], o["id"]))}
                        for o in others],
      "thread_parts": [], "freshness": 100.0, "added_via": None,
    })

if not out: die("لم تنجُ أي بطاقة بعد التحقق")

# ---------- 5) الكتابة ----------
day   = NOW.strftime("%Y-%m-%d")
shard = "%s.json" % day
prev  = rj(f"{DATA}/{shard}", [])
prev.extend(out)
json.dump(prev, open(f"{DATA}/{shard}", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if shard not in manifest.get("shards", []): manifest.setdefault("shards", []).append(shard)
manifest["generated_at"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
st = manifest.setdefault("stats", {})
st["cards"] = int(st.get("cards", 0)) + len(out)
st["fetched_at"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
st["window"] = "آخر %d ساعة" % WINDOW_HOURS
json.dump(manifest, open(f"{DATA}/manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

state["max_serial"] = serial
ids_today = [c["id"] for c in cands]
state["recent_ids"] = sorted(set(list(recent) + ids_today))[-4000:]
for c in cands:
    prevlast = state.setdefault("last_id_per_account", {}).get(c["handle"], "")
    if not prevlast or c["id"] > prevlast:
        state["last_id_per_account"][c["handle"]] = c["id"]
state["updated_at"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(state, open(f"{DATA}/state.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

report = ("سُحب %d · مرشّحون %d · قُرئ %d · قُبل %d · دُمج %d"
          % (len(raw), len(cands) + capped, len(cands), len(out), dup_merged))
if capped:         report += " · **لم يُقرأ %d** (سقف MAX_READ=%d)" % (capped, MAX_READ)
if batches_failed: report += " · %d دفعة تصنيف فشلت" % batches_failed
if failed_chunks:  report += " · %d دفعة سحب فشلت" % failed_chunks

with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
    f.write("DAILY_COUNT=%d\nDAILY_DAY=%s\nDAILY_REPORT=%s\n" % (len(out), day, report))
log("DONE — " + report)
