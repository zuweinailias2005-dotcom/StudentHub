from flask import Flask, render_template, request, redirect, url_for, flash, session
from database import get_db_connection
from werkzeug.security import check_password_hash
from ml_model import predict_risk

app = Flask(__name__)
app.secret_key = "studenthub-secret-key"


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        connection = get_db_connection()

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(user["password"], password):

            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["user_role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("dashboard"))

            else:
                return redirect(url_for("student_dashboard"))

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template("login.html")


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================
# ADMIN DASHBOARD
# =========================

@app.route("/")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return redirect(url_for("student_dashboard"))

    connection = get_db_connection()

    total_students = connection.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    active_students = connection.execute(
        "SELECT COUNT(*) FROM students WHERE status = 'Active'"
    ).fetchone()[0]

    inactive_students = connection.execute(
        "SELECT COUNT(*) FROM students WHERE status = 'Inactive'"
    ).fetchone()[0]

    total_courses = connection.execute(
        "SELECT COUNT(*) FROM courses"
    ).fetchone()[0]

    recent_students = connection.execute("""
        SELECT students.*, courses.name AS course
        FROM students
        JOIN courses ON students.course_id = courses.id
        ORDER BY students.id DESC
        LIMIT 5
    """).fetchall()

    course_stats = connection.execute("""
        SELECT courses.name, COUNT(students.id) AS total
        FROM courses
        LEFT JOIN students
        ON courses.id = students.course_id
        GROUP BY courses.id
    """).fetchall()

    connection.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        active_students=active_students,
        inactive_students=inactive_students,
        total_courses=total_courses,
        recent_students=recent_students,
        course_stats=course_stats
    )


# =========================
# STUDENTS LIST
# =========================

@app.route("/students")
def students():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return redirect(url_for("student_dashboard"))

    search = request.args.get("search", "").strip()
    course = request.args.get("course", "").strip()
    status = request.args.get("status", "").strip()
    risk = request.args.get("risk", "").strip()

    connection = get_db_connection()

    courses = connection.execute("""
        SELECT id, name
        FROM courses
        ORDER BY name
    """).fetchall()

    query = """
        SELECT
            students.*,
            courses.name AS course_name,
            performance.attendance,
            performance.average_marks,
            performance.assignment_completion
        FROM students
        LEFT JOIN courses
            ON students.course_id = courses.id
        LEFT JOIN performance
            ON students.id = performance.student_id
        WHERE 1=1
    """

    parameters = []

    if search:

        query += """
            AND (
                students.name LIKE ?
                OR students.email LIKE ?
            )
        """

        search_value = f"%{search}%"

        parameters.extend([
            search_value,
            search_value
        ])

    if course:

        query += " AND students.course_id = ?"

        parameters.append(course)

    if status:

        query += " AND students.status = ?"

        parameters.append(status)

    query += " ORDER BY students.id DESC"

    student_rows = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    student_list = []

    for student in student_rows:

        attendance = student["attendance"] or 0
        marks = student["average_marks"] or 0
        assignments = student["assignment_completion"] or 0

        risk_level = predict_risk(
            attendance,
            marks,
            assignments
        )

        if risk and risk_level != risk:
            continue

        student_list.append({
            "id": student["id"],
            "name": student["name"],
            "email": student["email"],
            "phone": student["phone"],
            "gender": student["gender"],
            "course_name": student["course_name"],
            "date_of_birth": student["date_of_birth"],
            "enrollment_date": student["enrollment_date"],
            "status": student["status"],
            "attendance": attendance,
            "average_marks": marks,
            "assignment_completion": assignments,
            "risk": risk_level
        })

    return render_template(
        "students.html",
        students=student_list,
        courses=courses,
        search=search,
        selected_course=course,
        selected_status=status,
        selected_risk=risk
    )


# =========================
# STUDENT DASHBOARD
# =========================

@app.route("/student-dashboard")
def student_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "student":
        return redirect(url_for("dashboard"))

    connection = get_db_connection()

    student = connection.execute("""
        SELECT
            students.*,
            courses.name AS course_name,
            performance.attendance,
            performance.average_marks,
            performance.assignment_completion
        FROM students
        LEFT JOIN courses
            ON students.course_id = courses.id
        LEFT JOIN performance
            ON students.id = performance.student_id
        WHERE students.email = ?
    """, (session["user_email"],)).fetchone()

    connection.close()

    if student is None:
        return redirect(url_for("logout"))

    attendance = student["attendance"] or 0
    average_marks = student["average_marks"] or 0
    assignment_completion = student["assignment_completion"] or 0

    risk = predict_risk(
        attendance,
        average_marks,
        assignment_completion
    )

    if risk == "High Risk":

        insight = (
            "Your current academic indicators suggest that you may "
            "need additional academic support. Focus on improving "
            "attendance, marks and assignment completion."
        )

    elif risk == "Medium Risk":

        insight = (
            "You are making progress, but some academic areas could "
            "be improved. Try to maintain regular attendance and "
            "complete assignments on time."
        )

    else:

        insight = (
            "Great work! Your current academic performance indicators "
            "are strong. Keep maintaining your attendance, marks and "
            "assignment completion."
        )

    alerts = []

    if attendance < 75:

        alerts.append(
            "Your attendance is below 75%. "
            "Try to attend classes regularly."
        )

    if average_marks < 50:

        alerts.append(
            "Your average marks are low. "
            "Consider spending more time on revision."
        )

    if assignment_completion < 60:

        alerts.append(
            "Several assignments may still need attention. "
            "Try to complete them on time."
        )

    return render_template(
        "student_dashboard.html",
        student=student,
        attendance=attendance,
        average_marks=average_marks,
        assignment_completion=assignment_completion,
        risk=risk,
        insight=insight,
        alerts=alerts
    )


