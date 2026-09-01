/* منطق الحالة — مفصول عن الدالة ليكون قابلًا للاختبار محليًا بلا Netlify */

export function empty(){
  return { likes:[], bookmarks:{}, collections:[], opened:[], rev:0, saved_at:null };
}

function toggle(list, id, on){
  const i = list.indexOf(id);
  if (on && i < 0) list.push(id);
  if (!on && i >= 0) list.splice(i, 1);
}

/* العميل يرسل عمليات لا حالة كاملة، فلا يدهس جهازٌ عملَ جهاز.
   أي عملية مجهولة تُتجاهل بصمت ولا تُسقط الطلب كله. */
export function apply(state, ops){
  let changed = 0;
  for (const op of ops || []) {
    if (!op || typeof op.k !== 'string') continue;
    const id = typeof op.id === 'string' ? op.id.slice(0,64) : '';
    const on = op.on !== false;
    if (op.k === 'like' && id){ toggle(state.likes, id, on); changed++; }
    else if (op.k === 'bm' && id && typeof op.coll === 'string'){
      const c = op.coll.slice(0,40);
      state.bookmarks[c] = state.bookmarks[c] || [];
      toggle(state.bookmarks[c], id, on);
      if (!state.bookmarks[c].length) delete state.bookmarks[c];
      changed++;
    }
    else if (op.k === 'open' && id){ toggle(state.opened, id, true); changed++; }
    else if (op.k === 'coll' && typeof op.name === 'string'){
      const n = op.name.trim().slice(0,40);
      if (n && !state.collections.includes(n)){ state.collections.push(n); changed++; }
    }
  }
  return changed;
}
