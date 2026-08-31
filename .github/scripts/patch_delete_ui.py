#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
زر حذف البطاقة في صفحة التفاصيل.

اللوحة كانت تملك ثلاث طرق للإضافة (تغريدة · حساب · مقالة) وصفرًا للحذف.
أي بطاقة خاطئة تبقى للأبد، ولا سبيل لإزالتها إلا تحرير JSON باليد.

الزر يمرّ بنفس مسار الطلبات المألوف، ويُظهر تأكيدًا فيه عنوان البطاقة —
فلا يُحذف شيء بضغطة طائشة.

آمن للتكرار؛ يتوقف دون تغيير إن لم يطابق الملف المتوقع.
"""
import sys

changed = []

# ───────────────────────── app.js ─────────────────────────
P = "app.js"
src = open(P, encoding="utf-8").read()

if "askDelete" in src:
    print("app.js: زر الحذف مركّب مسبقًا — تخطٍّ")
else:
    old = """        <button class="act ${liked?'on':''}" onclick="toggleLike('${i.id}',this)">${liked?ICON.likeF:ICON.like}</button>
        <button class="act ${bm?'on':''}" onclick="openBookmark('${i.id}')">${bm?ICON.bmF:ICON.bm}</button>
      </div>"""
    new = """        <button class="act ${liked?'on':''}" onclick="toggleLike('${i.id}',this)">${liked?ICON.likeF:ICON.like}</button>
        <button class="act ${bm?'on':''}" onclick="openBookmark('${i.id}')">${bm?ICON.bmF:ICON.bm}</button>
        <button class="act del" onclick="askDelete('${i.id}')" title="حذف البطاقة">${ICON.trash}</button>
      </div>"""
    if src.count(old) != 1:
        print("توقّف: شريط أدوات التفاصيل لم يطابق (%d)" % src.count(old)); sys.exit(1)
    src = src.replace(old, new)

    # أيقونة السلة
    icon_anchor = "  x:'<svg width=\"14\" height=\"14\" viewBox=\"0 0 24 24\" fill=\"currentColor\">"
    if src.count(icon_anchor) != 1:
        print("توقّف: كتلة الأيقونات لم تطابق"); sys.exit(1)
    src = src.replace(icon_anchor,
      "  trash:'<svg width=\"15\" height=\"15\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" "
      "stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\">"
      "<path d=\"M3 6h18\"/><path d=\"M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2\"/>"
      "<path d=\"M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6\"/>"
      "<path d=\"M10 11v6\"/><path d=\"M14 11v6\"/></svg>',\n" + icon_anchor)

    # صندوق التأكيد — يُحقن قبل openArticle
    anchor = "/* ---------- صندوق «أضف مقالة» ----------"
    if src.count(anchor) != 1:
        anchor = "function openAdd(){"
        if src.count(anchor) != 1:
            print("توقّف: لم أجد موضعًا لحقن صندوق الحذف"); sys.exit(1)

    box = r'''/* ---------- حذف بطاقة ----------
   اللوحة صفحة ثابتة لا تكتب في المستودع، فالحذف يمرّ بطلب مثل الإضافة.
   التأكيد يعرض العنوان كاملًا — لا حذف بضغطة واحدة طائشة. */
function askDelete(id){
  const i = Store.get(id);
  if(!i) return;
  const ov=document.createElement('div'); ov.className='ov'; ov.id='delov';
  ov.onclick=e=>{ if(e.target===ov) ov.remove(); };
  ov.innerHTML = `<div class="addbox">
    <h4>حذف هذه البطاقة؟</h4>
    <div class="delcard">
      <div class="delserial">${esc(i.serial_display)}</div>
      <div class="deltitle">${esc(i.arabic_title)}</div>
    </div>
    <p class="sub">تُزال من اللوحة نهائيًا. رقمها لا يُعاد استخدامه، والنسخة
      السابقة تبقى في تاريخ Git إن احتجتها.</p>
    <div class="addrow">
      <button onclick="document.getElementById('delov').remove()">إلغاء</button>
      <button class="go danger" onclick="delGo('${i.id}')">نعم، احذفها</button>
    </div>
    <div class="addnote">تفتح صفحة GitHub — اضغط التأكيد الأخضر فيها لإتمام الحذف.</div>
  </div>`;
  document.body.appendChild(ov);
}
function delGo(id){
  const i = Store.get(id);
  const url = REPO_ISSUE_URL + '?labels=delete'
            + '&title=' + encodeURIComponent('حذف: ' + (i ? i.serial_display : id))
            + '&body='  + encodeURIComponent(id + (i ? '\n\n' + i.arabic_title : ''));
  window.open(url,'_blank','noopener');
  const ov=document.getElementById('delov'); if(ov) ov.remove();
  toast('افتحت GitHub — اضغط التأكيد الأخضر لإتمام الحذف');
}

'''
    src = src.replace(anchor, box + anchor, 1)
    open(P, "w", encoding="utf-8").write(src)
    changed.append("app.js")
    print("app.js: زر الحذف وصندوق التأكيد")

# ───────────────────────── index.html ─────────────────────────
H = "index.html"
h = open(H, encoding="utf-8").read()

if ".delcard" in h:
    print("index.html: تنسيق الحذف مركّب مسبقًا — تخطٍّ")
else:
    anchor = ".artsub{margin:30px 0 12px"
    if h.count(anchor) != 1:
        anchor = ".artsub{"
        if h.count(anchor) < 1:
            print("توقّف: مرساة CSS لم تطابق"); sys.exit(1)
    css = """.act.del{color:var(--faint)}
.act.del:hover{color:#b3261e;border-color:#b3261e;background:#fdecea}
.delcard{background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-sm);
  padding:12px 14px;margin:4px 0 12px}
.delserial{font-size:11.5px;color:var(--muted);margin-bottom:4px}
.deltitle{font-size:14.5px;font-weight:600;line-height:1.7}
button.go.danger{background:#b3261e;border-color:#b3261e}
button.go.danger:hover{background:#8f1d17}
"""
    h = h.replace(anchor, css + anchor, 1)
    open(H, "w", encoding="utf-8").write(h)
    changed.append("index.html")
    print("index.html: تنسيق زر الحذف")

print("تم. المعدَّل: %s" % (", ".join(changed) if changed else "لا شيء"))
