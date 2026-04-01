from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
import random
import string

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
    {"id": 1, "name": "Drill", "description": "Powerful drill for any project", "price_per_day": 10, "image": "https://via.placeholder.com/300?text=Drill"},
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
        if r["item_id"] == item_id:
            existing_start = datetime.fromisoformat(r["start"])
            existing_end = datetime.fromisoformat(r["end"])
            if not (end <= existing_start or start >= existing_end):
                return False
    return True

def generate_rfid():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

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
    rfid = generate_rfid()
    reservations.append({
        "user": session["user"],
        "item_id": item_id,
        "start": start,
        "end": end,
        "locker": locker,
        "rfid": rfid
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
# Run the app
# ------------------------------
if __name__ == "__main__":
    app.run(debug=True)