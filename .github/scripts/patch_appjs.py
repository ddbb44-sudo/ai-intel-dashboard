#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
يعدّل app.js ليميّز رابط حساب X عن رابط تغريدة، فيوجّه الأول لوسم `account`.
آمن للتكرار: إن كان معدَّلًا مسبقًا يخرج بلا تغيير.
يتوقف عند أي عدم تطابق بدل التخمين.
"""
import sys

P = "app.js"
src = open(P, encoding="utf-8").read()

if "xprofile" in src:
    print("app.js معدَّل مسبقًا — لا تغيير")
    sys.exit(0)

PAIRS = []

PAIRS.append((
"""function linkKind(u){
  try{ const h=new URL(u).hostname.replace(/^www\\./,'');
    if(/^(x|twitter)\\.com$/.test(h)) return ['x','تغريدة X'];""",
"""const X_RESERVED = ['home','search','explore','notifications','messages','settings',
  'i','intent','compose','login','signup','about','tos','privacy','hashtag'];
function linkKind(u){
  try{ const U=new URL(u), h=U.hostname.replace(/^www\\./,'');
    if(/^(x|twitter)\\.com$/.test(h)){
      const seg = U.pathname.split('/').filter(Boolean);
      // /USER/status/123 = تغريدة · /USER = حساب
      if(seg.length===1 && !X_RESERVED.includes(seg[0].toLowerCase()))
        return ['xprofile','حساب X — يُتابَع يوميًا'];
      return ['x','تغريدة X'];
    }"""))

PAIRS.append((
'<span class="addkind" data-k="x">تغريدة X</span>',
'<span class="addkind" data-k="xprofile">حساب X</span>\n'
'      <span class="addkind" data-k="x">تغريدة X</span>'))

PAIRS.append((
"""  const body = u + (note ? '\\n\\nملاحظة عزيز: '+note : '');
  const url = REPO_ISSUE_URL + '?labels=inbox&title=' + encodeURIComponent('رابط: '+(label||'')) +
              '&body=' + encodeURIComponent(body);
  window.open(url,'_blank','noopener');
  document.getElementById('addov').remove();
  toast('افتحت GitHub — اضغط زر التأكيد الأخضر لإتمام الإضافة');""",
"""  const body = u + (note ? '\\n\\nملاحظة عزيز: '+note : '');
  const isAcc = (k==='xprofile');
  const url = REPO_ISSUE_URL
            + '?labels=' + (isAcc ? 'account' : 'inbox')
            + '&title=' + encodeURIComponent((isAcc?'حساب: ':'رابط: ')+(label||''))
            + '&body=' + encodeURIComponent(body);
  window.open(url,'_blank','noopener');
  document.getElementById('addov').remove();
  toast(isAcc ? 'افتحت GitHub — اضغط التأكيد الأخضر ليُضاف الحساب ويُسحب تاريخه'
              : 'افتحت GitHub — اضغط زر التأكيد الأخضر لإتمام الإضافة');"""))

PAIRS.append((
"""    <p class="sub">الصق رابط تغريدة أو مقالة أو فيديو أو مستودع. سيُقرأ ويُصنَّف ويُكتب بالعربية،
      ثم يظهر هنا ببطاقة تحمل وسم «مضافة يدويًا».</p>""",
"""    <p class="sub">الصق رابط تغريدة أو مقالة أو فيديو أو مستودع ← بطاقة واحدة.<br>
      أو الصق رابط <b>حساب X</b> (<code>x.com/USERNAME</code>) ← يُضاف للمتابعة اليومية
      ويُسحب تاريخه لآخر 60 يومًا تلقائيًا.</p>"""))

for i, (old, new) in enumerate(PAIRS, 1):
    n = src.count(old)
    if n != 1:
        print("توقّف: الموضع %d وُجد %d مرة (المتوقع 1) — app.js يختلف عن المتوقع، "
              "لم أغيّر شيئًا." % (i, n))
        sys.exit(1)
    src = src.replace(old, new)

open(P, "w", encoding="utf-8").write(src)
print("عُدّلت app.js — أربعة مواضع")
