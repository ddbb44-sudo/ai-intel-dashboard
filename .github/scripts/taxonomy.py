# -*- coding: utf-8 -*-
"""مفردات التصنيف المعتمدة — المصدر الوحيد للحقيقة (قرار عزيز 21 أغسطس 2026).
لا يُضاف وسم خارج هذه القوائم، ولا يُشتق التصنيف من البيانات الموجودة."""

CONTENT_TYPES = [
    "إصدار",      # شيء جديد نزل أو تحدّث
    "أداة",       # يشير إلى شيء يُستخدم — يفعّل محور نوع الأداة
    "شرح",        # خطوات · دليل · workflow · prompt مشروح
    "تجربة",      # جرّبت كذا فطلعت النتيجة كذا
    "بحث وقياس",  # ورقة علمية · benchmark · مقارنة مقاسة
    "رأي",        # تحليل شخصي أو جدل
    "خبر",        # حدث في السوق لا إصدار منتج
]

TOOL_TYPES = [
    "MCP", "Skill", "Agent", "Plugin", "Prompt", "API/SDK", "تطبيق", "نموذج",
]

DOMAINS = [
    "برمجة وهندسة", "أعمال وإدارة", "تصميم وواجهات", "تسويق ومحتوى",
    "نماذج وLLM", "بيانات وتحليلات", "بحث وتعليم", "إنتاجية شخصية",
    "فيديو وصوت", "أمن سيبراني", "روبوتات وعتاد", "صحة", "إسلامي",
]

# طبيعة التغيير — لم تتغيّر
CHANGE_TYPES = [
    "New Release","New Feature","Upgrade","Update","Model Update","API Update",
    "Pricing Change","New Integration","MCP Support","New Agent Feature",
    "Beta/Preview","General Availability","Deprecation","Shutdown",
    "Research Release","Open Source","Acquisition","Outage/Incident","Security",
]

# ── محور الموضoع (٣ سبتمبر ٢٠٢٦) ─────────────────────────────────────────
# لماذا وُلد: التصنيف كان بمحور الشكل وحده (إصدار · شرح · خبر)، فقُدّرت الأهمية
# من «قيمة الخبر للعالم» لا «قيمته لعزيز». النتيجة المقاسة على ٩٨٩ بطاقة:
# بطاقات Skill تُصنَّف important بنسبة ٢٩٪ بينما متوسط اللوحة ٣٨٪ — أي أن
# الأولوية الأولى مرتَّبة أسوأ من المتوسط، بينما صعد خبر صاروخ روسي وخبر اكتتاب.
#
# قيمة واحدة لكل بطاقة، وأعلى درجة تنطبق هي التي تُكتب — لا أوسعها.
AUDIENCE_TOPICS = [
    "سكيل",           # ملفات Skills: بناؤها · عيوبها · أدلّتها · إصداراتها
    "أداة يستعملها",  # أداة في USER_TOOLS أدناه
    "بنية الوكلاء",   # MCP · Agent · Plugin — البنية لا الأداة بعينها
    "نموذج",          # إصدار نموذج أو قدراته، ولا يقع في ما فوقه
    "عالم AI عام",    # يهمّ عمومًا ولا يمسّ عمله مباشرة
    "خارج الاهتمام",  # استحواذ · تمويل · تقييم · أسهم · دعاوى · تعيينات
]

# الأوزان لمرحلة إعادة المعايرة — غير مستعملة بعد، تُقرأ حين يُعاد وزن الترتيب.
# لا تُغيَّر بلا إعادة معايرة على أعلى ٢٠ بطاقة مقروءةً بعين عزيز.
TOPIC_WEIGHT = {
    "سكيل": 100, "أداة يستعملها": 88, "بنية الوكلاء": 80,
    "نموذج": 68, "عالم AI عام": 40, "خارج الاهتمام": 10,
}

