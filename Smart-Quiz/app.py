"""
Smart Quiz - Online Quiz Application
Flask backend: authentication, quiz engine, results, admin panel.
Uses SQLite for zero-config deployment (swap to MySQL by changing the DB path/URI).
"""

import os
import sqlite3
import json
from functools import wraps
from datetime import datetime

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, g)
from werkzeug.security import generate_password_hash, check_password_hash

from seed_data import CATEGORIES, QUESTIONS, ADMIN_USERNAME, ADMIN_PASSWORD

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "quiz.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart-quiz-secret-key-change-me")
app.config["DATABASE"] = DATABASE

# Seconds allowed per question (used for timer display)
TIME_PER_QUESTION = 30


# ---------------------------------------------------------------- database
def get_db():
    """Return a per-request SQLite connection."""
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables and seed data if the database is empty."""
    db = sqlite3.connect(DATABASE)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL CHECK(correct_option IN ('a','b','c','d')),
            created_at TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            incorrect INTEGER NOT NULL,
            score INTEGER NOT NULL,
            percentage REAL NOT NULL,
            answers TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()

    # Seed admin if none exists
    cur = db.execute("SELECT COUNT(*) AS c FROM admins")
    if cur.fetchone()[0] == 0:
        db.execute(
            "INSERT INTO admins (username, password_hash, created_at) VALUES (?,?,?)",
            (ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD), datetime.utcnow().isoformat()),
        )

    # Seed categories + questions if empty
    cur = db.execute("SELECT COUNT(*) AS c FROM categories")
    if cur.fetchone()[0] == 0:
        now = datetime.utcnow().isoformat()
        cat_ids = {}
        for name, desc in CATEGORIES:
            cur = db.execute(
                "INSERT INTO categories (name, description, created_at) VALUES (?,?,?)",
                (name, desc, now),
            )
            cat_ids[name] = cur.lastrowid
        for cat_name, qlist in QUESTIONS.items():
            cid = cat_ids[cat_name]
            for q, opts, correct in qlist:
                db.execute(
                    """INSERT INTO questions
                       (category_id, question_text, option_a, option_b, option_c, option_d,
                        correct_option, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (cid, q, opts[0], opts[1], opts[2], opts[3], correct, now),
                )
        db.commit()
    db.close()


# ---------------------------------------------------------------- auth helpers
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            flash("Admin login required.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


def current_user():
    if "user_id" not in session:
        return None
    return get_db().execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()


# ---------------------------------------------------------------- public pages
@app.route("/")
def index():
    db = get_db()
    total_questions = db.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]
    total_users = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    total_attempts = db.execute("SELECT COUNT(*) AS c FROM results").fetchone()["c"]
    categories = db.execute(
        """SELECT c.*, COUNT(q.id) AS question_count
           FROM categories c LEFT JOIN questions q ON q.category_id = c.id
           GROUP BY c.id ORDER BY c.name"""
    ).fetchall()
    return render_template(
        "index.html",
        total_questions=total_questions,
        total_users=total_users,
        total_attempts=total_attempts,
        categories=categories,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username, email, password_hash, created_at) VALUES (?,?,?,?)",
                    (username, email, generate_password_hash(password), datetime.utcnow().isoformat()),
                )
                db.commit()
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username or email already exists.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ? OR email = ?", (username, username)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username/email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------- user pages
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    categories = db.execute(
        """SELECT c.*, COUNT(q.id) AS question_count
           FROM categories c LEFT JOIN questions q ON q.category_id = c.id
           GROUP BY c.id ORDER BY c.name"""
    ).fetchall()
    stats = db.execute(
        """SELECT COUNT(*) AS attempts,
                  COALESCE(AVG(percentage),0) AS avg_score,
                  COALESCE(MAX(percentage),0) AS best_score
           FROM results WHERE user_id = ?""",
        (session["user_id"],),
    ).fetchone()
    recent = db.execute(
        """SELECT r.*, c.name AS category_name
           FROM results r JOIN categories c ON c.id = r.category_id
           WHERE r.user_id = ? ORDER BY r.created_at DESC LIMIT 5""",
        (session["user_id"],),
    ).fetchall()
    return render_template(
        "dashboard.html", categories=categories, stats=stats, recent=recent
    )


@app.route("/quiz/<int:category_id>")
@login_required
def quiz(category_id):
    db = get_db()
    category = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    if not category:
        flash("Category not found.", "danger")
        return redirect(url_for("dashboard"))
    count = db.execute(
        "SELECT COUNT(*) AS c FROM questions WHERE category_id = ?", (category_id,)
    ).fetchone()["c"]
    if count == 0:
        flash("No questions available in this category yet.", "warning")
        return redirect(url_for("dashboard"))
    return render_template(
        "quiz.html",
        category=category,
        question_count=count,
        time_per_question=TIME_PER_QUESTION,
    )


