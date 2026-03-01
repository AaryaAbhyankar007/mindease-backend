from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import datetime
import os
import random
from dotenv import load_dotenv

# =====================================================
# LOAD ENV
# =====================================================
load_dotenv()
app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL not set")

# =====================================================
# DATABASE CONNECTION
# =====================================================
def get_db():
    return psycopg2.connect(DATABASE_URL)

# =====================================================
# GLOBAL ERROR HANDLER
# =====================================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

# =====================================================
# HEALTH CHECK
# =====================================================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "OK"})

# =====================================================
# HOME
# =====================================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "MindEase Backend Running 🚀"})

# =====================================================
# REGISTER
# =====================================================
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        name = data["name"]
        email = data["email"]
        password = data["password"]

        conn = get_db()
        cur = conn.cursor()

        # Check existing email
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            return jsonify({"error": "Email already exists"}), 400

        cur.execute("""
            INSERT INTO users (name, email, password, created_at)
            VALUES (%s, %s, %s, %s)
        """, (name, email, password, datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "User registered successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# LOGIN
# =====================================================
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data["email"]
        password = data["password"]

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("""
            SELECT id, name FROM users
            WHERE email=%s AND password=%s
        """, (email, password))

        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            return jsonify({
                "message": "Login successful",
                "user_id": user["id"],
                "name": user["name"]
            })

        return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# RISK DETECTION
# =====================================================
def detect_risk(text):
    text = text.lower()

    critical_words = ["i want to die", "kill myself", "suicide"]
    high_words = ["hopeless", "worthless"]
    medium_words = ["sad", "alone", "depressed"]

    if any(w in text for w in critical_words):
        return "critical"
    if any(w in text for w in high_words):
        return "high"
    if any(w in text for w in medium_words):
        return "medium"
    return "low"

# =====================================================
# AI SIMULATION
# =====================================================
def generate_ai_response(risk):
    responses = {
        "low": "I'm here to listen. Tell me more.",
        "medium": "I understand this feels heavy. You're not alone.",
        "high": "That sounds very difficult. Please consider reaching out to someone you trust.",
        "critical": "I'm really concerned. Please seek immediate help or contact a crisis helpline."
    }
    return responses.get(risk)

def generate_quote():
    quotes = [
        "You are stronger than you think.",
        "Progress, not perfection.",
        "Your feelings are valid.",
        "Even tough days are part of growth."
    ]
    return random.choice(quotes)

def generate_recommendations(risk):
    if risk == "low":
        return ["Take a short walk", "Listen to music"]
    elif risk == "medium":
        return ["Practice deep breathing", "Call a friend"]
    elif risk == "high":
        return ["Talk to a counselor", "Avoid being alone"]
    else:
        return ["Contact emergency services", "Reach out to a helpline"]

# =====================================================
# CHAT
# =====================================================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data["user_id"]
        message = data["message"]

        risk = detect_risk(message)
        ai_response = generate_ai_response(risk)
        quote = generate_quote()
        recommendations = generate_recommendations(risk)

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO chats (user_id, message, response, risk_level, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, message, ai_response, risk, datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "response": ai_response,
            "risk_level": risk,
            "personalized_quote": quote,
            "recommendations": recommendations
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# CHAT HISTORY
# =====================================================
@app.route("/chat-history/<int:user_id>", methods=["GET"])
def chat_history(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT message, response, risk_level, created_at
        FROM chats
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify({"history": rows})

# =====================================================
# ANALYTICS
# =====================================================
@app.route("/analytics/<int:user_id>", methods=["GET"])
def analytics(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT risk_level FROM chats WHERE user_id=%s", (user_id,))
    rows = cur.fetchall()

    total = len(rows)
    high_risk = sum(1 for r in rows if r["risk_level"] in ["high", "critical"])

    cur.close()
    conn.close()

    return jsonify({
        "total_chats": total,
        "high_risk_chats": high_risk,
        "mental_state": "Improving" if high_risk < total/2 else "Needs Attention"
    })

# =====================================================
# SAVE GAME SCORE
# =====================================================
@app.route("/game-score", methods=["POST"])
def save_score():
    try:
        data = request.get_json()
        user_id = data["user_id"]
        score = data["score"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO game_scores (user_id, score, created_at)
            VALUES (%s, %s, %s)
        """, (user_id, score, datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Score saved successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# GET GAME SCORES
# =====================================================
@app.route("/game-scores/<int:user_id>", methods=["GET"])
def get_scores(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT score, created_at
        FROM game_scores
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify({"scores": rows})

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
