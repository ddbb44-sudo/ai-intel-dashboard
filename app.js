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
const Prefs = (() => {
  const KEY = 'aiintel.prefs.v1';
  const DEFAULT_COLLECTIONS = ['Drive7','Personal','Marketing','SEO','AI Tools','Research','Coding','Islamic','Later'];
  let s = { likes:[], bookmarks:{}, collections:[...DEFAULT_COLLECTIONS], opened:[] };
  try { const raw = localStorage.getItem(KEY); if (raw) s = Object.assign(s, JSON.parse(raw)); } catch(e) {}
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch(e) {} };
  return {
    state: () => s,
    liked: id => s.likes.includes(id),
    toggleLike(id){ const i = s.likes.indexOf(id); i<0 ? s.likes.push(id) : s.likes.splice(i,1); save(); return i<0; },
    bookmarksOf: id => Object.keys(s.bookmarks).filter(c => (s.bookmarks[c]||[]).includes(id)),
    isBookmarked: id => Object.values(s.bookmarks).some(a => a.includes(id)),
    toggleBookmark(id, coll){
      s.bookmarks[coll] = s.bookmarks[coll] || [];
      const i = s.bookmarks[coll].indexOf(id);
      i<0 ? s.bookmarks[coll].push(id) : s.bookmarks[coll].splice(i,1);
      save(); return i<0;
    },
    collections: () => s.collections,
    addCollection(n){ n=(n||'').trim(); if(n && !s.collections.includes(n)){ s.collections.push(n); save(); } },
    markOpened(id){ if(!s.opened.includes(id)){ s.opened.push(id); save(); } },
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

/* ---------- 4) TAXONOMY ----------
   المفردات المعلنة في ملف التعليمات هي المرجع. تظهر كاملة دائمًا حتى لو كان عدّها صفرًا،
   ويُضاف إليها أي تصنيف ظهر في البيانات ولم يكن معلنًا. لا يُخفى تصنيف طلبه المستخدم. */
const DECLARED = {
  content_types: ['Skill','MCP','Agent','Prompt','API','Release','Feature','Tutorial','Guide','Tool',
    'Workflow','Template','SDK','Dataset','Benchmark','Research Paper','Announcement','Case Study',
    'Comparison','Opinion','Thread','Demo','Course','News','Job','Event'],
  domains: ['AI','ML','LLM','Software Development','Coding','DevOps','Data','Analytics','Cybersecurity',
    'Robotics','Product','Design','UI','UX','Marketing','Digital Marketing','SEO','Content','Sales',
    'E-commerce','Business','Management','Operations','Customer Experience','Finance','Investment',
    'Legal','Healthcare','Medicine','Education','Research','Engineering','Automotive','Manufacturing',
    'Media','Creative','Video','Audio','Islamic','Personal Productivity','Automation'],
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
  const PIN=['Skill','MCP','Agent','Prompt','API'];
  const entM = countMap('entities');
  return {
    dates,
    pinned: PIN,
    content_types_ordered: merge('content_types', PIN),
    content_types: merge('content_types', PIN),
    domains: merge('domains'),
    change_types: merge('change_types'),
    entities: Object.entries(entM).sort((a,b)=>b[1]-a[1]).map(([t,n])=>[t,n,false])
  };
})();

/* ---------- 5) FILTER ENGINE ---------- */
const ZOPEN = { ct:false, dom:false, chg:false, ent:false };
const F = { q:'', ct:[], dom:[], ent:[], chg:[], src:[], lang:'', tier:'useful+', pref:[], coll:'', from:'', to:'', time:'', sort:'smart' };

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
      if (F.ct.length  && !F.ct.every(x => i.content_types.includes(x))) return false;
      if (F.dom.length && !F.dom.every(x => i.domains.includes(x))) return false;
      if (F.ent.length && !F.ent.every(x => i.entities.includes(x))) return false;
      if (F.chg.length && !F.chg.every(x => i.change_types.includes(x))) return false;
      if (F.pref.includes('liked') && !Prefs.liked(i.id)) return false;
      if (F.pref.includes('bookmarked') && !Prefs.isBookmarked(i.id)) return false;
      if (F.pref.includes('unread') && Prefs.isOpened(i.id)) return false;
      if (F.pref.includes('rec') && Ranking.relevance(i,v) < 12) return false;
      if (F.coll && !Prefs.bookmarksOf(i.id).includes(F.coll)) return false;
      const t = new Date(i.published_at).getTime();
      if (F.time){ const h = {d1:24,d7:168,d30:720}[F.time]; if (Date.now()-t > h*3600e3) return false; }
      if (F.from && t < new Date(F.from).getTime()) return false;
      if (F.to && t > new Date(F.to).getTime()+864e5) return false;
      if (q){
        const hay = (i.arabic_title+' '+i.arabic_summary+' '+i.detailed_explanation+' '+i.original_text+' '+
          i.content_types.join(' ')+' '+i.domains.join(' ')+' '+i.entities.join(' ')+' '+i.change_types.join(' ')+' '+
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
function avStyle(handle, size){
  const a = Store.author(handle), i = (a && a.sprite>=0) ? a.sprite : -1;
  if(i<0) return 'background-image:none';
  const k = size/SP.tile, c = i%SP.cols, r = Math.floor(i/SP.cols);
  return `background-size:${(SP.cols*SP.tile*k).toFixed(1)}px auto;background-position:${(-c*size).toFixed(1)}px ${(-r*size).toFixed(1)}px`;
}
const ICON = {
  like:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1L12 21l7.7-7.6 1.1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>',
  likeF:'<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1L12 21l7.7-7.6 1.1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>',
  bm:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>',
  bmF:'<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>',
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
      <div class="av" style="${avStyle(i.author,38)}" onclick="go('#/u/${esc(i.author)}')" title="${esc(a.name)}"></div>
      <div class="who">
        <div><span class="nm" onclick="go('#/u/${esc(i.author)}')">${esc(a.name)}</span> <span class="hd">@${esc(i.author)} · ${ago(i.published_at)}</span></div>
        <div style="display:flex;gap:6px;align-items:center;margin-top:3px">
          <span class="serial" onclick="copySerial('${i.serial_display}')" title="انسخ رقم البطاقة">${i.serial_display}</span>
          <span class="tier ${i.importance_tier}">${tierLbl}</span>
        </div>
      </div>
      <a class="xlink" href="${esc(i.source_url)}" target="_blank" rel="noopener" title="فتح المصدر في X">${ICON.x}</a>
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
        <button class="readmore" onclick="go('#/c/${i.id}')">قراءة المزيد</button>
      </div>
    </div>
  </article>`;
}

function filtersHTML(){
  const grp = (title, key, list) => {
    const id='g_'+key;
    const chip = ([name,n,pin]) => `<button class="chip ${pin?'pin ':''}${F[key].includes(name)?'on':''}${n?'':' empty'}" onclick="toggleF('${key}','${esc(name)}')" ${n?'':'title="تصنيف معتمد لكن لا توجد بطاقات تحمله في هذه الدفعة"'}>${esc(name)}<span class="c">(${n})</span></button>`;
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
    ${prefChip('liked','أعجبني')}${prefChip('bookmarked','محفوظ')}${prefChip('rec','مُرشَّح لي')}${prefChip('unread','لم أقرأه')}
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
  ${grp('المجال','dom',Taxonomy.domains)}
  <div class="fgroup"><h4>المصدر</h4><div class="chips">
    <button class="chip on">X / Twitter<span class="c">(${Store.all().length})</span></button>
    <button class="chip" disabled style="opacity:.45">YouTube<span class="c">(0)</span></button>
    <button class="chip" disabled style="opacity:.45">GitHub<span class="c">(0)</span></button>
    <button class="chip" disabled style="opacity:.45">مواقع<span class="c">(0)</span></button>
  </div><div class="note" style="font-size:11px;color:var(--faint);margin-top:6px">المصادر الأخرى غير مفعّلة في هذه التجربة الأولى.</div></div>
  <div class="fgroup"><h4>تفضيلاتي (نسخ احتياطي)</h4><div class="chips">
    <button class="chip" onclick="exportPrefs()">تصدير</button>
    <button class="chip" onclick="importPrefs()">استيراد</button>
    <button class="chip" onclick="resetAll()">مسح كل الفلاتر</button>
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
  setLive(items.length);
  armAutoLoad();
}

function viewDetail(id){
  const i = Store.get(id);
  if(!i) return viewFeed();
  Prefs.markOpened(id);
  const a = Store.author(i.author), m = i.metrics||{};
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
      </div>
    </div>
    <div class="dwrap">
      <div class="chead">
        <div class="av" style="${avStyle(i.author,38)}" onclick="go('#/u/${esc(i.author)}')"></div>
        <div class="who">
          <div><span class="nm" onclick="go('#/u/${esc(i.author)}')">${esc(a.name)}</span> <span class="hd">@${esc(i.author)}</span></div>
          <div class="hd">${ago(i.published_at)} · <span class="num">${new Date(i.published_at).toISOString().slice(0,10)}</span></div>
        </div>
        <a class="xlink" href="${esc(i.source_url)}" target="_blank" rel="noopener">${ICON.x}</a>
      </div>
      <h1>${esc(i.arabic_title)}</h1>
      <p style="font-size:15.5px;color:var(--ink-2);line-height:1.9;margin:0">${esc(i.arabic_summary)}</p>
      <div class="tags" style="margin-top:14px">
        ${i.entities.map(x=>`<span class="tag ent">${esc(x)}</span>`).join('')}
        ${i.change_types.map(x=>`<span class="tag chg">${esc(x)}</span>`).join('')}
        ${i.content_types.map(x=>`<span class="tag">${esc(x)}</span>`).join('')}
        ${i.domains.map(x=>`<span class="tag">${esc(x)}</span>`).join('')}
      </div>
      ${sec('شرح موسّع', '<p>'+esc(i.detailed_explanation)+'</p>')}
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
function toggleF(k,v){ const a=F[k]; const i=a.indexOf(v); i<0?a.push(v):a.splice(i,1); render(); }
function clearF(k){ F[k]=[]; render(); }
function clearChip(ix){ (window._chips[ix]||{}).clear?.(); render(); }
function setTier(t){ F.tier=t; render(); }
function setLang(l){ F.lang=l; render(); }
function setTime(t){ F.time = F.time===t?'':t; if(F.time){F.from='';F.to='';} render(); }
function setRange(which,val){
  if(which==='clear'){ F.from=''; F.to=''; }
  else { F[which]=val||''; F.time=''; 
    if(F.from && F.to && F.from>F.to){ const t=F.from; F.from=F.to; F.to=t; } }
  render();
}
function setSort(s){ F.sort=s; render(); }
function setColl(c){ F.coll = F.coll===c?'':c; render(); }
function showRest(id,btn){ document.getElementById(id+'_rest').style.display='contents'; btn.remove(); }
function toggleZero(k){ ZOPEN[k]=!ZOPEN[k]; document.getElementById('filters').innerHTML = filtersHTML(); }
function tagClick(e,k,v){ e.stopPropagation(); if(!F[k].includes(v)) F[k].push(v); if(location.hash!=='#/') go('#/'); else render(); window.scrollTo(0,0); }
function resetAll(){ Object.assign(F,{q:'',ct:[],dom:[],ent:[],chg:[],src:[],lang:'',tier:'useful+',pref:[],coll:'',from:'',to:'',time:'',sort:'smart'}); document.getElementById('q').value=''; render(); }
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
  Object.assign(F,{q:'',ct:[],dom:[],ent:[],chg:[],lang:'',tier:'all',pref:[kind==='liked'?'liked':'bookmarked'],coll:'',from:'',to:'',time:''});
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
  viewFeed();
  requestAnimationFrame(()=>window.scrollTo(0,_scroll));
}
function render(){
  SHOWN = 60;
  document.getElementById('filters').innerHTML = filtersHTML();
  const h = location.hash||'#/';
  if(h.startsWith('#/c/')) viewDetail(h.slice(4));
  else if(h.startsWith('#/u/')) viewProfile(decodeURIComponent(h.slice(4)));
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
    clearTimeout(t); t=setTimeout(()=>{ F.q=e.target.value; if((location.hash||'#/')!=='#/'){ location.hash='#/'; } else render(); },220);
  });
  refreshBadges();
  window.addEventListener('hashchange', route);
  document.getElementById('filters').innerHTML = filtersHTML();
  route();
})();
