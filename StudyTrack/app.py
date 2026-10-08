from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
import xml.etree.ElementTree as ET
from functools import wraps
from datetime import datetime, date, timedelta
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = "uniplan_secret_key"

DATABASE = "uniplan.db"
USERS_XML = "users.xml"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            code TEXT NOT NULL,
            credit INTEGER DEFAULT 3,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'Medium',
            deadline TEXT,
            status TEXT DEFAULT 'Pending',
            completed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_id INTEGER,
            exam_date TEXT NOT NULL,
            exam_time TEXT,
            room TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            weekly_target INTEGER DEFAULT 10
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# XML USER MANAGEMENT
# =========================================================

def init_users_xml():
    if not os.path.exists(USERS_XML):
        root = ET.Element("users")
        tree = ET.ElementTree(root)
        tree.write(USERS_XML, encoding="utf-8", xml_declaration=True)

    admin = get_user_by_email_xml("admin@uniplan.com")

    if not admin:
        register_user_xml(
            name="Administrator",
            email="admin@uniplan.com",
            password="admin123",
            role="admin"
        )


def register_user_xml(name, email, password, role="student"):
    tree = ET.parse(USERS_XML)
    root = tree.getroot()

    user_id = 1
    existing_ids = []

    for user in root.findall("user"):
        try:
            existing_ids.append(int(user.get("id")))
        except (TypeError, ValueError):
            pass

    if existing_ids:
        user_id = max(existing_ids) + 1

    user = ET.SubElement(root, "user")
    user.set("id", str(user_id))

    ET.SubElement(user, "name").text = name
    ET.SubElement(user, "email").text = email
    ET.SubElement(user, "password").text = generate_password_hash(password)
    ET.SubElement(user, "role").text = role
    ET.SubElement(user, "created_at").text = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    tree.write(USERS_XML, encoding="utf-8", xml_declaration=True)

    return user_id


def get_user_by_email_xml(email):
    if not os.path.exists(USERS_XML):
        return None

    tree = ET.parse(USERS_XML)
    root = tree.getroot()

    for user in root.findall("user"):
        email_element = user.find("email")

        if email_element is not None and email_element.text:
            if email_element.text.lower() == email.lower():
                return user

    return None


def get_user_by_id_xml(user_id):
    if not os.path.exists(USERS_XML):
        return None

    tree = ET.parse(USERS_XML)
    root = tree.getroot()

    for user in root.findall("user"):
        if user.get("id") == str(user_id):
            return user

    return None


def update_user_xml(user_id, name, email):
    tree = ET.parse(USERS_XML)
    root = tree.getroot()

    for user in root.findall("user"):
        if user.get("id") == str(user_id):

            name_element = user.find("name")
            email_element = user.find("email")

            if name_element is not None:
                name_element.text = name

            if email_element is not None:
                email_element.text = email

            tree.write(
                USERS_XML,
                encoding="utf-8",
                xml_declaration=True
            )

            return True

    return False


def get_all_users_xml():
    users = []

    if not os.path.exists(USERS_XML):
        return users

    tree = ET.parse(USERS_XML)
    root = tree.getroot()

    for user in root.findall("user"):
        users.append({
            "id": user.get("id"),
            "name": user.findtext("name", ""),
            "email": user.findtext("email", ""),
            "role": user.findtext("role", "student"),
            "created_at": user.findtext("created_at", "")
        })

    return users


def delete_user_xml(user_id):
    if not os.path.exists(USERS_XML):
        return False

    tree = ET.parse(USERS_XML)
    root = tree.getroot()

    for user in root.findall("user"):
        if user.get("id") == str(user_id):
            root.remove(user)
            tree.write(
                USERS_XML,
                encoding="utf-8",
                xml_declaration=True
            )
            return True

    return False


# =========================================================
# LOGIN DECORATORS
# =========================================================

def login_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return decorated_function


def admin_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))

        return function(*args, **kwargs)

    return decorated_function


# =========================================================
# SMART FUNCTIONS
# =========================================================

def calculate_smart_priority(priority, deadline):
    if not deadline:
        return priority

    try:
        deadline_date = datetime.strptime(
            deadline, "%Y-%m-%d"
        ).date()

        days_left = (deadline_date - date.today()).days

        if days_left <= 2:
            return "Urgent"

        if days_left <= 5 and priority in ["Low", "Medium"]:
            return "High"

    except ValueError:
        pass

    return priority


