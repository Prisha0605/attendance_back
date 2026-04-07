from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from utils.db import get_db
from psycopg2.extras import RealDictCursor
import numpy as np

student_bp = Blueprint("student", __name__)


# ---------------- MY COURSES ----------------
@student_bp.route("/my_courses")
@jwt_required()
def my_courses():
    student_id = get_jwt_identity()
    claims = get_jwt()

    if claims.get("role") != "student":
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT c.course_id, c.course_name
        FROM course c
        JOIN enrollment e ON c.course_id = e.course_id
        WHERE e.student_id = %s
    """, (student_id,))

    data = cur.fetchall()
    conn.close()

    return jsonify(data)


# ---------------- EMBEDDING ----------------
@student_bp.route("/embedding", methods=["GET"])
@jwt_required()
def get_my_embedding():
    student_id = get_jwt_identity()

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT face_embedding FROM student WHERE student_id = %s
    """, (student_id,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "No embedding found"}), 404

    emb = np.frombuffer(row["face_embedding"], dtype=np.float32)

    return jsonify({
        "id": student_id,
        "embedding": emb.tolist()
    })


# ---------------- ATTENDANCE HISTORY ----------------
@student_bp.route("/attendance_history", methods=["POST"])
@jwt_required()
def attendance_history():
    student_id = get_jwt_identity()
    course_id = request.json.get("course_id")

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT cs.session_date, a.status
        FROM attendance a
        JOIN class_session cs ON a.session_id = cs.session_id
        WHERE a.student_id=%s AND cs.course_id=%s
        ORDER BY cs.session_date DESC
    """, (student_id, course_id))

    records = cur.fetchall()

    total = len(records)
    present = sum(1 for r in records if r["status"] == "PRESENT")
    percentage = (present / total * 100) if total > 0 else 0

    conn.close()

    return jsonify({
        "records": records,
        "percentage": round(percentage, 2)
    })