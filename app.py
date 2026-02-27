from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "lifeshare_secret"
DB_NAME = "lifeshare.db"


# ---------- DATABASE CONNECTION ----------
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- DATABASE INIT ----------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Stories table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)

    # Likes table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            UNIQUE(story_id, username)
        )
    """)

    # Comments table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            comment TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ---------- LOGIN ----------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user"] = username
            flash("Login successful! Welcome back 😊", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password ❌", "error")

    return render_template("login.html")


# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )
            conn.commit()
            conn.close()

            flash("Account created successfully 🎉 Please login.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Username already exists ⚠️", "error")

    return render_template("register.html")


# ---------- HOME ----------
@app.route("/home")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("home.html", user=session["user"])


# ---------- CATEGORY ----------
@app.route("/category/<category>")
def category(category):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, username, content FROM stories WHERE category=?", (category,))
    rows = cur.fetchall()

    stories = []
    for row in rows:
        story_id = row["id"]

        cur.execute("SELECT COUNT(*) FROM likes WHERE story_id=?", (story_id,))
        likes = cur.fetchone()[0]

        cur.execute(
            "SELECT id, username, comment FROM comments WHERE story_id=?",
            (story_id,)
        )
        comments = cur.fetchall()

        stories.append({
            "id": story_id,
            "username": row["username"],
            "content": row["content"],
            "likes": likes,
            "comments": comments
        })

    conn.close()

    return render_template(
        "category.html",
        category=category,
        stories=stories,
        user=session["user"]
    )


# ---------- ADD STORY ----------
@app.route("/category/<category>/add", methods=["POST"])
def add_story(category):
    if "user" not in session:
        return redirect(url_for("login"))

    content = request.form["story_content"]
    username = session["user"]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO stories (username, category, content) VALUES (?, ?, ?)",
        (username, category, content)
    )
    conn.commit()
    conn.close()

    flash("Story added successfully ✨", "success")
    return redirect(url_for("category", category=category))


# ---------- EDIT STORY ----------
@app.route("/edit/<int:story_id>", methods=["POST"])
def edit_story(story_id):
    if "user" not in session:
        return redirect(url_for("login"))

    content = request.form["story_content"]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE stories SET content=? WHERE id=? AND username=?",
        (content, story_id, session["user"])
    )
    conn.commit()
    conn.close()

    flash("Story updated ✏️", "success")
    return redirect(request.referrer)


# ---------- DELETE STORY ----------
@app.route("/delete/<int:story_id>", methods=["POST"])
def delete_story(story_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM stories WHERE id=? AND username=?",
        (story_id, session["user"])
    )
    conn.commit()
    conn.close()

    flash("Story deleted 🗑️", "success")
    return redirect(request.referrer)


# ---------- LIKE STORY ----------
@app.route("/like/<int:story_id>", methods=["POST"])
def like_story(story_id):
    if "user" not in session:
        return jsonify({"error": "login required"}), 401

    username = session["user"]
    conn = get_db_connection()
    cur = conn.cursor()

    # Check if already liked
    cur.execute(
        "SELECT 1 FROM likes WHERE story_id=? AND username=?",
        (story_id, username)
    )
    liked_before = cur.fetchone()

    if liked_before:
        # UNLIKE
        cur.execute(
            "DELETE FROM likes WHERE story_id=? AND username=?",
            (story_id, username)
        )
        liked = False
    else:
        # LIKE
        cur.execute(
            "INSERT INTO likes (story_id, username) VALUES (?, ?)",
            (story_id, username)
        )
        liked = True

    conn.commit()

    # Updated like count
    cur.execute("SELECT COUNT(*) FROM likes WHERE story_id=?", (story_id,))
    likes = cur.fetchone()[0]

    conn.close()

    return jsonify({
        "likes": likes,
        "liked": liked
    })


# ---------- ADD COMMENT ----------
@app.route("/add_comment/<int:story_id>", methods=["POST"])
def add_comment(story_id):
    if "user" not in session:
        return jsonify({"error": "login required"}), 401

    comment = request.form["comment"]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO comments (story_id, username, comment) VALUES (?, ?, ?)",
        (story_id, session["user"], comment)
    )
    conn.commit()

    cur.execute(
        "SELECT id, username, comment FROM comments WHERE story_id=? ORDER BY id DESC LIMIT 1",
        (story_id,)
    )
    new_comment = cur.fetchone()
    conn.close()

    return jsonify({
        "id": new_comment["id"],
        "username": new_comment["username"],
        "comment": new_comment["comment"]
    })


# ---------- DELETE COMMENT ----------
@app.route("/delete_comment/<int:comment_id>", methods=["POST"])
def delete_comment(comment_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM comments WHERE id=? AND username=?",
        (comment_id, session["user"])
    )
    conn.commit()
    conn.close()

    flash("Comment deleted 🗑️", "success")
    return redirect(request.referrer)


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully 👋", "success")
    return redirect(url_for("login"))


# ---------- DELETE ACCOUNT ----------
@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM comments WHERE username=?", (username,))
    cur.execute("DELETE FROM likes WHERE username=?", (username,))
    cur.execute("DELETE FROM stories WHERE username=?", (username,))
    cur.execute("DELETE FROM users WHERE username=?", (username,))

    conn.commit()
    conn.close()

    session.pop("user", None)
    flash("Your account has been permanently deleted ❌", "success")
    return redirect(url_for("login"))


# ---------- TRENDING STORIES ----------
@app.route("/trending")
def trending():
    conn = get_db_connection()
    stories = conn.execute("""
        SELECT stories.*, COUNT(likes.id) AS like_count
        FROM stories
        LEFT JOIN likes ON stories.id = likes.story_id
        GROUP BY stories.id
        ORDER BY like_count DESC
        LIMIT 5
    """).fetchall()
    conn.close()

    return render_template("trending.html", stories=stories)


# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)
