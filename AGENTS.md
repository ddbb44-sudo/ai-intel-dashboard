# سياق Codex — مركز المعرفة للذكاء الاصطناعي

## ابدأ من هنا

1. اقرأ `CLAUDE.md` كاملًا قبل أي تعديل؛ فهو المرجع التشغيلي الأحدث وقواعده مبنية على أعطال حقيقية.
2. للتفصيل الوظيفي والمنتجي، ارجع إلى `docs/00-التعليمات.md` و`docs/00-architecture.md`.
3. لا تدّع نجاحًا بلا دليل تنفيذ أو تحقق. اذكر ما لم يُختبر بوضوح.

## الغرض والبنية

لوحة عربية شخصية تجمع محتوى AI من X ومصادر أخرى، تصنّفه وتشرحه وتتيح البحث والفلترة. هي تطبيق ويب ثابت:

- `index.html`: الواجهة والأنماط وتحميل البيانات.
- `app.js`: Store وPrefs وTaxonomy وFilterEngine وRanking والواجهة والتوجيه.
- `accounts.json`: مصدر الحقيقة للحسابات المتابَعة.
- `data/`: البطاقات، `manifest.json` للفهرسة، و`state.json` لحالة السحب.
- `.github/scripts/` و`.github/workflows/`: السحب والتصنيف والمعالجة والتشغيل الآلي.
- `sync/`: Netlify Functions + Blobs لمزامنة تفضيلات المستخدم.

## قواعد تعديل مختصرة

- استخدم العربية في الواجهة والشرح، وحافظ على المصطلحات التقنية الإنجليزية كما هي.
- لا تخمّن بيانات أو نتائج، ولا تضف سكربتات `patch_*` أو workflows ترقيعية.
- لا تعبث بـ`data/state.json` أو`data/manifest.json` أو`accounts.json` بلا سبب محدد وفحص تابع.
- لا تغيّر عتبات `dedupe.py` أو ترتيب الأهمية بلا بيانات معايرة.
- أبقِ `CHG_GROUPS` في `app.js` و`CHANGE_GROUPS` في `taxonomy.py` متطابقين عند تعديلهما.
- عند تعديل `accounts.json`، شغّل فحص/مزامنة `authors.json` بدل النسخ اليدوي.
- لا تحذف سطر `ignore` في `netlify.toml`؛ نشر Netlify الإنتاجي يستهلك نقاطًا.
- قبل الكتابة، افحص حالة Git. عند وجود عمل جارٍ من وكيل آخر، لا تلمس الملفات المتداخلة معه.

## التحقق قبل الدفع

شغّل ما يناسب نطاق التعديل، وعلى الأقل كامل المجموعة لتعديل المنطق أو خط المعالجة:

```sh
python -m pyflakes .github/scripts/*.py
python -m compileall -q .github/scripts
node --check app.js
node sync/tests/test_state.mjs
python .github/scripts/test_dedupe.py
python .github/scripts/test_jsontools.py
python .github/scripts/test_parity.py
python .github/scripts/sync_account_types.py --check
python .github/scripts/lint_design.py
```

## الحالة التصميمية الحالية

محور `audience_topic` هو الأولوية المفتوحة: يعبّر عن ما يهم المستخدم (Skill، أداة يستعملها، بنية الوكلاء، نموذج، عالم AI عام، خارج الاهتمام) وليس عن شكل المحتوى فقط. لا تُعدّل أوزان `Ranking` قبل اكتمال وسم البيانات وإعادة التقييم.
