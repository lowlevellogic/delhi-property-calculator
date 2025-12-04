import smtplib
from email.mime.text import MIMEText
import random
import string
import streamlit as st


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def send_otp_email(receiver_email: str):

    try:
        sender_email = st.secrets["email_auth"]["email"]
        sender_password = st.secrets["email_auth"]["password"]

        otp = generate_otp()

        msg = MIMEText(
            f"Your OTP for verification is:\n\n{otp}\n\nRegards,\nAggarwal Documents & Legal Consultants"
        )
        msg["Subject"] = "Your OTP Verification Code"
        msg["From"] = sender_email
        msg["To"] = receiver_email

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        return otp, None

    except Exception as error:
        return None, str(error)
