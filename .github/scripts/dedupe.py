#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تجميع البطاقات التي تنقل الخبر نفسه، واختيار أغناها معلومةً.

العطل الذي وُلدت منه (٣ سبتمبر ٢٠٢٦):
  خبر Gemini 3.8 ظهر في **سبع** بطاقات، وفرشاة دايسون في بطاقتين. السبب أن
  `cluster_id` كان نصًّا حرًّا **يخترعه النموذج** لكل بطاقة على حدة، فخرج لخبر
  واحد خمسة مفاتيح: gemini_38_ · gemini38_l · gemini_3.8 · gemini_cyb · gem38flash.
  ولأن الدمج كان يقع داخل تشغيلة اليوم وحدها، تكرّر خبر دايسون عبر يومين.

المبدأ هنا معاكس: **المفتاح يُحسب ولا يُخترع.**

ولماذا IDF: التجربة الأولى بتشابه بسيط دمجت ٣١ بطاقة OpenAI غير مترابطة في
عنقود واحد، لأن «openai» و«claude» و«gemini» تتكرر في ٥–٨٪ من العناوين فتبتلع
الإشارة. الوزن العكسي للتكرار يجعل الكلمة النادرة (camerajet · stacked · 3.8)
تقرّر، والكلمة الشائعة (نموذج · تطلق) لا تكاد تُحسب.

ثلاثة حرّاس تمنع الدمج الخاطئ — والدمج الخاطئ أسوأ من التكرار، لأن التكرار
يُرى ويُحذف، أما الخبر المبتلَع فلا يعرف صاحبه أنه فُقد:
  ١) اختلاف رقم الإصدار = خبران (‏Gemini 3.8 غير 3.5).
  ٢) الرأي لا يُدمج في الإصدار — «تقييمي للنموذج» ليس «إطلاق النموذج».
  ٣) بطاقة «حصاد الأسبوع» لا تبتلع الخبر المفرد ولا يبتلعها.

المعايرة (٩٨٩ بطاقة حقيقية، ١٣ زوجًا موجبًا و١١ سالبًا):
  الموجبات ‎0.151–0.843 · السالبات ‎0.018–0.135 → العتبة ‎0.145 تفصل الجميع.
