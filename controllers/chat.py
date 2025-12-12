import google.generativeai as genai
import os
from flask import request, jsonify, session
from app import app, db
from bson import ObjectId

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Fallback model order
GEMINI_MODELS = [
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemini-2.0-flash-exp",
    "models/gemini-flash-lite-latest",
]


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

        ctx = f"Student: {user.get('fullname','Student')}\nProgress:\n" + "\n".join(progress_list)
        return ctx
    except Exception as e:
        return f"Error fetching student context: {e}"


def generate_with_fallback(prompt):
    """
    Try each Gemini model one by one.
    If all fail, return fallback message.
    """
    for model_name in GEMINI_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and hasattr(response, "text"):
                return response.text

        except Exception as e:
            print(f"Gemini model failed ({model_name}):", e)

            # Continue to next model automatically
            continue

    # If ALL models fail:
    return "Sorry, my AI engine is temporarily over quota. Try again in a few minutes."


@app.route("/student/chat", methods=["POST"])
def student_chat():
    if session.get("role") != "student":
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    user_msg = data.get("message", "")

    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    context = get_student_context(session["user_id"])

    prompt = f"""
    You are Academia Assistant.
    Help the student with friendly, accurate, educational guidance.

    {context}

    User: {user_msg}
    """

    ai_response = generate_with_fallback(prompt)
    return jsonify({"response": ai_response})
