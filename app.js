/* =====================================================================
   AI Intelligence Dashboard — Prototype
   طبقات مستقلة: Store · Prefs · Taxonomy · FilterEngine · Ranking · UI · Router
   ===================================================================== */

/* ---------- 1) DATA LAYER ---------- */
const RAW = window.__RAW;
const Store = (() => {
  const items = RAW.items, authors = {}, byId = {};
  RAW.authors.forEach(a => authors[a.handle] = a);
  items.forEach(i => byId[i.id] = i);
  return {
    all: () => items,
    get: id => byId[id],
    bySerial: n => items.find(i => i.serial === n),
    author: h => authors[h] || {handle:h, name:h, avatar:'', bio:'', followers:null, url:'https://x.com/'+h, domains:[], entities:[]},
    authors: () => RAW.authors,
    stats: RAW.stats
  };
})();

/* ---------- 2) PREFERENCES (Like / Bookmark / learning signal) ---------- */
/* ---------- المزامنة ----------
   الإعجابات والمحفوظات كانت تعيش في متصفح واحد فقط: لا تنتقل بين الأجهزة،
   ويمسحها Safari بعد أسبوع بلا فتح. الحل: نسخة مركزية في المستودع.
   القراءة مجانية من أي جهاز بلا إعداد. الكتابة تحتاج توكن يُلصق مرة واحدة.
   المتصفح يبقى النسخة العاملة — إن فشلت المزامنة لا ينكسر شيء. */
const SYNC = {
  url: 'https://ai-intel-sync.netlify.app/prefs',
  key: 'sRRrqpWu3BzDKAmHDhTgfD6Z',
  qKey: 'aiintel.queue.v1',
  status: 'idle', _timer: null,
  queue(){ try { return JSON.parse(localStorage.getItem(this.qKey) || '[]'); } catch(e){ return []; } },
  setQueue(q){ try { localStorage.setItem(this.qKey, JSON.stringify(q.slice(-500))); } catch(e){} },
};

/* العميل يرسل عمليات لا حالة كاملة — نسخة مطابقة لما يطبّقه الخادم،
   تُستعمل لعرض فوري قبل وصول الرد ولتغطية فترة انقطاع الشبكة. */
function applyOps(st, ops){
  const tog = (list, id, on) => { const i = list.indexOf(id);
    if (on && i < 0) list.push(id); if (!on && i >= 0) list.splice(i,1); };
  (ops||[]).forEach(op => {
    if (!op || !op.k) return;
    const on = op.on !== false;
    if (op.k === 'like' && op.id) tog(st.likes, op.id, on);
    else if (op.k === 'bm' && op.id && op.coll){
      st.bookmarks[op.coll] = st.bookmarks[op.coll] || [];
      tog(st.bookmarks[op.coll], op.id, on);
      if (!st.bookmarks[op.coll].length) delete st.bookmarks[op.coll];
    }
    else if (op.k === 'open' && op.id) tog(st.opened, op.id, true);
    else if (op.k === 'coll' && op.name && !st.collections.includes(op.name)) st.collections.push(op.name);
  });
  return st;
}

/* كل تغيير يدخل طابورًا محفوظًا في المتصفح، فلا يضيع بانقطاع أو إغلاق */
function emit(op){
  const q = SYNC.queue(); q.push(op); SYNC.setQueue(q);
  if (SYNC.status !== 'saving') { SYNC.status = 'pending'; refreshSyncChip(); }
  clearTimeout(SYNC._timer);
  SYNC._timer = setTimeout(flushPrefs, 1200);   // دفعة واحدة بعد آخر ضغطة
}

const Prefs = (() => {
  const KEY = 'aiintel.prefs.v1';
  const DEFAULT_COLLECTIONS = ['Drive7','Personal','Marketing','SEO','AI Tools','Research','Coding','Islamic','Later'];
  let s = { likes:[], bookmarks:{}, collections:[...DEFAULT_COLLECTIONS], opened:[] };
  try { const raw = localStorage.getItem(KEY); if (raw) s = Object.assign(s, JSON.parse(raw)); } catch(e) {}
  const saveLocal = () => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch(e) {} };
  const save = saveLocal;
  return {
    state: () => s,
    replace(next){ s = Object.assign(s, next); saveLocal(); },
    liked: id => s.likes.includes(id),
    toggleLike(id){ const i = s.likes.indexOf(id); i<0 ? s.likes.push(id) : s.likes.splice(i,1);
      save(); emit({k:'like', id, on: i<0}); return i<0; },
    bookmarksOf: id => Object.keys(s.bookmarks).filter(c => (s.bookmarks[c]||[]).includes(id)),
    isBookmarked: id => Object.values(s.bookmarks).some(a => a.includes(id)),
    toggleBookmark(id, coll){
      s.bookmarks[coll] = s.bookmarks[coll] || [];
      const i = s.bookmarks[coll].indexOf(id);
      i<0 ? s.bookmarks[coll].push(id) : s.bookmarks[coll].splice(i,1);
      save(); emit({k:'bm', id, coll, on: i<0}); return i<0;
    },
    collections: () => s.collections,
    addCollection(n){ n=(n||'').trim(); if(n && !s.collections.includes(n)){ s.collections.push(n); save(); emit({k:'coll', name:n}); } },
    markOpened(id){ if(!s.opened.includes(id)){ s.opened.push(id); save(); emit({k:'open', id}); } },
    isOpened: id => s.opened.includes(id),
    /* متجه التفضيلات: يُبنى من الإعجابات والحفظ */
    vector(){
      const v = {ct:{}, dom:{}, ent:{}, au:{}}, ids = new Set(s.likes);
      Object.values(s.bookmarks).forEach(a => a.forEach(id => ids.add(id)));
      ids.forEach(id => { const it = Store.get(id); if(!it) return;
        it.content_types.forEach(x => v.ct[x]=(v.ct[x]||0)+1);
        it.domains.forEach(x => v.dom[x]=(v.dom[x]||0)+1);
        it.entities.forEach(x => v.ent[x]=(v.ent[x]||0)+1);
        v.au[it.author]=(v.au[it.author]||0)+1;
      });
      v.n = ids.size; return v;
    },
    export(){ return JSON.stringify(s,null,1); },
    import(json){ try{ s = Object.assign(s, JSON.parse(json)); save(); return true; }catch(e){ return false; } }
  };
})();

/* ---------- 3) RANKING ---------- */
const Ranking = {
  relevance(item, v){
    if(!v.n) return 0;
    let hits=0, tot=0;
    item.content_types.forEach(x=>{hits+=(v.ct[x]||0);tot++});
    item.domains.forEach(x=>{hits+=(v.dom[x]||0);tot++});
    item.entities.forEach(x=>{hits+=(v.ent[x]||0)*1.5;tot++});
    hits += (v.au[item.author]||0)*2;
    return Math.max(0, Math.min(100, Math.round((hits/Math.max(v.n,1))*45)));
  },
  score(item, v){
    const rel = this.relevance(item, v);
    return Math.round(.35*item.importance_score + .25*item.engagement_score + .30*rel + .10*item.freshness);
  }
};

/* الخادم هو المرجع، ثم تُطبَّق فوقه العمليات التي لم تصل بعد من هذا الجهاز */
function adopt(remote){
  const st = { likes: remote.likes || [], bookmarks: remote.bookmarks || {},
               opened: remote.opened || [],
               collections: (remote.collections && remote.collections.length)
                              ? remote.collections.slice() : Prefs.state().collections.slice() };
  applyOps(st, SYNC.queue());
  Prefs.replace(st);
}

