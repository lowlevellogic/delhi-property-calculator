import smtplib
from email.mime.text import MIMEText
import streamlit as st


def send_otp_email(to_email: str, otp_code: str):
    """
    Sends OTP email using Gmail SMTP.
    Configure in .streamlit/secrets.toml as:

    [email]
    USER = "aggarwal.dlc@gmail.com"
    APP_PASSWORD = "your-16-digit-app-password"
    """
    from_email = st.secrets["email"]["USER"]
    app_password = st.secrets["email"]["APP_PASSWORD"]

    subject = "Your OTP for Aggarwal Documents & Legal Consultants"
    body = f"""
Namaste,

Your OTP for creating an account on Aggarwal Documents & Legal Consultants (Delhi Property Calculator) is:

    {otp_code}

This OTP is valid for about 10 minutes.
If you did not request this, you can ignore this email.

Regards,
Aggarwal Documents & Legal Consultants
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, app_password)
        server.send_message(msg)