def get_deadline_status(deadline):
    if not deadline:
        return "No deadline"

    try:
        deadline_date = datetime.strptime(
            deadline, "%Y-%m-%d"
        ).date()

        days_left = (deadline_date - date.today()).days

        if days_left < 0:
            return "Overdue"

        if days_left == 0:
            return "Due Today"

        if days_left == 1:
            return "Due Tomorrow"

        return f"Due in {days_left} days"

    except ValueError:
        return "No deadline"


def calculate_study_streak(user_id):
    conn = get_db()

    rows = conn.execute("""
        SELECT DISTINCT DATE(completed_at) AS completed_date
        FROM tasks
        WHERE user_id = ?
        AND status = 'Completed'
        AND completed_at IS NOT NULL
        ORDER BY completed_date DESC
    """, (user_id,)).fetchall()

    conn.close()

    if not rows:
        return 0

    completed_dates = set()

    for row in rows:
        completed_dates.add(
            datetime.strptime(
                row["completed_date"],
                "%Y-%m-%d"
            ).date()
        )

    today = date.today()

    if today in completed_dates:
        current_date = today
    elif today - timedelta(days=1) in completed_dates:
        current_date = today - timedelta(days=1)
    else:
        return 0

    streak = 0

    while current_date in completed_dates:
        streak += 1
        current_date -= timedelta(days=1)

    return streak


def get_smart_recommendation(user_id):
    conn = get_db()

    exam = conn.execute("""
        SELECT exams.*, subjects.name AS subject_name
        FROM exams
        LEFT JOIN subjects
        ON exams.subject_id = subjects.id
        WHERE exams.user_id = ?
        AND exams.exam_date >= ?
        ORDER BY exams.exam_date ASC, exams.exam_time ASC
        LIMIT 1
    """, (user_id, date.today().strftime("%Y-%m-%d"))).fetchone()

    if exam:
        conn.close()

        return (
            f"Focus on your upcoming exam: "
            f"{exam['subject_name'] or 'Exam'} "
            f"on {exam['exam_date']}."
        )

    task = conn.execute("""
        SELECT tasks.*, subjects.name AS subject_name
        FROM tasks
        LEFT JOIN subjects
        ON tasks.subject_id = subjects.id
        WHERE tasks.user_id = ?
        AND tasks.status = 'Pending'
        ORDER BY
            CASE
                WHEN tasks.deadline IS NULL THEN 1
                ELSE 0
            END,
            tasks.deadline ASC
        LIMIT 1
    """, (user_id,)).fetchone()

    conn.close()

    if task:
        return f"Next task: {task['title']}."

    return "Great! You are all caught up."


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        if get_user_by_email_xml(email):
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        user_id = register_user_xml(
            name=name,
            email=email,
            password=password,
            role="student"
        )

        conn = get_db()

        conn.execute("""
            INSERT OR IGNORE INTO study_goals
            (user_id, weekly_target)
            VALUES (?, ?)
        """, (user_id, 10))

        conn.commit()
        conn.close()

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_email_xml(email)

        if not user:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        stored_password = user.findtext("password", "")

        if not check_password_hash(stored_password, password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = int(user.get("id"))
        session["name"] = user.findtext("name", "")
        session["email"] = user.findtext("email", "")
        session["role"] = user.findtext("role", "student")

        flash("Login successful.", "success")

        if session["role"] == "admin":
            return redirect(url_for("admin"))

        return redirect(url_for("dashboard"))

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    user_id = session["user_id"]

    conn = get_db()

    subject_count = conn.execute("""
        SELECT COUNT(*) AS total
        FROM subjects
        WHERE user_id = ?
    """, (user_id,)).fetchone()["total"]

    task_count = conn.execute("""
        SELECT COUNT(*) AS total
        FROM tasks
        WHERE user_id = ?
    """, (user_id,)).fetchone()["total"]

    completed_tasks = conn.execute("""
        SELECT COUNT(*) AS total
        FROM tasks
        WHERE user_id = ?
        AND status = 'Completed'
    """, (user_id,)).fetchone()["total"]

    pending_tasks = conn.execute("""
        SELECT COUNT(*) AS total
        FROM tasks
        WHERE user_id = ?
        AND status = 'Pending'
    """, (user_id,)).fetchone()["total"]

    assignment_count = conn.execute("""
        SELECT COUNT(*) AS total
        FROM assignments
        WHERE user_id = ?
    """, (user_id,)).fetchone()["total"]

    exam_count = conn.execute("""
        SELECT COUNT(*) AS total
        FROM exams
        WHERE user_id = ?
    """, (user_id,)).fetchone()["total"]

    conn.close()

    streak = calculate_study_streak(user_id)
    recommendation = get_smart_recommendation(user_id)

    return render_template(
        "dashboard.html",
        subject_count=subject_count,
        task_count=task_count,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        assignment_count=assignment_count,
        exam_count=exam_count,
        streak=streak,
        recommendation=recommendation
    )


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    user_id = session["user_id"]

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()

        if not name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("profile"))

        existing_user = get_user_by_email_xml(email)

        if existing_user and int(existing_user.get("id")) != user_id:
            flash("Email already used by another account.", "danger")
            return redirect(url_for("profile"))

        update_user_xml(user_id, name, email)

        session["name"] = name
        session["email"] = email

        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    user = get_user_by_id_xml(user_id)

    return render_template("profile.html", user=user)


