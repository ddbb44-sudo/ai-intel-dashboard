#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يحوّل report.json إلى بريد عربي واضح. يعمل حتى لو انهار السحب — لأن التقرير هو المخرَج."""
import json, os, html, datetime

DASH = "https://ddbb44-sudo.github.io/ai-intel-dashboard/"
RUN  = "%s/%s/actions/runs/%s" % (os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
                                  os.environ.get("GITHUB_REPOSITORY", ""),
                                  os.environ.get("GITHUB_RUN_ID", ""))
AR_MONTHS = ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
             "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]

def load():
    try:
        with open("report.json", encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {"status": "crashed",
                "error": "انهارت التشغيلة قبل أن تكتب تقريرها — راجع السجل",
                "day": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")}

r = load()
st = r.get("status", "unknown")
e  = html.escape

try:
    d = datetime.datetime.strptime(r.get("day", ""), "%Y-%m-%d")
    day_ar = "%d %s %d" % (d.day, AR_MONTHS[d.month - 1], d.year)
except Exception:
    day_ar = r.get("day", "")

mins = r.get("duration_secs", 0) // 60
secs = r.get("duration_secs", 0) % 60

HEAD_MAP = {
    "ok":      ("✅", "تم الفحص", "#2f7a48", "#eef7f1"),
    "nothing": ("○",  "تم الفحص — لا جديد يستحق", "#7a6a55", "#faf6f1"),
    "failed":  ("⚠️", "لم يتم الفحص", "#a8452f", "#fdf0ed"),
    "crashed": ("⚠️", "لم يتم الفحص", "#a8452f", "#fdf0ed"),
}
icon, headline, color, bg = HEAD_MAP.get(st, HEAD_MAP["failed"])

if st == "ok":
    subject = "✅ لوحة الذكاء الاصطناعي — %s · %d بطاقة جديدة" % (day_ar, r.get("accepted", 0))
elif st == "nothing":
    subject = "○ لوحة الذكاء الاصطناعي — %s · لا جديد" % day_ar
else:
    subject = "⚠️ لوحة الذكاء الاصطناعي — %s · لم يتم الفحص" % day_ar

def row(label, value, note=""):
    return ('<tr><td style="padding:9px 14px;border-bottom:1px solid #efe9e4;color:#7a6a5c;'
            'font-size:13.5px">%s</td><td style="padding:9px 14px;border-bottom:1px solid #efe9e4;'
            'font-weight:600;color:#2d2722;font-size:14px">%s'
            '<span style="color:#9a8b7d;font-weight:400;font-size:12.5px"> %s</span></td></tr>'
            % (label, value, note))

parts = []

# ── الحالة ──
parts.append(
 '<div style="background:%s;border:1px solid %s33;border-radius:12px;padding:18px 20px;margin-bottom:18px">'
 '<div style="font-size:19px;font-weight:700;color:%s">%s %s</div>'
 '<div style="color:#6b5d50;font-size:13.5px;margin-top:5px">%s · استغرقت %d دقيقة و%d ثانية</div>'
 '</div>' % (bg, color, color, icon, headline, day_ar, mins, secs))

if st in ("failed", "crashed"):
    parts.append(
     '<div style="background:#fff;border:1px solid #f0d9d2;border-radius:12px;padding:16px 18px;margin-bottom:18px">'
     '<div style="font-weight:700;color:#a8452f;margin-bottom:6px;font-size:14px">السبب</div>'
     '<div style="color:#3d3630;font-size:14px;line-height:1.8">%s</div>'
     '<div style="color:#7a6a5c;font-size:13px;margin-top:12px">لم تُحذف أي بطاقة، ولم يُفقد أي منشور — '
     'التشغيلة القادمة ستعيد المحاولة تلقائيًا.</div></div>' % e(r.get("error", "غير معروف")))
else:
    seen, total = r.get("accounts_seen", 0), r.get("accounts_total", 0)
    pct = round(seen / total * 100) if total else 0
    parts.append('<table style="width:100%;border-collapse:collapse;background:#fff;'
                 'border:1px solid #efe9e4;border-radius:12px;overflow:hidden;margin-bottom:18px">')
    parts.append(row("الحسابات المفحوصة", "%d من %d" % (seen, total), "(%d%%)" % pct))
    parts.append(row("التغريدات المسحوبة", "{:,}".format(r.get("pulled", 0))))
    parts.append(row("مرشّحون بعد التنظيف", str(r.get("candidates", 0))))
    parts.append(row("قُرئت وحُكم عليها", str(r.get("read", 0))))
    parts.append(row("بطاقات جديدة", str(r.get("accepted", 0)),
                     "· دُمج %d مصدرًا" % r.get("merged", 0) if r.get("merged") else ""))
    parts.append(row("التكلفة التقريبية", "$%.2f" % r.get("cost_estimate_usd", 0)))
    parts.append('</table>')

# ── ما لم يُسحب ──
unexp = r.get("missing_unexpected") or []
exp   = r.get("missing_expected") or []
if unexp or exp:
    parts.append('<div style="background:#fff;border:1px solid #efe9e4;border-radius:12px;'
                 'padding:16px 18px;margin-bottom:18px">')
    parts.append('<div style="font-weight:700;color:#2d2722;margin-bottom:10px;font-size:14px">'
                 'حسابات لم تُرجع نتائج</div>')
    if unexp:
        parts.append('<div style="color:#a8452f;font-size:13.5px;font-weight:600;margin-bottom:4px">'
                     'تستحق الانتباه (%d)</div>'
                     '<div style="color:#3d3630;font-size:13.5px;line-height:1.9;direction:ltr;'
                     'text-align:right;margin-bottom:12px">%s</div>'
                     '<div style="color:#7a6a5c;font-size:12.5px;margin-bottom:12px">'
                     'السبب المحتمل: لم تنشر شيئًا خلال 24 ساعة، أو تعذّر على الأكتور قراءتها. '
                     'إن تكرر الاسم نفسه ثلاثة أيام متتالية فالأرجح أن الحساب توقف أو غيّر اسمه.</div>'
                     % (len(unexp), " · ".join("@" + e(h) for h in unexp)))
    if exp:
        parts.append('<div style="color:#7a6a5c;font-size:13.5px;font-weight:600;margin-bottom:4px">'
                     'متوقّعة — حسابات خاملة معروفة (%d)</div>'
                     '<div style="color:#8a7b6d;font-size:13px;line-height:1.9;direction:ltr;'
                     'text-align:right">%s</div>'
                     % (len(exp), " · ".join("@" + e(h) for h in exp)))
    parts.append('</div>')

# ── ما استُبعد ولماذا ──
dr = r.get("dropped") or {}
if dr and st != "failed":
    items = " · ".join("%s: <b>%d</b>" % (e(k), v) for k, v in dr.items())
    extra = []
    if r.get("capped"):
        extra.append("<b>%d منشورًا لم يُقرأ</b> بسبب سقف القراءة اليومي" % r["capped"])
    if r.get("batches_failed"):
        extra.append("<b>%d دفعة تصنيف فشلت</b> بعد محاولتين — منشوراتها لم تُصنَّف"
                     % r["batches_failed"])
    parts.append('<div style="background:#fff;border:1px solid #efe9e4;border-radius:12px;'
                 'padding:16px 18px;margin-bottom:18px">'
                 '<div style="font-weight:700;color:#2d2722;margin-bottom:8px;font-size:14px">'
                 'ما استُبعد قبل القراءة</div>'
                 '<div style="color:#3d3630;font-size:13.5px;line-height:1.9">%s</div>%s</div>'
                 % (items,
                    ('<div style="color:#a8452f;font-size:13px;margin-top:10px;line-height:1.8">'
                     + "<br>".join(extra) + '</div>') if extra else ""))

# ── البطاقات الجديدة ──
titles = r.get("titles") or []
if titles:
    imp = [t for t in titles if t.get("tier") == "important"]
    rest = [t for t in titles if t.get("tier") != "important"]
    rows = []
    for t in imp + rest:
        badge = ('<span style="background:#fdf0e8;color:#a85c30;font-size:11px;padding:1px 7px;'
                 'border-radius:20px">مهم</span>') if t.get("tier") == "important" else ""
        rows.append('<div style="padding:10px 0;border-bottom:1px solid #f2ece7">'
                    '<a href="%s#/c/%s" style="color:#2d2722;text-decoration:none;font-size:14px;'
                    'font-weight:600;line-height:1.7">%s</a> %s'
                    '<div style="color:#9a8b7d;font-size:12px;margin-top:3px">%s · @%s</div></div>'
                    % (DASH, e(t.get("id", "")), e(t.get("title", "")), badge,
                       e(t.get("serial", "")), e(t.get("author", ""))))
    parts.append('<div style="background:#fff;border:1px solid #efe9e4;border-radius:12px;'
                 'padding:16px 18px;margin-bottom:18px">'
                 '<div style="font-weight:700;color:#2d2722;margin-bottom:6px;font-size:14px">'
                 'البطاقات الجديدة (%d)</div>%s</div>' % (len(titles), "".join(rows)))

parts.append('<div style="text-align:center;margin:22px 0 8px">'
             '<a href="%s" style="background:#c1633a;color:#fff;text-decoration:none;'
             'padding:12px 26px;border-radius:10px;font-weight:600;font-size:14.5px;'
             'display:inline-block">فتح اللوحة</a></div>'
             '<div style="text-align:center;color:#9a8b7d;font-size:12px">'
             '<a href="%s" style="color:#9a8b7d">سجل التشغيلة الكامل</a></div>' % (DASH, RUN))

body = ('<div style="direction:rtl;text-align:right;font-family:-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',Tahoma,Arial,sans-serif;background:#faf9f7;padding:24px 16px">'
        '<div style="max-width:600px;margin:0 auto">'
        '<div style="font-size:15px;font-weight:700;color:#2d2722;margin-bottom:16px">'
        'مركز المعرفة — الذكاء الاصطناعي</div>%s</div></div>' % "".join(parts))

open("email.html", "w", encoding="utf-8").write(body)
with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a", encoding="utf-8") as f:
    f.write("MAIL_SUBJECT=%s\n" % subject.replace("\n", " "))
print("subject:", subject)
print("email.html bytes:", len(body.encode()))
