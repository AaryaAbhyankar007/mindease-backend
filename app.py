from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import datetime
import os
import re
from dotenv import load_dotenv
from openai import OpenAI
import random

# =====================================================
# LOAD ENV
# =====================================================
load_dotenv()
app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not DATABASE_URL:
    raise Exception("DATABASE_URL not set")

if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# =====================================================
# DATABASE
# =====================================================
def get_db():
    return psycopg2.connect(DATABASE_URL)

# =====================================================
# GLOBAL 404 HANDLER (Prevents ugly HTML page)
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
# RISK DETECTION
# =====================================================
def detect_risk(text):
    text = text.lower()

    critical_phrases = [
        "i want to die", "kill myself", "suicide", "hurt myself",
        "मुझे मरना है", "आत्महत्या", "मला मरायचं आहे"
    ]

    if any(p in text for p in critical_phrases):
        return "critical"

    negative_words = [
        "sad", "depressed", "alone", "hopeless",
        "उदास", "निराश", "एकटा"
    ]

    score = sum(1 for w in negative_words if w in text)

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
# AI GENERATION
# =====================================================
def generate_ai(message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a compassionate mental health assistant."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content

def generate_quote(history, message):
    context = "\n".join(history)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Generate one short motivational quote."},
            {"role": "user", "content": f"{context}\n{message}"}
        ]
    )
    return response.choices[0].message.content.strip()

def generate_recommendations(history, message, risk):
    context = "\n".join(history)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Give 3 short practical self-care recommendations."},
            {"role": "user", "content": f"{context}\n{message}\nRisk: {risk}"}
        ]
    )

    text = response.choices[0].message.content.strip()
    return [line.strip("-•1234567890. ") for line in text.split("\n") if line.strip()][:3]

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

        ai_response = generate_ai(message)
        quote = generate_quote(history, message)
        recommendations = generate_recommendations(history, message, risk)

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
        "Progress, not perfection."
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
