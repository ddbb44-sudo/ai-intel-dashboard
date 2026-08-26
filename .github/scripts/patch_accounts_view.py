#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
يضيف إلى اللوحة شاشة «المتابَعون»: قائمة كل الحسابات المتابَعة، بحث داخلها،
ودخول لصفحة كل حساب (#/u/<handle>) الموجودة أصلًا.

آمن للتكرار، ويتوقف دون تغيير إن لم يطابق الملف المتوقع.
"""
import sys

changed = []

# ---------------- app.js ----------------
P = "app.js"
src = open(P, encoding="utf-8").read()

if "viewAccounts" in src:
    print("app.js: شاشة المتابَعون مركّبة مسبقًا — تخطٍّ")
else:
    # 1) المسار
    old_route = """  if(h.startsWith('#/u/')) return viewProfile(decodeURIComponent(h.slice(4)));
  viewFeed();"""
    new_route = """  if(h.startsWith('#/u/')) return viewProfile(decodeURIComponent(h.slice(4)));
  if(h.startsWith('#/accounts')) return viewAccounts();
  viewFeed();"""
    if src.count(old_route) != 1:
        print("توقّف: مسار route لم يطابق (%d)" % src.count(old_route)); sys.exit(1)
    src = src.replace(old_route, new_route)

    # 2) إعادة البناء عند تغيّر الفلاتر
    old_r2 = """  else if(h.startsWith('#/u/')) viewProfile(decodeURIComponent(h.slice(4)));"""
    new_r2 = """  else if(h.startsWith('#/u/')) viewProfile(decodeURIComponent(h.slice(4)));
  else if(h.startsWith('#/accounts')) viewAccounts();"""
    if src.count(old_r2) != 1:
        print("توقّف: render لم يطابق (%d)" % src.count(old_r2)); sys.exit(1)
    src = src.replace(old_r2, new_r2)

    # 3) صورة الحساب: الحسابات المضافة حديثًا بلا خانة في الـsprite،
    #    فنرجع لرابط الصورة مباشرة بدل مربع فارغ.
    old_av = """  const a = Store.author(handle), i = (a && a.sprite>=0) ? a.sprite : -1;
  if(i<0) return 'background-image:none';"""
    new_av = """  const a = Store.author(handle), i = (a && a.sprite>=0) ? a.sprite : -1;
  if(i<0) return (a && a.avatar)
    ? `background-image:url('${a.avatar}');background-size:cover;background-position:center`
    : 'background-image:none';"""
    if src.count(old_av) != 1:
        print("توقّف: avStyle لم يطابق (%d)" % src.count(old_av)); sys.exit(1)
    src = src.replace(old_av, new_av)

    # 4) الشاشة نفسها — تُحقن قبل viewProfile
    anchor = "function viewProfile(handle){"
    if src.count(anchor) != 1:
        print("توقّف: viewProfile لم يطابق"); sys.exit(1)

    view = r"""let ACCQ = '';
function accSearch(v){ ACCQ = (v||'').trim().toLowerCase(); viewAccounts(true); }
function viewAccounts(keepFocus){
  const cards = Store.all();
  const cnt = {};
  cards.forEach(i => { if(i.author) cnt[i.author] = (cnt[i.author]||0) + 1; });

  // authors.json هو مصدر القائمة؛ ونضيف أي حساب له بطاقات ولم يُسجَّل بعد
  const seen = {}, list = [];
  (Store.authors()||[]).forEach(a => { seen[a.handle.toLowerCase()] = 1; list.push(a); });
  Object.keys(cnt).forEach(h => {
    if(!seen[h.toLowerCase()]) list.push({handle:h, name:h, bio:'', followers:null,
      url:'https://x.com/'+h, sprite:-1, is_arabic:false, _new:true});
  });

  list.forEach(a => a._n = cnt[a.handle] || 0);
  const q = ACCQ;
  const shown = q ? list.filter(a =>
      (a.handle+' '+(a.name||'')+' '+(a.bio||'')).toLowerCase().includes(q)) : list;
  shown.sort((x,y) => y._n - x._n || (x.name||x.handle).localeCompare(y.name||y.handle,'ar'));

  const withCards = list.filter(a=>a._n>0).length;
  const row = a => `
    <div class="acccard" onclick="go('#/u/${encodeURIComponent(a.handle)}')">
      <div class="av" style="width:44px;height:44px;${avStyle(a.handle,44)}"></div>
      <div class="accmain">
        <div class="accname">${esc(a.name||a.handle)}${a._new?' <span class="accnew">جديد</span>':''}</div>
        <div class="acchandle">@${esc(a.handle)}</div>
        ${a.bio?`<div class="accbio">${esc(a.bio)}</div>`:''}
      </div>
      <div class="accright">
        <div class="accn ${a._n?'':'zero'}"><b>${a._n}</b><span>بطاقة</span></div>
        ${a.followers!=null?`<div class="accf">${nf(a.followers)} متابع</div>`:''}
        <a class="accx" href="${esc(a.url||('https://x.com/'+a.handle))}" target="_blank"
           rel="noopener" onclick="event.stopPropagation()" title="فتح في X">${ICON.x}</a>
      </div>
    </div>`;

  document.getElementById('main').innerHTML = `
    <div class="backbar"><button class="backbtn" onclick="go('#/')">→ رجوع إلى اللوحة</button></div>
    <div class="acchead">
      <h2>المتابَعون</h2>
      <div class="accsub"><b class="num">${list.length}</b> حسابًا مُتابَعًا ·
        <b class="num">${withCards}</b> منها له بطاقات ·
        <b class="num">${cards.length}</b> بطاقة إجمالًا</div>
      <input id="accq" class="accinput" placeholder="ابحث باسم الحساب أو معرّفه…"
        value="${esc(ACCQ)}" oninput="accSearch(this.value)" autocomplete="off">
      <div class="accnote">اضغط أي حساب لترى بطاقاته · لإضافة حساب جديد استخدم زر + والصق رابط ملفه الشخصي</div>
    </div>
    ${shown.length ? `<div class="accgrid">${shown.map(row).join('')}</div>`
      : `<div class="empty"><b>لا حساب يطابق بحثك</b>جرّب كلمة أخرى.</div>`}`;
  setLive(shown.length);
  if(keepFocus){
    const el = document.getElementById('accq');
    if(el){ el.focus(); el.setSelectionRange(el.value.length, el.value.length); }
  } else window.scrollTo(0,0);
}

"""
    src = src.replace(anchor, view + anchor)
    open(P, "w", encoding="utf-8").write(src)
    changed.append("app.js")
    print("app.js: أُضيفت شاشة المتابَعون")

# ---------------- index.html ----------------
H = "index.html"
h = open(H, encoding="utf-8").read()

if "#/accounts" in h:
    print("index.html: الزر والتنسيق مركّبان مسبقًا — تخطٍّ")
else:
    # زر في الشريط العلوي قبل زر الإضافة
    btn_anchor = '  <button class="iconbtn addbtn" onclick="openAdd()"'
    if h.count(btn_anchor) != 1:
        print("توقّف: زر الإضافة في index.html لم يطابق (%d)" % h.count(btn_anchor)); sys.exit(1)
    new_btn = ('  <button class="iconbtn hb" onclick="go(\'#/accounts\')" '
               'title="الحسابات المتابَعة" aria-label="الحسابات المتابَعة">\n'
               '    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
               'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
               '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
               '<circle cx="9" cy="7" r="4"/>'
               '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
               '<path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>\n'
               '  </button>\n')
    h = h.replace(btn_anchor, new_btn + btn_anchor)

    # التنسيق
    css_anchor = ".iconbtn.addbtn{background:var(--accent);border-color:var(--accent);color:#fff}"
    if h.count(css_anchor) != 1:
        print("توقّف: مرساة CSS لم تطابق"); sys.exit(1)
    css = css_anchor + """
.acchead{padding:18px 2px 10px}
.acchead h2{margin:0 0 4px;font-size:21px}
.accsub{color:var(--faint);font-size:12.5px;margin-bottom:12px}
.accinput{width:100%;max-width:420px;padding:9px 12px;border-radius:9px;
  border:1px solid var(--line);background:var(--card);color:var(--fg);font:inherit;font-size:13px}
.accinput:focus{outline:none;border-color:var(--accent)}
.accnote{color:var(--faint);font-size:11.5px;margin-top:8px}
.accgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:9px;padding-bottom:40px}
.acccard{display:flex;gap:11px;align-items:flex-start;padding:12px;border:1px solid var(--line);
  border-radius:12px;background:var(--card);cursor:pointer;transition:border-color .12s,transform .12s}
.acccard:hover{border-color:var(--accent);transform:translateY(-1px)}
.accmain{flex:1;min-width:0}
.accname{font-weight:650;font-size:14px;line-height:1.35}
.accnew{font-size:10px;background:var(--accent);color:#fff;border-radius:5px;padding:1px 5px;vertical-align:middle}
.acchandle{color:var(--faint);font-size:11.5px;direction:ltr;text-align:right}
.accbio{color:var(--faint);font-size:11.5px;margin-top:4px;line-height:1.5;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.accright{display:flex;flex-direction:column;align-items:flex-end;gap:3px;flex-shrink:0}
.accn{font-size:11px;color:var(--faint);text-align:center;line-height:1.2}
.accn b{display:block;font-size:16px;color:var(--fg)}
.accn.zero b{color:var(--faint);opacity:.6}
.accf{font-size:10.5px;color:var(--faint)}
.accx{color:var(--faint);margin-top:2px}
.accx:hover{color:var(--accent)}"""
    h = h.replace(css_anchor, css)
    open(H, "w", encoding="utf-8").write(h)
    changed.append("index.html")
    print("index.html: أُضيف زر المتابَعون وتنسيقه")

print("تم. المعدَّل: %s" % (", ".join(changed) if changed else "لا شيء"))