# =========================================================
# SUBJECTS
# =========================================================

@app.route("/subjects", methods=["GET", "POST"])
@login_required
def subjects():

    user_id = session["user_id"]

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        credit = request.form.get("credit", "3").strip()

        if not name or not code:
            flash("Subject name and code are required.", "danger")
            return redirect(url_for("subjects"))

        try:
            credit = int(credit)
        except ValueError:
            credit = 3

        conn = get_db()

        conn.execute("""
            INSERT INTO subjects
            (user_id, name, code, credit)
            VALUES (?, ?, ?, ?)
        """, (user_id, name, code, credit))

        conn.commit()
        conn.close()

        flash("Subject added successfully.", "success")
        return redirect(url_for("subjects"))

    conn = get_db()

    subject_list = conn.execute("""
        SELECT *
        FROM subjects
        WHERE user_id = ?
        ORDER BY name ASC
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "subjects.html",
        subjects=subject_list
    )


@app.route("/subject/delete/<int:subject_id>")
@login_required
def delete_subject(subject_id):

    user_id = session["user_id"]

    conn = get_db()

    conn.execute("""
        DELETE FROM subjects
        WHERE id = ?
        AND user_id = ?
    """, (subject_id, user_id))

    conn.commit()
    conn.close()

    flash("Subject deleted.", "success")
    return redirect(url_for("subjects"))


# =========================================================
# TASKS
# =========================================================

@app.route("/tasks", methods=["GET", "POST"])
@login_required
def tasks():

    user_id = session["user_id"]

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        priority = request.form.get("priority", "Medium")
        deadline = request.form.get("deadline", "").strip()
        subject_id = request.form.get("subject_id", "").strip()

        if not title:
            flash("Task title is required.", "danger")
            return redirect(url_for("tasks"))

        try:
            subject_value = int(subject_id) if subject_id else None
        except ValueError:
            subject_value = None

        conn = get_db()

        conn.execute("""
            INSERT INTO tasks
            (user_id, subject_id, title, description, priority, deadline, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Pending')
        """, (
            user_id,
            subject_value,
            title,
            description,
            priority,
            deadline if deadline else None
        ))

        conn.commit()
        conn.close()

        flash("Task added successfully.", "success")
        return redirect(url_for("tasks"))

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    conn = get_db()

    query = """
        SELECT tasks.*,
               subjects.name AS subject_name,
               subjects.code AS subject_code
        FROM tasks
        LEFT JOIN subjects
        ON tasks.subject_id = subjects.id
        WHERE tasks.user_id = ?
    """

    params = [user_id]

    if search:
        query += """
            AND (
                tasks.title LIKE ?
                OR tasks.description LIKE ?
                OR subjects.name LIKE ?
                OR subjects.code LIKE ?
            )
        """

        search_value = f"%{search}%"

        params.extend([
            search_value,
            search_value,
            search_value,
            search_value
        ])

    if status_filter in ["Pending", "Completed"]:
        query += " AND tasks.status = ?"
        params.append(status_filter)

    query += """
        ORDER BY
            CASE
                WHEN tasks.status = 'Pending' THEN 0
                ELSE 1
            END,
            tasks.deadline ASC
    """

    task_rows = conn.execute(query, params).fetchall()

    subject_list = conn.execute("""
        SELECT *
        FROM subjects
        WHERE user_id = ?
        ORDER BY name ASC
    """, (user_id,)).fetchall()

    conn.close()

    task_list = []

    for task in task_rows:

        task_data = dict(task)

        task_data["smart_priority"] = calculate_smart_priority(
            task["priority"],
            task["deadline"]
        )

        task_data["deadline_status"] = get_deadline_status(
            task["deadline"]
        )

        task_list.append(task_data)

    return render_template(
        "tasks.html",
        tasks=task_list,
        subjects=subject_list,
        search=search,
        status_filter=status_filter
    )


@app.route("/task/complete/<int:task_id>")
@login_required
def complete_task(task_id):

    user_id = session["user_id"]

    conn = get_db()

    task = conn.execute("""
        SELECT status
        FROM tasks
        WHERE id = ?
        AND user_id = ?
    """, (task_id, user_id)).fetchone()

    if not task:
        conn.close()
        flash("Task not found.", "danger")
        return redirect(url_for("tasks"))

    if task["status"] == "Completed":

        conn.execute("""
            UPDATE tasks
            SET status = 'Pending',
                completed_at = NULL
            WHERE id = ?
            AND user_id = ?
        """, (task_id, user_id))

    else:

        conn.execute("""
            UPDATE tasks
            SET status = 'Completed',
                completed_at = ?
            WHERE id = ?
            AND user_id = ?
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            task_id,
            user_id
        ))

    conn.commit()
    conn.close()

    return redirect(url_for("tasks"))


