# check_monthly_attendance.py

import os
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from utils.email_utils import send_low_attendance_email
import psycopg2
# ---------------------------------------------------
# LOAD ENV
# ---------------------------------------------------

load_dotenv()

# ---------------------------------------------------
# SETTINGS
# ---------------------------------------------------

MINIMUM_ATTENDANCE_PERCENTAGE = 95

# ---------------------------------------------------
# DATABASE CONNECTION
# ---------------------------------------------------

conn = psycopg2.connect(
    os.getenv("DATABASE_URL")
)

cur = conn.cursor(
    cursor_factory=RealDictCursor
)

# ---------------------------------------------------
# CURRENT MONTH
# ---------------------------------------------------
"""
current_month = datetime.now().strftime("%m")

current_year = datetime.now().strftime("%Y")

month_name = datetime.now().strftime("%B %Y")
"""

# ---------------------------------------------------
# PREVIOUS MONTH LOGIC
# ---------------------------------------------------

today = datetime.now()

# first day of current month
first_day_current_month = today.replace(day=1)

# last day of previous month
last_day_previous_month = first_day_current_month - timedelta(days=1)

current_month = last_day_previous_month.strftime("%m")

current_year = last_day_previous_month.strftime("%Y")

month_name = last_day_previous_month.strftime("%B %Y")
print(f"\n📊 CHECKING ATTENDANCE FOR {month_name}\n")

# ---------------------------------------------------
# GET ATTENDANCE
# ---------------------------------------------------

cur.execute("""
    SELECT
        s.student_id,
        s.name,
        s.email,
        c.course_name,
        c.course_id,

        SUM(
            CASE
                WHEN a.status = 'PRESENT'
                THEN 1
                ELSE 0
            END
        ) * 100.0 / COUNT(*) AS percentage

    FROM attendance a

    JOIN student s
    ON a.student_id = s.student_id

    JOIN class_session cs
    ON a.session_id = cs.session_id

    JOIN course c
    ON cs.course_id = c.course_id

    WHERE
        EXTRACT(MONTH FROM a.marked_at) = %s
        AND
        EXTRACT(YEAR FROM a.marked_at) = %s

    GROUP BY
        s.student_id,
        s.name,
        s.email,
        c.course_id,
        c.course_name
            
    HAVING COUNT(*) > 0
        
""", (current_month, current_year))

students = cur.fetchall()

# ---------------------------------------------------
# SEND EMAILS
# ---------------------------------------------------

for s in students:

    percentage = round(float(s["percentage"]), 2)

    print(
    f'{s["student_id"]} | {s["name"]} | {s["course_name"]} -> {percentage}%'
    )

    if percentage < MINIMUM_ATTENDANCE_PERCENTAGE:

        print(
            f'⚠ Sending email to {s["email"]}'
        )

        send_low_attendance_email(
            to_email=s["email"],
            student_name=s["name"],
            percentage=percentage,
            month_name=month_name,
            course_name=s["course_name"],
            minimum_percentage=MINIMUM_ATTENDANCE_PERCENTAGE
        )

conn.close()

print("\n✅ Monthly attendance check completed")