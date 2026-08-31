#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
عرض المقالة: جداول · قوائم · روابط بارزة · قراءة الجوال.

يستبدل كتلة العرض القديمة بالكامل بدل التخطي عند وجودها. الحارس السابق كان
يفحص `artTable` — وهي موجودة من install-5 — فتخطّى تحديث install-6 وضاعت
الروابط. العلامة هنا `artBlocks` وهي جديدة، والاستبدال شامل لا إضافي.

القرار التصميمي (بعد مراجعة عزيز): الرابط **فعل لا بيان**. كان آخر عمود في
الجدول، وفي العربية آخر عمود هو الأقصى يسارًا — أول ما يختفي عند التمرير.
قياس: عند عرض 760px يخرج من الشاشة تمامًا. فصار كل رابط داخل جدول يظهر
أيضًا كزرّ تحته، ولا يضيع أبدًا.
"""
import sys

changed = []

# ───────────────────────── app.js ─────────────────────────
P = "app.js"
src = open(P, encoding="utf-8").read()

if "artBlocks" in src:
    print("app.js: العرض الجديد مركّب مسبقًا — تخطٍّ")
else:
    start = src.find("function artTable(lines){")
    if start < 0:
        start = src.find("function richText(t){")
    end = src.find("function viewDetail(")
    if start < 0 or end < 0 or end <= start:
        print("توقّف: تعذّر تحديد كتلة العرض — لم أغيّر شيئًا"); sys.exit(1)

    NEW = r'''/* ---------- عرض نص المقالة ----------
   يحوّل النص المرتَّب إلى HTML: فقرات · عناوين ## · قوائم · جداول Markdown ·
   روابط [نص](رابط). لا يدخل HTML من النص إطلاقًا — نهرب أولًا ثم نضيف وسومنا. */
function artInline(s){
  var t = esc(s).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
        '<a class="artlink" href="$2" target="_blank" rel="noopener">$1</a>');
  t = t.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g,
        '$1<a class="artlink" href="$2" target="_blank" rel="noopener">$2</a>');
  return t;
}
/* كل رابط في النص يستحق زرًّا واضحًا. الرابط المدفون في خانة جدول لا يُرى. */
function artLinks(s){
  var out = [], seen = {}, m;
  var re = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
  while((m = re.exec(s))){ if(!seen[m[2]]){ seen[m[2]]=1; out.push([m[1], m[2]]); } }
  return out;
}
function artBtn(txt, url){
  var yt = /youtube\.com|youtu\.be/.test(url);
  var icon = yt
    ? '<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true"><path d="M21.6 7.2a2.8 2.8 0 0 0-2-2C17.9 4.8 12 4.8 12 4.8s-5.9 0-7.6.4a2.8 2.8 0 0 0-2 2A29 29 0 0 0 2 12a29 29 0 0 0 .4 4.8 2.8 2.8 0 0 0 2 2c1.7.4 7.6.4 7.6.4s5.9 0 7.6-.4a2.8 2.8 0 0 0 2-2A29 29 0 0 0 22 12a29 29 0 0 0-.4-4.8zM10 15.2V8.8l5.2 3.2z"/></svg>'
    : '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7L12 19"/></svg>';
  var host = '';
  try{ host = new URL(url).hostname.replace(/^www\./,''); }catch(e){ host = url; }
  return '<a class="artbtn" href="' + esc(url) + '" target="_blank" rel="noopener">' + icon +
    '<span><b>' + esc(txt) + '</b><i>' + esc(host) + '</i></span>' +
    '<svg class="x" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><path d="M15 3h6v6"/><path d="M10 14L21 3"/></svg></a>';
}
function artTable(lines){
  var rows = lines.filter(function(l){ return !/^\|?[\s:|-]{3,}\|?$/.test(l.trim()); })
    .map(function(l){
      var s = l.trim().replace(/^\|/,'').replace(/\|$/,'');
      return s.split('|').map(function(c){ return c.trim(); });
    });
  if(!rows.length) return '';
  var head = rows.shift();
  var th = head.map(function(c){ return '<th>' + artInline(c) + '</th>'; }).join('');
  var tb = rows.map(function(r){
    return '<tr>' + r.map(function(c){ return '<td>' + artInline(c) + '</td>'; }).join('') + '</tr>';
  }).join('');
  /* الجدول العريض على الجوال: بطاقات مفتاح/قيمة بدل تمرير أفقي مُتعب */
  var cards = rows.map(function(r){
    return '<div class="artkv">' + r.map(function(c,i){
      if(!c) return '';
      return '<div class="kvr"><span>' + esc(head[i]||'') + '</span><b>' + artInline(c) + '</b></div>';
    }).join('') + '</div>';
  }).join('');
  /* كل رابط في الجدول يظهر أيضًا كزرّ — وإلا اختفى مع التمرير */
  var btns = artLinks(lines.join('\n')).map(function(p){ return artBtn(p[0], p[1]); }).join('');
  return btns +
    '<div class="arttw" role="region" aria-label="جدول" tabindex="0"><table class="arttbl">' +
    '<thead><tr>' + th + '</tr></thead><tbody>' + tb + '</tbody></table></div>' +
    '<div class="artcards">' + cards + '</div>';
}
function artBlocks(t){
  if(!t) return '';
  return String(t).split(/\n{2,}/).map(function(b){
    b = b.trim();
    if(!b) return '';
    var lines = b.split('\n').map(function(l){ return l.trim(); }).filter(Boolean);
    /* جدول: سطران فأكثر وكلها تحوي فاصل «|». لا نشترط أن يبدأ السطر به —
       Google Docs يُخرج «أ | ب | ج» بلا أنابيب طرفية. */
    if(lines.length >= 2 && lines.every(function(l){ return l.indexOf('|') > -1; }))
      return artTable(lines);
    var m = b.match(/^#{2,4}\s*(.+)$/);
    if(m) return '<h4 class="artsub">' + esc(m[1]) + '</h4>';
    if(lines.length && lines.every(function(l){ return /^[-*]\s+/.test(l); }))
      return '<ul class="artul">' + lines.map(function(l){
        return '<li>' + artInline(l.replace(/^[-*]\s+/,'')) + '</li>'; }).join('') + '</ul>';
    /* فقرة ليست إلا رابطًا = زرّ، لا سطر أزرق تائه */
    var only = b.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/);
    if(only) return artBtn(only[1], only[2]);
    if(/^https?:\/\/\S+$/.test(b)) return artBtn(b, b);
    return '<p>' + artInline(b).replace(/\n/g,'<br>') + '</p>';
  }).join('');
}
function richText(t){ return artBlocks(t); }

'''
    src = src[:start] + NEW + src[end:]
    open(P, "w", encoding="utf-8").write(src)
    changed.append("app.js")
    print("app.js: عرض المقالة الجديد (جداول · بطاقات جوال · أزرار روابط)")

# ───────────────────────── index.html ─────────────────────────
H = "index.html"
h = open(H, encoding="utf-8").read()

if ".artbtn" in h:
    print("index.html: تنسيق المقالة مركّب مسبقًا — تخطٍّ")
else:
    anchor = ".artsub{margin:18px 0 6px;font-size:15px;font-weight:650}"
    if h.count(anchor) != 1:
        print("توقّف: مرساة CSS لم تطابق (%d)" % h.count(anchor)); sys.exit(1)
    css = """.artsub{margin:30px 0 12px;font-size:17px;font-weight:650;line-height:1.6;
  padding-inline-start:12px;border-inline-start:3px solid var(--accent)}
