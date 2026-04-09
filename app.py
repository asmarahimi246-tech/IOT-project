from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ------------------------------
# Users
# ------------------------------
users = {
    "user1@example.com": {"password": "1234", "name": "User 1"},
    "admin@example.com": {"password": "adminpass", "name": "Admin", "is_admin": True}
}

# ------------------------------
# Items for rent
# ------------------------------
items = [
    {"id": 1, "name": "Drill", "description": "Powerful drill for any project", "price_per_day": 10, "image": "https://via.placeholder.com/300?text=Drill", "rfid": "65:BD:66:75:CB"},
    {"id": 2, "name": "Ladder", "description": "Perfect for reaching high places", "price_per_day": 5, "image": "https://via.placeholder.com/300?text=Ladder"},
    {"id": 3, "name": "Pressure Washer", "description": "Make everything spotless", "price_per_day": 15, "image": "https://via.placeholder.com/300?text=Pressure+Washer"},
    {"id": 4, "name": "Lawn Mower", "description": "Keep your lawn neat and tidy", "price_per_day": 12, "image": "https://via.placeholder.com/300?text=Lawn+Mower"},
    {"id": 5, "name": "Party Tent", "description": "Ideal for outdoor parties", "price_per_day": 20, "image": "https://via.placeholder.com/300?text=Party+Tent"},
    {"id": 6, "name": "Projector", "description": "For movie nights or presentations", "price_per_day": 18, "image": "https://via.placeholder.com/300?text=Projector"},
    {"id": 7, "name": "Camera", "description": "Capture your favorite moments", "price_per_day": 25, "image": "https://via.placeholder.com/300?text=Camera"},
    {"id": 8, "name": "BBQ Grill", "description": "Perfect for summer cookouts", "price_per_day": 14, "image": "https://via.placeholder.com/300?text=BBQ+Grill"}
]

# ------------------------------
# Lockers
# ------------------------------
lockers = [1, 2, 3, 4, 5]

# ------------------------------
# Reservations
# ------------------------------
reservations = []

# ------------------------------
# Helper functions
# ------------------------------
def is_available(item_id, start, end):
    for r in reservations:
        if r["item_id"] == item_id and r.get("status") in ("reserved", "rented"):
            existing_start = datetime.fromisoformat(r["start"])
            existing_end = datetime.fromisoformat(r["end"])
            if not (end <= existing_start or start >= existing_end):
                return False
    return True

# ------------------------------
# Routes
# ------------------------------

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = users.get(email)
        if user and user["password"] == password:
            session["user"] = email
            if user.get("is_admin", False):
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid email or password")
    return render_template("login.html")

# Logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# Home / Items list
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", items=items)

# Item detail
@app.route("/item/<int:item_id>")
def item_detail(item_id):
    if "user" not in session:
        return redirect(url_for("login"))
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        return "Item not found"
    return render_template("item_detail.html", item=item)

# Check availability (AJAX)
@app.route("/check")
def check():
    item_id = int(request.args.get("item_id", 0))
    start = datetime.fromisoformat(request.args.get("start"))
    end = datetime.fromisoformat(request.args.get("end"))
    available = is_available(item_id, start, end) if item_id else True
    return jsonify({"available": available})

# Reserve item
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
    rfid = next((i["rfid"] for i in items if i["id"] == item_id), None)
    reservations.append({
        "user": session["user"],
        "item_id": item_id,
        "start": start,
        "end": end,
        "locker": locker,
        "rfid": rfid,
        "status": "reserved"
    })
    return jsonify({"message": "Reserved successfully", "locker": locker, "rfid": rfid})

# User dashboard
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    user_res = [r for r in reservations if r["user"] == session["user"]]
    return render_template("dashboard.html", reservations=user_res, items=items)

# Admin dashboard
@app.route("/admin")
def admin_dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    user = users.get(session["user"])
    if not user.get("is_admin", False):
        return "Access denied", 403
    return render_template("admin.html", reservations=reservations, items=items, users=users)

# ------------------------------
# Pico NFC API endpoints
# ------------------------------

@app.route("/api/pickup/<int:item_id>", methods=["POST"])
def api_pickup(item_id):
    """Mark item as picked up (no RFID needed) — switches reserved -> rented."""
    res = next((r for r in reservations if r["item_id"] == item_id and r.get("status") == "reserved"), None)
    if not res:
        return jsonify({"error": "No reserved item found"}), 404
    res["status"] = "rented"
    item = next((i for i in items if i["id"] == item_id), None)
    return jsonify({
        "message": "Item marked as picked up",
        "item": item["name"] if item else "Unknown",
        "user": res["user"],
        "locker": res["locker"]
    })

@app.route("/api/return", methods=["POST"])
def api_return():
    """Called by Pico when card is scanned — switches rented -> available."""
    data = request.json
    rfid = data.get("rfid")
    res = next((r for r in reservations if r["rfid"] == rfid and r.get("status") == "rented"), None)
    if not res:
        return jsonify({"error": "No rented item found for this card"}), 404
    res["status"] = "available"
    item = next((i for i in items if i["id"] == res["item_id"]), None)
    return jsonify({
        "message": "Item returned successfully",
        "item": item["name"] if item else "Unknown",
        "user": res["user"]
    })

@app.route("/api/status")
def api_status():
    """Returns current status of every item."""
    result = []
    for item in items:
        res = next(
            (r for r in reservations if r["item_id"] == item["id"] and r.get("status") in ("reserved", "rented")),
            None
        )
        result.append({
            "item": item["name"],
            "rfid": item.get("rfid"),
            "status": res["status"] if res else "available",
            "user": res["user"] if res else None,
            "locker": res["locker"] if res else None
        })
    return jsonify(result)

# ------------------------------
# Run the app
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)