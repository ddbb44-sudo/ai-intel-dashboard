#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إرسال التقرير عبر SMTP. بلا أي أكشن طرف ثالث — مكتبة بايثون القياسية فقط."""
import os, smtplib, ssl
from email.message import EmailMessage

def envs(n, d=""):
    v = os.environ.get(n)
    return v.strip() if v and v.strip() else d

USER = envs("MAIL_USERNAME")
PW   = envs("MAIL_PASSWORD")
TO   = envs("MAIL_TO", USER)
HOST = envs("MAIL_HOST", "smtp.gmail.com")
PORT = int(envs("MAIL_PORT", "465"))
SUBJ = envs("MAIL_SUBJECT", "تقرير لوحة الذكاء الاصطناعي")

if not USER or not PW:
    print("لم يُضبط MAIL_USERNAME/MAIL_PASSWORD — تخطّي الإرسال."); raise SystemExit(0)

try:
    body = open("email.html", encoding="utf-8").read()
except FileNotFoundError:
    body = "<div dir='rtl'>تعذّر إنشاء التقرير. راجع سجل التشغيلة.</div>"

msg = EmailMessage()
msg["Subject"] = SUBJ
msg["From"] = "لوحة الذكاء الاصطناعي <%s>" % USER
msg["To"] = TO
msg.set_content("تقريرك اليومي بصيغة HTML — افتحه في بريد يدعم التنسيق.")
msg.add_alternative(body, subtype="html")

ctx = ssl.create_default_context()
try:
    if PORT == 465:
        with smtplib.SMTP_SSL(HOST, PORT, context=ctx, timeout=60) as s:
            s.login(USER, PW); s.send_message(msg)
    else:
        with smtplib.SMTP(HOST, PORT, timeout=60) as s:
            s.starttls(context=ctx); s.login(USER, PW); s.send_message(msg)
    print("أُرسل التقرير إلى", TO)
except Exception as e:
    # فشل البريد لا يُفشل التشغيلة — التقرير موجود في السجل والمستودع
    print("فشل إرسال البريد:", e)
    raise SystemExit(0)