.artsub:first-child{margin-top:0}

/* الرابط فعلٌ لا بيان: زرّ لا خانة في آخر جدول */
.artbtn{display:flex;align-items:center;gap:11px;text-decoration:none;
  background:var(--surface-2);border:1px solid var(--line-2);border-radius:var(--r-sm);
  padding:11px 14px;margin:0 0 11px;color:var(--accent);transition:.15s}
.artbtn:hover{border-color:var(--accent);background:var(--accent-soft)}
.artbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.artbtn span{display:flex;flex-direction:column;gap:1px;min-width:0;flex:1}
.artbtn b{font-size:13.5px;font-weight:600;color:var(--accent);line-height:1.5}
.artbtn i{font-style:normal;font-size:11.5px;color:var(--muted);direction:ltr;text-align:right;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.artbtn .x{flex:0 0 auto;color:var(--faint)}
.artbtn:hover .x{color:var(--accent)}

.arttw{overflow-x:auto;margin:0 0 16px;border:1px solid var(--line);
  border-radius:var(--r-sm);background:var(--surface)}
.arttw:focus-visible{outline:2px solid var(--accent)}
.arttbl{border-collapse:collapse;width:100%;min-width:600px;font-size:13px}
.arttbl th,.arttbl td{padding:10px 13px;text-align:right;border-bottom:1px solid var(--line);
  vertical-align:top;line-height:1.7}
.arttbl th{background:var(--surface-2);font-weight:600;font-size:11.5px;color:var(--muted);
  white-space:nowrap;letter-spacing:.02em}
.arttbl tbody tr:last-child td{border-bottom:0}

.artcards{display:none}
.artkv{border:1px solid var(--line);border-radius:var(--r-sm);overflow:hidden;margin:0 0 12px}
.kvr{display:flex;gap:10px;padding:9px 12px;border-bottom:1px solid var(--line);font-size:13.5px}
.kvr:last-child{border-bottom:0}
.kvr span{flex:0 0 82px;color:var(--muted);font-size:11.5px;padding-top:2px}
.kvr b{font-weight:500;line-height:1.75;min-width:0;overflow-wrap:anywhere}

.artul{margin:10px 0 18px;padding-inline-start:22px}
.artul li{margin-bottom:8px;line-height:1.9}
.artul li::marker{color:var(--accent)}

.artlink{color:var(--accent);text-decoration:underline;text-underline-offset:3px;
  text-decoration-thickness:1px;word-break:break-word;overflow-wrap:anywhere}
.artlink:hover{color:var(--accent-2);text-decoration-thickness:2px}

.sec p{line-height:2.0;overflow-wrap:break-word;max-width:68ch}

@media(max-width:760px){
  .arttw{display:none}
  .artcards{display:block}
  .sec p,.artul li{font-size:15.2px;line-height:2.05}
  .artsub{font-size:16px;margin:24px 0 10px}
  .artbtn b{font-size:13px}
}"""
    h = h.replace(anchor, css)
    open(H, "w", encoding="utf-8").write(h)
    changed.append("index.html")
    print("index.html: تنسيق المقالة")

print("تم. المعدَّل: %s" % (", ".join(changed) if changed else "لا شيء"))
