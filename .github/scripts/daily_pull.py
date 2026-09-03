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
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dedupe
from jsontools import salvage

def envs(name, default):
    """GitHub Actions يمرّر المتغيّر غير المضبوط كنص فارغ لا كغائب،
    فـ os.environ.get(name, default) يعيد '' ويكسر أي تحويل. هذه تعالجها."""
    v = os.environ.get(name)
    return v.strip() if v and v.strip() else default

def envi(name, default):
    try: return int(envs(name, str(default)))
    except (TypeError, ValueError): return default

AKEY  = envs("ANTHROPIC_API_KEY", "")
APIFY = envs("APIFY_TOKEN", "")
MODEL = envs("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
ABASE = envs("ANTHROPIC_BASE", "https://api.anthropic.com")
DATA  = "data"

# سقوف معلنة — تُذكر في التقرير دائمًا
WINDOW_HOURS   = envi("WINDOW_HOURS", 24)
PER_ACCOUNT    = envi("PER_ACCOUNT", 25)
MAX_READ       = envi("MAX_READ", 250)      # سقف حماية للتكلفة — يوم عادي ≈ 101
MAX_CARDS      = envi("MAX_CARDS", 60)
BATCH          = envi("BATCH", 20)
PARALLEL       = envi("PARALLEL", 4)    # دفعات التصنيف بالتوازي
POLL_MAX       = envi("POLL_MAX", 1500)   # 25 دقيقة كحد أقصى للاستطلاع

def log(m): print(m, flush=True)

REPORT = {"status": "unknown", "error": "", "started_at": None, "day": "",
          "pulled": 0, "accounts_seen": 0, "accounts_total": 0,
          "missing": [], "missing_expected": [], "missing_unexpected": [],
          "candidates": 0, "read": 0, "capped": 0, "accepted": 0, "merged": 0,
          "batches_total": 0, "batches_failed": 0, "titles": [],
          "dropped": {}, "duration_secs": 0, "cost_estimate_usd": 0.0}

def write_report():
    REPORT["duration_secs"] = int(time.time() - T0)
    try:
        with open("report.json", "w", encoding="utf-8") as f:
            json.dump(REPORT, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log("report write failed: %s" % e)

def die(m):
    log("FATAL: " + m)
    REPORT["status"] = "failed"; REPORT["error"] = m
    write_report()
    with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
        f.write("DAILY_ERROR=%s\n" % m.replace("\n", " ")[:300])
    sys.exit(0)   # لا نُفشل الـ workflow: التقرير هو المخرَج

T0 = time.time()

if not AKEY:  die("ANTHROPIC_API_KEY غير مضبوط")
if not APIFY: die("APIFY_TOKEN غير مضبوط")

# §33 — المفردات المعتمدة. أي تغيير هنا يجب أن يوازيه تغيير في
# .github/scripts/taxonomy.py و DECLARED في tpl_js.html، ثم تشغيل retag.
TAX = {
 "content_types": ['إصدار','أداة','شرح','تجربة','بحث وقياس','رأي','خبر'],
 "tool_types":    ['MCP','Skill','Agent','Plugin','Prompt','API/SDK','تطبيق','نموذج'],
 "domains": ['برمجة وهندسة','أعمال وإدارة','تصميم وواجهات','تسويق ومحتوى','نماذج وLLM',
   'بيانات وتحليلات','بحث وتعليم','إنتاجية شخصية','فيديو وصوت','أمن سيبراني',
   'روبوتات وعتاد','صحة','إسلامي'],
 "audience_topics": ['سكيل','أداة يستعملها','بنية الوكلاء','نموذج','عالم AI عام','خارج الاهتمام'],
 "user_tools": ['ChatGPT','OpenAI','Codex','Sora','Claude','Claude Code','Cowork','Anthropic',
   'Gemini','Google AI Studio','AI Studio','NotebookLM','GitHub','Cursor','Vercel','Ollama',
   'Netlify','Apify','Chrome','Google Docs','Google Drive','Gmail','Trello','WordPress',
   'Chatbase','المكتبة الشاملة'],
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
REPORT["accounts_total"] = len(handles)
REPORT["day"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
REPORT["started_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
EXPECTED_QUIET = {a["handle"] for a in accounts.get("accounts", [])
                  if a.get("note") or not a.get("active_30d", True)}

# ---------- 1) السحب ----------
def _get(url, timeout=180):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return json.loads(r.read().decode())

APIFY_BASE_URL = envs("APIFY_BASE", "https://api.apify.com")

def apify_run(hs, label):
    """تشغيلة واحدة غير متزامنة ثم استطلاع.
    قياس حقيقي (21 أغسطس): تشغيلة واحدة بـ69 حسابًا = 1,648 تغريدة في ~9 دقائق،
    مقابل 225 تغريدة في 24 دقيقة حين قُسّمت إلى دفعات — لأن كل دفعة تشغيلة مستقلة
    بوقت إقلاع خاص، والتقسيم يضاعف الكلفة بلا فائدة."""
    payload = {"mode": "profileTweets", "twitterHandles": hs,
               "maxItemsPerTarget": PER_ACCOUNT,
               "outputVariant": "rich", "fieldStyle": "camelCase"}
    base = APIFY_BASE_URL
    if "127.0.0.1" in base or "localhost" in base:      # وضع الاختبار المحلي
        req = urllib.request.Request(
            base + "/v2/acts/xquik~x-tweet-scraper/run-sync-get-dataset-items?token=" + APIFY,
            data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    req = urllib.request.Request(base + "/v2/acts/xquik~x-tweet-scraper/runs?token=" + APIFY,
            data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        run = json.loads(r.read().decode())["data"]
    rid, dsid = run["id"], run.get("defaultDatasetId")
    log("  %s: تشغيلة %s بدأت (%d حسابًا)" % (label, rid, len(hs)))
    deadline = time.time() + POLL_MAX
    last = 0
    while time.time() < deadline:
        time.sleep(15)
        try:
            st = _get("%s/v2/actor-runs/%s?token=%s" % (base, rid, APIFY))["data"]
        except Exception as e:
            log("  poll error: %s" % e); continue
        got = (st.get("stats") or {}).get("itemCount")
        if got and got != last:
            last = got; log("  %s: %d عنصرًا حتى الآن" % (label, got))
        status = st.get("status")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            dsid = st.get("defaultDatasetId") or dsid
            if status != "SUCCEEDED":
                raise RuntimeError("تشغيلة %s انتهت بحالة %s" % (rid, status))
            break
    else:
        raise RuntimeError("تشغيلة %s لم تنتهِ خلال %d دقيقة" % (rid, POLL_MAX // 60))
    items, offset = [], 0
    while True:
        page = _get("%s/v2/datasets/%s/items?token=%s&clean=true&limit=1000&offset=%d"
                    % (base, dsid, APIFY, offset))
        if not page: break
        items.extend(page); offset += len(page)
        if len(page) < 1000: break
    return items

# تشغيلة واحدة لكل الحسابات. إن فشلت، نصفان — فلا يسقط كل شيء بسبب عطل واحد.
raw, failed_handles = [], []
try:
    raw = apify_run(handles, "الكل")
except Exception as e:
    log("التشغيلة الموحّدة فشلت: %s — أُقسّمها نصفين" % e)
    mid = len(handles) // 2
    for part, name in ((handles[:mid], "النصف الأول"), (handles[mid:], "النصف الثاني")):
        try:
            raw.extend(apify_run(part, name))
        except Exception as e2:
            log("%s فشل: %s" % (name, e2))
            failed_handles.extend(part)

if not raw: die("Apify لم يُعد أي منشور — لم تُسحب أي حسابات")
seen_accounts = {((t.get("author") or {}).get("username") or "").lower() for t in raw}
seen_accounts.discard("")
log("إجمالي المسحوب: %d من %d حسابًا" % (len(raw), len(seen_accounts)))
REPORT["pulled"] = len(raw); REPORT["accounts_seen"] = len(seen_accounts)

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
REPORT["dropped"] = {"خارج النافذة": drop_old, "ردود": drop_reply,
                     "مقروء سابقًا": drop_seen, "بلا نص كافٍ": drop_empty}
REPORT["candidates"] = len(cands)
if not cands:
    REPORT["status"] = "nothing"; write_report()
    with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
        f.write("DAILY_NOTHING=1\n")
    log("لا جديد اليوم"); sys.exit(0)

# ---------- الاختيار عند السقف: بالتناوب لا بالتفاعل ----------
# الترتيب بالتفاعل الخام كان يعني أن حسابًا عربيًا صغيرًا لا يهزم OpenAI أبدًا،
# فيُقصى كلما لُمس السقف. البديل: جولة لكل حساب بالتناوب — كل حساب يقدّم أفضل
# منشور له قبل أن يأخذ أي حساب منشوره الثاني.
def _eng(c):
    m = c["m"]
    return (m.get("likes") or 0) + 2*(m.get("bookmarks") or 0) + 3*(m.get("reposts") or 0)

capped, trimmed_accounts = 0, []
if len(cands) > MAX_READ:
    by_acc = {}
    for c in cands:
        by_acc.setdefault(c["handle"], []).append(c)
    for h in by_acc:
        by_acc[h].sort(key=lambda c: -_eng(c))          # الأقوى داخل كل حساب أولًا
    order = sorted(by_acc)                               # ترتيب ثابت لا عشوائي
    picked, depth = [], 0
    while len(picked) < MAX_READ and any(len(v) > depth for v in by_acc.values()):
        for h in order:
            if len(by_acc[h]) > depth and len(picked) < MAX_READ:
                picked.append(by_acc[h][depth])
        depth += 1
    kept_ids = {c["id"] for c in picked}
    for h in order:
        left = len([c for c in by_acc[h] if c["id"] not in kept_ids])
        if left: trimmed_accounts.append("%s(%d)" % (h, left))
    capped = len(cands) - len(picked)
    cands = picked
    log("لُمس السقف: قُرئ %d وتُرك %d — بالتناوب على %d حسابًا" % (len(cands), capped, len(order)))

REPORT["capped"] = capped; REPORT["read"] = len(cands)
REPORT["trimmed_accounts"] = trimmed_accounts

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
 "audience_topic":"واحد فقط — انظر المحور الحاكم أدناه",
 "content_type":"واحد فقط","tool_types":[],"domains":[],"entities":[],"change_types":[],
 "importance_tier":"important|useful","glossary":[{"term":"","ar":""}]}
حين keep=false اكتف بـ id و keep و reason (و duplicate_of/cluster_id إن كان تكرارًا).

## التصنيف — المحور الحاكم أولًا
**`audience_topic`: قيمة واحدة، وهي أهمّ حقل في البطاقة.**
اللوحة تخصّ عزيز لا عموم القرّاء، فالسؤال ليس «كم يهمّ هذا الخبرُ العالم؟»
بل **«هل يمسّ هذا عملَ عزيز؟»**. اختر **أعلى درجة تنطبق** لا أوسعها:

1. **سكيل** — ملفات Skills: بناؤها · عيوبها · إصداراتها · أدلّتها. أولويته الأولى،
   ولو جاءت في صورة دراسة أو رأي. «دراسة: ٩١٫٨٪ من ملفات Skills فيها عيوب» = سكيل.
2. **أداة يستعملها** — الأداة من القائمة المعتمدة أدناه، والخبر يمسّها هي:
   ميزة · تسعير · حدّ استخدام · تعطّل · ثغرة أمنية · طريقة استعمال.
3. **بنية الوكلاء** — MCP أو Agent أو Plugin بوصفها بنيةً، لا أداةً بعينها.
4. **نموذج** — إصدار نموذج أو قياس قدراته، ولا يقع فيما فوقه.
5. **عالم AI عام** — يهمّ عمومًا ولا يمسّ عمله: أبحاث بعيدة · روبوتات ·
   عتاد · أثر مجتمعي · أخبار شركات لا يستعملها.
6. **خارج الاهتمام** — استحواذ · تمويل · تقييم شركات · أسهم · اكتتاب · دعاوى ·
   تعيينات · صراعات شركات. **ويُستثنى فيرتفع:** التسعير · الإيقاف والتعطّل ·
   أمن أداةٍ يستعملها. «Anthropic تُقيَّم بتريليونين» = خارج الاهتمام،
   و«ثغرة في Claude Code» = أداة يستعملها.

**الفرق بين ١ و٢ حين يجتمعان:** «Skill جديد لـ Claude» = سكيل (الأعلى يفوز).
**والشكل لا يقرّر الدرجة:** الدرجة موضوعٌ لا صيغة.

## بقية المحاور — والإفراط في الوسم خطأ
**نوع المحتوى: واحد فقط.** إن أعلن المنشور شيئًا جديدًا فهو «إصدار» لا «خبر».
إن كان جوهره تعليم القارئ كيف يفعل شيئًا فهو «شرح» لا «أداة». «خبر» للسوق:
استحواذ · تمويل · سياسة · تعطّل.

**نوع الأداة: صفر إلى اثنين، وفقط مع «أداة» أو «إصدار».** `MCP` لخادم أو موصّل MCP
تحديدًا لا لمجرد ذكر الكلمة، وكذلك `Agent`. `Plugin` لإضافة داخل برنامج قائم.
`نموذج` لنموذج ذكاء اصطناعي. إن لم تنطبق واحدة بوضوح فأعد [].

**المجال: رئيسي واحد + ثانٍ فقط إن كان جمهوره سيبحث عن البطاقة فعلًا** ولو لم تكن
موضوعها — أداة توليد فيديو يريدها المصمّم أيضًا، وتغيير في احتساب المشاهدات
يهم صانع المحتوى. اثنان كحد أقصى.

**القاعدة الحاكمة: الوسم الذي لا يمكن الدفاع عنه من نص المنشور لا يوضع.**

## القوائم المعتمدة (لا تخرج عنها إطلاقًا)
""" + ("audience_topic (واحد): " + json.dumps(TAX['audience_topics'], ensure_ascii=False) + "\n"
     + "أدوات عزيز (لدرجة «أداة يستعملها»): " + json.dumps(TAX['user_tools'], ensure_ascii=False) + "\n"
     + "content_type (واحد): " + json.dumps(TAX['content_types'], ensure_ascii=False) + "\n"
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
    """دفعة واحدة، بمحاولتين كاملتين. الفشل يُعاد لا يُعلَن فورًا."""
    n, part = args
    payload = [{"id": c["id"], "account": "@" + c["handle"], "date": c["created"],
                "lang": c["lang"], "metrics": c["m"], "links": c["links"],
                "text": c["text"], "quoted": c["q"]} for c in part]
    prompt = HEAD + "\n## المنشورات\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    last = ""
    for attempt in (1, 2):
        try:
            # 20 بطاقة × (شرح موسّع + تصنيف) تتجاوز 8000 توكن بسهولة، فيُقصّ
            # المخرَج في منتصف JSON ويفشل التحليل مرتين بالسبب نفسه.
            # (تقريرا 1 و3 سبتمبر: «Expecting , delimiter» — قصٌّ لا عطل نموذج.)
            resp = claude(prompt, max_tokens=24000)
            txt = "".join(b.get("text", "") for b in resp.get("content", []))
            mm = re.search(r'\[.*\]', txt, re.S)
            if not mm:
                last = "مخرَج غير قابل للقراءة"; time.sleep(5); continue
            try:
                arr = json.loads(mm.group(0))
            except Exception:
                arr = salvage(mm.group(0))
                if not arr:
                    raise
                log("دفعة %d: أُنقذ %d قرارًا من مخرَج مقصوص" % (n, len(arr)))
            log("دفعة %d: %d قرارًا (محاولة %d)" % (n, len(arr), attempt))
            return n, arr, ""
        except Exception as e:
            last = str(e)[:200]
            log("دفعة %d محاولة %d فشلت: %s" % (n, attempt, last))
            time.sleep(8)
    return n, None, last

chunks = [(i//BATCH + 1, cands[i:i+BATCH]) for i in range(0, len(cands), BATCH)]
REPORT["batches_total"] = len(chunks)
decisions, batches_failed, batch_errors = {}, 0, []
# بالتوازي: التصنيف كان يستهلك 43 دقيقة من 53 حين كان تسلسليًا
with ThreadPoolExecutor(max_workers=PARALLEL) as ex:
    for n, arr, err in ex.map(run_batch, chunks):
        if arr is None:
            batches_failed += 1; batch_errors.append("دفعة %d: %s" % (n, err)); continue
        for d in arr:
            if isinstance(d, dict) and d.get("id"): decisions[str(d["id"])] = d

kept = [c for c in cands if decisions.get(c["id"], {}).get("keep")]
log("قُبل %d من %d قُرئت (%d دفعة فشلت)" % (len(kept), len(cands), batches_failed))
if not kept:
    REPORT["status"] = "nothing"; REPORT["batches_failed"] = batches_failed
    REPORT["batch_errors"] = batch_errors
    REPORT["missing"] = [h for h in handles if h.lower() not in seen_accounts]
    REPORT["missing_unexpected"] = [h for h in REPORT["missing"] if h not in EXPECTED_QUIET]
    REPORT["missing_expected"]   = [h for h in REPORT["missing"] if h in EXPECTED_QUIET]
    write_report()
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
out, dup_merged, topic_missing = [], 0, []
for c in kept:
    d = decisions[c["id"]]
    # content_type مفرد الآن؛ نقبل الشكل القديم أيضًا تحسّبًا
    _ct_raw = d.get("content_type") or d.get("content_types")
    if isinstance(_ct_raw, str): _ct_raw = [_ct_raw]
    ct  = clean(_ct_raw, TAX["content_types"])[:1]
    tl  = clean(d.get("tool_types"), TAX["tool_types"])[:2]
    dom = clean(d.get("domains"),    TAX["domains"])[:2]
    chg = clean(d.get("change_types"), TAX["change_types"])
    # المحور الحاكم: قيمة واحدة معتمدة. الردّ الشاذّ يهبط إلى «عالم AI عام»
    # لا إلى فراغ — الحقل الفارغ يُسقط البطاقة من كل فلاتر المحور بلا أثر يُرى.
    _top = (d.get("audience_topic") or "").strip()
    if _top not in TAX["audience_topics"]:
        if _top: log("تنبيه: audience_topic غير معتمد (%s) في %s — رُدّ إلى «عالم AI عام»" % (_top, c["id"]))
        else:    topic_missing.append(c["id"])
        _top = "عالم AI عام"
    if not dom:
        log("تنبيه: بطاقة بلا مجال معتمد (%s) — تُترك بلا مجال بدل التخمين" % c["id"])
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
      "audience_topic": _top,
      "content_types": ct, "tool_types": tl, "domains": dom, "entities": d.get("entities") or [], "change_types": chg,
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

# ---------- 4.5) منع التكرار ----------
# العطل (٣ سبتمبر): خبر Gemini 3.8 ظهر في سبع بطاقات وفرشاة دايسون في بطاقتين.
# النموذج كان يخترع cluster_id نصًّا حرًّا فيختلف لكل بطاقة، ودمجُه لا يتجاوز
# تشغيلة اليوم أصلًا. هنا المفتاح يُحسب، والمقارنة تشمل ما نُشر في الأيام السابقة،
# والمشكوك فيه وحده يُعرض على النموذج في نداء واحد.

def _all_cards():
    got = []
    for sh in manifest.get("shards", []):
        d = rj("%s/%s" % (DATA, sh), [])
        if isinstance(d, list):
            got.extend([x for x in d if isinstance(x, dict)])
    return got

_corpus = _all_cards()
_idf = dedupe.build_idf(_corpus + out)

# البطاقات المنشورة داخل نافذة الأيام، مع ملفّها كي نكتب فيه
_cut = (NOW - datetime.timedelta(days=dedupe.WINDOW_DAYS + 1)).strftime("%Y-%m-%d")
_shard_of, _recent = {}, []
for _sh in manifest.get("shards", []):
    _d = rj("%s/%s" % (DATA, _sh), [])
    if not isinstance(_d, list):
        continue
    for _row in _d:
        if isinstance(_row, dict) and (_row.get("published_at") or "")[:10] >= _cut:
            _shard_of[id(_row)] = (_sh, _d)
            _recent.append(_row)

# كل الأزواج المرشّحة: داخل اليوم، ومع المنشور سابقًا
_pairs = dedupe.all_pairs(out, _idf)
_sig_new = {id(c): dedupe.signature(c) for c in out}
_sig_old = {id(c): dedupe.signature(c) for c in _recent}
for _a in out:
    for _b in _recent:
        _ok, _sc, _ = dedupe.same_event(_sig_new[id(_a)], _sig_old[id(_b)], _idf)
        if _ok:
            _pairs.append((_a, _b, _sc))

_sure, _ask = dedupe.pairs_needing_judgment(_pairs)
_confirmed = list(_sure)
if _ask:
    try:
        _r = claude(dedupe.judge_prompt(_ask), max_tokens=1500)
        _txt = "".join(b.get("text", "") for b in _r.get("content", []) if b.get("type") == "text")
        _m = re.search(r"\[.*\]", _txt, re.S)
        _confirmed += dedupe.apply_judgment(_ask, json.loads(_m.group(0)) if _m else None)
        log("حكم التكرار: %d زوجًا قاطعًا · %d سُئل عنها · %d أُكِّدت"
            % (len(_sure), len(_ask), len(_confirmed) - len(_sure)))
    except Exception as _e:
        # عند العجز لا ندمج: التكرار يُرى ويُحذف، والخبر المبتلَع لا يُعرف أنه فُقد
        log("تعذّر حكم التكرار (%s) — أُبقيت الأزواج المشكوكة بلا دمج" % _e)

_pair_new  = [(a, b) for a, b in _confirmed if id(a) in _sig_new and id(b) in _sig_new]
_pair_old  = [(a, b) for a, b in _confirmed if id(b) in _sig_old]

# أ) تكرار داخل دفعة اليوم — يبقى الأغنى معلومةً وتصير البقية مصادر تحته
_kept, _dropped_today = [], 0
for _g in dedupe.groups_from_pairs(out, _pair_new):
    if len(_g) == 1:
        _kept.append(_g[0]); continue
    _w, _rest = dedupe.pick_winner(_g)
    _w["also_reported"] = (_w.get("also_reported") or []) + dedupe.sources_of(_rest)
    _dropped_today += len(_rest)
    log("دُمج داخل اليوم: %d تحت «%s» (@%s)" % (len(_rest), _w["arabic_title"][:46], _w["author"]))
    _kept.append(_w)
out = _kept

# ب) تكرار لخبر منشور سابقًا — لا بطاقة جديدة، بل مصدر يُضاف للقائمة
_survivors, _touched, _merged_old = [], {}, 0
for _c in out:
    _hit = next((b for a, b in _pair_old if id(a) == id(_c) and id(b) in _shard_of), None)
    if _hit is None:
        _survivors.append(_c); continue
    _hit["also_reported"] = (_hit.get("also_reported") or []) + dedupe.sources_of([_c])
    _sh, _doc = _shard_of[id(_hit)]
    _touched[_sh] = _doc
    _merged_old += 1
    log("تكرار لخبر منشور: «%s» (@%s) صار مصدرًا تحت %s"
        % (_c["arabic_title"][:44], _c["author"], _hit.get("serial_display")))
out = _survivors

for _sh, _doc in _touched.items():
    json.dump(_doc, open("%s/%s" % (DATA, _sh), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ج) الأرقام التسلسلية تُعاد بعد الحذف كي لا تبقى فجوات
serial = int(state.get("max_serial", 0))
for _c in out:
    serial += 1
    _c["id"] = "c%03d" % serial
    _c["serial"] = serial
    _c["serial_display"] = "#%06d" % serial

dup_merged += _dropped_today + _merged_old
REPORT["deduped_today"] = _dropped_today
REPORT["deduped_previous_days"] = _merged_old
log("منع التكرار: %d داخل اليوم · %d مع أيام سابقة · بقي %d بطاقة"
    % (_dropped_today, _merged_old, len(out)))

if not out:
    log("كل بطاقات اليوم كانت تكرارًا لأخبار منشورة — لا جديد يُكتب")

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
# ما فشلت دفعته لا يُسجَّل مقروءًا، فيُقرأ غدًا بدل أن يضيع بلا أثر.
# العطل: كل منشورات الدفعة الفاشلة كانت تُوسم «مقروءة» فلا تعود أبدًا —
# صمتٌ كامل: لا بطاقة ولا رسالة (تقريرا 1 و3 سبتمبر، ≈20 منشورًا لكل دفعة).
_undecided = [c["id"] for c in cands if c["id"] not in decisions]
ids_today = [c["id"] for c in cands if c["id"] in decisions]
if _undecided:
    log("لم يُصنَّف %d منشورًا — تُركت غير مقروءة لتُقرأ غدًا" % len(_undecided))
    REPORT["undecided"] = len(_undecided)
state["recent_ids"] = sorted(set(list(recent) + ids_today))[-4000:]
for c in [x for x in cands if x["id"] in decisions]:
    prevlast = state.setdefault("last_id_per_account", {}).get(c["handle"], "")
    if not prevlast or c["id"] > prevlast:
        state["last_id_per_account"][c["handle"]] = c["id"]
state["updated_at"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(state, open(f"{DATA}/state.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

missing = [h for h in handles if h.lower() not in seen_accounts]
REPORT.update({
  "status": "ok", "accepted": len(out), "merged": dup_merged,
  "batches_failed": batches_failed, "batch_errors": batch_errors,
  "missing": missing,
  "missing_expected":   [h for h in missing if h in EXPECTED_QUIET],
  "missing_unexpected": [h for h in missing if h not in EXPECTED_QUIET],
  "titles": [{"serial": r["serial_display"], "author": r["author"],
              "title": r["arabic_title"], "tier": r["importance_tier"],
              "id": r["id"]} for r in out],
  # مقاس من تشغيلة 21 أغسطس: ~$0.0028 للمنشور المصنَّف + $0.00015 للتغريدة المسحوبة
  "cost_estimate_usd": round(len(cands) * 0.0028 + len(raw) * 0.00015, 3),
})
write_report()

report = ("سُحب %d تغريدة من %d/%d حسابًا · مرشّحون %d · قُرئ %d · قُبل %d · دُمج %d"
          % (len(raw), len(seen_accounts), len(handles), len(cands) + capped,
             len(cands), len(out), dup_merged))
if REPORT["missing_unexpected"]:
    report += " · **%d حسابًا بلا نتائج**: %s" % (len(REPORT["missing_unexpected"]),
                                                  "، ".join(REPORT["missing_unexpected"][:15]))
if capped:         report += " · **لم يُقرأ %d** (سقف MAX_READ=%d)" % (capped, MAX_READ)
if batches_failed: report += " · %d دفعة تصنيف فشلت" % batches_failed

# توزيع المحور الحاكم — يُعلَن كل يوم كي يُرى انحرافُه يوم وقوعه.
_topics = {}
for _c in out: _topics[_c["audience_topic"]] = _topics.get(_c["audience_topic"], 0) + 1
if _topics:
    REPORT["topics"] = _topics
    report += " · الموضوع: " + " · ".join("%s %d" % (k, v) for k, v in
              sorted(_topics.items(), key=lambda kv: -kv[1]))
if topic_missing:
    REPORT["topic_missing"] = topic_missing
    report += " · **%d بطاقة بلا موضوع** رُدّت إلى «عالم AI عام»" % len(topic_missing)

with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
    f.write("DAILY_COUNT=%d\nDAILY_DAY=%s\nDAILY_REPORT=%s\n" % (len(out), day, report))
log("DONE — " + report)
