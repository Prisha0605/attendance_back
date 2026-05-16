# utils/email_utils.py

import os
import smtplib

from dotenv import load_dotenv

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# LOAD .env
load_dotenv()


def send_low_attendance_email(
    to_email,
    student_name,
    percentage,
    month_name,
    course_name,
    minimum_percentage
):

    # ------------------------------------------------
    # ENV VARIABLES
    # ------------------------------------------------

    sender_email = os.getenv("BREVO_EMAIL")

    smtp_login = os.getenv("BREVO_SMTP_LOGIN")

    smtp_password = os.getenv("BREVO_SMTP_PASSWORD")

    # ------------------------------------------------
    # EMAIL CONTENT
    # ------------------------------------------------

    subject = f"Low Attendance Warning - {course_name} for {month_name}"

    body = f"""
Hello {student_name},

This is to inform you that your attendance for the subject: {course_name}
during {month_name} is currently:  {percentage}%
which is below the minimum required attendance of {minimum_percentage}%.
Please improve your attendance to avoid academic issues.
Regards,
Attendance Management System
"""

    # ------------------------------------------------
    # CREATE EMAIL
    # ------------------------------------------------

    msg = MIMEMultipart()

    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    # ------------------------------------------------
    # SEND EMAIL
    # ------------------------------------------------

    try:

        server = smtplib.SMTP(
            "smtp-relay.brevo.com",
            587
        )

        server.starttls()

        server.login(
            smtp_login,
            smtp_password
        )

        server.send_message(msg)

        server.quit()

        print(f"✅ Email sent to {to_email}")

    except Exception as e:

        print(f"❌ Failed to send email to {to_email}")

        print(e)