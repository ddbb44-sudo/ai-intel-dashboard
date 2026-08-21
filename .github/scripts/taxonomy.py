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
