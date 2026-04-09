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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items_nfc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        uid TEXT UNIQUE,
        status TEXT DEFAULT 'available'
    )
    """)

    # Voeg testdata toe als tabel nog leeg is
    cur.execute("SELECT COUNT(*) AS count FROM items_nfc")
    count = cur.fetchone()["count"]

    if count == 0:
        cur.execute(
            "INSERT INTO items_nfc (item_id, uid, status) VALUES (?, ?, ?)",
            (1, "04A3BC129F", "available")
        )
        cur.execute(
            "INSERT INTO items_nfc (item_id, uid, status) VALUES (?, ?, ?)",
            (2, "123456ABCD", "available")
        )
        cur.execute(
            "INSERT INTO items_nfc (item_id, uid, status) VALUES (?, ?, ?)",
            (3, "A1B2C3D4E5", "available")
        )
        cur.execute(
            "INSERT INTO items_nfc (item_id, uid, status) VALUES (?, ?, ?)",
            (4, "FFEEDD1122", "available")
        )

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
# ITEMS
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
            conn.close()
            return False

    conn.close()
    return True


def generate_rfid():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def get_item_name(item_id):
    item = next((i for i in items if i["id"] == item_id), None)
    return item["name"] if item else "Unknown item"

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
    conn.close()

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
        return "Item not found", 404

    return render_template("item_detail.html", item=item)


@app.route("/nfc_items")
def nfc_items():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items_nfc")
    rows = cur.fetchall()
    conn.close()

    nfc_items_data = []
    for row in rows:
        nfc_items_data.append({
            "id": row["id"],
            "item_id": row["item_id"],
            "item_name": get_item_name(row["item_id"]),
            "uid": row["uid"],
            "status": row["status"]
        })

    return render_template("nfc_items.html", nfc_items=nfc_items_data)

# ------------------------------
# API
# ------------------------------
@app.route("/check")
def check():
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    if not start_str or not end_str:
        return jsonify({"error": "Start and end are required"}), 400

    try:
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)
    except ValueError:
        return jsonify({"error": "Invalid datetime format"}), 400

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

    data = request.get_json()

    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    item_id = data.get("item_id")
    start = data.get("start")
    end = data.get("end")

    if not item_id or not start or not end:
        return jsonify({"error": "item_id, start and end are required"}), 400

    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        return jsonify({"error": "Invalid datetime format"}), 400

    if not is_available(item_id, start_dt, end_dt):
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


@app.route("/scan_nfc", methods=["POST"])
def scan_nfc():
    data = request.get_json()

    if not data or "uid" not in data:
        return jsonify({"error": "UID missing"}), 400

    uid = str(data["uid"]).strip()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM items_nfc WHERE uid = ?", (uid,))
    item = cur.fetchone()

    if not item:
        conn.close()
        return jsonify({"error": "Unknown UID"}), 404

    current_status = item["status"]

    if current_status in ["available", "returned"]:
        new_status = "on loan"
    else:
        new_status = "returned"

    cur.execute(
        "UPDATE items_nfc SET status = ? WHERE uid = ?",
        (new_status, uid)
    )

    conn.commit()

    item_name = get_item_name(item["item_id"])

    conn.close()

    return jsonify({
        "message": "Status updated",
        "uid": uid,
        "item_id": item["item_id"],
        "item_name": item_name,
        "old_status": current_status,
        "new_status": new_status
    })

# ------------------------------
# RUN
# ------------------------------
if __name__ == "__main__":
    app.run(debug=True)