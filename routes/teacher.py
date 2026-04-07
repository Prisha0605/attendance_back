from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from utils.db import get_db
from psycopg2.extras import RealDictCursor
from datetime import datetime

teacher_bp = Blueprint("teacher", __name__)


# ---------------- START SESSION ----------------
@teacher_bp.route("/teacher/start_session", methods=["POST"])
@jwt_required()
def start_session():
    claims = get_jwt()
    if claims.get("role") != "teacher":
        return jsonify({"error": "Unauthorized"}), 403

    course_id = request.json.get("course_id")
    classroom_id = request.json.get("classroom_id")

    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # prevent duplicate session
    cur.execute("""
        SELECT * FROM class_session
        WHERE course_id=%s AND session_date=%s AND is_active=1
    """, (course_id, today))

    if cur.fetchone():
        return jsonify({"message": "Session already active"}), 400

    cur.execute("""
        INSERT INTO class_session
        (course_id, classroom_id, session_date, start_time, is_active)
        VALUES (%s, %s, %s, %s, 1)
    """, (course_id, classroom_id, today, now_time))

    conn.commit()
    conn.close()

    return jsonify({"message": "Session started"})


# ---------------- END SESSION ----------------
@teacher_bp.route("/teacher/end_session", methods=["POST"])
@jwt_required()
def end_session():
    claims = get_jwt()

    if claims.get("role") != "teacher":
        return jsonify({"error": "Unauthorized"}), 403

    course_id = request.json.get("course_id")
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # get active session
    cur.execute("""
        SELECT session_id FROM class_session
        WHERE course_id=%s AND session_date=%s AND is_active=1
    """, (course_id, today))

    session = cur.fetchone()

    if not session:
        return jsonify({"message": "No active session"}), 400

    session_id = session["session_id"]

    # all students
    cur.execute("""
        SELECT student_id FROM enrollment WHERE course_id=%s
    """, (course_id,))
    all_students = [s["student_id"] for s in cur.fetchall()]

    # present students
    cur.execute("""
        SELECT student_id FROM attendance WHERE session_id=%s
    """, (session_id,))
    present_students = [s["student_id"] for s in cur.fetchall()]

    # absent students
    absent_students = set(all_students) - set(present_students)

    for student in absent_students:
        cur.execute("""
            INSERT INTO attendance
            (student_id, session_id, status, marked_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (student_id, session_id) DO NOTHING
        """, (student, session_id, "ABSENT", datetime.now()))

    # end session
    cur.execute("""
        UPDATE class_session
        SET is_active=0, end_time=%s
        WHERE session_id=%s
    """, (now_time, session_id))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Session ended",
        "absent_count": len(absent_students)
    })


# ---------------- TEACHER COURSES ----------------
@teacher_bp.route("/teacher/my_courses", methods=["GET"])
@jwt_required()
def my_courses():
    teacher_id = get_jwt_identity()

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT course_id, course_name
        FROM course
        WHERE teacher_id = %s
    """, (teacher_id,))

    data = cur.fetchall()
    conn.close()

    return jsonify(data)


# ---------------- CLASSROOMS ----------------
@teacher_bp.route("/teacher/classrooms", methods=["GET"])
@jwt_required()
def get_classrooms():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT classroom_id, beacon_minor FROM classroom
    """)

    data = cur.fetchall()
    conn.close()

    return jsonify(data)


# ---------------- COURSE ATTENDANCE ----------------
@teacher_bp.route("/teacher/course_attendance", methods=["POST"])
@jwt_required()
def course_attendance():
    data = request.json

    course_id = data.get("course_id")
    date = data.get("date")
    student_id = data.get("student_id")

    # ✅ CLEAN INPUTS
    if date == "" or date is None:
        date = None

    if student_id:
        student_id = student_id.strip()
        if student_id == "":
            student_id = None

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ---------------- BASE QUERY ----------------
    query = """
        SELECT s.student_id, s.name, a.status, cs.session_date
        FROM attendance a
        JOIN student s ON a.student_id = s.student_id
        JOIN class_session cs ON a.session_id = cs.session_id
        WHERE cs.course_id = %s
    """

    params = [course_id]

    # ---------------- FILTERS ----------------
    if date:
        query += " AND cs.session_date = %s"
        params.append(date)

    if student_id:
        query += " AND s.student_id = %s"
        params.append(student_id)

    query += " ORDER BY cs.session_date DESC"

    print("DEBUG QUERY:", query)
    print("DEBUG PARAMS:", params)

    cur.execute(query, params)
    records = cur.fetchall()

    # ---------------- SUMMARY ----------------
    total = len(records)
    present = sum(1 for r in records if r["status"] == "PRESENT")
    absent = total - present

    # ---------------- STUDENT STATS ----------------
    cur.execute("""
        SELECT s.student_id, s.name,
        COALESCE(
            SUM(CASE WHEN a.status='PRESENT' THEN 1 ELSE 0 END) * 100.0 
            / NULLIF(COUNT(*), 0),
        0) AS percentage
        FROM attendance a
        JOIN student s ON a.student_id = s.student_id
        JOIN class_session cs ON a.session_id = cs.session_id
        WHERE cs.course_id = %s
        GROUP BY s.student_id, s.name
    """, (course_id,))

    student_stats = cur.fetchall()

    # ✅ FORCE FLOAT
    for s in student_stats:
        s["percentage"] = float(s["percentage"])

    conn.close()

    return jsonify({
        "records": records,
        "summary": {
            "total": total,
            "present": present,
            "absent": absent
        },
        "student_stats": student_stats
    })
