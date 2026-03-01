from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import datetime
import os
import re
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
# DATABASE
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
# HEALTH
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

        cur.execute("""
            INSERT INTO users (name, email, password, streak, last_active)
            VALUES (%s, %s, %s, 0, NULL)
        """, (name, email, password))

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
            SELECT * FROM users
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
# RISK DETECTION (MULTILINGUAL)
# =====================================================
def detect_risk(text):
    text = text.lower()

    critical = [
        "i want to die", "kill myself", "suicide", "hurt myself",
        "मुझे मरना है", "आत्महत्या", "मला मरायचं आहे",
        "quiero morir", "suicidio"
    ]

    if any(p in text for p in critical):
        return "critical"

    negative = [
        "sad", "depressed", "alone", "hopeless",
        "उदास", "निराश", "एकटा",
        "triste", "solo"
    ]

    score = sum(1 for w in negative if w in text)

    if score >= 2:
        return "high"
    elif score == 1:
        return "medium"
    return "low"

# =====================================================
# USER HISTORY
# =====================================================
def get_user_history(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT message FROM chats
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [r["message"] for r in rows]

# =====================================================
# SMART AI SIMULATION
# =====================================================
def generate_ai_response(message, risk):
    empathetic_responses = {
        "low": "I'm glad you're sharing your thoughts. Tell me more about how you're feeling.",
        "medium": "I understand this might feel heavy. You're not alone in this.",
        "high": "That sounds really difficult. I'm here with you. Let's take this one step at a time.",
        "critical": "I'm really concerned about you. Please consider reaching out to someone immediately. You deserve help."
    }
    return empathetic_responses.get(risk)

def generate_personalized_quote(history):
    if not history:
        return "Every new day is a fresh beginning."

    keywords = " ".join(history).lower()

    if "alone" in keywords:
        return "Even when you feel alone, you are deeply valued."
    if "hopeless" in keywords:
        return "Hope can return in the smallest moments."
    if "sad" in keywords:
        return "Your sadness does not define your strength."

    return random.choice([
        "You are stronger than you think.",
        "Progress, not perfection.",
        "Your feelings are valid."
    ])

def generate_recommendations(risk):
    if risk == "low":
        return ["Keep a gratitude journal.", "Go for a short walk.", "Listen to calming music."]
    elif risk == "medium":
        return ["Practice deep breathing.", "Talk to a trusted friend.", "Try a short meditation."]
    elif risk == "high":
        return ["Reach out to someone immediately.", "Avoid isolation.", "Consider speaking to a counselor."]
    else:
        return ["Call emergency services.", "Contact a suicide helpline.", "Stay with someone you trust."]

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
        history = get_user_history(user_id)

        ai_response = generate_ai_response(message, risk)
        quote = generate_personalized_quote(history)
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
    high_count = sum(1 for r in rows if r["risk_level"] in ["high", "critical"])

    affirmations = [
        "You are stronger than you think.",
        "Your feelings are valid.",
        "Keep going — you are doing your best."
    ]

    return jsonify({
        "total_chats": total,
        "high_risk_count": high_count,
        "affirmation": random.choice(affirmations)
    })

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
