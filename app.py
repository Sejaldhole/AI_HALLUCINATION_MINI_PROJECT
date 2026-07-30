from flask import Flask, render_template, request, session, redirect, url_for
import joblib
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------- LOAD MODEL ----------------
model = joblib.load("model.pkl")
vectorizer = joblib.load("vectorizer.pkl")

# ---------------- DATABASE INIT ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        question TEXT,
        answer TEXT,
        prediction TEXT,
        confidence REAL
    )
    """)

    conn.commit()
    conn.close()

# Initialize database
init_db()

@app.route("/user/predict", methods=["GET", "POST"])
def predict():

    # If not logged in, go to login page
    if "user_id" not in session:
        return redirect("/login")

    prediction = None
    probability = None

    if request.method == "POST":
        question = request.form.get("question")
        answer = request.form.get("answer")

        if question and answer:
            combined_text = question + " " + answer

            transformed = vectorizer.transform([combined_text])
            pred = model.predict(transformed)[0]
            prob = model.predict_proba(transformed)[0]

            prediction = "Hallucinated" if pred == 1 else "Real"
            probability = round(max(prob) * 100, 2)

            # Save to database
            conn = sqlite3.connect("database.db")
            c = conn.cursor()

            c.execute("""
                INSERT INTO history (user_id, question, answer, prediction, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (session["user_id"], question, answer, prediction, probability))

            conn.commit()
            conn.close()

    return render_template("index.html", prediction=prediction, probability=probability)
# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        except:
            conn.close()
            return "Username already exists!"

        conn.close()
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            return redirect(url_for("dashboard"))
        else:
            return "Invalid credentials!"

    return render_template("login.html")


@app.route("/user/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Total predictions
    c.execute("SELECT COUNT(*) FROM history WHERE user_id=?", (session["user_id"],))
    total = c.fetchone()[0]

    # Real answers
    c.execute("SELECT COUNT(*) FROM history WHERE user_id=? AND prediction='Real'", (session["user_id"],))
    real = c.fetchone()[0]

    # Hallucinated answers
    c.execute("SELECT COUNT(*) FROM history WHERE user_id=? AND prediction='Hallucinated'", (session["user_id"],))
    hallucinated = c.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total=total,
        real=real,
        hallucinated=hallucinated
    )



@app.route("/user/profile")
def profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Get username
    c.execute("SELECT username FROM users WHERE id=?", (session["user_id"],))
    user = c.fetchone()

    # Count predictions
    c.execute("SELECT COUNT(*) FROM history WHERE user_id=?", (session["user_id"],))
    total_predictions = c.fetchone()[0]

    conn.close()

    return render_template("profile.html", username=user[0], total=total_predictions)


@app.route("/user/analytics")
def analytics():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Count real predictions
    c.execute(
        "SELECT COUNT(*) FROM history WHERE user_id=? AND prediction=?",
        (session["user_id"], "Real")
    )
    real = c.fetchone()[0]

    # Count hallucinated predictions
    c.execute(
        "SELECT COUNT(*) FROM history WHERE user_id=? AND prediction=?",
        (session["user_id"], "Hallucinated")
    )
    hallucinated = c.fetchone()[0]

    conn.close()

    return render_template(
        "analytics.html",
        real=real,
        hallucinated=hallucinated
    )

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))


@app.route("/history")
def history():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        SELECT question, answer, prediction, confidence
        FROM history
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],))

    rows = c.fetchall()

    conn.close()

    return render_template("history.html", rows=rows)



# ---------------- ADMIN LOGIN ----------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


@app.route("/admin/login", methods=["GET","POST"])
def admin_login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return "Invalid Admin Credentials"

    return render_template("admin_login.html")


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM history")
    total_predictions = c.fetchone()[0]

    conn.close()

    return render_template("admin_dashboard.html", users_count=total_users, predictions_count=total_predictions)


@app.route("/admin/users")
def admin_users():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    conn.close()

    return render_template("admin_users.html", users=users)

# ---------------- ADMIN DELETE USER ----------------
@app.route("/admin/delete_user/<int:user_id>")
def delete_user(user_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    c.execute("DELETE FROM history WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_users"))


# ---------------- ADMIN ADD USER ----------------
@app.route("/admin/add_user", methods=["POST"])
def add_user():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    username = request.form["username"]
    password = request.form["password"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
    except:
        pass
    conn.close()

    return redirect(url_for("admin_users"))


@app.route("/admin/predictions")
def admin_predictions():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM history")
    predictions = cursor.fetchall()

    conn.close()

    return render_template("admin_predictions.html", predictions=predictions)







# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)