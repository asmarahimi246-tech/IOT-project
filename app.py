from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
import random
import string
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ------------------------------
# DATABASE
# ------------------------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        item_id INTEGER,
        start TEXT,
        end TEXT,
        locker INTEGER,
        rfid TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ------------------------------
# USERS
# ------------------------------
users = {
    "user1@example.com": {"password": "1234"},
    "admin@example.com": {"password": "adminpass", "is_admin": True}
}

# ------------------------------
# ITEMS (MET ECHTE FOTO'S)
# ------------------------------
items = [
    {"id": 1, "name": "Drill", "description": "Powerful drill", "price_per_day": 10, "image": "images/drill.jpg"},
    {"id": 2, "name": "Ladder", "description": "Reach high places", "price_per_day": 5, "image": "images/ladder.jpg"},
    {"id": 3, "name": "Pressure Washer", "description": "Clean everything", "price_per_day": 15, "image": "images/washer.jpg"},
    {"id": 4, "name": "Lawn Mower", "description": "Cut grass easily", "price_per_day": 12, "image": "images/mower.jpg"}
]

lockers = [1, 2, 3, 4, 5]

# ------------------------------
# HELPERS
# ------------------------------
def is_available(item_id, start, end):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM reservations WHERE item_id = ?", (item_id,))
    rows = cur.fetchall()

    for r in rows:
        existing_start = datetime.fromisoformat(r["start"])
        existing_end = datetime.fromisoformat(r["end"])

        if not (end <= existing_start or start >= existing_end):
            return False

    return True

def generate_rfid():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# ------------------------------
# AUTH
# ------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = users.get(email)

        if user and user["password"] == password:
            session["user"] = email
            return redirect(url_for("index"))

        return render_template("login.html", error="Invalid login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ------------------------------
# PAGES
# ------------------------------
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", items=items)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM reservations WHERE user = ?", (session["user"],))
    reservations = cur.fetchall()

    return render_template("dashboard.html", reservations=reservations)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/item/<int:item_id>")
def item_detail(item_id):
    if "user" not in session:
        return redirect(url_for("login"))

    item = next((i for i in items if i["id"] == item_id), None)

    if not item:
        return "Item not found"

    return render_template("item_detail.html", item=item)

# ------------------------------
# API
# ------------------------------
@app.route("/check")
def check():
    start = datetime.fromisoformat(request.args.get("start"))
    end = datetime.fromisoformat(request.args.get("end"))

    result = []

    for item in items:
        result.append({
            "id": item["id"],
            "available": is_available(item["id"], start, end)
        })

    return jsonify(result)

@app.route("/reserve", methods=["POST"])
def reserve():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.json
    item_id = data["item_id"]
    start = data["start"]
    end = data["end"]

    if not is_available(item_id, datetime.fromisoformat(start), datetime.fromisoformat(end)):
        return jsonify({"error": "Item not available"}), 400

    locker = random.choice(lockers)
    rfid = generate_rfid()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reservations (user, item_id, start, end, locker, rfid)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session["user"], item_id, start, end, locker, rfid))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Reserved successfully",
        "locker": locker,
        "rfid": rfid
    })

# ------------------------------
# RUN
# ------------------------------
if __name__ == "__main__":
    app.run(debug=True)