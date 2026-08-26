#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
يحوّل Issue بوسم `account` إلى حساب متابَع في accounts.json.

نفس فلسفة process_issue.py: عند أي شك — لا تكتب، واترك الـ Issue مفتوحة مع سبب
واضح. الفشل الصامت ممنوع.

المخرَج: يكتب المعرّفات الجديدة في new_handles.txt ليقرأها backfill_account.py
في خطوة تالية (لا نمرّرها عبر $GITHUB_ENV في نفس الخطوة — راجع §34).
"""
import json, os, re, sys, time, collections, urllib.request, urllib.error

OWNER  = os.environ["GH_OWNER"]
REPO   = os.environ["GH_REPO"]
NUMBER = int(os.environ["ISSUE_NUMBER"])
AUTHOR = os.environ.get("ISSUE_AUTHOR", "")
BODY   = (os.environ.get("ISSUE_BODY", "") or "") + "\n" + (os.environ.get("ISSUE_TITLE", "") or "")
GH_TOK = os.environ["GITHUB_TOKEN"]

def _envs(n, d):
    v = os.environ.get(n)
    return v.strip() if v and v.strip() else d

APIFY = _envs("APIFY_TOKEN", "")
ABASE = _envs("APIFY_BASE", "https://api.apify.com")
ACT   = "xquik~x-tweet-scraper"

def log(m): print(m, flush=True)

def gh(method, path, payload=None):
    req = urllib.request.Request("https://api.github.com" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method, headers={"Authorization": "Bearer " + GH_TOK,
        "Accept": "application/vnd.github+json", "User-Agent": "ai-intel-account",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")

def comment(msg):
    try: gh("POST", "/repos/%s/%s/issues/%d/comments" % (OWNER, REPO, NUMBER), {"body": msg})
    except Exception as e: log("comment failed: %s" % e)

def bail(msg):
    """تُترك الـ Issue مفتوحة ليراها عزيز ويصحّح."""
    log("BAIL: " + msg)
    comment("تعذّرت الإضافة: %s\n\nالطلب باقٍ مفتوحًا — صحّح وأعد المحاولة." % msg)
    sys.exit(0)

# ---------- 1) الهوية ----------
if AUTHOR.lower() != OWNER.lower():
    log("author %s is not owner — ignoring" % AUTHOR); sys.exit(0)

# ---------- 2) استخراج المعرّفات ----------
# مسارات X ليست حسابات
RESERVED = {"home","search","explore","notifications","messages","settings","i","intent",
            "compose","login","signup","about","tos","privacy","hashtag","status"}

handles, tweet_urls = [], []
seen = set()

for m in re.finditer(r'https?://(?:www\.)?(?:x|twitter)\.com/([^/\s?#]+)([^\s]*)', BODY, re.I):
    h, rest = m.group(1), m.group(2) or ""
    if "/status/" in rest:                      # رابط تغريدة لا حساب
        tweet_urls.append(m.group(0)); continue
    if h.lower() in RESERVED: continue
    if h.lower() not in seen: seen.add(h.lower()); handles.append(h)

for m in re.finditer(r'(?<![\w/])@([A-Za-z0-9_]{1,15})\b', BODY):
    h = m.group(1)
    if h.lower() in RESERVED: continue
    if h.lower() not in seen: seen.add(h.lower()); handles.append(h)

if not handles:
    if tweet_urls:
        bail("هذا رابط **تغريدة** لا حساب. لإضافة تغريدة استخدم وسم `inbox`. "
             "ولإضافة حساب ألصق رابط الملف الشخصي: `https://x.com/USERNAME`")
    bail("لم أجد معرّف حساب. ألصق رابط الملف الشخصي `https://x.com/USERNAME` أو اكتب `@USERNAME`.")

log("معرّفات مستخرجة: %s" % ", ".join(handles))

# ---------- 3) التحقق من وجود الحساب فعلًا على X ----------
def probe(handle):
    """تشغيلة صغيرة (منشور واحد) للتأكد أن الحساب موجود وينشر.
    التكلفة ≈ $0.00015. بدونها قد يدخل معرّف مكتوب خطأ ويبقى صامتًا للأبد."""
    if not APIFY: return None, "APIFY_TOKEN غير مضبوط"
    payload = {"mode": "profileTweets", "twitterHandles": [handle], "maxItems": 1,
               "outputVariant": "rich", "fieldStyle": "camelCase"}
    try:
        req = urllib.request.Request(ABASE + "/v2/acts/%s/runs?token=%s" % (ACT, APIFY),
            data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            run = json.loads(r.read().decode())["data"]
    except Exception as e:
        return None, "تعذّر بدء التحقق: %s" % e

    rid, dsid = run["id"], run.get("defaultDatasetId")
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(10)
        try:
            with urllib.request.urlopen(
                ABASE + "/v2/actor-runs/%s?token=%s" % (rid, APIFY), timeout=60) as r:
                st = json.loads(r.read().decode())["data"]
        except Exception:
            continue
        if st.get("status") in ("SUCCEEDED","FAILED","ABORTED","TIMED-OUT"):
            dsid = st.get("defaultDatasetId") or dsid
            if st["status"] != "SUCCEEDED":
                return None, "انتهى التحقق بحالة %s" % st["status"]
            break
    else:
        return None, "التحقق لم ينتهِ خلال 5 دقائق"

    try:
        with urllib.request.urlopen(
            ABASE + "/v2/datasets/%s/items?token=%s&clean=true&limit=1" % (dsid, APIFY),
            timeout=60) as r:
            items = json.loads(r.read().decode())
    except Exception as e:
        return None, "تعذّرت قراءة نتيجة التحقق: %s" % e

    if not items: return None, "لم يُعد X أي منشور — تأكد من صحة المعرّف وأن الحساب عام"
    a = (items[0].get("author") or {})
    return {"handle": a.get("username") or handle,
            "name": a.get("name") or "",
            "followers": a.get("followers")}, ""

# ---------- 4) الإضافة ----------
p = "accounts.json"
with open(p, encoding="utf-8") as f:
    acc = json.load(f, object_pairs_hook=collections.OrderedDict)

existing = {a["handle"].lower() for a in acc.get("accounts", [])}
added, already, failed = [], [], []

for h in handles:
    if h.lower() in existing:
        already.append(h); log("موجود مسبقًا: %s" % h); continue
    info, err = probe(h)
    if not info:
        failed.append((h, err)); log("تعذّر التحقق من %s: %s" % (h, err)); continue
    entry = collections.OrderedDict([("handle", info["handle"]),
                                     ("name", info["name"] or info["handle"]),
                                     ("active", True)])
    acc["accounts"].append(entry)
    existing.add(info["handle"].lower())
    added.append(info)
    log("أُضيف: %s (%s · %s متابعًا)" % (info["handle"], info["name"], info["followers"]))

if added:
    acc["updated"] = time.strftime("%Y-%m-%d")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(acc, f, ensure_ascii=False, indent=1)
        f.write("\n")

with open("new_handles.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(a["handle"] for a in added))

# ---------- 5) التقرير ----------
lines = []
if added:
    lines.append("**أُضيف للسحب اليومي:**\n")
    for a in added:
        lines.append("- [@%s](https://x.com/%s) — %s · %s متابعًا"
                     % (a["handle"], a["handle"], a["name"], a["followers"]))
    lines.append("\nيبدأ السحب التاريخي لآخر 60 يومًا الآن — سأعلّق بالنتيجة بعد دقائق.")
if already:
    lines.append("\n**متابَع مسبقًا (لم يتغيّر شيء):** " + "، ".join("@"+h for h in already))
if failed:
    lines.append("\n**تعذّر التحقق — لم يُضَف:**\n")
    for h, e in failed:
        lines.append("- @%s — %s" % (h, e))
if tweet_urls:
    lines.append("\n**تجاهلت روابط تغريدات** (لإضافة تغريدة استخدم وسم `inbox`): %d"
                 % len(tweet_urls))

comment("\n".join(lines) or "لا جديد.")

with open("account_summary.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

log("added=%d already=%d failed=%d" % (len(added), len(already), len(failed)))
if failed and not added:
    sys.exit(0)   # لا نُفشل التشغيلة — التعليق هو المخرَج
