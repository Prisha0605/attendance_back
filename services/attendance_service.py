import json
from datetime import datetime
from utils.db import get_db
from psycopg2.extras import RealDictCursor
from services.ble_service import detect_classroom_from_ble


def process_attendance(student_id, course_id, ble_json):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_time = now.time()

    # ---------------- CHECK ACTIVE SESSION ----------------
    cur.execute("""
        SELECT session_id, classroom_id, start_time, end_time
        FROM class_session
        WHERE course_id=%s AND session_date=%s AND is_active=1
    """, (course_id, today))

    session = cur.fetchone()

    if not session:
        return "ABSENT", "No active session"

    session_id = session["session_id"]
    classroom_id = session["classroom_id"]

    # ---------------- TIME CHECK ----------------
    if session["start_time"]:
        start = datetime.strptime(session["start_time"], "%H:%M:%S").time()

        if session["end_time"]:
            end = datetime.strptime(session["end_time"], "%H:%M:%S").time()

            if not (start <= current_time <= end):
                return "ABSENT", "Outside class time"
        else:
            if current_time < start:
                return "ABSENT", "Session not started yet"

    # ---------------- BLE CHECK ----------------
    ble_readings = json.loads(ble_json)
    minor, rssi = detect_classroom_from_ble(ble_readings)

    if not minor:
        return "ABSENT", "No BLE detected"

    cur.execute("""
        SELECT classroom_id FROM classroom
        WHERE beacon_minor=%s
    """, (minor,))

    room = cur.fetchone()

    if not room or room["classroom_id"] != classroom_id:
        return "ABSENT", "Wrong classroom"

    # ---------------- SAVE ATTENDANCE ----------------
    cur.execute("""
        INSERT INTO attendance
        (student_id, session_id, status, marked_at, classroom_id, rssi)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (student_id, session_id) DO NOTHING
    """, (student_id, session_id, "PRESENT", datetime.now(), classroom_id, rssi))

    conn.commit()
    conn.close()

    return "PRESENT", "Attendance marked"