async function pullPrefs(){
  try {
    const r = await fetch(SYNC.url + '?t=' + Date.now(), {cache:'no-store'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const remote = await r.json();
    if (!remote || typeof remote !== 'object') throw new Error('bad');
    adopt(remote);
    SYNC.status = SYNC.queue().length ? 'pending' : 'synced';
    if (SYNC.queue().length) flushPrefs();
    return true;
  } catch(e){ SYNC.status = 'offline'; return false; }   // المحلي يبقى سليمًا
}

async function flushPrefs(){
  const q = SYNC.queue();
  if (!q.length){ SYNC.status = 'synced'; refreshSyncChip(); return; }
  SYNC.status = 'saving'; refreshSyncChip();
  try {
    const r = await fetch(SYNC.url, {method:'POST',
      headers:{'content-type':'application/json', 'x-key': SYNC.key},
      body: JSON.stringify({ops: q})});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const st = await r.json();
    SYNC.setQueue(SYNC.queue().slice(q.length));   // ما جدّ أثناء الإرسال يبقى
    adopt(st);
    SYNC.status = SYNC.queue().length ? 'pending' : 'synced';
    if (typeof refreshBadges === 'function') refreshBadges();
  } catch(e){
    SYNC.status = 'failed';                        // الطابور محفوظ — يُعاد بهدوء
    clearTimeout(SYNC._timer);
    SYNC._timer = setTimeout(flushPrefs, 20000);
  }
  refreshSyncChip();
}

/* ---------- 4) TAXONOMY ----------
   المفردات المعلنة في ملف التعليمات هي المرجع. تظهر كاملة دائمًا حتى لو كان عدّها صفرًا،
   ويُضاف إليها أي تصنيف ظهر في البيانات ولم يكن معلنًا. لا يُخفى تصنيف طلبه المستخدم. */
const DECLARED = {
  content_types: ['إصدار','أداة','شرح','تجربة','بحث وقياس','رأي','خبر'],
  tool_types: ['MCP','Skill','Agent','Plugin','Prompt','API/SDK','تطبيق','نموذج'],
  domains: ['برمجة وهندسة','أعمال وإدارة','تصميم وواجهات','تسويق ومحتوى','نماذج وLLM',
    'بيانات وتحليلات','بحث وتعليم','إنتاجية شخصية','فيديو وصوت','أمن سيبراني',
    'روبوتات وعتاد','صحة','إسلامي'],
  change_types: ['New Release','New Feature','Upgrade','Update','Model Update','API Update',
    'Pricing Change','New Integration','MCP Support','New Agent Feature','Beta / Preview',
    'General Availability','Deprecation','Shutdown','Research Release','Open Source','Acquisition',
    'Outage / Incident','Security']
};
const Taxonomy = (() => {
  const countMap = key => { const m={}; Store.all().forEach(i => (i[key]||[]).forEach(x => m[x]=(m[x]||0)+1)); return m; };
  const merge = (key, pinned) => {
    const m = countMap(key);
    const declared = DECLARED[key] || [];
    const extra = Object.keys(m).filter(x => !declared.includes(x)).sort((a,b)=>m[b]-m[a]);
    const rows = declared.concat(extra).map(t => [t, m[t]||0, (pinned||[]).includes(t)]);
    // المثبّتة أولًا، ثم غير الفارغة بالعدد، ثم الفارغة
    const pin = rows.filter(r=>r[2]);
    const full = rows.filter(r=>!r[2] && r[1]>0).sort((a,b)=>b[1]-a[1]);
    const zero = rows.filter(r=>!r[2] && r[1]===0);
    return pin.concat(full, zero);
  };
  const dm={};
  Store.all().forEach(i => { const d=i.published_at.slice(0,10); dm[d]=(dm[d]||0)+1; });
  const dates = Object.entries(dm).sort((a,b)=> b[0].localeCompare(a[0]));
  const PIN=[];   // التثبيت انتقل إلى محور «نوع الأداة» المستقل
  const entM = countMap('entities');
  const srcM = {}; Store.all().forEach(i => { const t = i.source_type||'x'; srcM[t]=(srcM[t]||0)+1; });
  const srcRows = ['x','article','web','youtube','github'].map(t => [t, srcM[t]||0, false])
      .concat(Object.keys(srcM).filter(t=>!['x','article','web','youtube','github'].includes(t)).map(t=>[t,srcM[t],false]));
  return {
    sources: srcRows,
    dates,
    pinned: PIN,
    content_types_ordered: merge('content_types'),
    content_types: merge('content_types'),
    tool_types: merge('tool_types'),
    domains: merge('domains'),
    change_types: merge('change_types'),
    entities: Object.entries(entM).sort((a,b)=>b[1]-a[1]).map(([t,n])=>[t,n,false])
  };
})();

/* ---------- 5) FILTER ENGINE ---------- */
const ZOPEN = { ct:false, tool:false, dom:false, chg:false, ent:false };
const F = { q:'', ct:[], tool:[], dom:[], ent:[], chg:[], src:[], lang:'', tier:'useful+', pref:[], coll:'', from:'', to:'', time:'', sort:'smart' };

const FilterEngine = {
  apply(items){
    const v = Prefs.vector();
    const q = F.q.trim().toLowerCase();
    let out = items.filter(i => {
      if (F.tier==='important' && i.importance_tier!=='important') return false;
      if (F.tier==='useful+' && !(i.importance_tier==='important'||i.importance_tier==='useful')) return false;
      if (F.lang==='ar' && !i.is_arabic_source) return false;
      if (F.lang==='fr' && i.is_arabic_source) return false;
      if (F.src.length && !F.src.includes(i.source_type)) return false;
      if (F.ct.length  && !F.ct.some(x => i.content_types.includes(x))) return false;
      if (F.tool.length && !F.tool.some(x => (i.tool_types||[]).includes(x))) return false;
      if (F.dom.length && !F.dom.some(x => i.domains.includes(x))) return false;
      if (F.ent.length && !F.ent.every(x => i.entities.includes(x))) return false;
      if (F.chg.length && !F.chg.every(x => i.change_types.includes(x))) return false;
      if (F.pref.includes('liked') && !Prefs.liked(i.id)) return false;
      if (F.pref.includes('bookmarked') && !Prefs.isBookmarked(i.id)) return false;
      if (F.pref.includes('unread') && Prefs.isOpened(i.id)) return false;
      if (F.pref.includes('mine') && i.added_via !== 'issue') return false;
      if (F.pref.includes('rec') && Ranking.relevance(i,v) < 12) return false;
      if (F.coll && !Prefs.bookmarksOf(i.id).includes(F.coll)) return false;
      const t = new Date(i.published_at).getTime();
      if (F.time){ const h = {d1:24,d7:168,d30:720}[F.time]; if (Date.now()-t > h*3600e3) return false; }
      if (F.from && t < new Date(F.from).getTime()) return false;
      if (F.to && t > new Date(F.to).getTime()+864e5) return false;
      if (q){
        const hay = (i.arabic_title+' '+i.arabic_summary+' '+i.detailed_explanation+' '+i.original_text+' '+
          i.content_types.join(' ')+' '+(i.tool_types||[]).join(' ')+' '+i.domains.join(' ')+' '+i.entities.join(' ')+' '+i.change_types.join(' ')+' '+
          i.author+' '+(Store.author(i.author).name||'')).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    const m = i => i.metrics || {};
    const sorters = {
      smart:   (a,b) => Ranking.score(b,v) - Ranking.score(a,v),
      newest:  (a,b) => new Date(b.published_at) - new Date(a.published_at),
      likes:   (a,b) => (m(b).likes||0) - (m(a).likes||0),
      reposts: (a,b) => (m(b).reposts||0) - (m(a).reposts||0),
      views:   (a,b) => (m(b).views||0) - (m(a).views||0),
      eng:     (a,b) => b.engagement_score - a.engagement_score
    };
    return out.sort(sorters[F.sort] || sorters.smart);
  },
  activeChips(){
    const out = [];
    const push = (label, clear) => out.push({label, clear});
    if (F.q) push('بحث: '+F.q, () => { F.q=''; document.getElementById('q').value=''; });
    F.ct.forEach(x => push(x, () => F.ct = F.ct.filter(y=>y!==x)));
    F.tool.forEach(x => push(x, () => F.tool = F.tool.filter(y=>y!==x)));
    F.dom.forEach(x => push(x, () => F.dom = F.dom.filter(y=>y!==x)));
    F.ent.forEach(x => push(x, () => F.ent = F.ent.filter(y=>y!==x)));
    F.chg.forEach(x => push(x, () => F.chg = F.chg.filter(y=>y!==x)));
    F.pref.forEach(x => push({liked:'أعجبني',bookmarked:'محفوظ',rec:'مُرشَّح لي',unread:'لم أقرأه'}[x], () => F.pref = F.pref.filter(y=>y!==x)));
    if (F.coll) push('مجموعة: '+F.coll, () => F.coll='');
    if (F.lang) push(F.lang==='ar'?'عربي':'أجنبي', () => F.lang='');
    if (F.time) push({d1:'آخر 24 ساعة',d7:'آخر 7 أيام',d30:'آخر 30 يومًا'}[F.time], () => F.time='');
    if (F.from||F.to) push('من '+(F.from?dLabel(F.from):'البداية')+' إلى '+(F.to?dLabel(F.to):'النهاية'), () => { F.from=''; F.to=''; });
    if (F.tier==='important') push('مهم فقط', () => F.tier='useful+');
    if (F.tier==='all') push('يشمل الضوضاء', () => F.tier='useful+');
    return out;
  }
};

/* ---------- 6) HELPERS ---------- */
const esc = s => (s==null?'':String(s)).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const nf = n => n==null ? '—' : n>=1e6 ? (n/1e6).toFixed(n>=1e7?0:1)+'M' : n>=1e3 ? (n/1e3).toFixed(n>=1e4?0:1)+'K' : String(n);
function dLabel(iso){ const [y,m,d]=iso.split('-'); return (+d)+' '+AR_MONTHS[(+m)-1]+' '+y; }
const AR_MONTHS=['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
function arPlural(n, one, two, few, many){
  if(n===1) return one; if(n===2) return two;
  return (n%100>=3 && n%100<=10) ? n+' '+few : n+' '+many;
}
function ago(iso){
  const d=new Date(iso), h=(Date.now()-d)/3600e3;
  if(h<1) return 'قبل دقائق';
  if(h<24){ const n=Math.round(h); return 'قبل '+arPlural(n,'ساعة','ساعتين','ساعات','ساعة'); }
  if(h<48) return 'أمس';
  const dd=Math.round(h/24);
  if(dd<30) return 'قبل '+arPlural(dd,'يوم','يومين','أيام','يومًا');
  return d.getDate()+' '+AR_MONTHS[d.getMonth()]+' '+d.getFullYear();
}
function toast(msg){ const t=document.getElementById('toast'); t.textContent=msg; t.classList.add('show'); clearTimeout(t._h); t._h=setTimeout(()=>t.classList.remove('show'),1900); }
const SP = {cols: RAW.stats.sprite_cols||10, tile: RAW.stats.sprite_tile||52};
const SRC_LABEL = {x:'X / Twitter', youtube:'YouTube', github:'GitHub', web:'مواقع ومقالات', article:'مقالات'};
const SRC_HUE   = {youtube:0, github:265, web:200, x:20, article:150};
function srcOf(i){ return i.source_type || 'x'; }
function isX(i){ return srcOf(i)==='x'; }
/* اسم المصدر المعروض: حساب X، أو اسم القناة/المستودع/الموقع */
function srcName(i){ return isX(i) ? (Store.author(i.author).name || i.author) : (i.source_name || i.source_site || i.author); }
function srcSub(i){ return isX(i) ? '@'+i.author : (i.source_site || SRC_LABEL[srcOf(i)] || ''); }
/* شارة حرفية ملوّنة للمصادر غير X (لا صورة حساب لها) */
function badgeHTML(i, size){
  const t = srcOf(i), h = SRC_HUE[t] != null ? SRC_HUE[t] : 200;
  const ch = (srcName(i).trim()[0] || '#').toUpperCase();
  return `<div class="av badge" style="width:${size}px;height:${size}px;font-size:${Math.round(size*0.42)}px;`+
         `background:hsl(${h} 55% 94%);color:hsl(${h} 45% 38%)">${esc(ch)}</div>`;
}
function avatarHTML(i, size, onclick){
  if(!isX(i)) return badgeHTML(i, size);
  return `<div class="av" style="width:${size}px;height:${size}px;${avStyle(i.author,size)}" ${onclick||''} title="${esc(srcName(i))}"></div>`;
}
function avStyle(handle, size){
  const a = Store.author(handle), i = (a && a.sprite>=0) ? a.sprite : -1;
  if(i<0) return (a && a.avatar)
    ? `background-image:url('${a.avatar}');background-size:cover;background-position:center`
    : 'background-image:none';
  const k = size/SP.tile, c = i%SP.cols, r = Math.floor(i/SP.cols);
  return `background-size:${(SP.cols*SP.tile*k).toFixed(1)}px auto;background-position:${(-c*size).toFixed(1)}px ${(-r*size).toFixed(1)}px`;
}
const ICON = {
  ext:'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><path d="M15 3h6v6"/><path d="M10 14L21 3"/></svg>',
  like:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1L12 21l7.7-7.6 1.1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>',
  likeF:'<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1L12 21l7.7-7.6 1.1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>',
  bm:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>',
  bmF:'<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>',
  trash:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>',
  x:'<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.9 2H22l-7 8 8.2 12h-6.4l-5-7.3L6 22H2.9l7.5-8.6L2.5 2h6.6l4.5 6.6zM17.8 20.1h1.7L7.3 3.8H5.5z"/></svg>'
};

/* ---------- 7) UI COMPONENTS ---------- */
function cardHTML(i){
  const a = Store.author(i.author);
  const liked = Prefs.liked(i.id), bm = Prefs.isBookmarked(i.id);
  const m = i.metrics||{};
  const tags = [
    ...i.entities.slice(0,3).map(x=>`<button class="tag ent" onclick="tagClick(event,'ent','${esc(x)}')">${esc(x)}</button>`),
    ...i.change_types.slice(0,2).map(x=>`<button class="tag chg" onclick="tagClick(event,'chg','${esc(x)}')">${esc(x)}</button>`),
    ...(i.tool_types||[]).map(x=>`<button class="tag tool" onclick="tagClick(event,'tool','${esc(x)}')">${esc(x)}</button>`),
    ...i.content_types.slice(0,2).map(x=>`<button class="tag" onclick="tagClick(event,'ct','${esc(x)}')">${esc(x)}</button>`),
    ...i.domains.slice(0,2).map(x=>`<button class="tag" onclick="tagClick(event,'dom','${esc(x)}')">${esc(x)}</button>`)
  ].join('');
  const tierLbl = {important:'مهم', useful:'مفيد', low:'قيمة منخفضة', noise:'ضوضاء'}[i.importance_tier];
  const th = (i.thread_parts||[]).length;
  const dup = i.also_reported.length
    ? `<div class="dup" onclick="go('#/c/${i.id}')">ذكرها أيضًا <b class="num">${i.also_reported.length}</b> ${i.also_reported.length>2?'مصادر':'مصدر'} — ${i.also_reported.map(s=>'@'+esc(s.author)).join('، ')}${th?` · وسلسلة من <b class="num">${th+1}</b> منشورات لنفس الحساب`:''}</div>`
    : (th ? `<div class="dup" onclick="go('#/c/${i.id}')">سلسلة من <b class="num">${th+1}</b> منشورات لنفس الحساب</div>` : '');
  const met = [];
  if(m.likes!=null) met.push(`<span title="إعجابات">♥ <b class="num">${nf(m.likes)}</b></span>`);
  if(m.reposts!=null) met.push(`<span title="إعادة نشر">⇄ <b class="num">${nf(m.reposts)}</b></span>`);
  if(m.replies!=null) met.push(`<span title="ردود">↩ <b class="num">${nf(m.replies)}</b></span>`);
  if(m.bookmarks!=null) met.push(`<span title="حفظ">⚑ <b class="num">${nf(m.bookmarks)}</b></span>`);
  if(m.views!=null) met.push(`<span title="مشاهدات">◉ <b class="num">${nf(m.views)}</b></span>`);
  return `<article class="card" id="card-${i.id}">
    <div class="chead">
      ${avatarHTML(i,38, isX(i)?`onclick="go('#/u/${esc(i.author)}')"`:'')}
      <div class="who">
        <div>${isX(i)
            ? `<span class="nm" onclick="go('#/u/${esc(i.author)}')">${esc(srcName(i))}</span>`
            : `<span class="nm plain">${esc(srcName(i))}</span>`}
          <span class="hd">${esc(srcSub(i))} · ${ago(i.published_at)}</span>${i.added_via==='issue'?' <span class="mine" title="أضفتها بنفسك">مضافة يدويًا</span>':''}</div>
        <div style="display:flex;gap:6px;align-items:center;margin-top:3px">
          <span class="serial" onclick="copySerial('${i.serial_display}')" title="انسخ رقم البطاقة">${i.serial_display}</span>
          <span class="tier ${i.importance_tier}">${tierLbl}</span>
        </div>
      </div>
      ${i.source_url?`<a class="xlink" href="${esc(i.source_url)}" target="_blank" rel="noopener" title="فتح المصدر">${isX(i)?ICON.x:ICON.ext}</a>`:''}
    </div>
    <h3 class="t" onclick="go('#/c/${i.id}')">${esc(i.arabic_title)}</h3>
    <p class="s">${esc(i.arabic_summary)}</p>
    ${dup}
    <div class="tags">${tags}</div>
    <div class="cfoot">
      <div class="met">${met.join('')}</div>
      <div class="acts">
        <button class="act ${liked?'on':''}" onclick="toggleLike('${i.id}',this)" title="إعجاب (إشارة تفضيل داخلية)">${liked?ICON.likeF:ICON.like}</button>
        <button class="act ${bm?'on':''}" onclick="openBookmark('${i.id}')" title="حفظ في مجموعة">${bm?ICON.bmF:ICON.bm}</button>
        ${!i.source_url?'':`<a class="srcbtn" href="${esc(i.source_url)}" target="_blank" rel="noopener" title="${esc(i.source_url)}">${isX(i)?ICON.x:ICON.ext}<span>${isX(i)?'التغريدة الأصلية':'المصدر'}</span></a>`}
        <button class="readmore" onclick="go('#/c/${i.id}')">قراءة المزيد</button>
      </div>
    </div>
  </article>`;
}

function filtersHTML(){
  const grp = (title, key, list) => {
    const id='g_'+key;
    const lbl  = n => (key==='src' ? (SRC_LABEL[n]||n) : n);
    const chip = ([name,n,pin]) => `<button class="chip ${pin?'pin ':''}${F[key].includes(name)?'on':''}${n?'':' empty'}" onclick="toggleF('${key}','${esc(name)}')" ${n?'':'title="تصنيف معتمد لكن لا توجد بطاقات تحمله في هذه الدفعة"'}>${esc(lbl(name))}<span class="c">(${n})</span></button>`;
    const full = list.filter(r=>r[1]>0 || r[2]);
    const zero = list.filter(r=>r[1]===0 && !r[2]);
    const openZ = ZOPEN[key];
    return `<div class="fgroup"><h4>${title} <span class="gcount">${full.length}</span>${F[key].length?`<button onclick="clearF('${key}')">مسح</button>`:''}</h4>
      <div class="chips ${full.length>14?'scroll':''}" id="${id}">${full.map(chip).join('')}${openZ?zero.map(chip).join(''):''}</div>
      ${zero.length?`<button class="more" onclick="toggleZero('${key}')">${openZ?'إخفاء':'إظهار'} ${zero.length} تصنيفًا معتمدًا بلا بطاقات ${openZ?'−':'+'}</button>`:''}</div>`;
  };
  const prefChip = (k,l) => `<button class="chip ${F.pref.includes(k)?'on':''}" onclick="toggleF('pref','${k}')">${l}</button>`;
  const colls = Prefs.collections().map(cn => `<button class="chip ${F.coll===cn?'on':''}" onclick="setColl('${esc(cn)}')">${esc(cn)}</button>`).join('');
  return `
  <div class="fgroup"><h4>تفضيلاتي</h4><div class="chips">
    ${prefChip('liked','أعجبني')}${prefChip('bookmarked','محفوظ')}${prefChip('rec','مُرشَّح لي')}${prefChip('unread','لم أقرأه')}${prefChip('mine','أضفتها بنفسي')}
  </div></div>
  <div class="fgroup"><h4>المجموعات</h4><div class="chips">${colls}</div></div>
  <div class="fgroup"><h4>الأهمية</h4><div class="chips">
    <button class="chip ${F.tier==='important'?'on':''}" onclick="setTier('important')">مهم فقط</button>
    <button class="chip ${F.tier==='useful+'?'on':''}" onclick="setTier('useful+')">مهم + مفيد</button>
    <button class="chip ${F.tier==='all'?'on':''}" onclick="setTier('all')">الكل</button>
  </div></div>
  <div class="fgroup"><h4>اللغة</h4><div class="chips">
    <button class="chip ${F.lang===''?'on':''}" onclick="setLang('')">الكل</button>
    <button class="chip ${F.lang==='ar'?'on':''}" onclick="setLang('ar')">عربي</button>
    <button class="chip ${F.lang==='fr'?'on':''}" onclick="setLang('fr')">أجنبي</button>
  </div></div>
  <div class="fgroup"><h4>الزمن</h4><div class="chips">
    <button class="chip ${F.time==='d1'?'on':''}" onclick="setTime('d1')">آخر 24 ساعة</button>
    <button class="chip ${F.time==='d7'?'on':''}" onclick="setTime('d7')">7 أيام</button>
    <button class="chip ${F.time==='d30'?'on':''}" onclick="setTime('d30')">30 يومًا</button>
  </div>
  <div class="dsel"><label>من</label>
    <select onchange="setRange('from',this.value)">
      <option value="">— أقدم تاريخ —</option>
      ${Taxonomy.dates.slice().reverse().map(([d,n])=>`<option value="${d}" ${F.from===d?'selected':''}>${dLabel(d)} (${n})</option>`).join('')}
    </select></div>
  <div class="dsel"><label>إلى</label>
    <select onchange="setRange('to',this.value)">
      <option value="">— أحدث تاريخ —</option>
      ${Taxonomy.dates.map(([d,n])=>`<option value="${d}" ${F.to===d?'selected':''}>${dLabel(d)} (${n})</option>`).join('')}
    </select></div>
  ${(F.from||F.to)?`<button class="more" onclick="setRange('clear')">مسح المدى الزمني</button>`:''}
  </div>
  ${grp('طبيعة التغيير','chg',Taxonomy.change_types)}
  ${grp('الشركة / المنتج','ent',Taxonomy.entities)}
  ${grp('نوع المحتوى','ct',Taxonomy.content_types_ordered)}
  ${grp('نوع الأداة','tool',Taxonomy.tool_types)}
  ${grp('المجال','dom',Taxonomy.domains)}
  ${grp('المصدر','src',Taxonomy.sources)}
  <div class="fgroup"><h4>تفضيلاتي — مزامنة ونسخ احتياطي</h4><div class="chips">
    <button class="chip" id="syncChip" onclick="openSync()">${syncLabel()}</button>
    <button class="chip" onclick="exportPrefs()">تصدير</button>
    <button class="chip" onclick="importPrefs()">استيراد</button>
    <button class="chip" onclick="resetAll()">مسح كل الفلاتر</button>
  </div>
  <div class="note" style="font-size:11px;color:var(--faint);margin-top:6px">
    إعجاباتك ومحفوظاتك تُقرأ من المستودع على كل جهاز. للكتابة من هذا الجهاز فعّل المزامنة مرة واحدة.
  </div></div>`;
}

/* ---------- 8) VIEWS ---------- */
let SHOWN = 60; const PAGE_STEP = 60;
function moreCards(){ SHOWN += PAGE_STEP; viewFeed(); }
function showAllCards(){ SHOWN = 100000; viewFeed(); }
function armAutoLoad(){
  const s = document.getElementById('sentinel');
  if(!s) return;
  if(window._io) window._io.disconnect();
  window._io = new IntersectionObserver(es=>{
    if(es.some(e=>e.isIntersecting)){ window._io.disconnect(); moreCards(); }
  }, {rootMargin:'900px 0px'});
  window._io.observe(s);
}
function viewFeed(){
  const items = FilterEngine.apply(Store.all());
  const chips = FilterEngine.activeChips();
  const sortBtn = (k,l) => `<button class="${F.sort===k?'on':''}" onclick="setSort('${k}')">${l}</button>`;
  const html = `
    <div class="bar">
      <div class="count"><b class="num">${items.length}</b> بطاقة مطابقة${items.length!==Store.all().length?` <span class="num">من ${Store.all().length}</span>`:''}${items.length>SHOWN?` — <span class="shownote">تُحمَّل تلقائيًا مع التمرير (ظهر <b class="num">${SHOWN}</b>)</span>`:''}</div>
      <div class="sortsel">
        ${sortBtn('smart','ذكي')}${sortBtn('newest','الأحدث')}${sortBtn('eng','الأكثر تفاعلًا')}${sortBtn('likes','الأعلى إعجابًا')}${sortBtn('reposts','الأعلى نشرًا')}${sortBtn('views','الأكثر مشاهدة')}
      </div>
    </div>
    ${chips.length?`<div class="active-filters">${chips.map((c,ix)=>`<span class="afc">${esc(c.label)}<button onclick="clearChip(${ix})">×</button></span>`).join('')}</div>`:''}
    ${items.length? items.slice(0,SHOWN).map(cardHTML).join('') :
      `<div class="empty"><b>لا توجد بطاقات مطابقة</b>جرّب توسيع الفلاتر أو مسحها.</div>`}
    ${items.length>SHOWN? `<div id="sentinel"></div>
      <div class="loadrow">
        <button class="loadmore" onclick="moreCards()">تحميل <span class="num">${Math.min(PAGE_STEP, items.length-SHOWN)}</span> بطاقة أخرى — تبقّى <span class="num">${items.length-SHOWN}</span></button>
        <button class="loadall" onclick="showAllCards()">عرض الكل (<span class="num">${items.length}</span>) دفعة واحدة</button>
      </div>` : (items.length>PAGE_STEP? `<div class="allshown">ظهرت كل الـ<b class="num">${items.length}</b> بطاقة المطابقة</div>`:'')}`;
  document.getElementById('main').innerHTML = html;
  window._chips = chips;
  window._lastCount = items.length;
  setLive(items.length);
  armAutoLoad();
}

/* نص طويل ← فقرات. سطران فارغان = فقرة جديدة، و«## » = عنوان فرعي.
   بدون هذا تظهر المقالة الكاملة كتلة واحدة لا تُقرأ. */
/* ---------- عرض نص المقالة ----------
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

function viewDetail(id){
  const i = Store.get(id);
  if(!i) return viewFeed();
  Prefs.markOpened(id);
  const a = Store.author(i.author), m = i.metrics||{}, xsrc = isX(i);
  const liked = Prefs.liked(i.id), bm = Prefs.isBookmarked(i.id);
  const cell = (l,v) => `<div class="mcell"><b>${nf(v)}</b><span>${l}</span></div>`;
  const sec = (t,body) => body ? `<div class="sec"><h5>${t}</h5>${body}</div>` : '';
  const cluster = (i.also_reported.length ? sec('نفس الخبر ذكرته مصادر أخرى',
      i.also_reported.map(s=>`<a class="lnk" href="${esc(s.url)}" target="_blank" rel="noopener">@${esc(s.author)} — ${esc(s.url)}</a>`).join('')) : '')
    + ((i.thread_parts||[]).length ? sec('بقية السلسلة من نفس الحساب',
      i.thread_parts.map(s=>`<a class="lnk" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>`).join('')) : '');
  const quoted = i.quoted ? sec('المنشور المقتبَس',
      `<div class="qbox"><b>@${esc(i.quoted.h)}</b><br>${esc(i.quoted.x)}</div>`) : '';
  const gloss = i.glossary.length ? sec('شرح المصطلحات',
      i.glossary.map(g=>`<div class="gl"><b>${esc(g.term)}</b><span>${esc(g.ar)}</span></div>`).join('')) : '';
  const links = i.external_links.length ? sec('الروابط المرفقة',
      i.external_links.map(l=>`<a class="lnk" href="${esc(l)}" target="_blank" rel="noopener">${esc(l)}</a>`).join('')) : '';
  document.getElementById('main').innerHTML = `
   <div class="detail">
    <div class="backbar">
      <button class="backbtn" onclick="back()">→ رجوع إلى اللوحة</button>
      <span class="serial">${i.serial_display}</span>
      <span class="tier ${i.importance_tier}">${({important:'مهم',useful:'مفيد',low:'قيمة منخفضة',noise:'ضوضاء'})[i.importance_tier]}</span>
      <div style="margin-inline-start:auto;display:flex;gap:6px">
        <button class="act ${liked?'on':''}" onclick="toggleLike('${i.id}',this)">${liked?ICON.likeF:ICON.like}</button>
        <button class="act ${bm?'on':''}" onclick="openBookmark('${i.id}')">${bm?ICON.bmF:ICON.bm}</button>
        <button class="act del" onclick="askDelete('${i.id}')" title="حذف البطاقة">${ICON.trash}</button>
      </div>
    </div>
    <div class="dwrap">
      <div class="chead">
        ${avatarHTML(i,38, xsrc?`onclick="go('#/u/${esc(i.author)}')"`:'')}
        <div class="who">
          <div>${xsrc?`<span class="nm" onclick="go('#/u/${esc(i.author)}')">${esc(srcName(i))}</span>`:`<span class="nm plain">${esc(srcName(i))}</span>`} <span class="hd">${esc(srcSub(i))}</span></div>
          <div class="hd">${ago(i.published_at)} · <span class="num">${new Date(i.published_at).toISOString().slice(0,10)}</span></div>
        </div>
        ${i.source_url?`<a class="xlink" href="${esc(i.source_url)}" target="_blank" rel="noopener" title="فتح المصدر">${isX(i)?ICON.x:ICON.ext}</a>`:''}
      </div>
      <h1>${esc(i.arabic_title)}</h1>
      <p style="font-size:15.5px;color:var(--ink-2);line-height:1.9;margin:0">${esc(i.arabic_summary)}</p>
      ${!i.source_url?'':`<a class="opensrc" href="${esc(i.source_url)}" target="_blank" rel="noopener">
        ${xsrc?ICON.x:ICON.ext}<b>${xsrc?'افتح التغريدة الأصلية على X':'افتح المصدر الأصلي'}</b>
        <span class="u">${esc(i.source_url.replace(/^https?:\/\/(www\.)?/,''))}</span></a>`}
      <div class="tags" style="margin-top:14px">
        ${i.entities.map(x=>`<span class="tag ent">${esc(x)}</span>`).join('')}
        ${i.change_types.map(x=>`<span class="tag chg">${esc(x)}</span>`).join('')}
        ${(i.tool_types||[]).map(x=>`<span class="tag tool">${esc(x)}</span>`).join('')}
        ${i.content_types.map(x=>`<span class="tag">${esc(x)}</span>`).join('')}
        ${i.domains.map(x=>`<span class="tag">${esc(x)}</span>`).join('')}
      </div>
      ${sec(srcOf(i)==='article'?'المقالة':'شرح موسّع', richText(i.detailed_explanation))}
      ${sec('لماذا هذا مهم', '<p>'+esc(i.why_it_matters)+'</p>')}
      ${gloss}
      ${quoted}
      ${sec('النص الأصلي ('+(i.is_arabic_source?'عربي':'إنجليزي')+')', '<div class="orig">'+esc(i.original_text)+'</div>')}
      ${links}
      ${cluster}
      ${sec('بيانات التفاعل',
        '<div class="metgrid">'+cell('إعجابات',m.likes)+cell('ردود',m.replies)+cell('إعادة نشر',m.reposts)+cell('اقتباسات',m.quotes)+cell('حفظ',m.bookmarks)+cell('مشاهدات',m.views)+'</div>'+
        '<div class="note">الأرقام لقطة لحظية وقت السحب: '+'<span class="num">'+new Date(i.metrics_captured_at).toISOString().slice(0,16).replace('T',' ')+'</span> UTC — وليست قيمًا حية.</div>')}
      ${sec('التقييم الداخلي',
        `<div class="metgrid">${cell('أهمية',i.importance_score)}${cell('تفاعل مُطبَّع',i.engagement_score)}${cell('قرب شخصي',Ranking.relevance(i,Prefs.vector()))}${cell('حداثة',Math.round(i.freshness))}${cell('الترتيب',Ranking.score(i,Prefs.vector()))}</div>
        <div class="note">«التفاعل المُطبَّع» محسوب نسبة إلى عدد متابعي الحساب، لا بالأرقام المطلقة. «القرب الشخصي» يبدأ من صفر ويرتفع كلما ضغطت إعجاب أو حفظت بطاقات مشابهة.</div>`)}
      ${sec('ملاحظات مهمة من النقاش',
        '<div class="note" style="font-size:13px">لم تُسحب الردود في هذه الجولة — اتُّفق على قصرها لاحقًا على البطاقات المهمة فقط. القسم يظهر فارغًا بدل تعبئته بمحتوى غير محقَّق.</div>')}
    </div>
   </div>`;
  window.scrollTo(0,0);
}

let ACCQ = '';
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

function viewProfile(handle){
  const a = Store.author(handle);
  const mine = Store.all().filter(i=>i.author===handle || (i.also_reported||[]).some(s=>s.author===handle));
  const v = Prefs.vector();
  mine.sort((x,y)=>Ranking.score(y,v)-Ranking.score(x,v));
  const meta = [];
  if(a.followers!=null) meta.push(`<span>المتابعون <b class="num">${nf(a.followers)}</b></span>`);
  meta.push(`<span>${a.is_arabic?'حساب عربي':'حساب أجنبي'}</span>`);
  if(a.location) meta.push(`<span>${esc(a.location)}</span>`);
  meta.push(`<span>${a.source==='official'?'حساب رسمي مقترح':'من قائمة '+esc((a.source||'').replace('list:',''))}</span>`);
  meta.push(`<span>بطاقات <b class="num">${mine.length}</b></span>`);
  const doms = (a.domains||[]).slice(0,8).map(d=>`<button class="tag" onclick="tagClick(event,'dom','${esc(d)}')">${esc(d)}</button>`).join('');
  const ents = (a.entities||[]).slice(0,8).map(d=>`<button class="tag ent" onclick="tagClick(event,'ent','${esc(d)}')">${esc(d)}</button>`).join('');
  document.getElementById('main').innerHTML = `
    <div class="backbar"><button class="backbtn" onclick="back()">→ رجوع إلى اللوحة</button></div>
    <div class="phead">
      <div class="av lg" style="${avStyle(handle,68)}"></div>
      <div class="pinfo">
        <h2>${esc(a.name)}</h2>
        <div class="hd">@${esc(a.handle)}</div>
        <div class="bio">${esc(a.bio)||'<span style="color:var(--faint)">لا توجد نبذة</span>'}</div>
        <div class="pmeta">${meta.join('')}</div>
        <div class="tags" style="margin-top:10px">${ents}${doms}</div>
        <div style="margin-top:12px;display:flex;gap:7px;flex-wrap:wrap">
          <a class="btn" href="${esc(a.url)}" target="_blank" rel="noopener" style="text-decoration:none">فتح الحساب في X</a>
          ${a.website?`<a class="btn ghost" href="${esc(a.website)}" target="_blank" rel="noopener" style="text-decoration:none">الموقع</a>`:''}
          ${a.linkedin?`<a class="btn ghost" href="${esc(a.linkedin)}" target="_blank" rel="noopener" style="text-decoration:none">LinkedIn</a>`:'<span class="btn ghost" style="opacity:.55;cursor:default">LinkedIn غير متاح</span>'}
        </div>
      </div>
    </div>
    ${(setLive(mine.length),'')}${mine.length? mine.map(cardHTML).join('') : `<div class="empty"><b>لم تُقبل أي بطاقة من هذا الحساب</b>كل منشوراته الخمسة الأخيرة صُنِّفت ضوضاء أو خارج نطاق الاهتمام.</div>`}`;
  window.scrollTo(0,0);
}

/* ---------- 9) ACTIONS ---------- */
/* كل تغيير في الفلاتر يمر من هنا.
   السبب: كان render() وحده يعيد بناء القائمة لكن يترك المتصفح عند موضع التمرير القديم،
   فيبقى عزيز ينظر إلى منتصف النتائج الجديدة فيظن أن شيئًا لم يتغيّر (فحص 21 أغسطس:
   بعد فلترة من 608 إلى 144 بطاقة بقي التمرير عند 6000px وظهرت البطاقة #000197 في أعلى الشاشة).
   الحل: ارجع لأعلى القائمة، وأعلن العدد الجديد بإشعار قصير. */
function refilter(){
  const before = window._lastCount;
  render();
  if(location.hash && location.hash!=='#/' && location.hash!=='') return;
  window.scrollTo({top:0, behavior:'instant'});
  const n = window._lastCount;
  if(n!==before) toast(n ? arPlural(n,'بطاقة واحدة مطابقة','بطاقتان مطابقتان','بطاقات مطابقة','بطاقة مطابقة') : 'لا توجد بطاقات مطابقة');
  const fl = document.getElementById('filters'); if(fl) fl.scrollTop = window._flScroll||0;
}
function toggleF(k,v){ const a=F[k]; const i=a.indexOf(v); i<0?a.push(v):a.splice(i,1); refilter(); }
function clearF(k){ F[k]=[]; refilter(); }
function clearChip(ix){ (window._chips[ix]||{}).clear?.(); refilter(); }
function setTier(t){ F.tier=t; refilter(); }
function setLang(l){ F.lang=l; refilter(); }
function setTime(t){ F.time = F.time===t?'':t; if(F.time){F.from='';F.to='';} refilter(); }
function setRange(which,val){
  if(which==='clear'){ F.from=''; F.to=''; }
  else { F[which]=val||''; F.time=''; 
    if(F.from && F.to && F.from>F.to){ const t=F.from; F.from=F.to; F.to=t; } }
  refilter();
}
function setSort(s){ F.sort=s; refilter(); }
function setColl(c){ F.coll = F.coll===c?'':c; refilter(); }
function showRest(id,btn){ document.getElementById(id+'_rest').style.display='contents'; btn.remove(); }
function toggleZero(k){ ZOPEN[k]=!ZOPEN[k]; document.getElementById('filters').innerHTML = filtersHTML(); }
function tagClick(e,k,v){ e.stopPropagation(); if(!F[k].includes(v)) F[k].push(v); if(location.hash!=='#/') go('#/'); else refilter(); }
function resetAll(){ Object.assign(F,{q:'',ct:[],tool:[],dom:[],ent:[],chg:[],src:[],lang:'',tier:'useful+',pref:[],coll:'',from:'',to:'',time:'',sort:'smart'}); document.getElementById('q').value=''; refilter(); }
function copySerial(s){ navigator.clipboard?.writeText(s); toast('نُسخ رقم البطاقة '+s); }
function toggleLike(id,btn){
  const on = Prefs.toggleLike(id);
  btn.classList.toggle('on',on); btn.innerHTML = on?ICON.likeF:ICON.like;
  toast(on?'أُضيفت إلى تفضيلاتك — سيتعلم الترتيب منها':'أُزيلت من تفضيلاتك');
  refreshBadges();
  if(F.sort==='smart' || F.pref.length) setTimeout(render,350);
}
function openBookmark(id){
  const cur = Prefs.bookmarksOf(id);
  const rows = Prefs.collections().map(c=>`<div class="collrow ${cur.includes(c)?'on':''}" onclick="pickColl('${id}','${esc(c)}',this)">
      <span style="flex:1">${esc(c)}</span><span>${cur.includes(c)?'✓':'+'}</span></div>`).join('');
  const ov=document.createElement('div'); ov.className='ov'; ov.onclick=e=>{if(e.target===ov){ov.remove();render();}};
  ov.innerHTML = `<div class="modal">
      <h4>حفظ البطاقة</h4><p>اختر مجموعة أو أنشئ مجموعة جديدة.</p>
      <div id="collrows">${rows}</div>
      <div class="newcoll"><input id="newcoll" placeholder="اسم مجموعة جديدة"><button class="btn" onclick="addColl('${id}')">إضافة</button></div>
      <div style="margin-top:14px;text-align:end"><button class="btn ghost" onclick="this.closest('.ov').remove();render()">تم</button></div>
    </div>`;
  document.body.appendChild(ov);
}
function pickColl(id,c,el){
  const on = Prefs.toggleBookmark(id,c);
  el.classList.toggle('on',on); el.lastElementChild.textContent = on?'✓':'+';
  refreshBadges();
  toast(on?('حُفظت في '+c):('أُزيلت من '+c));
}
function addColl(id){
  const el=document.getElementById('newcoll'); const n=el.value.trim();
  if(!n) return; Prefs.addCollection(n); Prefs.toggleBookmark(id,n);
  el.value=''; document.querySelector('.ov').remove(); refreshBadges(); render(); toast('أُنشئت المجموعة '+n);
}
function exportPrefs(){
  const blob=new Blob([Prefs.export()],{type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='ai-intel-prefs.json'; a.click();
  toast('صُدِّرت تفضيلاتك');
}
function importPrefs(){
  const inp=document.createElement('input'); inp.type='file'; inp.accept='application/json';
  inp.onchange=()=>{ const f=inp.files[0]; if(!f) return; const r=new FileReader();
    r.onload=()=>{ toast(Prefs.import(r.result)?'استُوردت التفضيلات':'ملف غير صالح'); render(); }; r.readAsText(f); };
  inp.click();
}
function setLive(n){
  const el=document.getElementById('liveCount'); if(!el) return;
  if(el.textContent !== String(n)){ el.textContent=n; el.classList.remove('pulse'); void el.offsetWidth; el.classList.add('pulse'); }
}
function toggleAside(){ document.body.classList.toggle('fopen'); }

/* ---- صينية «أعجبني» و«المحفوظات» ---- */
function refreshBadges(){
  const s=Prefs.state();
  const nl=s.likes.length, nb=new Set(Object.values(s.bookmarks).flat()).size;
  const bl=document.getElementById('bLike'), bb=document.getElementById('bBm');
  if(bl){ bl.textContent=nl; bl.classList.toggle('zero',!nl); }
  if(bb){ bb.textContent=nb; bb.classList.toggle('zero',!nb); }
}
/* ---------- صندوق «أضف رابطًا» ----------
   الصفحة ملفات ثابتة بلا خادم، فلا يمكنها الكتابة في المستودع ولا استدعاء نموذج.
   لذلك تُجهّز البطاقةَ طلبًا في GitHub بضغطة، ثم تلتقطه المهمة المجدولة وتصنّفه. */
const REPO_ISSUE_URL = 'https://github.com/ddbb44-sudo/ai-intel-dashboard/issues/new';
const X_RESERVED = ['home','search','explore','notifications','messages','settings',
  'i','intent','compose','login','signup','about','tos','privacy','hashtag'];
function linkKind(u){
  try{ const U=new URL(u), h=U.hostname.replace(/^www\./,'');
    if(/^(x|twitter)\.com$/.test(h)){
      const seg = U.pathname.split('/').filter(Boolean);
      // /USER/status/123 = تغريدة · /USER = حساب
      if(seg.length===1 && !X_RESERVED.includes(seg[0].toLowerCase()))
        return ['xprofile','حساب X — يُتابَع يوميًا'];
      return ['x','تغريدة X'];
    }
    if(/^(youtube\.com|youtu\.be|m\.youtube\.com)$/.test(h)) return ['youtube','فيديو YouTube'];
    if(h==='github.com') return ['github','مستودع GitHub'];
    return ['web','مقالة أو موقع'];
  }catch(e){ return [null,null]; }
}
/* ---------- حذف بطاقة ----------
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

/* ---------- صندوق «أضف مقالة» ----------
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

function openAdd(){
  const ov=document.createElement('div'); ov.className='ov'; ov.id='addov';
  ov.onclick=e=>{ if(e.target===ov) ov.remove(); };
  ov.innerHTML = `<div class="addbox">
    <h4>أضف رابطًا إلى اللوحة</h4>
    <p class="sub">الصق رابط تغريدة أو مقالة أو فيديو أو مستودع ← بطاقة واحدة.<br>
      أو الصق رابط <b>حساب X</b> (<code>x.com/USERNAME</code>) ← يُضاف للمتابعة اليومية
      ويُسحب تاريخه لآخر 60 يومًا تلقائيًا.</p>
    <input type="url" id="addurl" placeholder="https://…" autocomplete="off" inputmode="url"
      oninput="addCheck()" onkeydown="if(event.key==='Enter')addGo()">
    <div class="addkinds" id="addkinds">
      <span class="addkind" data-k="xprofile">حساب X</span>
      <span class="addkind" data-k="x">تغريدة X</span>
      <span class="addkind" data-k="web">مقالة أو موقع</span>
      <span class="addkind" data-k="youtube">فيديو YouTube</span>
      <span class="addkind" data-k="github">مستودع GitHub</span>
    </div>
    <textarea id="addnote" placeholder="ملاحظتك (اختياري) — تُكتب داخل البطاقة باسمك ولا تُخلط بمحتوى المصدر"></textarea>
    <div class="addrow">
      <button onclick="document.getElementById('addov').remove()">إلغاء</button>
      <button class="go" id="addgo" disabled onclick="addGo()">إضافة</button>
    </div>
    <div class="addnote">تفتح صفحة GitHub والرابط مكتوب فيها مسبقًا — <b>اضغط زر التأكيد الأخضر فيها ثم أغلقها</b>.
      هذه الضغطة هي تسجيل دخولك، وهي بديل وضع مفتاح مكشوف في صفحة يراها الجميع.</div>
  </div>`;
  document.body.appendChild(ov);
  setTimeout(()=>document.getElementById('addurl').focus(),40);
}
function addCheck(){
  const v=(document.getElementById('addurl').value||'').trim();
  const ok=/^https?:\/\/.+\..+/.test(v);
  document.getElementById('addgo').disabled=!ok;
  const [k]=ok?linkKind(v):[null];
  document.querySelectorAll('#addkinds .addkind').forEach(el=>el.classList.toggle('on', el.dataset.k===k));
}
function addGo(){
  const u=(document.getElementById('addurl').value||'').trim();
  if(!/^https?:\/\/.+\..+/.test(u)) return;
  const note=(document.getElementById('addnote').value||'').trim();
  const [k,label]=linkKind(u);
  const body = u + (note ? '\n\nملاحظة عزيز: '+note : '');
  const isAcc = (k==='xprofile');
  const url = REPO_ISSUE_URL
            + '?labels=' + (isAcc ? 'account' : 'inbox')
            + '&title=' + encodeURIComponent((isAcc?'حساب: ':'رابط: ')+(label||''))
            + '&body=' + encodeURIComponent(body);
  window.open(url,'_blank','noopener');
  document.getElementById('addov').remove();
  toast(isAcc ? 'افتحت GitHub — اضغط التأكيد الأخضر ليُضاف الحساب ويُسحب تاريخه'
              : 'افتحت GitHub — اضغط زر التأكيد الأخضر لإتمام الإضافة');
}
function syncLabel(){
  const m = {synced:'\u2713 محفوظ', saving:'\u2026 يحفظ', pending:'\u2026 بانتظار الحفظ',
             failed:'\u26a0 تعذّر الحفظ', offline:'\u26a0 بلا اتصال', idle:'مزامنة'};
  return m[SYNC.status] || 'مزامنة';
}
function refreshSyncChip(){
  const el = document.getElementById('syncChip');
  if (el) el.textContent = syncLabel();
}
function openSync(){
  const n = SYNC.queue().length;
  const ov = document.createElement('div'); ov.className='ov'; ov.id='syncov';
  ov.onclick = e => { if (e.target===ov) ov.remove(); };
  ov.innerHTML = `<div class="addbox">
    <h4>حفظ التفضيلات</h4>
    <p class="sub">إعجاباتك ومحفوظاتك تُحفظ خارج المتصفح، فتظهر على جوالك وماكك معًا
      ولا يمحوها Safari. <b>بلا أي إعداد على أي جهاز.</b></p>
    <div class="addnote">الحالة الآن: <b>${syncLabel()}</b>${n ? ` · <b>${n}</b> تغييرًا لم يُرفع بعد` : ''}</div>
    <div class="addrow">
      <button onclick="document.getElementById('syncov').remove()">إغلاق</button>
      <button class="go" onclick="flushPrefs();pullPrefs().then(()=>{refreshBadges();render();});document.getElementById('syncov').remove();toast('يزامن الآن\u2026')">زامن الآن</button>
    </div>
  </div>`;
  document.body.appendChild(ov);
}
function closeTray(){ const t=document.getElementById('tray'); if(t) t.remove(); document.removeEventListener('click',_trayOut,true); }
function _trayOut(e){ const t=document.getElementById('tray'); if(t && !t.contains(e.target) && !e.target.closest('.iconbtn.hb')) closeTray(); }
function trayRow(id, onRemove, sub){
  const it=Store.get(id); if(!it) return '';
  return `<div class="trow" id="tr-${sub||'l'}-${id}">
    <div class="av" style="${avStyle(it.author,28)}"></div>
    <div class="tt" onclick="closeTray();go('#/c/${id}')">${esc(it.arabic_title)}
      <div class="sn">${it.serial_display} · @${esc(it.author)}</div></div>
    <button class="rm" title="إزالة" onclick="${onRemove}">✕</button>
  </div>`;
}
function openTray(kind){
  const cur=document.getElementById('tray'); const same = cur && cur.dataset.kind===kind;
  closeTray(); if(same) return;
  const s=Prefs.state(); let body='', n=0, title='';
  if(kind==='liked'){
    title='ما أعجبني';
    const ids=s.likes.slice().reverse(); n=ids.length;
    body = n ? ids.map(id=>trayRow(id, `unlikeFromTray('${id}')`,'l')).join('')
             : `<div class="trayempty">لم تُعجب بأي بطاقة بعد.<br>اضغط ♥ على أي بطاقة لتبدأ تعليم النظام ما يهمك.</div>`;
  } else {
    title='المحفوظات';
    const colls=Prefs.collections().filter(c=>(s.bookmarks[c]||[]).length);
    n=new Set(Object.values(s.bookmarks).flat()).size;
    body = colls.length ? colls.map(c=>`<div class="trsec"><span>${esc(c)}</span><span>${(s.bookmarks[c]||[]).length}</span></div>`+
        (s.bookmarks[c]||[]).slice().reverse().map(id=>trayRow(id, `unbmFromTray('${id}','${esc(c)}')`, c.replace(/\W/g,''))).join('')).join('')
      : `<div class="trayempty">لا توجد بطاقات محفوظة.<br>اضغط ⚑ على أي بطاقة واخترْ لها مجموعة.</div>`;
  }
  const el=document.createElement('div'); el.className='tray'; el.id='tray'; el.dataset.kind=kind;
  el.innerHTML = `<div class="trayhd"><b>${title}</b><span class="n">${n}</span></div>
    <div id="traybody">${body}</div>
    ${n?`<div class="trayfoot">
      <button class="btn" onclick="showOnly('${kind}')">عرضها في اللوحة</button>
      <button class="btn ghost" onclick="closeTray()">إغلاق</button></div>`:''}`;
  document.body.appendChild(el);
  setTimeout(()=>document.addEventListener('click',_trayOut,true),0);
}
function _trayAfterRemove(kind,msg){
  refreshBadges(); toast(msg);
  const t=document.getElementById('tray');
  if(t){ const n = kind==='liked' ? Prefs.state().likes.length
                                  : new Set(Object.values(Prefs.state().bookmarks).flat()).size;
    t.querySelector('.trayhd .n').textContent = n;
    if(!n){ closeTray(); openTray(kind); } }
  render();
}
function unlikeFromTray(id){
  Prefs.toggleLike(id);
  const r=document.getElementById('tr-l-'+id); if(r) r.remove();
  _trayAfterRemove('liked','أُزيل الإعجاب');
}
function unbmFromTray(id,coll){
  Prefs.toggleBookmark(id,coll);
  const r=document.getElementById('tr-'+coll.replace(/\W/g,'')+'-'+id); if(r) r.remove();
  _trayAfterRemove('bm','أُزيل من '+coll);
}
function showOnly(kind){
  closeTray();
  Object.assign(F,{q:'',ct:[],tool:[],dom:[],ent:[],chg:[],lang:'',tier:'all',pref:[kind==='liked'?'liked':'bookmarked'],coll:'',from:'',to:'',time:''});
  document.getElementById('q').value='';
  if((location.hash||'#/')!=='#/') location.hash='#/'; else render();
}

/* ---------- 10) ROUTER ---------- */
let _scroll = 0;
function go(hash){ if(location.hash==='#/'||location.hash==='') _scroll = window.scrollY; location.hash = hash; }
function back(){ if(history.length>1) history.back(); else location.hash='#/'; }
function route(){
  const h = location.hash || '#/';
  if(h.startsWith('#/c/')) return viewDetail(h.slice(4));
  if(h.startsWith('#/u/')) return viewProfile(decodeURIComponent(h.slice(4)));
  if(h.startsWith('#/accounts')) return viewAccounts();
  viewFeed();
  requestAnimationFrame(()=>window.scrollTo(0,_scroll));
}
function render(){
  SHOWN = 60;
  document.getElementById('filters').innerHTML = filtersHTML();
  const h = location.hash||'#/';
  if(h.startsWith('#/c/')) viewDetail(h.slice(4));
  else if(h.startsWith('#/u/')) viewProfile(decodeURIComponent(h.slice(4)));
  else if(h.startsWith('#/accounts')) viewAccounts();
  else viewFeed();
}

/* ---------- 11) BOOT ---------- */
(function(){
  if(window.innerWidth>=1001) document.body.classList.add('fopen');
  const s = Store.stats;
  (function(){
    const d = new Date(s.fetched_at);
    const TZ = 'Asia/Riyadh';
    const part = (opt) => new Intl.DateTimeFormat('en-CA', Object.assign({timeZone:TZ}, opt)).format(d);
    let stamp;
    try {
      const day  = new Intl.DateTimeFormat('ar', {timeZone:TZ, weekday:'long'}).format(d);
      const dnum = Number(part({day:'numeric'}));
      const mon  = AR_MONTHS[Number(part({month:'numeric'})) - 1];
      const yr   = part({year:'numeric'});
      let hh = Number(part({hour:'numeric', hour12:false})), mm = part({minute:'2-digit'});
      const mer = hh < 12 ? 'ص' : 'م';
      hh = hh % 12 || 12;
      stamp = `${day} ${dnum} ${mon} ${yr} — ${hh}:${mm} ${mer}`;
    } catch(e){ stamp = s.fetched_at.replace('T',' ').replace('Z',' UTC'); }
    document.getElementById('upbar').innerHTML =
      `<div>آخر تحديث: <b>${stamp}</b> <span class="sep">بتوقيت الرياض</span></div>
       <div class="sep">·</div>
       <div>النافذة: <b>${esc(s.window)}</b></div>
       <div class="sep">·</div>
       <div>المصدر: <b>X</b> — <b class="num">${s.accounts_watched}</b> حسابًا</div>
       <div class="sep">·</div>
       <div><span class="live-dot on"></span>التحديث التلقائي: <b class="on">مفعّل</b> — يوميًا 6:00 صباحًا بتوقيت الرياض</div>`;
  })();
  document.getElementById('topstat').innerHTML =
    `<div>سُحب <b class="num">${s.tweets_fetched}</b> منشورًا</div>
     <div>قُبلت <b class="num">${s.cards}</b> بطاقة</div>
     <div>دُمج <b class="num">${s.merged_sources}</b> مصدرًا</div>
     <div>رُفض <b class="num">${s.rejected}</b></div>
     <div><b class="num">${s.accounts_watched}</b> حسابًا</div>`;
  let t; document.getElementById('q').addEventListener('input', e => {
    clearTimeout(t); t=setTimeout(()=>{ F.q=e.target.value; if((location.hash||'#/')!=='#/'){ location.hash='#/'; } else refilter(); },220);
  });
  refreshBadges();
  SYNC.status = SYNC.queue().length ? 'pending' : 'idle';
  pullPrefs().then(ok => { if (ok) { refreshBadges(); render(); } refreshSyncChip(); });
  /* العودة إلى اللسان أو إلى الشبكة تلتقط ما فعله الجهاز الآخر */
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) pullPrefs().then(ok => { if (ok) { refreshBadges(); render(); } refreshSyncChip(); });
  });
  window.addEventListener('online', flushPrefs);
  window.addEventListener('hashchange', route);
  document.getElementById('filters').innerHTML = filtersHTML();
  route();
})();
