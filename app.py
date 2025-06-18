from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"

def get_db():
    conn = sqlite3.connect("ratings.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/", methods=["GET", "POST"])
def login():
    db = get_db()
    majors = db.execute("SELECT * FROM Majors").fetchall()

    if request.method == "POST":
        student_id = request.form["student_id"]
        major_id = request.form["major_id"]

        db.execute("""
            INSERT INTO Students (student_id, major_id) VALUES (?, ?)
            ON CONFLICT(student_id) DO UPDATE SET major_id=excluded.major_id
        """, (student_id, major_id))
        db.commit()

        session["student_id"] = student_id
        session["major_id"] = major_id

        return redirect("/courses")

    return render_template("login.html", majors=majors)

@app.route("/courses")
def courses():
    if "student_id" not in session:
        return redirect("/")

    category_filter = request.args.get("category") #دریافت فیلتر

    db = get_db()
    query = """
         SELECT c.id, c.name, c.category, GROUP_CONCAT(p.name, ', ') as professors
        FROM Courses c
        JOIN CourseMajor cm ON c.id = cm.course_id
        LEFT JOIN CourseProfessor cp ON c.id = cp.course_id
        LEFT JOIN Professors p ON cp.professor_id = p.id
        WHERE cm.major_id = ?
    """ 
    params = [session["major_id"]]

    if category_filter:
        query += " AND c.category = ?"
        params.append(category_filter)

    query += " GROUP BY c.id"

    courses = db.execute(query, params).fetchall()

    return render_template("courses.html", courses=courses, selected_category=category_filter)


@app.route("/rate/<int:course_id>", methods=["GET", "POST"])
def rate(course_id):
    if "student_id" not in session:
        return redirect("/")

    db = get_db()
    term = "1403-بهار"  # ترم فعلی را اینجا تعریف کن (بعداً میشه خودکارش کرد)

    if request.method == "POST":
        professor_id = int(request.form["professor"])
        q1 = int(request.form["q1"])
        q2 = int(request.form["q2"])
        q3 = int(request.form["q3"])
        q4 = int(request.form["q4"])
        comment = request.form["comment"]

        # بررسی اینکه رأی قبلاً ثبت شده یا نه
        existing = db.execute("""
            SELECT * FROM Votes
            WHERE student_id = ? AND course_id = ? AND professor_id = ? AND term = ?
        """, (session["student_id"], course_id, professor_id, term)).fetchone()

        if existing:
            return render_template("error.html")

        db.execute("""
            INSERT INTO Votes (student_id, course_id, professor_id, q1, q2, q3, q4, comment, term)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session["student_id"], course_id, professor_id, q1, q2, q3, q4, comment, term))
        db.commit()
        return redirect("/courses")

    course = db.execute("SELECT id, name FROM Courses WHERE id = ?", (course_id,)).fetchone()
    professors = db.execute("""
        SELECT p.id, p.name FROM Professors p
        JOIN CourseProfessor cp ON cp.professor_id = p.id
        WHERE cp.course_id = ?
    """, (course_id,)).fetchall()

    return render_template("rate.html", course=course, professors=professors)


@app.route("/stats/<int:course_id>", methods=["GET", "POST"])
def stats(course_id):
    db = get_db()
    course = db.execute("SELECT id, name FROM Courses WHERE id = ?", (course_id,)).fetchone()

    professors = db.execute("""
        SELECT p.id, p.name FROM Professors p
        JOIN CourseProfessor cp ON cp.professor_id = p.id
        WHERE cp.course_id = ?
    """, (course_id,)).fetchall()

    selected_professor_name = None
    stats = None
    comments = []
    compare_results = None
    selected_professors = []

    if request.method == "POST":
        action = request.form.get("action")

        if action == "compare":
            # دریافت لیست اساتید انتخاب شده
            selected_professors = request.form.getlist("professors")
            if selected_professors:
                # تبدیل به int
                prof_ids = [int(p) for p in selected_professors]

                compare_results = []
                for pid in prof_ids:
                    prof = db.execute("SELECT id, name FROM Professors WHERE id = ?", (pid,)).fetchone()
                    if prof:
                        stat = db.execute("""
                            SELECT AVG(q1) as avg_q1, AVG(q2) as avg_q2, AVG(q3) as avg_q3, AVG(q4) as avg_q4
                            FROM Votes WHERE course_id = ? AND professor_id = ?
                        """, (course_id, pid)).fetchone()

                        compare_results.append({
                            "id": prof["id"],
                            "name": prof["name"],
                            "avg_q1": stat["avg_q1"],
                            "avg_q2": stat["avg_q2"],
                            "avg_q3": stat["avg_q3"],
                            "avg_q4": stat["avg_q4"]
                        })
            else:
                # اگر هیچ استادی انتخاب نشد، مقایسه انجام نشود
                compare_results = None

        elif action == "view_single":
            # مشاهده آمار یک استاد
            professor_id = request.form.get("professors")
            if not professor_id:
                professor_id = request.form.get("professor")  # fallback
            if professor_id:
                professor_id = int(professor_id)
                prof = db.execute("SELECT id, name FROM Professors WHERE id = ?", (professor_id,)).fetchone()
                if prof:
                    selected_professor_name = prof["name"]

                    stats = db.execute("""
                        SELECT AVG(q1) as avg_q1, AVG(q2) as avg_q2, AVG(q3) as avg_q3, AVG(q4) as avg_q4
                        FROM Votes WHERE course_id = ? AND professor_id = ?
                    """, (course_id, professor_id)).fetchone()

                    comments = db.execute("""
                        SELECT comment FROM Votes
                        WHERE course_id = ? AND professor_id = ? AND comment IS NOT NULL AND comment != ''
                    """, (course_id, professor_id)).fetchall()

    return render_template(
        "stats.html",
        course=course,
        professors=professors,
        stats=stats,
        comments=comments,
        selected_professor_name=selected_professor_name,
        compare_results=compare_results,
        selected_professors=[int(p) for p in selected_professors] if selected_professors else []
    )



if __name__ == "__main__":
    app.run(debug=True)
