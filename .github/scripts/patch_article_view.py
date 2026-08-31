#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
زر «مقالة» في اللوحة + عرض المقالة الكاملة بفقرات.

أهم ما فيه ليس الزر بل إصلاح العرض: كان الشرح الموسّع يُطبع داخل <p> واحدة،
فتضيع فواصل الأسطر. مقالة كاملة كانت ستظهر كتلة واحدة لا تُقرأ. الإصلاح يفيد
كل البطاقات القديمة أيضًا، لأن برومبت السحب اليومي يطلب «فقرات مفصولة بسطرين».

آمن للتكرار؛ يتوقف دون تغيير إن لم يطابق الملف المتوقع.
"""
import sys

changed = []

# ───────────────────────── app.js ─────────────────────────
P = "app.js"
src = open(P, encoding="utf-8").read()

if "richText" in src:
    print("app.js: مركّب مسبقًا — تخطٍّ")
else:
    PAIRS = []

    # ١) نوع مصدر جديد: مقالة
    PAIRS.append((
      "const SRC_LABEL = {x:'X / Twitter', youtube:'YouTube', github:'GitHub', web:'مواقع ومقالات'};",
      "const SRC_LABEL = {x:'X / Twitter', youtube:'YouTube', github:'GitHub', web:'مواقع ومقالات', article:'مقالات'};"))

    PAIRS.append((
      "const SRC_HUE   = {youtube:0, github:265, web:200, x:20};",
      "const SRC_HUE   = {youtube:0, github:265, web:200, x:20, article:150};"))

    # يظهر في الفلتر دائمًا حتى قبل أول مقالة
    PAIRS.append((
      "  const srcRows = ['x','web','youtube','github'].map(t => [t, srcM[t]||0, false])\n"
      "      .concat(Object.keys(srcM).filter(t=>!['x','web','youtube','github'].includes(t)).map(t=>[t,srcM[t],false]));",
      "  const srcRows = ['x','article','web','youtube','github'].map(t => [t, srcM[t]||0, false])\n"
      "      .concat(Object.keys(srcM).filter(t=>!['x','article','web','youtube','github'].includes(t)).map(t=>[t,srcM[t],false]));"))

    # ٢) عرض النص الطويل بفقرات وعناوين فرعية
    PAIRS.append((
      "      ${sec('شرح موسّع', '<p>'+esc(i.detailed_explanation)+'</p>')}",
      "      ${sec(srcOf(i)==='article'?'المقالة':'شرح موسّع', richText(i.detailed_explanation))}"))

    # ٣) روابط المصدر: مقالة ملصوقة بلا رابط، ورمز X كان يظهر لكل المصادر
    #    (عطل قديم يمسّ web وyoutube وgithub أيضًا، لا المقالات وحدها)
    PAIRS.append((
      """        <a class="xlink" href="${esc(i.source_url)}" target="_blank" rel="noopener">${ICON.x}</a>""",
      """        ${i.source_url?`<a class="xlink" href="${esc(i.source_url)}" target="_blank" rel="noopener" title="فتح المصدر">${isX(i)?ICON.x:ICON.ext}</a>`:''}"""))

    PAIRS.append((
      """      <a class="opensrc" href="${esc(i.source_url)}" target="_blank" rel="noopener">""",
      """      ${!i.source_url?'':`<a class="opensrc" href="${esc(i.source_url)}" target="_blank" rel="noopener">"""))

    PAIRS.append((
      """        <span class="u">${esc(i.source_url.replace(/^https?:\\/\\/(www\\.)?/,''))}</span></a>""",
      """        <span class="u">${esc(i.source_url.replace(/^https?:\\/\\/(www\\.)?/,''))}</span></a>`}"""))

    PAIRS.append((
      """      <a class="xlink" href="${esc(i.source_url)}" target="_blank" rel="noopener" title="فتح المصدر">${isX(i)?ICON.x:ICON.ext}</a>""",
      """      ${i.source_url?`<a class="xlink" href="${esc(i.source_url)}" target="_blank" rel="noopener" title="فتح المصدر">${isX(i)?ICON.x:ICON.ext}</a>`:''}"""))

    PAIRS.append((
      """        <a class="srcbtn" href="${esc(i.source_url)}" target="_blank" rel="noopener" title="${esc(i.source_url)}">${isX(i)?ICON.x:ICON.ext}<span>${isX(i)?'التغريدة الأصلية':'المصدر'}</span></a>""",
      """        ${!i.source_url?'':`<a class="srcbtn" href="${esc(i.source_url)}" target="_blank" rel="noopener" title="${esc(i.source_url)}">${isX(i)?ICON.x:ICON.ext}<span>${isX(i)?'التغريدة الأصلية':'المصدر'}</span></a>`}"""))

    # ٤) الدالة نفسها — تُحقن قبل viewDetail
    anchor = "function viewDetail("
    if src.count(anchor) < 1:
        print("توقّف: viewDetail غير موجودة"); sys.exit(1)
    helper = """/* نص طويل ← فقرات. سطران فارغان = فقرة جديدة، و«## » = عنوان فرعي.
   بدون هذا تظهر المقالة الكاملة كتلة واحدة لا تُقرأ. */
