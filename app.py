from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------
# Create Flask App
# -----------------------------
app = Flask(__name__)
CORS(app)

# -----------------------------
# Debug Route (Check Environment)
# -----------------------------
@app.route("/check-env")
def check_env():
    return {
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DB_PORT": os.getenv("DB_PORT")
    }

# -----------------------------
# Database Connection (POSTGRESQL)
# -----------------------------
def get_db_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"]
    )

# -----------------------------
# Home Route
# -----------------------------
@app.route("/")
def home():
    return "MindEase Backend Running Successfully 🚀"

# -----------------------------
# REGISTER API
# -----------------------------
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not name or not email or not password:
            return jsonify({"error": "All fields are required"}), 400

        hashed_password = generate_password_hash(password)

        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
        INSERT INTO users (name, email, password)
        VALUES (%s, %s, %s)
        """

        cursor.execute(query, (name, email, hashed_password))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "User registered successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# LOGIN API
# -----------------------------
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        query = "SELECT * FROM users WHERE email=%s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user and check_password_hash(user["password"], password):
            return jsonify({
                "message": "Login successful",
                "user_id": user["id"]
            })
        else:
            return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# CHAT API
# -----------------------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()

        user_id = data.get("user_id")
        user_message = data.get("message")

        if not user_id or not user_message:
            return jsonify({"error": "user_id and message are required"}), 400

        api_key = os.getenv("GOOGLE_AI_KEY")

        if not api_key:
            return jsonify({"error": "API key not found"}), 500

        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_message}]
                }
            ]
        }

        response = requests.post(url, json=payload, timeout=30)

        if response.status_code != 200:
            return jsonify({
                "error": "Gemini API failed",
                "details": response.text
            }), 500

        result = response.json()
        ai_reply = result["candidates"][0]["content"]["parts"][0]["text"]

        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
        INSERT INTO chat_history (user_id, message, response, emotion)
        VALUES (%s, %s, %s, %s)
        """

        cursor.execute(query, (user_id, user_message, ai_reply, "neutral"))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"response": ai_reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# GET CHAT HISTORY
# -----------------------------
@app.route("/history/<int:user_id>", methods=["GET"])
def get_history(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        query = """
        SELECT * FROM chat_history
        WHERE user_id=%s
        ORDER BY created_at ASC
        """

        cursor.execute(query, (user_id,))
        chats = cursor.fetchall()

        cursor.close()
        connection.close()

        return jsonify(chats)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# Run Server
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
