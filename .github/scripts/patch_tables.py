#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
عرض جداول Markdown داخل المقالة.

بطاقة c870 كشفت أن المقالة الأصلية كانت تحوي خمسة جداول بعشرة أعمدة، فسُطّحت
إلى أسطر «المفتاح: القيمة» لأن البرومبت لم يعرض صيغة جدول أصلًا. صحّحنا
البرومبت ليُخرج جداول Markdown — ويبقى أن تعرفها اللوحة، وإلا ظهرت أنابيب خامًا.

آمن للتكرار؛ يتوقف دون تغيير إن لم يطابق الملف المتوقع.
"""
import sys

changed = []

# ───────── app.js ─────────
P = "app.js"
src = open(P, encoding="utf-8").read()

if "artTable" in src:
    print("app.js: عرض الجداول مركّب مسبقًا — تخطٍّ")
else:
    old = """function richText(t){
  if(!t) return '';
  return String(t).split(/\\n{2,}/).map(function(b){
    b = b.trim();
    if(!b) return '';
    var m = b.match(/^#{2,4}\\s*(.+)$/);
    if(m) return '<h4 class="artsub">' + esc(m[1]) + '</h4>';
    return '<p>' + esc(b).replace(/\\n/g,'<br>') + '</p>';
  }).join('');
}"""
    new = """function artTable(lines){
  // صف فاصل مثل |---|---| ليس بيانات
  var rows = lines.filter(function(l){ return !/^\\|[\\s:|-]+\\|?$/.test(l.trim()); })
    .map(function(l){
      var s = l.trim().replace(/^\\|/,'').replace(/\\|$/,'');
      return s.split('|').map(function(c){ return c.trim(); });
    });
  if(!rows.length) return '';
  var head = rows.shift();
  var th = head.map(function(c){ return '<th>' + artInline(c) + '</th>'; }).join('');
  var tb = rows.map(function(r){
    return '<tr>' + r.map(function(c){ return '<td>' + artInline(c) + '</td>'; }).join('') + '</tr>';
  }).join('');
  return '<div class="arttw"><table class="arttbl"><thead><tr>' + th +
         '</tr></thead><tbody>' + tb + '</tbody></table></div>';
}
function artInline(s){
  // نهرب أولًا ثم نضيف وسومنا — فلا يدخل HTML من نص المقالة
  var t = esc(s).replace(/\\*\\*([^*]+)\\*\\*/g, '<b>$1</b>');
  // [نص](رابط) — روابط المقالة تُحفظ ولا تُمحى
  t = t.replace(/\\[([^\\]]+)\\]\\((https?:\\/\\/[^)\\s]+)\\)/g,
        '<a class="artlink" href="$2" target="_blank" rel="noopener">$1</a>');
  // رابط عارٍ لم يُغلَّف
  t = t.replace(/(^|[\\s(])(https?:\\/\\/[^\\s<)]+)/g,
        '$1<a class="artlink" href="$2" target="_blank" rel="noopener">$2</a>');
  return t;
}
function richText(t){
  if(!t) return '';
  return String(t).split(/\\n{2,}/).map(function(b){
    b = b.trim();
    if(!b) return '';
    var lines = b.split('\\n').map(function(l){ return l.trim(); }).filter(Boolean);
    if(lines.length >= 2 && lines.every(function(l){ return l.indexOf('|') === 0; }))
      return artTable(lines);
    var m = b.match(/^#{2,4}\\s*(.+)$/);
    if(m) return '<h4 class="artsub">' + esc(m[1]) + '</h4>';
    if(lines.length && lines.every(function(l){ return /^[-*]\\s+/.test(l); }))
      return '<ul class="artul">' + lines.map(function(l){
        return '<li>' + artInline(l.replace(/^[-*]\\s+/,'')) + '</li>'; }).join('') + '</ul>';
    return '<p>' + artInline(b).replace(/\\n/g,'<br>') + '</p>';
  }).join('');
}"""
    if src.count(old) != 1:
        print("توقّف: richText لم تطابق (%d) — لم أغيّر شيئًا" % src.count(old)); sys.exit(1)
    src = src.replace(old, new)
    open(P, "w", encoding="utf-8").write(src)
    changed.append("app.js")
    print("app.js: جداول وقوائم وغامق داخل المقالة")

# ───────── index.html ─────────
H = "index.html"
h = open(H, encoding="utf-8").read()

if ".arttbl" in h:
    print("index.html: تنسيق الجدول مركّب مسبقًا — تخطٍّ")
else:
    anchor = ".artsub{margin:18px 0 6px;font-size:15px;font-weight:650}"
    if h.count(anchor) != 1:
        print("توقّف: مرساة CSS لم تطابق (%d)" % h.count(anchor)); sys.exit(1)
    css = anchor + """
.arttw{overflow-x:auto;margin:14px 0;border:1px solid var(--line);border-radius:var(--r-sm)}
.arttbl{border-collapse:collapse;width:100%;min-width:480px;font-size:13px}
.arttbl th,.arttbl td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--line);
  vertical-align:top;line-height:1.65}
.arttbl th{background:var(--surface-2);font-weight:600;font-size:12px;color:var(--ink-2);white-space:nowrap}
.arttbl tr:last-child td{border-bottom:0}
.artul{margin:10px 0;padding-inline-start:20px}
.artul li{margin-bottom:6px;line-height:1.8}
.artlink{color:var(--accent);text-decoration:underline;text-underline-offset:3px;
  word-break:break-word;overflow-wrap:anywhere}
.artlink:hover{color:var(--accent-2)}
.sec p{line-height:1.95;overflow-wrap:break-word}
/* ملاحظة: هناك فيض أفقي 5px سابق لهذا العمل، سببه درج الفلاتر
   position:fixed خارج الشاشة — و overflow-x:hidden الموجود أصلًا في السطر 24
   لا يقصّ العناصر الثابتة. لم أمسّه هنا: إصلاحه يتطلب تغيير موضع الدرج،
   وهو واجهة أساسية لا تُخاطَر بها لأجل 5 بكسل. */
@media(max-width:700px){
  .sec p,.artul li{font-size:15px;line-height:2.0}
  .artsub{font-size:16px;margin:20px 0 8px}
  .arttbl{min-width:340px;font-size:12.5px}
  .arttbl th,.arttbl td{padding:8px 9px}
  .arttw{margin:12px -4px}
  .detail{padding-inline:2px}
}"""
    h = h.replace(anchor, css)
    open(H, "w", encoding="utf-8").write(h)
    changed.append("index.html")
    print("index.html: تنسيق الجداول والقوائم")

print("تم. المعدَّل: %s" % (", ".join(changed) if changed else "لا شيء"))