"""
import math
import re

WINDOW_DAYS = 3        # الخبر لا يُعاد نقله بعد ثلاثة أيام عادةً
T_MERGE     = 0.145    # عتبة معايَرة (انظر أعلاه) — تحتها لا سؤال ولا دمج
T_SURE      = 0.45     # فوقها يُدمج بلا سؤال: التطابق صارخ (دايسون 0.84)
ROUNDUP     = re.compile(r"حصاد|أبرز ما|ملخص (?:الأسبوع|أسبوع)|جولة على")

# عائلات نوع المحتوى: لا يُدمج إلا ما كان من العائلة نفسها
FAMILY = {
    "إصدار": "خبر", "أداة": "خبر", "خبر": "خبر",
    "رأي": "رأي", "شرح": "شرح", "تجربة": "شرح", "بحث وقياس": "بحث",
}

AR_STOP = set("""في من على عن إلى مع أن إن ما لا هذا هذه التي الذي بعد قبل عند كل بين أو
ثم يا هو هي كما لكن حتى قد لقد نحو ضمن دون بلا عبر خلال أول آخر جديد جديدة الآن اليوم أمس
أي أية ذلك تلك هناك هنا الـ""".split())
EN_STOP = set("""the a an of for and or with to in on at by from is are new now via using
its it this that has have will can you your our their more most best just about into""".split())


def _norm(s):
    s = (s or "").lower()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي")):
        s = s.replace(a, b)
    return s


def _ents(card):
    """الكيانات قد تصل نصوصًا أو قواميس — نقبل الشكلين ولا ننهار على الثالث."""
    out = []
    for e in (card.get("entities") or []):
        if isinstance(e, str):
            out.append(e)
        elif isinstance(e, dict):
            v = e.get("name") or e.get("ar") or e.get("term") or ""
            if v:
                out.append(str(v))
    return [_norm(x) for x in out if x]


# سعرٌ لا إصدار: «بسعر 2.5 دولار» رقمٌ عشري لكنه ليس رقم نسخة
_PRICE = re.compile(r"(?:\$|بسعر|سعر|دولار|ريال)\s*$")

def versions(text):
    """أرقام الإصدار وحدها.

    بلا حدود كلمات: «Qwen3.8-Flash» و«GLM-5.3» يلتصق فيهما الرقم بالحرف،
    وكان النمط القديم يفوّتهما — فاندمج نموذجان مختلفان في عنقود واحد.
    """
    t = text or ""
    v = set()
    for m in re.finditer(r"(?<![\d.])(\d{1,3}\.\d{1,3})(?![\d.])", t):
        if _PRICE.search(t[max(0, m.start() - 14):m.start()]):
            continue
        v.add(m.group(1))
    v |= set(m.lower() for m in re.findall(r"\bv\d+(?:\.\d+)?\b", t, re.I))
    return v


def signature(card):
    """توقيع البطاقة: كلمات مميزة · كيانات · أرقام إصدار · العائلة · اليوم."""
    title = card.get("arabic_title") or ""
    ents = _ents(card)
    raw = re.sub(r"[^\w؀-ۿ\.\s]", " ", _norm(title + " " + " ".join(ents)))
    toks = {w for w in raw.split() if len(w) >= 3 and w not in AR_STOP and w not in EN_STOP}
    return {
        "tokens": toks,
        "ents": set(ents),
        "vers": versions(title) | versions(" ".join(ents)),
        "family": FAMILY.get((card.get("content_types") or [""])[0] or "", "خبر"),
        "day": (card.get("published_at") or "")[:10],
        "roundup": bool(ROUNDUP.search(title)),
    }


def build_idf(cards):
    """وزن عكسي للتكرار من كل بطاقات اللوحة — الكلمة الشائعة لا تكاد تُحسب."""
    n = max(1, len(cards))
    df = {}
    for c in cards:
        for w in signature(c)["tokens"]:
            df[w] = df.get(w, 0) + 1
    return {"n": n, "df": df, "default": math.log(n)}


def _w(tokens, idf):
    d, n = idf["df"], idf["n"]
    return sum(math.log(n / (1 + d.get(t, 0))) for t in tokens)


def _dayspan(d1, d2):
    try:
        a = int(d1[:4]) * 372 + int(d1[5:7]) * 31 + int(d1[8:10])
        b = int(d2[:4]) * 372 + int(d2[5:7]) * 31 + int(d2[8:10])
    except Exception:
        return 99
    return abs(b - a)


def same_event(sa, sb, idf):
    """أهما الخبر نفسه؟ يعيد (نعم/لا، الدرجة، السبب)."""
    if sa["day"] and sb["day"] and _dayspan(sa["day"], sb["day"]) > WINDOW_DAYS:
        return False, 0.0, "خارج النافذة"
    if sa["family"] != sb["family"]:
        return False, 0.0, "نوع محتوى مختلف"
    if sa["vers"] and sb["vers"] and not (sa["vers"] & sb["vers"]):
        return False, 0.0, "رقم إصدار مختلف"
    if sa["roundup"] != sb["roundup"]:
        return False, 0.0, "حصاد مقابل خبر مفرد"

    inter = sa["tokens"] & sb["tokens"]
    union = sa["tokens"] | sb["tokens"]
    if not union:
        return False, 0.0, "بلا كلمات"
    score = _w(inter, idf) / max(1e-9, _w(union, idf))
    if score >= T_MERGE:
        return True, score, "تشابه موزون فوق العتبة"
    return False, score, "دون العتبة"


def info_score(card):
    """«أكثر من جلب معلومات» — مقياس معلَن لا ذوق.

    المتن الموضوعي أولًا، ثم الحقائق المحدَّدة (أرقام · روابط · كيانات)،
    والتفاعل مرجّحًا أخيرًا عند التقارب لا أساسًا.
    """
    body = " ".join([
        card.get("detailed_explanation") or "",
        card.get("arabic_summary") or "",
        card.get("why_it_matters") or "",
    ])
    facts = len(re.findall(r"\d+(?:[\.,]\d+)?", body))
    links = len(card.get("external_links") or [])
    ents = len(_ents(card))
    eng = card.get("engagement_score") or 0
    return round(len(body) + 12 * facts + 25 * links + 8 * ents + 0.5 * eng, 2)


def all_pairs(cards, idf):
    """كل الأزواج التي اجتازت الحرّاس، بدرجاتها — لا تجميع بعد."""
    sigs = [signature(c) for c in cards]
    out = []
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            ok, sc, _ = same_event(sigs[i], sigs[j], idf)
            if ok:
                out.append((cards[i], cards[j], sc))
    return out


def groups_from_pairs(cards, pairs):
    """عناقيد نجمية من أزواج مؤكَّدة.

    لماذا نجمية لا متعدّية: الضم المتعدّي يربط ‏Qwen3.8 بـ‏GLM-5.3 عبر بطاقة
    وسيطة، فتتسلسل العناقيد حتى تبتلع ما لا علاقة له. هنا كل عضو يجب أن يكون
    مرتبطًا بمركز العنقود مباشرة، والمركز أغنى البطاقات معلومةً.
    """
    idx = {id(c): k for k, c in enumerate(cards)}
    linked = {k: set() for k in range(len(cards))}
    for a, b, *_ in pairs:
        ia, ib = idx.get(id(a)), idx.get(id(b))
        if ia is not None and ib is not None:
            linked[ia].add(ib); linked[ib].add(ia)
    order = sorted(range(len(cards)), key=lambda k: -info_score(cards[k]))
    taken, groups = set(), []
    for i in order:
        if i in taken:
            continue
        taken.add(i)
        g = [cards[i]]
        for j in order:
            if j not in taken and j in linked[i]:
                taken.add(j); g.append(cards[j])
        groups.append(g)
    return groups


def cluster(cards, idf=None):
    """تجميع مباشر بلا حكم نموذج — يُستعمل في الاختبارات وعند تعذّر النداء."""
    if idf is None:
        idf = build_idf(cards)
    return groups_from_pairs(cards, all_pairs(cards, idf))


def match_existing(new_card, recent_cards, idf):
    """أقرب بطاقة منشورة سابقًا تنقل الخبر نفسه — أو None.

    هذه هي التي تمنع تكرار دايسون: الجديد يُقارَن بما نُشر في الأيام السابقة،
    لا ببطاقات اليوم وحدها.
    """
    sn = signature(new_card)
    best, best_s = None, 0.0
    for c in recent_cards:
        ok, s, _ = same_event(sn, signature(c), idf)
        if ok and s > best_s:
            best, best_s = c, s
    return best, best_s


def pick_winner(group):
    """الأغنى معلومةً يبقى؛ والبقية تصير مصادر تحته."""
    ranked = sorted(group, key=lambda c: (-info_score(c), c.get("published_at") or ""))
    return ranked[0], ranked[1:]


def sources_of(cards):
    """مصادر إضافية بلا تكرار، بشكل يطابق حقل also_reported القائم."""
    seen, out = set(), []
    for c in cards:
        h = c.get("author") or ""
        if h and h.lower() not in seen:
            seen.add(h.lower())
            out.append({"author": h, "url": c.get("source_url") or ""})
        for s in (c.get("also_reported") or []):
            a = (s.get("author") or "").lower()
            if a and a not in seen:
                seen.add(a)
                out.append({"author": s.get("author"), "url": s.get("url") or ""})
    return out


# ── الحكم على المتشابه غير القاطع ────────────────────────────────────────
# الحدّ الذي بلغته الرياضيات: «Grok 4.6 يدخل Copilot» و«Grok 4.6 يدخل
# Perplexity» يتشابهان 0.24، و«Gemini 3.8 من GoogleAI» و«من Abdullah4AI»
# يتشابهان 0.15. الأول حدثان والثاني حدث واحد — والفرق معنى لا عدد.
# فما بين T_MERGE و T_SURE يُسأل النموذج سؤالًا واحدًا محدّدًا، ونداؤه واحد
# لكل التشغيلة لا لكل زوج.
#
# القاعدة عند العجز: **لا تدمج**. التكرار يراه صاحبه فيحذفه، أما الخبر
# المبتلَع فلا يعرف أنه فُقد.

def pairs_needing_judgment(pairs):
    """يفرز الأزواج: قاطعة تُدمج، ومشكوكة تُسأل، وما دونها يُترك."""
    sure, ask = [], []
    for a, b, score in pairs:
        if score >= T_SURE:
            sure.append((a, b))
        elif score >= T_MERGE:
            ask.append((a, b))
    return sure, ask


def judge_prompt(ask):
    """سؤال واحد عن كل الأزواج المشكوكة."""
    lines = []
    for i, (a, b) in enumerate(ask, 1):
        lines.append("%d)\nأ: %s\nب: %s" % (i, a.get("arabic_title", ""), b.get("arabic_title", "")))
    return (
        "لكل زوج أدناه: هل يصفان **الحدث نفسه** (نفس الإعلان/الإطلاق/الواقعة)، "
        "أم حدثين مختلفين يشتركان في المنتج أو الشركة فقط؟\n"
        "مثال على حدثين مختلفين: «النموذج يدخل Copilot» و«النموذج يدخل Perplexity».\n"
        "مثال على حدث واحد: «جوجل تطلق النموذج» و«إطلاق النموذج في التطبيق».\n\n"
        + "\n\n".join(lines)
        + "\n\nأعد JSON فقط: [{\"i\":1,\"same\":true|false}, ...]"
    )


def apply_judgment(ask, answer):
    """يحوّل رد النموذج إلى قائمة أزواج مؤكَّدة. أي غموض = لا دمج."""
    same = {}
    if isinstance(answer, list):
        for row in answer:
            if isinstance(row, dict) and isinstance(row.get("i"), int):
                same[row["i"]] = bool(row.get("same"))
    return [p for i, p in enumerate(ask, 1) if same.get(i) is True]