@app.route("/api/quiz/<int:category_id>")
@login_required
def api_quiz_questions(category_id):
    """Return quiz questions WITHOUT correct answers (answers revealed after submit)."""
    rows = get_db().execute(
        """SELECT id, question_text, option_a, option_b, option_c, option_d
           FROM questions WHERE category_id = ? ORDER BY RANDOM()""",
        (category_id,),
    ).fetchall()
    questions = [
        {
            "id": r["id"],
            "question": r["question_text"],
            "options": {
                "a": r["option_a"],
                "b": r["option_b"],
                "c": r["option_c"],
                "d": r["option_d"],
            },
        }
        for r in rows
    ]
    return jsonify({"questions": questions, "time_per_question": TIME_PER_QUESTION})


@app.route("/api/submit", methods=["POST"])
@login_required
def api_submit():
    """Score the submitted answers, store the result, return the result id."""
    data = request.get_json(force=True)
    category_id = data.get("category_id")
    answers = data.get("answers", {})  # {question_id: 'a'|'b'|'c'|'d'|null}

    db = get_db()
    questions = db.execute(
        "SELECT id, correct_option FROM questions WHERE category_id = ?",
        (category_id,),
    ).fetchall()
    qmap = {q["id"]: q["correct_option"] for q in questions}

    correct = 0
    for qid, chosen in answers.items():
        if chosen and qmap.get(int(qid)) == chosen:
            correct += 1

    total = len(qmap)
    incorrect = total - correct
    score = round((correct / total) * 100, 2) if total else 0.0

    cur = db.execute(
        """INSERT INTO results
           (user_id, category_id, total_questions, correct, incorrect, score,
            percentage, answers, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            session["user_id"], category_id, total, correct, incorrect, score,
            score, json.dumps(answers), datetime.utcnow().isoformat(),
        ),
    )
    db.commit()
    return jsonify({"result_id": cur.lastrowid, "score": score})


@app.route("/result/<int:result_id>")
@login_required
def result(result_id):
    db = get_db()
    res = db.execute(
        """SELECT r.*, c.name AS category_name
           FROM results r JOIN categories c ON c.id = r.category_id
           WHERE r.id = ? AND r.user_id = ?""",
        (result_id, session["user_id"]),
    ).fetchone()
    if not res:
        flash("Result not found.", "danger")
        return redirect(url_for("dashboard"))

    answers = json.loads(res["answers"])
    questions = db.execute(
        """SELECT id, question_text, option_a, option_b, option_c, option_d, correct_option
           FROM questions WHERE category_id = ? ORDER BY id""",
        (res["category_id"],),
    ).fetchall()
    review = []
    for q in questions:
        chosen = answers.get(str(q["id"]))
        review.append({
            "question": q["question_text"],
            "options": {"a": q["option_a"], "b": q["option_b"],
                        "c": q["option_c"], "d": q["option_d"]},
            "correct": q["correct_option"],
            "chosen": chosen,
            "is_correct": chosen == q["correct_option"],
        })
    return render_template("result.html", res=res, review=review)


@app.route("/history")
@login_required
def history():
    rows = get_db().execute(
        """SELECT r.*, c.name AS category_name
           FROM results r JOIN categories c ON c.id = r.category_id
           WHERE r.user_id = ? ORDER BY r.created_at DESC""",
        (session["user_id"],),
    ).fetchall()
    return render_template("history.html", results=rows)


# ---------------------------------------------------------------- admin auth
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = get_db().execute(
            "SELECT * FROM admins WHERE username = ?", (username,)
        ).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "danger")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------- admin panel
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        "users": db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"],
        "categories": db.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"],
        "questions": db.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"],
        "attempts": db.execute("SELECT COUNT(*) AS c FROM results").fetchone()["c"],
        "avg_score": db.execute("SELECT COALESCE(AVG(percentage),0) AS a FROM results").fetchone()["a"],
    }
    recent_results = db.execute(
        """SELECT r.*, u.username, c.name AS category_name
           FROM results r JOIN users u ON u.id = r.user_id
           JOIN categories c ON c.id = r.category_id
           ORDER BY r.created_at DESC LIMIT 10"""
    ).fetchall()
    top_categories = db.execute(
        """SELECT c.name, COUNT(r.id) AS attempts, COALESCE(AVG(r.percentage),0) AS avg
           FROM categories c LEFT JOIN results r ON r.category_id = c.id
           GROUP BY c.id ORDER BY attempts DESC LIMIT 5"""
    ).fetchall()
    return render_template(
        "admin_dashboard.html", stats=stats,
        recent_results=recent_results, top_categories=top_categories,
    )


@app.route("/admin/questions")
@admin_required
def admin_questions():
    db = get_db()
    category_id = request.args.get("category_id", type=int)
    query = """SELECT q.*, c.name AS category_name FROM questions q
               JOIN categories c ON c.id = q.category_id"""
    params = []
    if category_id:
        query += " WHERE q.category_id = ?"
        params.append(category_id)
    query += " ORDER BY c.name, q.id"
    questions = db.execute(query, params).fetchall()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return render_template("admin_questions.html", questions=questions,
                           categories=categories, selected=category_id)


@app.route("/admin/questions/add", methods=["GET", "POST"])
@admin_required
def admin_question_add():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    if request.method == "POST":
        try:
            db.execute(
                """INSERT INTO questions
                   (category_id, question_text, option_a, option_b, option_c, option_d,
                    correct_option, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    request.form["category_id"],
                    request.form["question_text"].strip(),
                    request.form["option_a"].strip(),
                    request.form["option_b"].strip(),
                    request.form["option_c"].strip(),
                    request.form["option_d"].strip(),
                    request.form["correct_option"],
                    datetime.utcnow().isoformat(),
                ),
            )
            db.commit()
            flash("Question added successfully.", "success")
            return redirect(url_for("admin_questions"))
        except Exception as e:
            flash(f"Error adding question: {e}", "danger")
    return render_template("admin_question_form.html", categories=categories, question=None)


