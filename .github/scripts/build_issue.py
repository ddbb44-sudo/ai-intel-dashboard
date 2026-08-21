#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يحوّل report.json إلى تقرير Markdown يُنشَر كطلب في المستودع،
فيصل عزيز بريدًا عبر إشعارات GitHub نفسها — بلا كلمة مرور ولا خادم بريد."""
import json, os, datetime

DASH  = "https://ddbb44-sudo.github.io/ai-intel-dashboard/"
OWNER = os.environ.get("GH_OWNER", "ddbb44-sudo")
RUN   = "%s/%s/actions/runs/%s" % (os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
                                   os.environ.get("GITHUB_REPOSITORY", ""),
                                   os.environ.get("GITHUB_RUN_ID", ""))
AR_MONTHS = ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
             "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]

try:
    with open("report.json", encoding="utf-8") as f: r = json.load(f)
except Exception:
    r = {"status": "crashed", "error": "انهارت التشغيلة قبل أن تكتب تقريرها — راجع السجل",
         "day": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")}

st = r.get("status", "unknown")
try:
    d = datetime.datetime.strptime(r.get("day", ""), "%Y-%m-%d")
    day_ar = "%d %s %d" % (d.day, AR_MONTHS[d.month - 1], d.year)
except Exception:
    day_ar = r.get("day", "")

mins, secs = r.get("duration_secs", 0) // 60, r.get("duration_secs", 0) % 60

if st == "ok":
    title = "✅ %s — تم الفحص · %d بطاقة جديدة" % (day_ar, r.get("accepted", 0))
elif st == "nothing":
    title = "○ %s — تم الفحص · لا جديد يستحق" % day_ar
else:
    title = "⚠️ %s — لم يتم الفحص" % day_ar

L = ["@%s" % OWNER, ""]

if st in ("failed", "crashed"):
    L += ["## ⚠️ لم يتم الفحص", "",
          "**السبب:** %s" % r.get("error", "غير معروف"), "",
          "لم تُحذف أي بطاقة ولم يُفقد أي منشور. التشغيلة القادمة ستعيد المحاولة تلقائيًا.", ""]
else:
    seen, total = r.get("accounts_seen", 0), r.get("accounts_total", 0)
    pct = round(seen / total * 100) if total else 0
    L += ["## %s %s" % ("✅" if st == "ok" else "○",
                        "تم الفحص" if st == "ok" else "تم الفحص — لا جديد يستحق"),
          "", "استغرق %d دقيقة و%d ثانية." % (mins, secs), "",
          "| | |", "|---|---|",
          "| **الحسابات المفحوصة** | %d من %d (%d%%) |" % (seen, total, pct),
          "| التغريدات المسحوبة | %s |" % "{:,}".format(r.get("pulled", 0)),
          "| مرشّحون بعد التنظيف | %d |" % r.get("candidates", 0),
          "| قُرئت وحُكم عليها | %d |" % r.get("read", 0),
          "| **بطاقات جديدة** | **%d**%s |" % (r.get("accepted", 0),
              (" · دُمج %d مصدرًا" % r["merged"]) if r.get("merged") else ""),
          "| التكلفة التقريبية | $%.2f |" % r.get("cost_estimate_usd", 0), ""]

unexp, exp = r.get("missing_unexpected") or [], r.get("missing_expected") or []
if unexp:
    L += ["### ⚠️ حسابات لم تُرجع نتائج — تستحق الانتباه (%d)" % len(unexp), "",
          " · ".join("`@%s`" % h for h in unexp), "",
          "> السبب المحتمل: لم تنشر شيئًا خلال 24 ساعة، أو تعذّر على الأكتور قراءتها.",
          "> **إن تكرر الاسم نفسه ثلاثة أيام متتالية** فالأرجح أن الحساب توقف أو غيّر اسمه.", ""]
if exp:
    L += ["<details><summary>حسابات خاملة معروفة — متوقّعة (%d)</summary>" % len(exp), "",
          " · ".join("`@%s`" % h for h in exp), "", "</details>", ""]

dr = r.get("dropped") or {}
if dr and st != "failed":
    L += ["### ما استُبعد قبل القراءة", "",
          " · ".join("%s: **%d**" % (k, v) for k, v in dr.items()), ""]
    warn = []
    if r.get("capped"):
        warn.append("⚠️ **%d منشورًا لم يُقرأ** بسبب سقف القراءة اليومي." % r["capped"])
    if r.get("batches_failed"):
        warn.append("⚠️ **%d دفعة تصنيف فشلت** بعد محاولتين — منشوراتها لم تُصنَّف." % r["batches_failed"])
        for be in (r.get("batch_errors") or [])[:3]:
            warn.append("  - `%s`" % be)
    if warn: L += warn + [""]

titles = r.get("titles") or []
if titles:
    imp  = [t for t in titles if t.get("tier") == "important"]
    rest = [t for t in titles if t.get("tier") != "important"]
    L += ["### البطاقات الجديدة (%d)" % len(titles), ""]
    for t in imp + rest:
        L.append("- %s[%s](%s#/c/%s) — `%s` · @%s"
                 % ("**مهم** · " if t.get("tier") == "important" else "",
                    t.get("title", ""), DASH, t.get("id", ""),
                    t.get("serial", ""), t.get("author", "")))
    L.append("")

L += ["---", "", "**[افتح اللوحة](%s)** · [سجل التشغيلة](%s)" % (DASH, RUN)]

open("issue_body.md", "w", encoding="utf-8").write("\n".join(L))
with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
    f.write("ISSUE_TITLE=%s\n" % title.replace("\n", " "))
print("title:", title)
print("body bytes:", len("\n".join(L).encode()))