@app.route("/task/delete/<int:task_id>")
@login_required
def delete_task(task_id):

    user_id = session["user_id"]

    conn = get_db()

    conn.execute("""
        DELETE FROM tasks
        WHERE id = ?
        AND user_id = ?
    """, (task_id, user_id))

    conn.commit()
    conn.close()

    flash("Task deleted.", "success")
    return redirect(url_for("tasks"))


# =========================================================
# ASSIGNMENTS
# =========================================================

@app.route("/assignments", methods=["GET", "POST"])
@login_required
def assignments():

    user_id = session["user_id"]

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        subject_id = request.form.get("subject_id", "").strip()
        deadline = request.form.get("deadline", "").strip()

        if not title:
            flash("Assignment title is required.", "danger")
            return redirect(url_for("assignments"))

        try:
            subject_value = int(subject_id) if subject_id else None
        except ValueError:
            subject_value = None

        conn = get_db()

        conn.execute("""
            INSERT INTO assignments
            (user_id, subject_id, title, description, deadline, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
        """, (
            user_id,
            subject_value,
            title,
            description,
            deadline if deadline else None
        ))

        conn.commit()
        conn.close()

        flash("Assignment added successfully.", "success")
        return redirect(url_for("assignments"))

    conn = get_db()

    assignment_list = conn.execute("""
        SELECT assignments.*,
               subjects.name AS subject_name,
               subjects.code AS subject_code
        FROM assignments
        LEFT JOIN subjects
        ON assignments.subject_id = subjects.id
        WHERE assignments.user_id = ?
        ORDER BY assignments.deadline ASC
    """, (user_id,)).fetchall()

    subject_list = conn.execute("""
        SELECT
            id,
            user_id,
            name AS subject_name,
            code AS subject_code,
            credit,
            created_at
        FROM subjects
        WHERE user_id = ?
        ORDER BY name ASC
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "assignments.html",
        assignments=assignment_list,
        subjects=subject_list
    )


@app.route("/assignment/complete/<int:assignment_id>")
@login_required
def complete_assignment(assignment_id):

    user_id = session["user_id"]

    conn = get_db()

    assignment = conn.execute("""
        SELECT status
        FROM assignments
        WHERE id = ?
        AND user_id = ?
    """, (assignment_id, user_id)).fetchone()

    if not assignment:
        conn.close()
        flash("Assignment not found.", "danger")
        return redirect(url_for("assignments"))

    new_status = (
        "Pending"
        if assignment["status"] == "Completed"
        else "Completed"
    )

    conn.execute("""
        UPDATE assignments
        SET status = ?
        WHERE id = ?
        AND user_id = ?
    """, (new_status, assignment_id, user_id))

    conn.commit()
    conn.close()

    return redirect(url_for("assignments"))


@app.route("/assignment/delete/<int:assignment_id>")
@login_required
def delete_assignment(assignment_id):

    user_id = session["user_id"]

    conn = get_db()

    conn.execute("""
        DELETE FROM assignments
        WHERE id = ?
        AND user_id = ?
    """, (assignment_id, user_id))

    conn.commit()
    conn.close()

    flash("Assignment deleted.", "success")
    return redirect(url_for("assignments"))


# =========================================================
# EXAMS
# =========================================================

@app.route("/exams", methods=["GET", "POST"])
@login_required
def exams():

    user_id = session["user_id"]

    if request.method == "POST":

        subject_id = request.form.get("subject_id", "").strip()
        exam_date = request.form.get("exam_date", "").strip()
        exam_time = request.form.get("exam_time", "").strip()
        room = request.form.get("room", "").strip()

        if not exam_date:
            flash("Exam date is required.", "danger")
            return redirect(url_for("exams"))

        try:
            subject_value = int(subject_id) if subject_id else None
        except ValueError:
            subject_value = None

        conn = get_db()

        conn.execute("""
            INSERT INTO exams
            (user_id, subject_id, exam_date, exam_time, room)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            subject_value,
            exam_date,
            exam_time,
            room
        ))

        conn.commit()
        conn.close()

        flash("Exam added successfully.", "success")
        return redirect(url_for("exams"))

    conn = get_db()

    exam_list = conn.execute("""
        SELECT exams.*,
               subjects.name AS subject_name,
               subjects.code AS subject_code
        FROM exams
        LEFT JOIN subjects
        ON exams.subject_id = subjects.id
        WHERE exams.user_id = ?
        ORDER BY exams.exam_date ASC, exams.exam_time ASC
    """, (user_id,)).fetchall()

    subject_list = conn.execute("""
        SELECT
            id,
            user_id,
            name AS subject_name,
            code AS subject_code,
            credit,
            created_at
        FROM subjects
        WHERE user_id = ?
        ORDER BY name ASC
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "exams.html",
        exams=exam_list,
        subjects=subject_list,
        current_date=date.today().isoformat()
    )

@app.route("/exam/delete/<int:exam_id>")
@login_required
def delete_exam(exam_id):

    user_id = session["user_id"]

    conn = get_db()

    conn.execute("""
        DELETE FROM exams
        WHERE id = ?
        AND user_id = ?
    """, (exam_id, user_id))

    conn.commit()
    conn.close()

    flash("Exam deleted.", "success")
    return redirect(url_for("exams"))


# =========================================================
# PROGRESS
# =========================================================

@app.route("/progress")
@login_required
def progress():

    user_id = session["user_id"]

    conn = get_db()

    # =========================
    # Overall Task Progress
    # =========================
    total_tasks = conn.execute("""
        SELECT COUNT(*) AS total
        FROM tasks
        WHERE user_id = ?
    """, (user_id,)).fetchone()["total"]

    completed_tasks = conn.execute("""
        SELECT COUNT(*) AS total
        FROM tasks
        WHERE user_id = ?
        AND status = 'Completed'
    """, (user_id,)).fetchone()["total"]

    pending_tasks = conn.execute("""
        SELECT COUNT(*) AS total
        FROM tasks
        WHERE user_id = ?
        AND status = 'Pending'
    """, (user_id,)).fetchone()["total"]

    # =========================
    # Subject-wise Progress
    # =========================
    subject_rows = conn.execute("""
        SELECT
            subjects.id,
            subjects.name AS subject_name,
            subjects.code AS subject_code,
            COUNT(tasks.id) AS total,
            SUM(
                CASE
                    WHEN tasks.status = 'Completed' THEN 1
                    ELSE 0
                END
            ) AS completed
        FROM subjects
        LEFT JOIN tasks
            ON subjects.id = tasks.subject_id
            AND tasks.user_id = ?
        WHERE subjects.user_id = ?
        GROUP BY subjects.id
        ORDER BY subjects.name ASC
    """, (user_id, user_id)).fetchall()

    conn.close()

    # =========================
    # Overall Percentage
    # =========================
    if total_tasks > 0:
        completion_percentage = round(
            (completed_tasks / total_tasks) * 100
        )
    else:
        completion_percentage = 0

    # =========================
    # Study Streak
    # =========================
    streak = calculate_study_streak(user_id)

    # =========================
    # Smart Recommendation
    # =========================
    smart_recommendation = get_smart_recommendation(user_id)

    # =========================
    # Prepare Subject Progress
    # =========================
    subject_progress = []

    for row in subject_rows:

        total = row["total"] or 0
        completed = row["completed"] or 0

        if total > 0:
            percentage = round((completed / total) * 100)
        else:
            percentage = 0

        subject_progress.append({
            "subject_name": row["subject_name"],
            "subject_code": row["subject_code"],
            "total": total,
            "completed": completed,
            "percentage": percentage
        })

    # =========================
    # Send Data to Template
    # =========================
    return render_template(
        "progress.html",
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        progress=completion_percentage,
        study_streak=streak,
        smart_recommendation=smart_recommendation,
        subject_progress=subject_progress
    )

# =========================================================
# STUDY GOAL
# =========================================================

@app.route("/study-goal", methods=["GET", "POST"])
@login_required
def study_goal():

    user_id = session["user_id"]

    if request.method == "POST":

        target = request.form.get("weekly_target", "10").strip()

        try:
            target = int(target)

            if target < 1:
                raise ValueError

        except ValueError:
            flash("Please enter a valid weekly target.", "danger")
            return redirect(url_for("study_goal"))

        conn = get_db()

        conn.execute("""
            INSERT INTO study_goals
            (user_id, weekly_target)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET weekly_target = excluded.weekly_target
        """, (user_id, target))

        conn.commit()
        conn.close()

        flash("Study goal updated.", "success")
        return redirect(url_for("study_goal"))

    conn = get_db()

    goal = conn.execute("""
        SELECT weekly_target
        FROM study_goals
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    conn.close()

    weekly_target = goal["weekly_target"] if goal else 10

    return render_template(
        "study_goal.html",
        weekly_target=weekly_target
    )


# =========================================================
# XML EXPORT
# =========================================================

@app.route("/export-xml")
@login_required
def export_xml():

    user_id = session["user_id"]

    conn = get_db()

    subjects = conn.execute("""
        SELECT *
        FROM subjects
        WHERE user_id = ?
        ORDER BY id
    """, (user_id,)).fetchall()

    tasks = conn.execute("""
        SELECT *
        FROM tasks
        WHERE user_id = ?
        ORDER BY id
    """, (user_id,)).fetchall()

    assignments = conn.execute("""
        SELECT *
        FROM assignments
        WHERE user_id = ?
        ORDER BY id
    """, (user_id,)).fetchall()

    exams = conn.execute("""
        SELECT *
        FROM exams
        WHERE user_id = ?
        ORDER BY id
    """, (user_id,)).fetchall()

    goal = conn.execute("""
        SELECT *
        FROM study_goals
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    conn.close()

    root = ET.Element("studytrack_data")

    subjects_element = ET.SubElement(root, "subjects")

    for subject in subjects:
        element = ET.SubElement(subjects_element, "subject")
        element.set("id", str(subject["id"]))

        ET.SubElement(element, "name").text = subject["name"]
        ET.SubElement(element, "code").text = subject["code"]
        ET.SubElement(element, "credit").text = str(subject["credit"])

    tasks_element = ET.SubElement(root, "tasks")

    for task in tasks:
        element = ET.SubElement(tasks_element, "task")
        element.set("id", str(task["id"]))

        ET.SubElement(element, "subject_id").text = (
            str(task["subject_id"])
            if task["subject_id"] is not None
            else ""
        )

        ET.SubElement(element, "title").text = task["title"]
        ET.SubElement(element, "description").text = (
            task["description"] or ""
        )
        ET.SubElement(element, "priority").text = task["priority"]
        ET.SubElement(element, "deadline").text = (
            task["deadline"] or ""
        )
        ET.SubElement(element, "status").text = task["status"]

    assignments_element = ET.SubElement(root, "assignments")

    for assignment in assignments:
        element = ET.SubElement(
            assignments_element,
            "assignment"
        )

        element.set("id", str(assignment["id"]))

        ET.SubElement(element, "subject_id").text = (
            str(assignment["subject_id"])
            if assignment["subject_id"] is not None
            else ""
        )

        ET.SubElement(element, "title").text = assignment["title"]
        ET.SubElement(element, "description").text = (
            assignment["description"] or ""
        )
        ET.SubElement(element, "deadline").text = (
            assignment["deadline"] or ""
        )
        ET.SubElement(element, "status").text = assignment["status"]

    exams_element = ET.SubElement(root, "exams")

    for exam in exams:
        element = ET.SubElement(exams_element, "exam")
        element.set("id", str(exam["id"]))

        ET.SubElement(element, "subject_id").text = (
            str(exam["subject_id"])
            if exam["subject_id"] is not None
            else ""
        )

        ET.SubElement(element, "exam_date").text = exam["exam_date"]
        ET.SubElement(element, "exam_time").text = (
            exam["exam_time"] or ""
        )
        ET.SubElement(element, "room").text = exam["room"] or ""

    goal_element = ET.SubElement(root, "study_goal")

    if goal:
        ET.SubElement(goal_element, "weekly_target").text = str(
            goal["weekly_target"]
        )
    else:
        ET.SubElement(goal_element, "weekly_target").text = "10"

    tree = ET.ElementTree(root)

    xml_bytes = BytesIO()

    tree.write(
        xml_bytes,
        encoding="utf-8",
        xml_declaration=True
    )

    xml_bytes.seek(0)

    return send_file(
        xml_bytes,
        mimetype="application/xml",
        as_attachment=True,
        download_name="studytrack_data.xml"
    )


# =========================================================
# XML IMPORT
# =========================================================

@app.route("/import-xml", methods=["POST"])
@login_required
def import_xml():

    file = request.files.get("xml_file")

    if not file or not file.filename:
        flash("Please select an XML file.", "danger")
        return redirect(url_for("dashboard"))

    conn = None

    try:
        tree = ET.parse(file)
        root = tree.getroot()

        user_id = session["user_id"]

        conn = get_db()

        subject_map = {}

        subjects_element = root.find("subjects")

        if subjects_element is not None:

            for subject in subjects_element.findall("subject"):

                old_id = subject.get("id")
                name = subject.findtext("name", "").strip()
                code = subject.findtext("code", "").strip()

                try:
                    credit = int(
                        subject.findtext("credit", "3")
                    )
                except ValueError:
                    credit = 3

                if not name or not code:
                    continue

                existing = conn.execute("""
                    SELECT id
                    FROM subjects
                    WHERE user_id = ?
                    AND name = ?
                    AND code = ?
                """, (
                    user_id,
                    name,
                    code
                )).fetchone()

                if existing:
                    new_id = existing["id"]

                else:
                    cursor = conn.execute("""
                        INSERT INTO subjects
                        (user_id, name, code, credit)
                        VALUES (?, ?, ?, ?)
                    """, (
                        user_id,
                        name,
                        code,
                        credit
                    ))

                    new_id = cursor.lastrowid

                if old_id:
                    subject_map[str(old_id)] = new_id

        tasks_element = root.find("tasks")

        if tasks_element is not None:

            for task in tasks_element.findall("task"):

                old_subject_id = task.findtext(
                    "subject_id",
                    ""
                ).strip()

                subject_id = subject_map.get(
                    old_subject_id
                )

                title = task.findtext(
                    "title",
                    ""
                ).strip()

                if not title:
                    continue

                description = task.findtext(
                    "description",
                    ""
                )

                priority = task.findtext(
                    "priority",
                    "Medium"
                )

                deadline = task.findtext(
                    "deadline",
                    ""
                ).strip()

                status = task.findtext(
                    "status",
                    "Pending"
                )

                if status not in ["Pending", "Completed"]:
                    status = "Pending"

                completed_at = (
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if status == "Completed"
                    else None
                )

                conn.execute("""
                    INSERT INTO tasks
                    (
                        user_id,
                        subject_id,
                        title,
                        description,
                        priority,
                        deadline,
                        status,
                        completed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    subject_id,
                    title,
                    description,
                    priority,
                    deadline if deadline else None,
                    status,
                    completed_at
                ))

        assignments_element = root.find("assignments")

        if assignments_element is not None:

            for assignment in assignments_element.findall(
                "assignment"
            ):

                old_subject_id = assignment.findtext(
                    "subject_id",
                    ""
                ).strip()

                subject_id = subject_map.get(
                    old_subject_id
                )

                title = assignment.findtext(
                    "title",
                    ""
                ).strip()

                if not title:
                    continue

                description = assignment.findtext(
                    "description",
                    ""
                )

                deadline = assignment.findtext(
                    "deadline",
                    ""
                ).strip()

                status = assignment.findtext(
                    "status",
                    "Pending"
                )

                if status not in ["Pending", "Completed"]:
                    status = "Pending"

                conn.execute("""
                    INSERT INTO assignments
                    (
                        user_id,
                        subject_id,
                        title,
                        description,
                        deadline,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    subject_id,
                    title,
                    description,
                    deadline if deadline else None,
                    status
                ))

        exams_element = root.find("exams")

        if exams_element is not None:

            for exam in exams_element.findall("exam"):

                old_subject_id = exam.findtext(
                    "subject_id",
                    ""
                ).strip()

                subject_id = subject_map.get(
                    old_subject_id
                )

                exam_date = exam.findtext(
                    "exam_date",
                    ""
                ).strip()

                if not exam_date:
                    continue

                exam_time = exam.findtext(
                    "exam_time",
                    ""
                )

                room = exam.findtext(
                    "room",
                    ""
                )

                conn.execute("""
                    INSERT INTO exams
                    (
                        user_id,
                        subject_id,
                        exam_date,
                        exam_time,
                        room
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_id,
                    subject_id,
                    exam_date,
                    exam_time,
                    room
                ))

        goal_element = root.find("study_goal")

        if goal_element is not None:

            try:
                weekly_target = int(
                    goal_element.findtext(
                        "weekly_target",
                        "10"
                    )
                )

                if weekly_target < 1:
                    weekly_target = 10

            except ValueError:
                weekly_target = 10

            conn.execute("""
                INSERT INTO study_goals
                (user_id, weekly_target)
                VALUES (?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET weekly_target = excluded.weekly_target
            """, (
                user_id,
                weekly_target
            ))

        conn.commit()
        conn.close()

        flash(
            "XML data imported successfully.",
            "success"
        )

    except ET.ParseError:
        if conn:
            conn.close()

        flash(
            "Invalid XML file.",
            "danger"
        )

    except Exception as error:
        if conn:
            conn.rollback()
            conn.close()

        flash(
            f"Import failed: {error}",
            "danger"
        )

    return redirect(url_for("dashboard"))


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin():

    users = get_all_users_xml()

    students = [
        user
        for user in users
        if user["role"] == "student"
    ]

    conn = get_db()

    total_subjects = conn.execute("""
        SELECT COUNT(*) AS total
        FROM subjects
    """).fetchone()["total"]

    total_tasks = conn.execute("""
        SELECT COUNT(*) AS total
        FROM tasks
    """).fetchone()["total"]

    total_assignments = conn.execute("""
        SELECT COUNT(*) AS total
        FROM assignments
    """).fetchone()["total"]

    total_exams = conn.execute("""
        SELECT COUNT(*) AS total
        FROM exams
    """).fetchone()["total"]

    conn.close()

    return render_template(
        "admin.html",
        students=students,
        total_students=len(students),
        total_subjects=total_subjects,
        total_tasks=total_tasks,
        total_assignments=total_assignments,
        total_exams=total_exams
    )


# =========================================================
# ADMIN STUDENTS
# =========================================================

@app.route("/admin/students")
@admin_required
def admin_students():

    students = [
        user
        for user in get_all_users_xml()
        if user["role"] == "student"
    ]

    return render_template(
        "admin_students.html",
        students=students
    )


# =========================================================
# ADMIN DELETE STUDENT
# =========================================================

@app.route("/admin/student/delete/<int:student_id>")
@admin_required
def admin_delete_student(student_id):

    conn = get_db()

    conn.execute("""
        DELETE FROM subjects
        WHERE user_id = ?
    """, (student_id,))

    conn.execute("""
        DELETE FROM tasks
        WHERE user_id = ?
    """, (student_id,))

    conn.execute("""
        DELETE FROM assignments
        WHERE user_id = ?
    """, (student_id,))

    conn.execute("""
        DELETE FROM exams
        WHERE user_id = ?
    """, (student_id,))

    conn.execute("""
        DELETE FROM study_goals
        WHERE user_id = ?
    """, (student_id,))

    conn.commit()
    conn.close()

    delete_user_xml(student_id)

    flash(
        "Student and all related data deleted.",
        "success"
    )

    return redirect(url_for("admin_students"))


# =========================================================
# 404 ERROR
# =========================================================

@app.errorhandler(404)
def page_not_found(error):
    return render_template(
        "404.html"
    ), 404


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    init_db()
    init_users_xml()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )