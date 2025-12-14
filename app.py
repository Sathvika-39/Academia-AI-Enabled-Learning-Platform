from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
import cloudinary
import os
from dotenv import load_dotenv
import bcrypt

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = (os.getenv("SECRET_KEY") or "dev-secret").strip()

# ---------------- MONGO (FIXED) ----------------
MONGO_URI = (os.getenv("MONGO_URI") or "").strip()   # ✅ STRIP NEWLINES/SPACES
DB_NAME = (os.getenv("DB_NAME") or "Ascend").strip()

if not MONGO_URI:
    raise RuntimeError("❌ MONGO_URI is missing in Render env vars")

# Ensure standard options exist (and no newline issues)
if "retryWrites=" not in MONGO_URI:
    joiner = "&" if "?" in MONGO_URI else "?"
    MONGO_URI = f"{MONGO_URI}{joiner}retryWrites=true"

if "w=" not in MONGO_URI:
    MONGO_URI = f"{MONGO_URI}&w=majority" if "?" in MONGO_URI else f"{MONGO_URI}?w=majority"

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=8000,
    connectTimeoutMS=8000,
    socketTimeoutMS=8000,
)

db = client[DB_NAME]

try:
    client.admin.command("ping")
    print("✅ MongoDB connected")
except Exception as e:
    print("❌ MongoDB connection failed:", repr(e))
    raise

courses_collection = db["courses"]
enrollments_collection = db["enrollments"]
users_collection = db["users"]

# ---------------- CLOUDINARY ----------------
cloudinary.config(
    cloud_name=(os.getenv("CLOUDINARY_CLOUD_NAME") or "").strip(),
    api_key=(os.getenv("CLOUDINARY_API_KEY") or "").strip(),
    api_secret=(os.getenv("CLOUDINARY_API_SECRET") or "").strip(),
)

# ---------------- ADMIN BOOTSTRAP ----------------
def create_admin_if_not_exists():
    admin_email = "admin@ascend.com"
    if users_collection.find_one({"email": admin_email}):
        print("ℹ️ Admin user already exists")
        return

    hashed_password = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
    users_collection.insert_one({
        "fullname": "Super Admin",
        "email": admin_email,
        "mobile": "9999999999",
        "password": hashed_password.decode("utf-8"),
        "role": "admin",
    })
    print("✅ Admin user created")

try:
    create_admin_if_not_exists()
except Exception as e:
    print("⚠️ Admin creation skipped:", repr(e))

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/courses")
def courses():
    return render_template("courses.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/signin-up", methods=["GET", "POST"])
def signin_signup():
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        if not email or not password:
            return render_template("signin-up.html",
                                   error="Email and password are required.",
                                   error_type=action, panel=action)

        if action == "signup":
            fullname = (request.form.get("fullname") or "").strip()
            mobile = (request.form.get("mobile") or "").strip()
            role = (request.form.get("role") or "").strip()

            if not fullname or not mobile or not role:
                return render_template("signin-up.html",
                                       error="All fields are required for signup.",
                                       error_type="signup", panel="signup")

            if users_collection.find_one({"email": email}):
                return render_template("signin-up.html",
                                       error="Email already exists. Please sign in.",
                                       error_type="signup", panel="signup")

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

        elif action == "signin":
            user = users_collection.find_one({"email": email})
            if not user:
                return render_template("signin-up.html",
                                       error="No account found with this email.",
                                       error_type="signin", panel="signin")

            if not bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
                return render_template("signin-up.html",
                                       error="Incorrect password.",
                                       error_type="signin", panel="signin")

            session.clear()
            session["user_id"] = str(user["_id"])
            session["role"] = user["role"]

            if user["role"] == "student":
                return redirect("/student/dashboard")
            if user["role"] == "instructor":
                return redirect("/instructor/dashboard")
            if user["role"] == "admin":
                return redirect("/admin/dash")

            return render_template("signin-up.html",
                                   error="Unknown user role. Contact support.",
                                   error_type="signin", panel="signin")

        return render_template("signin-up.html",
                               error="Invalid action.",
                               error_type="signin", panel="signin")

    return render_template("signin-up.html", panel="signin")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("signin_signup"))

@app.context_processor
def inject_theme():
    theme = request.cookies.get("theme", "light")
    return dict(theme=theme)

@app.route("/health")
def health():
    client.admin.command("ping")
    return {"status": "ok"}

# Import controllers
from controllers.admin import *
from controllers.instructor import *
from controllers.student import *
from controllers.chat import *

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int((os.getenv("PORT") or "5000").strip()), debug=True)
