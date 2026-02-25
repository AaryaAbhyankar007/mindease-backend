from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# -----------------------------
# DATABASE CONNECTION
# -----------------------------
def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise Exception("DATABASE_URL is not set")
    return psycopg2.connect(database_url, sslmode="require")


# -----------------------------
# CREATE TABLES (SAFE)
# -----------------------------
def create_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Users Table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        """)

        # Chat History Table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            message TEXT,
            response TEXT,
            risk_level VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Game Scores Table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS game_scores (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("✅ All tables verified/created successfully.")

    except Exception as e:
        print("❌ Database Setup Error:", e)


# -----------------------------
# HOME ROUTE
# -----------------------------
@app.route("/")
def home():
    return "MindEase Backend Running Successfully 🚀"


# -----------------------------
# REGISTER
# -----------------------------
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

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, hashed_password)
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "User registered successfully"})

    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "Email already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# LOGIN
# -----------------------------
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            return jsonify({"message": "Login successful", "user_id": user["id"]})

        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# CHAT WITH RISK DETECTION
# -----------------------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        message = data.get("message")
        location = data.get("location")

        if not user_id or not message:
            return jsonify({"error": "Required fields missing"}), 400

        # Risk detection
        keywords = ["suicide", "kill myself", "end my life", "want to die"]
        risk_level = "low"
        if any(word in message.lower() for word in keywords):
            risk_level = "high"

        # AI call
        api_key = os.getenv("GOOGLE_AI_KEY")
        if not api_key:
            return jsonify({"error": "AI key missing"}), 500

        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {"contents": [{"role": "user", "parts": [{"text": message}]}]}
        response = requests.post(url, json=payload, timeout=30)

        if response.status_code != 200:
            return jsonify({"error": "AI service failed"}), 500

        result = response.json()
        ai_reply = result["candidates"][0]["content"]["parts"][0]["text"]

        # Save chat
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chat_history (user_id, message, response, risk_level)
            VALUES (%s, %s, %s, %s)
        """, (user_id, message, ai_reply, risk_level))
        conn.commit()
        cur.close()
        conn.close()

        # Emergency Support Info
        support = None
        if risk_level == "high":
            city = location if location else "India"
            support = {
                "helpline": "📞 National Suicide Helpline (India): 9152987821",
                "maps_link": f"https://www.google.com/maps/search/psychologist+near+{city}"
            }

        return jsonify({
            "response": ai_reply,
            "risk_level": risk_level,
            "emergency": risk_level == "high",
            "support": support
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# GAME SCORE
# -----------------------------
@app.route("/game-score", methods=["POST"])
def game_score():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        score = data.get("score")

        if not user_id or score is None:
            return jsonify({"error": "Required fields missing"}), 400

        try:
            score = int(score)
        except ValueError:
            return jsonify({"error": "Score must be an integer"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO game_scores (user_id, score) VALUES (%s, %s)", (user_id, score))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Score saved successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# CHAT HISTORY
# -----------------------------
@app.route("/history/<int:user_id>", methods=["GET"])
def history(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT message, response, risk_level, created_at
            FROM chat_history
            WHERE user_id=%s
            ORDER BY created_at DESC
        """, (user_id,))
        chats = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(chats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    create_tables()  # Ensures all tables exist
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
