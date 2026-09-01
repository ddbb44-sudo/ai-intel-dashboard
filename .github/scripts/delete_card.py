#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
يحذف بطاقة من اللوحة عبر طلب بوسم `delete`.

كانت اللوحة تملك ثلاث طرق للإضافة وصفرًا للحذف — فأي بطاقة خاطئة تبقى للأبد.
هذا هو باب الخروج.

الأمان:
  • لا ينفّذ إلا لصاحب المستودع.
  • يحذف بطاقة واحدة بمعرّف صريح — لا حذف جماعي ولا بالنمط.
  • يسجّل عنوان البطاقة المحذوفة في التعليق، فيبقى أثرٌ لما جرى.
  • عند أي شك لا يحذف، ويترك الطلب مفتوحًا بسبب واضح.
"""
import json, os, re, sys, glob, datetime, urllib.request

OWNER  = os.environ["GH_OWNER"]
REPO   = os.environ["GH_REPO"]
NUMBER = int(os.environ["ISSUE_NUMBER"])
AUTHOR = os.environ.get("ISSUE_AUTHOR", "")
BODY   = (os.environ.get("ISSUE_BODY", "") or "") + "\n" + (os.environ.get("ISSUE_TITLE", "") or "")
GH_TOK = os.environ["GITHUB_TOKEN"]
DATA   = "data"

def log(m): print(m, flush=True)

def gh(method, path, payload=None):
    req = urllib.request.Request("https://api.github.com" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method, headers={"Authorization": "Bearer " + GH_TOK,
        "Accept": "application/vnd.github+json", "User-Agent": "ai-intel-delete",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")

def comment(msg):
    try: gh("POST", "/repos/%s/%s/issues/%d/comments" % (OWNER, REPO, NUMBER), {"body": msg})
    except Exception as e: log("comment failed: %s" % e)

def bail(msg):
    log("BAIL: " + msg)
    comment("لم أحذف شيئًا: %s\n\nالطلب باقٍ مفتوحًا." % msg)
    sys.exit(0)

# ── إيصال الفشل ────────────────────────────────────────────────────────────
# قاعدة: لا عملية تفشل بصمت. أي انهيار غير متوقّع يترك تعليقًا على الطلب
# بنصّ العطل، فيعرف صاحبه أن الطلب لم يُنفَّذ ولماذا — بدل انتظار لا ينتهي.
def _crash(t, v, tb):
    import traceback
    detail = "".join(traceback.format_exception(t, v, tb))[-1200:]
    try:
        comment("\u26a0\ufe0f **تعذّر تنفيذ الطلب — عطل تقني.** الطلب يبقى مفتوحًا ولم يُكتب شيء.\n\n"
                "```\n" + detail + "\n```")
    except Exception:
        pass
    sys.__excepthook__(t, v, tb)

sys.excepthook = _crash


if AUTHOR.lower() != OWNER.lower():
    log("author %s is not owner — ignoring" % AUTHOR); sys.exit(0)

# ---------- 1) المعرّف ----------
# نقبل c870 أو #000870 أو 870
cid = None
m = re.search(r'\bc(\d{3,6})\b', BODY)
if m:
    cid = "c" + m.group(1)
else:
    m = re.search(r'#0*(\d{1,6})\b', BODY) or re.search(r'\b(\d{3,6})\b', BODY)
    if m: cid = "c%03d" % int(m.group(1))

if not cid:
    bail("لم أجد معرّف بطاقة. اكتب `c870` أو `#000870`.")
log("المطلوب حذفه: %s" % cid)

# ---------- 2) البحث ----------
SKIP = ("manifest.json", "state.json", "authors.json")
found = None
for f in sorted(glob.glob(os.path.join(DATA, "*.json"))):
    if os.path.basename(f) in SKIP: continue
    try:
        with open(f, encoding="utf-8") as fh: items = json.load(fh)
    except Exception: continue
    if not isinstance(items, list): continue
    for i, c in enumerate(items):
        if c.get("id") == cid:
            found = (f, i, c, items); break
    if found: break

if not found:
    bail("لا توجد بطاقة بالمعرّف `%s`." % cid)

path, idx, card, items = found
title  = card.get("arabic_title", "")
serial = card.get("serial_display", cid)
log("وُجدت في %s: %s — %s" % (path, serial, title))

# ---------- 3) الحذف ----------
items.pop(idx)
if items:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=1)
    log("بقي %d بطاقة في %s" % (len(items), os.path.basename(path)))
else:
    os.remove(path)
    log("الشارد صار فارغًا — حُذف الملف")

# ---------- 4) المانيفست ----------
mp = os.path.join(DATA, "manifest.json")
with open(mp, encoding="utf-8") as fh: man = json.load(fh)
if not items:
    base = os.path.basename(path)
    man["shards"] = [s for s in man.get("shards", []) if s != base]
st = man.setdefault("stats", {})
st["cards"] = max(0, int(st.get("cards", 0)) - 1)
man["generated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(mp, "w", encoding="utf-8") as fh:
    json.dump(man, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

# ملاحظة مقصودة: لا نُنقص state.max_serial — الأرقام لا تُعاد استخدامها أبدًا،
# وإلا حمل رقمٌ واحد بطاقتين مختلفتين في تاريخ المستودع.

with open("delete_result.md", "w", encoding="utf-8") as fh:
    fh.write("حُذفت البطاقة **%s** — %s\n\n" % (serial, title))
    fh.write("- الملف: `%s`\n" % path)
    fh.write("- رقم البطاقة لا يُعاد استخدامه.\n")
    fh.write("- النسخة السابقة محفوظة في تاريخ Git إن احتجتها.\n")

with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as fh:
    fh.write("DEL_ID=%s\nDEL_SERIAL=%s\n" % (cid, serial))

log("تم حذف %s" % serial)