@app.route("/admin/questions/edit/<int:qid>", methods=["GET", "POST"])
@admin_required
def admin_question_edit(qid):
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    question = db.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    if not question:
        flash("Question not found.", "danger")
        return redirect(url_for("admin_questions"))
    if request.method == "POST":
        db.execute(
            """UPDATE questions SET category_id=?, question_text=?, option_a=?,
               option_b=?, option_c=?, option_d=?, correct_option=? WHERE id=?""",
            (
                request.form["category_id"],
                request.form["question_text"].strip(),
                request.form["option_a"].strip(),
                request.form["option_b"].strip(),
                request.form["option_c"].strip(),
                request.form["option_d"].strip(),
                request.form["correct_option"],
                qid,
            ),
        )
        db.commit()
        flash("Question updated successfully.", "success")
        return redirect(url_for("admin_questions"))
    return render_template("admin_question_form.html", categories=categories, question=question)


@app.route("/admin/questions/delete/<int:qid>", methods=["POST"])
@admin_required
def admin_question_delete(qid):
    db = get_db()
    db.execute("DELETE FROM questions WHERE id = ?", (qid,))
    db.commit()
    flash("Question deleted.", "success")
    return redirect(url_for("admin_questions"))


@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        if name:
            try:
                db.execute(
                    "INSERT INTO categories (name, description, created_at) VALUES (?,?,?)",
                    (name, desc, datetime.utcnow().isoformat()),
                )
                db.commit()
                flash("Category created.", "success")
            except sqlite3.IntegrityError:
                flash("Category name already exists.", "danger")
        return redirect(url_for("admin_categories"))
    categories = db.execute(
        """SELECT c.*, COUNT(q.id) AS question_count
           FROM categories c LEFT JOIN questions q ON q.category_id = c.id
           GROUP BY c.id ORDER BY c.name"""
    ).fetchall()
    return render_template("admin_categories.html", categories=categories)


@app.route("/admin/categories/delete/<int:cid>", methods=["POST"])
@admin_required
def admin_category_delete(cid):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (cid,))
    db.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("admin_categories"))


@app.route("/admin/users")
@admin_required
def admin_users():
    db = get_db()
    users = db.execute(
        """SELECT u.*,
                  (SELECT COUNT(*) FROM results r WHERE r.user_id = u.id) AS attempts,
                  (SELECT COALESCE(AVG(r.percentage),0) FROM results r WHERE r.user_id = u.id) AS avg_score
           FROM users u ORDER BY u.created_at DESC"""
    ).fetchall()
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/delete/<int:uid>", methods=["POST"])
@admin_required
def admin_user_delete(uid):
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (uid,))
    db.commit()
    flash("User deleted.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/results")
@admin_required
def admin_results():
    db = get_db()
    rows = db.execute(
        """SELECT r.*, u.username, c.name AS category_name
           FROM results r JOIN users u ON u.id = r.user_id
           JOIN categories c ON c.id = r.category_id
           ORDER BY r.created_at DESC LIMIT 200"""
    ).fetchall()
    return render_template("admin_results.html", results=rows)


@app.context_processor
def inject_globals():
    return {"now_year": datetime.utcnow().year}


# ---------------------------------------------------------------- entry point
init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
