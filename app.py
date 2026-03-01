from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import datetime
import os
import re
import openai   # legacy import for openai==0.28
from dotenv import load_dotenv   # ✅ NEW

# =====================================================
# LOAD .env LOCALLY
# =====================================================
load_dotenv()  # this will read your .env file

app = Flask(__name__)

# =====================================================
# ENV VARIABLES
# =====================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not DATABASE_URL:
    raise Exception("DATABASE_URL not set")

if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set")

openai.api_key = OPENAI_API_KEY

# =====================================================
# DATABASE CONNECTION
# =====================================================
def get_db():
    return psycopg2.connect(DATABASE_URL)

# =====================================================
# HEALTH CHECK
# =====================================================
@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

# =====================================================
# HOME
# =====================================================
@app.route("/", methods=["GET"])
def home():
    return "MindEase Backend Running 🚀"

# =====================================================
# MULTILINGUAL RISK DETECTION
# =====================================================
def detect_risk(text):
    text = text.lower()

    critical_phrases = [
        "i want to die", "kill myself", "end my life", "suicide", "hurt myself",
        "मुझे मरना है", "आत्महत्या", "खुद को नुकसान पहुँचाना",
        "मला मरायचं आहे", "आत्महत्या करणार", "स्वतःला इजा करणार",
        "quiero morir", "suicidio", "matarme", "hacerme daño"
    ]

    if any(phrase in text for phrase in critical_phrases):
        return "critical"

    negative_words = [
        "sad", "depressed", "alone", "hopeless", "worthless",
        "उदास", "निराश", "अकेला", "बेकार",
        "एकटा", "निरर्थक",
        "triste", "deprimido", "solo", "sin esperanza", "inútil"
    ]

    score = sum(1 for word in negative_words if re.search(r'\b' + word + r'\b', text))

    if score >= 2:
        return "high"
    elif score == 1:
        return "medium"
    else:
        return "low"

# =====================================================
# REGISTER
# =====================================================
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, password)
        )

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
        email = data.get("email")
        password = data.get("password")

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user:
            return jsonify({
                "message": "Login successful",
                "user_id": user["id"],
                "name": user["name"]
            })
        else:
            return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# CHAT WITH REAL AI (MULTILINGUAL + FALLBACK)
# =====================================================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        message = data.get("message")
        location = data.get("location", "")

        risk_level = detect_risk(message)

        ai_response = None
        try:
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a supportive mental health assistant. Respond in the same language as the user. Be empathetic."
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            )
            ai_response = completion.choices[0].message["content"]

        except Exception:
            ai_response = "I'm here for you. I understand you're feeling anxious. Take a deep breath — you're not alone."

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO chats (user_id, message, response, risk_level, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, message, ai_response, risk_level, datetime.datetime.utcnow()))

        cur.execute("""
            INSERT INTO chat_history (user_id, message, response, created_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, message, ai_response, datetime.datetime.utcnow()))

        support = {}
        if risk_level in ["high", "critical"]:
            support["emergency"] = "Call local emergency services immediately."
            if location:
                support["nearby_psychologist"] = f"https://www.google.com/maps/search/{location} psychologist near me"

            cur.execute("""
                INSERT INTO alerts (user_id, type, triggered_at)
                VALUES (%s, %s, %s)
            """, (user_id, risk_level, datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "response": ai_response,
            "risk_level": risk_level,
            "support": support
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# CHAT HISTORY
# =====================================================
@app.route("/chat-history/<int:user_id>", methods=["GET"])
def chat_history(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("""
            SELECT id, message, response, created_at
            FROM chat_history
            WHERE user_id=%s
            ORDER BY created_at DESC
        """, (user_id,))

        rows = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify({
            "history": [
                {
                    "id": r["id"],
                    "message": r["message"],
                    "response": r["response"],
                    "created_at": r["created_at"].isoformat()
                }
                for r in rows
            ]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# ANALYTICS
# =====================================================
@app.route("/analytics/<int:user_id>", methods=["GET"])
def analytics(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("""
            SELECT risk_level FROM chats
            WHERE user_id=%s
        """, (user_id,))

        rows = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify({
            "total_chats": len(rows),
            "high_risk_count": sum(1 for r in rows if r["risk_level"] in ["high", "critical"])
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# GAME SCORE
# =====================================================
@app.route("/game-score", methods=["POST"])
def game_score():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        score = data.get("score")

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO game_scores (user_id, score, created_at)
            VALUES (%s, %s, %s)
        """, (user_id, score, datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Score saved"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
