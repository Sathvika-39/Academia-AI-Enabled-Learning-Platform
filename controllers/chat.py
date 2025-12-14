import os
import threading
import google.generativeai as genai

from flask import request, jsonify, session
from bson import ObjectId

# IMPORTANT: keep this import as you already structured it
from app import app, db


# --------------------------------------------------
# Gemini Key Pool (Round-robin + failover)
# --------------------------------------------------
def _parse_keys() -> list[str]:
    raw = (os.getenv("GEMINI_API_KEYS") or "").strip()
    if not raw:
        # fallback to single key if you still use GEMINI_API_KEY
        one = (os.getenv("GEMINI_API_KEY") or "").strip()
        return [one] if one else []
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return keys


_GEMINI_KEYS = _parse_keys()
if not _GEMINI_KEYS:
    # Don't crash import if you want site to run without AI,
    # but clearly log it so you see it in Render logs.
    print("❌ GEMINI_API_KEYS / GEMINI_API_KEY not set. AI chat will fail.")

_MODEL_NAME = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()

_key_lock = threading.Lock()
_key_idx = 0


def _next_key() -> str | None:
    """Thread-safe round-robin key selection inside a worker."""
    global _key_idx
    if not _GEMINI_KEYS:
        return None
    with _key_lock:
        key = _GEMINI_KEYS[_key_idx % len(_GEMINI_KEYS)]
        _key_idx += 1
    return key


def _should_try_next_key(err: Exception) -> bool:
    """
    Decide whether to retry with another key.
    We retry for quota/rate-limit or temporary server/network style issues.
    """
    msg = (repr(err) + " " + str(err)).lower()

    # Quota / rate limit patterns
    if "429" in msg or "resource_exhausted" in msg or "quota" in msg or "rate" in msg:
        return True

    # Temporary server issues
    if "503" in msg or "500" in msg or "unavailable" in msg or "deadline" in msg or "timeout" in msg:
        return True

    # Auth errors shouldn't rotate usually (unless a single key is revoked)
    # If you want to rotate even on auth errors, return True here.
    return False


def generate_ai_response(prompt: str) -> str:
    """
    Generates response using Gemini with key rotation + retries.
    Tries up to N keys (N = number of keys) in the same request before failing.
    """
    if not _GEMINI_KEYS:
        return "⚠️ AI is not configured (missing GEMINI_API_KEYS)."

    attempts = min(len(_GEMINI_KEYS), 6)  # safety cap (but 3-4 keys will be fine)

    last_err = None
    tried = []

    for _ in range(attempts):
        key = _next_key()
        if not key:
            break
        tried.append(key[:6] + "…" if len(key) > 6 else "***")

        try:
            genai.configure(api_key=key)

            model = genai.GenerativeModel(_MODEL_NAME)

            # You can also pass generation_config, safety_settings if you want
            resp = model.generate_content(prompt)

            text = getattr(resp, "text", None)
            if text and str(text).strip():
                return str(text).strip()

            # Empty response - treat as temporary and rotate
            last_err = RuntimeError("Empty AI response")
            continue

        except Exception as e:
            last_err = e
            print("Gemini error:", repr(e), "| model:", _MODEL_NAME, "| tried:", tried)

            if _should_try_next_key(e):
                continue  # try next key
            else:
                # not a retryable error
                break

    # If all keys failed
    print("❌ All Gemini keys failed. Last error:", repr(last_err), "| tried:", tried)
    return "⚠️ AI service is temporarily unavailable. Please try again later."


# --------------------------------------------------
# Student context (unchanged, but slightly hardened)
# --------------------------------------------------
def get_student_context(user_id: str) -> str:
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)}) or {}
        enrollments = db.enrollments.find({"user_id": ObjectId(user_id)})

        progress_list = []
        for e in enrollments:
            course = db.courses.find_one({"_id": e.get("course_id")})
            if course:
                progress_list.append(
                    f"- {course.get('title', 'Course')}: {e.get('progress', 0)}% completed"
                )

        ctx = (
            f"Student: {user.get('fullname', 'Student')}\n"
            f"Progress:\n" + ("\n".join(progress_list) if progress_list else "- No enrollments yet")
        )
        return ctx

    except Exception as e:
        return f"Error fetching student context: {repr(e)}"


# --------------------------------------------------
# Route
# --------------------------------------------------
@app.route("/student/chat", methods=["POST"])
def student_chat():
    if session.get("role") != "student":
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()

    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    context = get_student_context(session["user_id"])

    prompt = f"""
You are Academia Assistant.
Help the student with friendly, accurate, educational guidance.

{context}

User: {user_msg}
"""

    ai_response = generate_ai_response(prompt)
    return jsonify({"response": ai_response})
