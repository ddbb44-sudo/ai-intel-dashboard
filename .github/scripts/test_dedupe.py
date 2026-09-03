#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات التجميع — كل حالة منها عطلٌ وقع فعلًا في اللوحة، لا فرضٌ نظري."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dedupe

P = F = 0


def ok(name, cond):
    global P, F
    if cond:
        P += 1; print("  ✓ " + name)
    else:
        F += 1; print("  ✗ " + name)


def card(t, day="2026-09-02", ct="إصدار", ents=(), body="", author="a", eng=0, links=()):
    return {"arabic_title": t, "published_at": day + "T10:00:00Z", "content_types": [ct],
            "entities": list(ents), "detailed_explanation": body, "arabic_summary": "",
            "why_it_matters": "", "author": author, "engagement_score": eng,
            "external_links": list(links), "source_url": "https://x.com/%s/status/1" % author}


# خلفية واقعية: أسماء الشركات تتكرر في اللوحة الحقيقية بنسبة ٥–٨٪، ووزن IDF
# مبنيٌّ على ذلك. لو كانت الخلفية فقيرة صارت «openai» كلمةً نادرة فيُدمج ما لا يُدمج.
BRANDS = ["OpenAI ChatGPT", "Google Gemini", "Anthropic Claude", "xAI Grok", "Meta Llama"]
CORPUS = [card("%s تطلق نموذج جديد رقم %d" % (BRANDS[i % 5], i), ents=BRANDS[i % 5].split())
          for i in range(60)]

# ── ١) العطل الأصلي: خبر واحد بعناوين مختلفة ─────────────────────────────
g1 = card("Google تُطلق Gemini 3.8 Flash: نموذج عمل ذكي لمهام Agent", ents=["Google", "Gemini 3.8 Flash"])
g2 = card("جوجل تطلق Gemini 3.8 Flash بقدرات متقدمة في الاستدلال والبرمجة", ents=["Gemini 3.8 Flash", "Google"])
g3 = card("إطلاق Gemini 3.8 Flash في تطبيق Gemini", ents=["Gemini 3.8 Flash"])
idf = dedupe.build_idf(CORPUS + [g1, g2, g3])
ok("Gemini 3.8: عنوانان مختلفان لخبر واحد يُدمجان",
   dedupe.same_event(dedupe.signature(g1), dedupe.signature(g2), idf)[0])
ok("Gemini 3.8: الثالث ينضم أيضًا",
   dedupe.same_event(dedupe.signature(g1), dedupe.signature(g3), idf)[0])

# ── ٢) دايسون عبر يومين — التكرار الذي فات النموذج ───────────────────────
d1 = card("دايسون تطلق فرشاة أسنان CameraJet بكاميرا وذكاء اصطناعي بسعر 499 دولار",
          day="2026-09-01", ents=["Dyson", "CameraJet"])
d2 = card("دايسون تطلق CameraJet فرشاة أسنان ذكية بكاميرا وذكاء اصطناعي بـ 499 دولار",
          day="2026-09-02", ents=["Dyson", "CameraJet"])
idf2 = dedupe.build_idf(CORPUS + [d1, d2])
ok("دايسون: يومان مختلفان ويُدمجان", dedupe.same_event(dedupe.signature(d1), dedupe.signature(d2), idf2)[0])
ok("دايسون: match_existing تجد البطاقة المنشورة أمس",
   dedupe.match_existing(d2, [d1], idf2)[0] is d1)

# ── ٣) حرّاس الدمج الخاطئ ────────────────────────────────────────────────
v1 = card("Google تطلق Gemini 3.8 Flash", ents=["Gemini 3.8 Flash"])
v2 = card("Google تطلق Gemini 3.5 Transcribe", ents=["Gemini 3.5 Transcribe"])
idf3 = dedupe.build_idf(CORPUS + [v1, v2])
ok("رقم إصدار مختلف لا يُدمج", not dedupe.same_event(dedupe.signature(v1), dedupe.signature(v2), idf3)[0])

