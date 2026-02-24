from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load local .env only
load_dotenv()

app = Flask(__name__)
CORS(app)

# Database connection
def get_db_connection():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL is not set")

    return psycopg2.connect(database_url, sslmode="require")

# Create / Update Tables Properly
def create_tables():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Users
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        """)

        # Chat History (base structure)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            message TEXT,
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 🔥 IMPORTANT FIX
        cursor.execute("""
        ALTER TABLE chat_history
        ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20);
        """)

        # Game Scores
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_scores (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            score INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        connection.commit()
        cursor.close()
        connection.close()

        print("Database updated successfully.")

    except Exception as e:
        print("Table error:", e)

# Home route
@app.route("/")
def home():
    return "MindEase Backend Running Successfully 🚀"

# Register
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not name or not email or not password:
            return jsonify({"error": "All fields required"}), 400

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

# Login
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()

        email = data.get("email")
        password = data.get("password")

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

        return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Chat with Risk Detection
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()

        user_id = data.get("user_id")
        user_message = data.get("message")

        if not user_id or not user_message:
            return jsonify({"error": "Required fields missing"}), 400

        # Risk keywords
        critical_keywords = [
            "suicide", "kill myself", "end my life",
            "self harm", "hurt myself",
            "i want to die", "want to die",
            "can't go on", "cant go on",
            "wish i was dead", "give up on life"
        ]

        risk_level = "low"
        message_lower = user_message.lower()

        for word in critical_keywords:
            if word in message_lower:
                risk_level = "high"
                break

        # AI Call
        api_key = os.getenv("GOOGLE_AI_KEY")

        if not api_key:
            return jsonify({"error": "AI key missing"}), 500

        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"

        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": user_message}]
            }]
        }

        response = requests.post(url, json=payload, timeout=30)

        if response.status_code != 200:
            return jsonify({"error": "AI failed"}), 500

        result = response.json()
        ai_reply = result["candidates"][0]["content"]["parts"][0]["text"]

        # Save Chat
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO chat_history (user_id, message, response, risk_level)
            VALUES (%s, %s, %s, %s)
        """, (user_id, user_message, ai_reply, risk_level))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            "response": ai_reply,
            "risk_level": risk_level,
            "emergency": risk_level == "high"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Game Score
@app.route("/game-score", methods=["POST"])
def save_score():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        score = data.get("score")

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO game_scores (user_id, score)
            VALUES (%s, %s)
        """, (user_id, score))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Score saved"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# History
@app.route("/history/<int:user_id>")
def history(user_id):
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

# Run
if __name__ == "__main__":
    create_tables()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
