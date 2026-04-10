from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
import random
import string
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ------------------------------
# USERS
# ------------------------------
users = {
    "user@example.com": {"name": "Test user", "password": "Welkom1234"},
    "admin@example.com": {"name": "Admin", "password": "adminpass", "is_admin": True}
}

# ------------------------------
# ITEMS
# ------------------------------
items = [
    {"id": 1, "name": "Drill", "description": "Powerful drill", "price_per_day": 10, "image": "images/Drill.png"},
]

lockers = [1, 2, 3, 4, 5]

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
        rfid TEXT,
        status TEXT DEFAULT 'active'
    )
    """)

    try:
        cur.execute("ALTER TABLE reservations ADD COLUMN status TEXT DEFAULT 'active'")
    except sqlite3.OperationalError:
        pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items_nfc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        uid TEXT UNIQUE,
        status TEXT DEFAULT 'available',
        last_returned TEXT
    )
    """)

    try:
        cur.execute("ALTER TABLE items_nfc ADD COLUMN last_returned TEXT")
    except sqlite3.OperationalError:
        pass

    cur.execute("SELECT COUNT(*) AS count FROM items_nfc")
    count = cur.fetchone()["count"]

    if count == 0:
        cur.execute("""
            INSERT INTO items_nfc (item_id, uid, status, last_returned)
            VALUES (?, ?, ?, ?)
        """, (1, "65:BD:66:75:CB", "available", None))

    conn.commit()
    conn.close()


init_db()

# ------------------------------
# HELPERS
# ------------------------------
def generate_rfid():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def get_item_name(item_id):
    item = next((i for i in items if i["id"] == item_id), None)
    return item["name"] if item else "Unknown item"


def get_user_display_name(email):
    if not email:
        return None
    user = users.get(email)
    if user and user.get("name"):
        return user["name"]
    return email


def is_admin_logged_in():
    if "user" not in session:
        return False
    current_user = users.get(session["user"])
    return bool(current_user and current_user.get("is_admin"))


def is_available(item_id, start, end):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM reservations
        WHERE item_id = ? AND status = 'active'
    """, (item_id,))
    rows = cur.fetchall()

    for r in rows:
        existing_start = datetime.fromisoformat(r["start"])
        existing_end = datetime.fromisoformat(r["end"])

        if not (end <= existing_start or start >= existing_end):
            conn.close()
            return False

    conn.close()
    return True

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
            if user.get("is_admin"):
                return redirect(url_for("admin"))
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

    cur.execute("""
        SELECT * FROM reservations
        WHERE user = ? AND status != 'deleted'
        ORDER BY id DESC
    """, (session["user"],))
    rows = cur.fetchall()
    conn.close()

    reservations = []
    for r in rows:
        reservations.append({
            "id": r["id"],
            "item_id": r["item_id"],
            "item_name": get_item_name(r["item_id"]),
            "start": r["start"],
            "end": r["end"],
            "locker": r["locker"],
            "rfid": r["rfid"],
            "status": r["status"]
        })

    return render_template("dashboard.html", reservations=reservations)


@app.route("/admin")
def admin():
    if not is_admin_logged_in():
        return redirect(url_for("index") if "user" in session else url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM reservations
        WHERE status != 'deleted'
        ORDER BY id DESC
    """)
    reservations = cur.fetchall()
    conn.close()

    return render_template(
        "admin.html",
        reservations=reservations,
        users=users,
        items=items
    )


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
    if not is_admin_logged_in():
        return redirect(url_for("index") if "user" in session else url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items_nfc")
    rows = cur.fetchall()

    nfc_items_data = []
    for row in rows:
        reserved_by = None

        if row["status"] == "on loan":
            cur.execute("""
                SELECT user
                FROM reservations
                WHERE item_id = ? AND status = 'active'
                ORDER BY id DESC
                LIMIT 1
            """, (row["item_id"],))
            reservation = cur.fetchone()
            if reservation:
                reserved_by = get_user_display_name(reservation["user"])

        nfc_items_data.append({
            "id": row["id"],
            "item_id": row["item_id"],
            "item_name": get_item_name(row["item_id"]),
            "uid": row["uid"],
            "status": row["status"],
            "reserved_by": reserved_by,
            "last_returned": row["last_returned"]
        })

    conn.close()
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
        item_id = int(item_id)
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        return jsonify({"error": "Invalid item_id or datetime format"}), 400

    if end_dt <= start_dt:
        return jsonify({"error": "End date must be after start date"}), 400

    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    if not is_available(item_id, start_dt, end_dt):
        return jsonify({"error": "Item not available"}), 400

    locker = random.choice(lockers)
    rfid = generate_rfid()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reservations (user, item_id, start, end, locker, rfid, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session["user"],
        item_id,
        start,
        end,
        locker,
        rfid,
        "active"
    ))

    reservation_id = cur.lastrowid

    cur.execute("""
        UPDATE items_nfc
        SET status = ?, last_returned = ?
        WHERE item_id = ?
    """, ("on loan", "currently on loan", item_id))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Reserved successfully",
        "reservation_id": reservation_id,
        "item_id": item_id,
        "item_name": item["name"],
        "locker": locker,
        "rfid": rfid,
        "status": "active",
        "nfc_status": "on loan"
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

    if current_status != "on loan":
        conn.close()
        return jsonify({
            "error": "Item is not currently on loan, NFC return denied",
            "uid": uid,
            "item_id": item["item_id"],
            "item_name": get_item_name(item["item_id"]),
            "current_status": current_status
        }), 400

    new_status = "available"
    new_last_returned = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reservation_status = None

    cur.execute("""
        SELECT * FROM reservations
        WHERE item_id = ? AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
    """, (item["item_id"],))
    reservation = cur.fetchone()

    if reservation:
        now = datetime.now()
        end_dt = datetime.fromisoformat(reservation["end"])

        if now < end_dt:
            reservation_status = "returned early"
        else:
            reservation_status = "returned on time"

        cur.execute("""
            UPDATE reservations
            SET status = ?
            WHERE id = ?
        """, (reservation_status, reservation["id"]))

    cur.execute("""
        UPDATE items_nfc
        SET status = ?, last_returned = ?
        WHERE uid = ?
    """, (new_status, new_last_returned, uid))

    conn.commit()

    item_name = get_item_name(item["item_id"])

    conn.close()

    return jsonify({
        "message": "Item returned successfully",
        "uid": uid,
        "item_id": item["item_id"],
        "item_name": item_name,
        "old_status": current_status,
        "new_status": new_status,
        "last_returned": new_last_returned,
        "reservation_status": reservation_status
    })


@app.route("/delete_reservation/<int:reservation_id>", methods=["POST"])
def delete_reservation(reservation_id):
    if not is_admin_logged_in():
        return redirect(url_for("index") if "user" in session else url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
    reservation = cur.fetchone()

    if not reservation:
        conn.close()
        return redirect(url_for("admin"))

    if reservation["status"] in ["returned early", "returned on time"]:
        cur.execute("""
            UPDATE reservations
            SET status = 'deleted'
            WHERE id = ?
        """, (reservation_id,))
        conn.commit()

    conn.close()
    return redirect(url_for("admin"))

# ------------------------------
# RUN
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)