# أدوات عزيز — أكّدها في ٣ سبتمبر ٢٠٢٦. النسخة الحاكمة في CLAUDE.md.
# هذه القائمة هي مدخل درجة «أداة يستعملها»: ما ليس فيها يهبط إلى «عالم AI عام».
# أيّ أداة تدخل عمله تُضاف هنا وفي CLAUDE.md معًا.
USER_TOOLS = [
    "ChatGPT", "OpenAI", "Codex", "Sora",
    "Claude", "Claude Code", "Cowork", "Anthropic",
    "Gemini", "Google AI Studio", "AI Studio", "NotebookLM",
    "GitHub", "Cursor", "Vercel", "Ollama", "Netlify", "Apify",
    "Chrome", "Google Docs", "Google Drive", "Gmail",
    "Trello", "WordPress", "Chatbase", "المكتبة الشاملة",
]

# مجموعات العرض لطبيعة التغيير (٣ سبتمبر ٢٠٢٦).
# النموذج يظلّ يُخرج القيم أعلاه؛ الدمج للعرض والفلترة فقط، فلا يحتاج إعادة وسم.
# نسخة مطابقة في app.js باسم CHG_GROUPS — أيّ تعديل هنا يُنسخ هناك.
CHANGE_GROUPS = {
    "ميزة أو تحديث": ["New Feature", "Update", "Upgrade", "Model Update", "API Update"],
    "إصدار جديد":    ["New Release", "General Availability"],
    "مفتوح المصدر":  ["Open Source"],
    "تكامل ووكلاء":  ["New Integration", "MCP Support", "New Agent Feature"],
    "بحث":           ["Research Release"],
    "أمن":           ["Security"],
    "تجريبي":        ["Beta/Preview", "Beta / Preview"],
    "تسعير":         ["Pricing Change"],
    "توقّف أو عطل":  ["Deprecation", "Shutdown", "Outage/Incident", "Outage / Incident"],
    "استحواذ":       ["Acquisition"],
}
CHANGE_GROUP_OF = {v: g for g, vs in CHANGE_GROUPS.items() for v in vs}

# خريطة الدمج للمجالات القديمة — تُستخدم كشبكة أمان إن ردّ النموذج بمجال قديم
LEGACY_DOMAIN = {
    "Software Development":"برمجة وهندسة","Coding":"برمجة وهندسة","DevOps":"برمجة وهندسة","Engineering":"برمجة وهندسة",
    "Business":"أعمال وإدارة","Management":"أعمال وإدارة","Operations":"أعمال وإدارة","Product":"أعمال وإدارة",
    "Finance":"أعمال وإدارة","Investment":"أعمال وإدارة","Legal":"أعمال وإدارة",
    "Design":"تصميم وواجهات","UI":"تصميم وواجهات","UX":"تصميم وواجهات","Creative":"تصميم وواجهات",
    "Marketing":"تسويق ومحتوى","Digital Marketing":"تسويق ومحتوى","SEO":"تسويق ومحتوى","Content":"تسويق ومحتوى",
    "Media":"تسويق ومحتوى","Sales":"تسويق ومحتوى","E-commerce":"تسويق ومحتوى","Customer Experience":"تسويق ومحتوى",
    "LLM":"نماذج وLLM",
    "Data":"بيانات وتحليلات","Analytics":"بيانات وتحليلات","ML":"بيانات وتحليلات",
    "Research":"بحث وتعليم","Education":"بحث وتعليم",
    "Personal Productivity":"إنتاجية شخصية","Automation":"إنتاجية شخصية",
    "Video":"فيديو وصوت","Audio":"فيديو وصوت",
    "Cybersecurity":"أمن سيبراني",
    "Robotics":"روبوتات وعتاد","Manufacturing":"روبوتات وعتاد","Automotive":"روبوتات وعتاد",
    "Healthcare":"صحة","Medicine":"صحة",
    "Islamic":"إسلامي",
    "AI": None,   # محذوف عمدًا — كان على 550 من 608 بطاقة فلا يفلتر شيئًا
}
