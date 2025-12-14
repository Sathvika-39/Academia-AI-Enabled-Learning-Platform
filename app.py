from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
import cloudinary
import os
from dotenv import load_dotenv
import bcrypt

# --------------------------------------------------
# Load env (local only). On Render, set env vars in dashboard.
# --------------------------------------------------
load_dotenv()

# --------------------------------------------------
# Flask App
# --------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")  # ✅ do not hardcode

# --------------------------------------------------
# MongoDB Connection (Render safe + fail-fast)
# --------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "Ascend")

if not MONGO_URI:
    raise RuntimeError("❌ MONGO_URI is missing. Set it in Render → Environment Variables.")

# Ensure Atlas options exist (helps some setups)
if "retryWrites" not in MONGO_URI:
    joiner = "&" if "?" in MONGO_URI else "?"
    MONGO_URI = f"{MONGO_URI}{joiner}retryWrites=true&w=majority"

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=8000,
    connectTimeoutMS=8000,
    socketTimeoutMS=8000,
)

db = client[DB_NAME]

# Verify DB connection on boot (so we fail early with real error)
try:
    client.admin.command("ping")
    print("✅ MongoDB connected")
except Exception as e:
    print("❌ MongoDB connection failed:", e)
    raise

courses_collection = db["courses"]
enrollments_collection = db["enrollments"]
users_collection = db["users"]

# --------------------------------------------------
# Cloudinary Config
# --------------------------------------------------
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

# --------------------------------------------------
# Create admin user (runs on Render too)
# --------------------------------------------------
def create_admin_if_not_exists():
    admin_email = "admin@ascend.com"
    existing_admin = users_collection.find_one({"email": admin_email})

    if existing_admin:
        print("ℹ️ Admin user already exists")
        return

    hashed_password = bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt())

    users_collection.insert_one({
        "fullname": "Super Admin",
        "email": admin_email,
        "mobile": "9999999999",
        "password": hashed_password.decode("utf-8"),
        "role": "admin",
    })
    print("✅ Admin user created")

# Run at import time (Gunicorn/Render will execute this)
try:
    create_admin_if_not_exists()
except Exception as e:
    print("⚠️ Admin creation skipped:", e)

# --------------------------------------------------
# Routes
# --------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/courses")
def courses():
    return render_template("courses.html")

@app.route("/about")
def about():
    return render_template("about.html")

# Sign In / Sign Up
@app.route("/signin-up", methods=["GET", "POST"])
def signin_signup():
    if request.method == "POST":
        action = request.form.get("action")  # "signup" or "signin"
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            return render_template(
                "signin-up.html",
                error="Email and password are required.",
                error_type=action,
                panel=action
            )

        # ---------------- SIGNUP ----------------
        if action == "signup":
            fullname = request.form.get("fullname", "").strip()
            mobile = request.form.get("mobile", "").strip()
            role = request.form.get("role", "").strip()

            if not fullname or not mobile or not role:
                return render_template(
                    "signin-up.html",
                    error="All fields are required for signup.",
                    error_type="signup",
                    panel="signup"
                )

            if users_collection.find_one({"email": email}):
                return render_template(
                    "signin-up.html",
                    error="Email already exists. Please sign in.",
                    error_type="signup",
                    panel="signup"
                )

            hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
            users_collection.insert_one({
                "fullname": fullname,
                "email": email,
                "mobile": mobile,
                "password": hashed_pw.decode("utf-8"),
                "role": role
            })

            flash("Signup successful! Please sign in.", "success")
            return redirect(url_for("signin_signup"))

        # ---------------- SIGNIN ----------------
        elif action == "signin":
            user = users_collection.find_one({"email": email})
            if not user:
                return render_template(
                    "signin-up.html",
                    error="No account found with this email.",
                    error_type="signin",
                    panel="signin"
                )

            if not bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
                return render_template(
                    "signin-up.html",
                    error="Incorrect password.",
                    error_type="signin",
                    panel="signin"
                )

            session.clear()
            session["user_id"] = str(user["_id"])
            session["role"] = user["role"]

            if user["role"] == "student":
                return redirect("/student/dashboard")
            elif user["role"] == "instructor":
                return redirect("/instructor/dashboard")
            elif user["role"] == "admin":
                return redirect("/admin/dash")

            return render_template(
                "signin-up.html",
                error="Unknown user role. Contact support.",
                error_type="signin",
                panel="signin"
            )

        # Unknown action
        return render_template(
            "signin-up.html",
            error="Invalid action.",
            error_type="signin",
            panel="signin"
        )

    return render_template("signin-up.html", panel="signin")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("signin_signup"))

@app.context_processor
def inject_theme():
    theme = request.cookies.get("theme", "light")
    return dict(theme=theme)

# Health route (check DB from browser)
@app.route("/health")
def health():
    client.admin.command("ping")
    return {"status": "ok"}

# --------------------------------------------------
# Controllers (keep as you had)
# --------------------------------------------------
from controllers.admin import *
from controllers.instructor import *
from controllers.student import *
from controllers.chat import *

# --------------------------------------------------
# Local run only (Render uses gunicorn)
# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