q1 = card("إطلاق Qwen3.8-Flash نموذج متعدد الوسائط", ents=["Qwen"])
q2 = card("إطلاق GLM-5.3-Flash نموذج متعدد الوسائط", ents=["GLM"])
ok("رقم ملتصق بالحروف يُقرأ (Qwen3.8 ≠ GLM-5.3)",
   not dedupe.same_event(dedupe.signature(q1), dedupe.signature(q2), dedupe.build_idf(CORPUS + [q1, q2]))[0])

r1 = card("Anthropic تطلق Fable 5.1 نموذج متوازن", ents=["Anthropic", "Fable 5.1"])
r2 = card("Fable 5.1 نموذج سريع لكنه ليس في مستوى النماذج الرائدة", ct="رأي", ents=["Fable 5.1"])
ok("الرأي لا يُدمج في الإصدار",
   not dedupe.same_event(dedupe.signature(r1), dedupe.signature(r2), dedupe.build_idf(CORPUS + [r1, r2]))[0])

h1 = card("حصاد أسبوع جوجل: Gemini 3.7 Flash في الـ API وWeatherNext مفتوح المصدر", ents=["Google"])
h2 = card("Gemini 3.7 Flash: قفزة في البرمجة والوكلاء بنصف السعر", ents=["Gemini 3.7 Flash"])
ok("حصاد الأسبوع لا يبتلع الخبر المفرد",
   not dedupe.same_event(dedupe.signature(h1), dedupe.signature(h2), dedupe.build_idf(CORPUS + [h1, h2]))[0])

o1 = card("Google تطلق Gemini 3.8 Flash", day="2026-09-01", ents=["Gemini 3.8 Flash"])
o2 = card("Google تطلق Gemini 3.8 Flash", day="2026-09-30", ents=["Gemini 3.8 Flash"])
ok("خارج نافذة الأيام لا يُدمج",
   not dedupe.same_event(dedupe.signature(o1), dedupe.signature(o2), dedupe.build_idf(CORPUS + [o1, o2]))[0])

n1 = card("OpenAI تطلق ChatGPT Health لربط السجلات الطبية", ents=["OpenAI", "ChatGPT"])
n2 = card("OpenAI تبلّغ السلطات عن مستخدم هدّد بالعنف عبر ChatGPT", ct="خبر", ents=["OpenAI", "ChatGPT"])
ok("خبران مختلفان لنفس الشركة لا يُدمجان",
   not dedupe.same_event(dedupe.signature(n1), dedupe.signature(n2), dedupe.build_idf(CORPUS + [n1, n2]))[0])

# ── ٤) الفائز: أكثر من جلب معلومات ──────────────────────────────────────
rich = card("Gemini 3.8 Flash", ents=["Gemini 3.8 Flash", "Google"], author="rich",
            body="شرح مطوّل " * 60 + " 40% و 25 نقطة", links=["https://x"], eng=5)
poor = card("Gemini 3.8 Flash", ents=["Gemini 3.8 Flash"], author="poor", body="سطر واحد", eng=900)
w, rest = dedupe.pick_winner([poor, rich])
ok("يبقى الأغنى معلومةً لا الأعلى تفاعلًا", w is rich and rest == [poor])
ok("مقياس المعلومات يفضّل المتن والحقائق", dedupe.info_score(rich) > dedupe.info_score(poor))

srcs = dedupe.sources_of([poor])
ok("المهزوم يصير مصدرًا تحت الفائز", len(srcs) == 1 and srcs[0]["author"] == "poor")

# ── ٥) العنقدة النجمية لا تتسلسل ────────────────────────────────────────
groups = dedupe.cluster([g1, g2, g3, d1, v2, n2] + CORPUS[:5])
gem = [g for g in groups if g1 in g][0]
ok("بطاقات Gemini 3.8 الثلاث في عنقود واحد", len(gem) == 3 and g2 in gem and g3 in gem)
ok("لا يبتلع العنقود ما لا علاقة له", d1 not in gem and v2 not in gem and n2 not in gem)

print("\nنجح %d · فشل %d" % (P, F))
sys.exit(1 if F else 0)