# =========================
# STUDENT DETAILS
# =========================

@app.route("/student/<int:student_id>")
def student_detail(student_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return redirect(url_for("student_dashboard"))

    connection = get_db_connection()

    student = connection.execute("""
        SELECT students.*, courses.name AS course
        FROM students
        JOIN courses
        ON students.course_id = courses.id
        WHERE students.id = ?
    """, (student_id,)).fetchone()

    connection.close()

    if not student:
        return "Student not found."

    return render_template(
        "student_detail.html",
        student=student
    )


# =========================
# EDIT STUDENT
# =========================

@app.route("/student/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return redirect(url_for("student_dashboard"))

    connection = get_db_connection()

    if request.method == "POST":

        connection.execute("""
            UPDATE students
            SET
                name = ?,
                email = ?,
                phone = ?,
                gender = ?,
                course_id = ?,
                date_of_birth = ?,
                enrollment_date = ?,
                status = ?
            WHERE id = ?
        """, (
            request.form["name"],
            request.form["email"],
            request.form["phone"],
            request.form["gender"],
            request.form["course_id"],
            request.form["date_of_birth"],
            request.form["enrollment_date"],
            request.form["status"],
            student_id
        ))

        connection.commit()
        connection.close()

        flash("Student updated successfully.")

        return redirect(
            url_for(
                "student_detail",
                student_id=student_id
            )
        )

    student = connection.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    courses = connection.execute(
        "SELECT * FROM courses ORDER BY name"
    ).fetchall()

    connection.close()

    return render_template(
        "student_form.html",
        student=student,
        courses=courses
    )


# =========================
# DELETE STUDENT
# =========================

@app.route("/student/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return redirect(url_for("student_dashboard"))

    connection = get_db_connection()

    connection.execute(
        "DELETE FROM students WHERE id = ?",
        (student_id,)
    )

    connection.commit()
    connection.close()

    flash("Student deleted successfully.")

    return redirect(url_for("students"))


# =========================
# ANALYTICS DASHBOARD
# =========================

@app.route("/analytics")
def analytics():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return redirect(url_for("student_dashboard"))

    connection = get_db_connection()

    course_data = connection.execute("""
        SELECT courses.name, COUNT(students.id) AS total
        FROM courses
        LEFT JOIN students
        ON courses.id = students.course_id
        GROUP BY courses.id
    """).fetchall()

    status_data = connection.execute("""
        SELECT status, COUNT(*) AS total
        FROM students
        GROUP BY status
    """).fetchall()

    total_students = connection.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    total_courses = connection.execute(
        "SELECT COUNT(*) FROM courses"
    ).fetchone()[0]

    connection.close()

    course_labels = [
        row["name"] for row in course_data
    ]

    course_values = [
        row["total"] for row in course_data
    ]

    status_labels = [
        row["status"] for row in status_data
    ]

    status_values = [
        row["total"] for row in status_data
    ]

    return render_template(
        "analytics.html",
        total_students=total_students,
        total_courses=total_courses,
        course_labels=course_labels,
        course_values=course_values,
        status_labels=status_labels,
        status_values=status_values
    )


# =========================
# ANALYTICS API
# =========================

@app.route("/api/analytics")
def analytics_api():

    if "user_id" not in session:
        return {"error": "Not logged in"}, 401

    if session.get("user_role") != "admin":
        return {"error": "Access denied"}, 403

    connection = get_db_connection()

    course_data = connection.execute("""
        SELECT courses.name, COUNT(students.id) AS total
        FROM courses
        LEFT JOIN students
        ON courses.id = students.course_id
        GROUP BY courses.id
    """).fetchall()

    status_data = connection.execute("""
        SELECT status, COUNT(*) AS total
        FROM students
        GROUP BY status
    """).fetchall()

    connection.close()

    return {
        "course_labels": [
            row["name"] for row in course_data
        ],

        "course_values": [
            row["total"] for row in course_data
        ],

        "status_labels": [
            row["status"] for row in status_data
        ],

        "status_values": [
            row["total"] for row in status_data
        ]
    }


# =========================
# AI RISK PREDICTION
# =========================

@app.route("/risk-prediction")
def risk_prediction():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return redirect(url_for("student_dashboard"))

    connection = get_db_connection()

    students = connection.execute("""
        SELECT
            students.id,
            students.name,
            students.email,
            performance.attendance,
            performance.average_marks,
            performance.assignment_completion
        FROM students
        LEFT JOIN performance
        ON students.id = performance.student_id
    """).fetchall()

    connection.close()

    results = []

    for student in students:

        attendance = student["attendance"] or 0
        marks = student["average_marks"] or 0
        assignments = student["assignment_completion"] or 0

        risk = predict_risk(
            attendance,
            marks,
            assignments
        )

        results.append({
            "name": student["name"],
            "email": student["email"],
            "attendance": attendance,
            "marks": marks,
            "assignments": assignments,
            "risk": risk
        })

    return render_template(
        "risk_prediction.html",
        students=results
    )


# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":
    app.run(debug=True)