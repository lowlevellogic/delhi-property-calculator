import smtplib
from email.mime.text import MIMEText
from random import randint
import streamlit as st

def send_otp_email(to_email):
    otp = str(randint(100000, 999999))

    msg = MIMEText(f"""
Your OTP code is: {otp}

Valid for 10 minutes.
Do NOT share this OTP with anyone.
""")
    msg["Subject"] = "Your Verification OTP"
    msg["From"] = st.secrets["EMAIL_USER"]
    msg["To"] = to_email

    try:
        server = smtplib.SMTP(st.secrets["EMAIL_HOST"], int(st.secrets["EMAIL_PORT"]))
        server.starttls()
        server.login(st.secrets["EMAIL_USER"], st.secrets["EMAIL_PASS"])
        server.sendmail(st.secrets["EMAIL_USER"], to_email, msg.as_string())
        server.quit()
        return otp, None
    except Exception as e:
        return None, str(e)
