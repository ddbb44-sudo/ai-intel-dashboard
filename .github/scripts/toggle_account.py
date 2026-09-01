#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
يوقف حسابًا عن السحب أو يعيد تشغيله، عبر طلب عنوانه:
    إيقاف حساب: @handle
    تشغيل حساب: @handle

لماذا إيقاف لا حذف: `active: false` يوقف السحب ويُبقي تاريخ الحساب وبطاقاته
كما هي — قرار عزيز (١ سبتمبر). حذف السطر يفقد ما جُمع بلا رجعة، والإيقاف
قابل للتراجع بضغطة. البطاقات القديمة تبقى في اللوحة دائمًا.

الأمان:
  • لا ينفّذ إلا لصاحب المستودع.
  • حساب واحد بمعرّف صريح — لا إيقاف جماعي.
  • لا يلمس البطاقات إطلاقًا.
  • عند أي شك لا يكتب، ويترك الطلب مفتوحًا بسبب واضح.
"""
import json, os, re, sys, urllib.request

OWNER  = os.environ["GH_OWNER"]
REPO   = os.environ["GH_REPO"]
NUMBER = int(os.environ["ISSUE_NUMBER"])
AUTHOR = os.environ.get("ISSUE_AUTHOR", "")
TITLE  = os.environ.get("ISSUE_TITLE", "") or ""
BODY   = os.environ.get("ISSUE_BODY", "") or ""
GH_TOK = os.environ["GITHUB_TOKEN"]
ACC    = "accounts.json"

def log(m): print(m, flush=True)

def gh(method, path, payload=None):
    req = urllib.request.Request("https://api.github.com" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method, headers={"Authorization": "Bearer " + GH_TOK,
        "Accept": "application/vnd.github+json", "User-Agent": "ai-intel-toggle",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")

def comment(msg):
    try: gh("POST", "/repos/%s/%s/issues/%d/comments" % (OWNER, REPO, NUMBER), {"body": msg})
    except Exception as e: log("comment failed: %s" % e)

def close():
    try: gh("PATCH", "/repos/%s/%s/issues/%d" % (OWNER, REPO, NUMBER), {"state": "closed"})
    except Exception as e: log("close failed: %s" % e)

def bail(msg):
    log("BAIL: " + msg)
    comment("لم أغيّر شيئًا: %s\n\nالطلب باقٍ مفتوحًا." % msg)
    sys.exit(0)

# ── إيصال الفشل ────────────────────────────────────────────────────────────
def _crash(t, v, tb):
    import traceback
    detail = "".join(traceback.format_exception(t, v, tb))[-1200:]
    try:
        comment("⚠️ **تعذّر تنفيذ الطلب — عطل تقني.** الطلب يبقى مفتوحًا ولم يُكتب شيء.\n\n"
                "```\n" + detail + "\n```")
    except Exception:
        pass
    sys.__excepthook__(t, v, tb)

sys.excepthook = _crash

if AUTHOR.lower() != OWNER.lower():
    log("author %s is not owner — ignoring" % AUTHOR); sys.exit(0)

text = TITLE + "\n" + BODY
if re.search(r"إيقاف\s*حساب", text):
    want_active = False
elif re.search(r"تشغيل\s*حساب", text):
    want_active = True
else:
    bail("لم أفهم المطلوب: العنوان يجب أن يبدأ بـ«إيقاف حساب:» أو «تشغيل حساب:»")

m = re.search(r"@?([A-Za-z0-9_]{2,15})\b", TITLE.split(":", 1)[-1]) \
    or re.search(r"@([A-Za-z0-9_]{2,15})\b", BODY)
if not m:
    bail("لم أجد معرّف حساب صالحًا في الطلب")
handle = m.group(1)

with open(ACC, encoding="utf-8") as f:
    data = json.load(f)
rows = data.get("accounts", [])

hit = next((a for a in rows if str(a.get("handle", "")).lower() == handle.lower()), None)
if not hit:
    bail("الحساب `@%s` غير موجود في قائمة المتابَعة" % handle)

was = hit.get("active", True)
if was == want_active:
    comment("لا تغيير: الحساب `@%s` %s أصلًا." % (handle, "موقوف" if not want_active else "يُسحب"))
    close(); sys.exit(0)

hit["active"] = want_active
with open(ACC, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
    f.write("\n")

state = "أُوقف السحب من" if not want_active else "استُؤنف السحب من"
log("%s @%s" % (state, handle))
comment("✅ %s `@%s`.\n\n"
        "بطاقاته السابقة باقية في اللوحة كما هي — الإيقاف يخصّ السحب اليومي فقط، "
        "وهو قابل للتراجع بطلب «%s حساب: @%s»."
        % (state, handle, "تشغيل" if not want_active else "إيقاف", handle))
close()

print("TOGGLED_HANDLE=%s" % handle)
with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
    f.write("TOGGLED_HANDLE=%s\nTOGGLED_STATE=%s\n" % (handle, "on" if want_active else "off"))