function richText(t){
  if(!t) return '';
  return String(t).split(/\\n{2,}/).map(function(b){
    b = b.trim();
    if(!b) return '';
    var m = b.match(/^#{2,4}\\s*(.+)$/);
    if(m) return '<h4 class="artsub">' + esc(m[1]) + '</h4>';
    return '<p>' + esc(b).replace(/\\n/g,'<br>') + '</p>';
  }).join('');
}

"""

    for n,(old,new) in enumerate(PAIRS,1):
        c = src.count(old)
        if c != 1:
            print("توقّف: الموضع %d وُجد %d مرة (المتوقع 1)" % (n,c)); sys.exit(1)
        src = src.replace(old,new)

    src = src.replace(anchor, helper + anchor, 1)

    # ٥) صندوق «أضف مقالة»
    add_anchor = "function openAdd(){"
    if src.count(add_anchor) != 1:
        print("توقّف: openAdd غير موجودة"); sys.exit(1)

    art = r"""/* ---------- صندوق «أضف مقالة» ----------
   زر منفصل عن + عمدًا: رابط المقالة نفسه لا يخبرنا إن كان عزيز يريد بطاقة
   موجزة أم قراءة كاملة مرتّبة. القصد لا يُستنتج من الرابط، فيُسأل عنه.

   ولماذا لا يوجد صندوق نص هنا؟ اللوحة صفحة ثابتة تمرّر المحتوى عبر رابط،
   وللروابط سقف طول لا تمرّ فيه مقالة. فبدل «انسخ ← الصق هنا ← ننسخ ← الصق
   هناك»، نفتح الطلب فارغًا ويلصق عزيز مرة واحدة. */
const ART_ISSUE = REPO_ISSUE_URL + '?labels=article&title=' + encodeURIComponent('مقالة: ');
function openArticle(){
  const ov=document.createElement('div'); ov.className='ov'; ov.id='artov';
  ov.onclick=e=>{ if(e.target===ov) ov.remove(); };
  ov.innerHTML = `<div class="addbox">
    <h4>أضف مقالة</h4>
    <p class="sub">تُقرأ كاملة وتُرتَّب بفقرات وعناوين، وتُصنَّف كبقية البطاقات.
      تجدها بفلتر <b>المصدر ← مقالات</b>.</p>
    <div class="artpick">
      <button class="artopt" onclick="artText()">
        <b>عندي نص المقالة</b>
        <span>يفتح طلبًا فارغًا جاهزًا — الصق النص هناك مباشرة واضغط التأكيد</span>
      </button>
      <button class="artopt" onclick="artShowUrl()">
        <b>عندي رابط المقالة</b>
        <span>تُقرأ بمتصفح حقيقي إن تعذّر جلبها بالطريقة العادية</span>
      </button>
    </div>
    <div id="arturlrow" style="display:none;margin-top:12px">
      <input type="url" id="arturl" placeholder="https://…" autocomplete="off" inputmode="url"
        oninput="document.getElementById('artgo').disabled=!/^https?:\/\/.+\..+/.test(this.value.trim())"
        onkeydown="if(event.key==='Enter')artGo()">
      <div class="addrow" style="margin-top:10px">
        <button onclick="document.getElementById('artov').remove()">إلغاء</button>
        <button class="go" id="artgo" disabled onclick="artGo()">أضف المقالة</button>
      </div>
    </div>
    <div class="addnote">ما تضيفه بنفسك لا يُرفض أبدًا، ويظهر في «أضفتها بنفسي».</div>
  </div>`;
  document.body.appendChild(ov);
}
function artShowUrl(){
  document.getElementById('arturlrow').style.display='block';
  setTimeout(()=>document.getElementById('arturl').focus(),40);
}
function artText(){
  window.open(ART_ISSUE, '_blank', 'noopener');
  document.getElementById('artov').remove();
  toast('افتحت طلبًا فارغًا — الصق نص المقالة فيه واضغط التأكيد الأخضر');
}
function artGo(){
  const u=(document.getElementById('arturl').value||'').trim();
  if(!/^https?:\/\/.+\..+/.test(u)) return;
  window.open(ART_ISSUE + '&body=' + encodeURIComponent(u), '_blank', 'noopener');
  document.getElementById('artov').remove();
  toast('افتحت GitHub — اضغط التأكيد الأخضر لتُقرأ المقالة وتُضاف');
}

"""
    src = src.replace(add_anchor, art + add_anchor, 1)
    open(P,"w",encoding="utf-8").write(src)
    changed.append("app.js")
    print("app.js: نوع «مقالة» + عرض بفقرات + صندوق الإضافة")

# ───────────────────────── index.html ─────────────────────────
H = "index.html"
h = open(H, encoding="utf-8").read()

if "openArticle()" in h:
    print("index.html: مركّب مسبقًا — تخطٍّ")
else:
    btn_anchor = '  <button class="iconbtn addbtn" onclick="openAdd()"'
    if h.count(btn_anchor) != 1:
        print("توقّف: زر الإضافة لم يطابق (%d)" % h.count(btn_anchor)); sys.exit(1)
    new_btn = ('  <button class="iconbtn artbtn" onclick="openArticle()" '
               'title="أضف مقالة" aria-label="أضف مقالة">\n'
               '    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
               'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
               '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
               '<path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M8 9h2"/></svg>\n'
               '  </button>\n')
    h = h.replace(btn_anchor, new_btn + btn_anchor)

    css_anchor = ".iconbtn.addbtn{background:var(--accent);border-color:var(--accent);color:#fff}"
    if h.count(css_anchor) != 1:
        print("توقّف: مرساة CSS لم تطابق"); sys.exit(1)
    css = css_anchor + """
.artpick{display:flex;flex-direction:column;gap:8px;margin-top:6px}
.artopt{display:block;width:100%;text-align:right;padding:13px 15px;border-radius:10px;
  border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer;
  font:inherit;transition:border-color .12s}
.artopt:hover{border-color:var(--accent)}
.artopt b{display:block;font-size:14px;margin-bottom:3px}
.artopt span{display:block;font-size:11.5px;color:var(--faint);line-height:1.6}
.artsub{margin:18px 0 6px;font-size:15px;font-weight:650}
.artsub:first-child{margin-top:0}"""
    h = h.replace(css_anchor, css)
    open(H,"w",encoding="utf-8").write(h)
    changed.append("index.html")
    print("index.html: زر المقالة وتنسيقه")

print("تم. المعدَّل: %s" % (", ".join(changed) if changed else "لا شيء"))
