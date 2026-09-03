#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار إنقاذ المخرَج المقصوص — العطل: دفعة كاملة تُفقد لأن آخر كائن انقطع."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jsontools import salvage

P = F = 0
def ok(name, cond):
    global P, F
    if cond: P += 1; print("  ✓ " + name)
    else: F += 1; print("  ✗ " + name)

full = '[{"id":"1","keep":true,"arabic_title":"أ"},{"id":"2","keep":false},{"id":"3","keep":true}]'
ok("JSON سليم يُقرأ كاملًا", len(salvage(full)) == 3)

cut = '[{"id":"1","keep":true,"arabic_title":"أ"},{"id":"2","keep":false},{"id":"3","keep":tr'
r = salvage(cut)
ok("المقصوص: يُنقَذ ما اكتمل ويُترك الناقص", len(r) == 2 and r[0]["id"] == "1" and r[1]["id"] == "2")

braces = '[{"id":"1","arabic_summary":"نص فيه } قوس داخل نص","keep":true},{"id":"2","keep":tru'
r2 = salvage(braces)
ok("قوس داخل نص لا يخدع الماسح", len(r2) == 1 and r2[0]["id"] == "1")

esc = r'[{"id":"1","arabic_title":"اقتباس \" وقوس }","keep":true},{"id":"2"'
ok("علامة اقتباس مهرَّبة لا تكسر المسح", len(salvage(esc)) == 1)

ok("بلا كائنات مكتملة يعيد فارغًا", salvage('[{"id":"1"') == [])
ok("الكائن بلا id يُهمَل", salvage('[{"keep":true},{"id":"9","keep":true}]')[0]["id"] == "9")

print("\nنجح %d · فشل %d" % (P, F))
sys.exit(1 if F else 0)
