import { apply, empty } from '../netlify/functions/_state.mjs';
let pass=0, fail=0;
const eq=(name,a,b)=>{const A=JSON.stringify(a),B=JSON.stringify(b); if(A===B){pass++;console.log('  ✓',name)} else {fail++;console.log('  ✗',name,'\n     got:',A,'\n     want:',B)}};

let s = empty();
apply(s,[{k:'bm',id:'c001',coll:'Personal',on:true}]);
eq('حفظ بطاقة', s.bookmarks, {Personal:['c001']});

apply(s,[{k:'bm',id:'c001',coll:'Personal',on:false}]);
eq('إلغاء الحفظ يحذف المجموعة الفارغة', s.bookmarks, {});

// جهازان مختلفان يعملان بالتتابع
s = empty();
apply(s,[{k:'bm',id:'a',coll:'Drive7',on:true}]);      // الماك
apply(s,[{k:'bm',id:'b',coll:'Drive7',on:true}]);      // الجوال
eq('عمل الجهازين يجتمع', s.bookmarks.Drive7, ['a','b']);

// الحذف من جهاز لا يُبعث من جديد
apply(s,[{k:'bm',id:'a',coll:'Drive7',on:false}]);
eq('الحذف يبقى محذوفًا', s.bookmarks.Drive7, ['b']);

// تكرار نفس العملية لا يضاعف
s = empty();
apply(s,[{k:'like',id:'x',on:true},{k:'like',id:'x',on:true}]);
eq('لا تكرار في الإعجاب', s.likes, ['x']);

// المجموعات
s = empty();
apply(s,[{k:'coll',name:' بحوث '},{k:'coll',name:'بحوث'}]);
eq('مجموعة جديدة بلا تكرار ومقلّمة', s.collections, ['بحوث']);

// المفتوح
s = empty(); apply(s,[{k:'open',id:'z'},{k:'open',id:'z'}]);
eq('المقروء يُسجَّل مرة', s.opened, ['z']);

// مدخلات فاسدة لا تُسقط شيئًا
s = empty();
const n = apply(s,[null,{k:'nope'},{k:'bm'},{id:'y'},{k:'like',id:'y',on:true}]);
eq('يتجاهل الفاسد ويطبّق السليم', [s.likes, n], [['y'],1]);

// حدود الطول
s = empty();
apply(s,[{k:'coll',name:'ط'.repeat(80)}]);
eq('اسم المجموعة يُقصّ إلى ٤٠', s.collections[0].length, 40);

console.log(`\nنجح ${pass} · فشل ${fail}`);
process.exit(fail?1:0);
