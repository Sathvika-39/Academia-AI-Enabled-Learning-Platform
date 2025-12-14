import google.generativeai as genai
import os
from flask import request, jsonify, session
from app import app, db
from bson import ObjectId

# --------------------------------------------------
# Configure Gemini
# --------------------------------------------------
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

MODEL_NAME = "models/gemini-2.5-flash"


def get_student_context(user_id):
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        enrollments = db.enrollments.find({"user_id": ObjectId(user_id)})

        progress_list = []
        for e in enrollments:
            course = db.courses.find_one({"_id": e["course_id"]})
            if course:
                progress_list.append(
                    f"- {course['title']}: {e.get('progress', 0)}% completed"
                )

        ctx = (
            f"Student: {user.get('fullname', 'Student')}\n"
            f"Progress:\n" + "\n".join(progress_list)
        )
        return ctx

    except Exception as e:
        return f"Error fetching student context: {e}"


def generate_ai_response(prompt):
    """
    Generate response using ONLY Gemini 2.5 Flash.
    """
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)

        if response and hasattr(response, "text"):
            return response.text

        return "⚠️ AI response was empty. Please try again."

    except Exception as e:
        print("Gemini error:", e)
        return "⚠️ AI service is temporarily unavailable. Please try again later."


@app.route("/student/chat", methods=["POST"])
def student_chat():
    if session.get("role") != "student":
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    user_msg = data.get("message", "").strip()

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
