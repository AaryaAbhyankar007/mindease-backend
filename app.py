from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# -----------------------------
# Load .env file (local only)
# -----------------------------
load_dotenv()

# -----------------------------
# Create Flask App
# -----------------------------
app = Flask(__name__)
CORS(app)

# -----------------------------
# Database Connection
# -----------------------------
def get_db_connection():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL is not set")

    return psycopg2.connect(
        database_url,
        sslmode="require"
    )

# -----------------------------
# Auto Create Tables
# -----------------------------
def create_tables():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            message TEXT,
            response TEXT,
            emotion VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        connection.commit()
        cursor.close()
        connection.close()

    except Exception as e:
        print("Table creation error:", e)

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

        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, hashed_password)
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "User registered successfully"})

    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "Email already exists"}), 400

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

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
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
# CHAT API (WITH CRITICAL DETECTION)
# -----------------------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()

        user_id = data.get("user_id")
        user_message = data.get("message")

        if not user_id or not user_message:
            return jsonify({"error": "user_id and message are required"}), 400

        # -----------------------------
        # Critical Case Detection
        # -----------------------------
        critical_keywords = [
            "suicide",
            "kill myself",
            "end my life",
            "self harm",
            "hurt myself"
        ]

        risk_level = "low"

        for word in critical_keywords:
            if word in user_message.lower():
                risk_level = "high"
                break

        # -----------------------------
        # Gemini API Call
        # -----------------------------
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

        # -----------------------------
        # Save Chat to Database
        # -----------------------------
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO chat_history (user_id, message, response, emotion)
            VALUES (%s, %s, %s, %s)
        """, (user_id, user_message, ai_reply, risk_level))

        connection.commit()
        cursor.close()
        connection.close()

        # -----------------------------
        # Return Response with Risk Level
        # -----------------------------
        return jsonify({
            "response": ai_reply,
            "risk_level": risk_level
        })

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

        cursor.execute("""
            SELECT * FROM chat_history
            WHERE user_id=%s
            ORDER BY created_at ASC
        """, (user_id,))

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
    create_tables()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
