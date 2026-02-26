from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
from deep_translator import GoogleTranslator
import datetime
import os
import re

app = Flask(__name__)

# =====================================================
# DATABASE CONNECTION
# =====================================================
def get_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not set")
    return psycopg2.connect(db_url)

# =====================================================
# HOME
# =====================================================
@app.route("/", methods=["GET"])
def home():
    return "MindEase Backend Running 🚀"

# =====================================================
# AI SENTIMENT SCORING
# =====================================================
def sentiment_score(text):
    text = text.lower()

    positive_words = ["happy", "good", "great", "hope", "better", "love"]
    negative_words = ["sad", "depressed", "alone", "hopeless", "pain", "worthless"]

    score = 0

    for word in positive_words:
        if re.search(r'\b' + word + r'\b', text):
            score += 1

    for word in negative_words:
        if re.search(r'\b' + word + r'\b', text):
            score -= 1

    return score

# =====================================================
# RISK DETECTION
# =====================================================
def detect_risk(text):
    text = text.lower()

    critical_phrases = [
        "i want to die",
        "kill myself",
        "end my life",
        "suicide",
        "hurt myself",
        "no reason to live"
    ]

    if any(phrase in text for phrase in critical_phrases):
        return "critical"

    score = sentiment_score(text)

    if score <= -2:
        return "high"
    elif score < 0:
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
# CHAT (AUTO LANGUAGE + ALERT FIXED)
# =====================================================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        message = data.get("message")
        location = data.get("location", "")

        # Translate message to English (auto detect)
        translator = GoogleTranslator(source="auto", target="en")
        translated = translator.translate(message)

        # Detect risk
        risk_level = detect_risk(translated)

        # Base response
        response_text = f"I understand: {translated}"

        # Translate back to original language
        source_lang = translator.source
        final_response = GoogleTranslator(
            source="en",
            target=source_lang
        ).translate(response_text)

        conn = get_db()
        cur = conn.cursor()

        # Save to chats
        cur.execute("""
            INSERT INTO chats (user_id, message, response, risk_level, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, message, final_response, risk_level, datetime.datetime.utcnow()))

        # Save to chat_history
        cur.execute("""
            INSERT INTO chat_history (user_id, message, response, created_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, message, final_response, datetime.datetime.utcnow()))

        support = {}

        # If high or critical → create alert
        if risk_level in ["high", "critical"]:

            support["emergency"] = "Call local emergency services immediately."

            if location:
                support["nearby_psychologist"] = \
                    f"https://www.google.com/maps/search/{location} psychologist near me"

            # INSERT MATCHING YOUR ALERTS TABLE
            cur.execute("""
                INSERT INTO alerts (user_id, type, triggered_at)
                VALUES (%s, %s, %s)
            """, (user_id, risk_level, datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "response": final_response,
            "risk_level": risk_level,
            "support": support
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# CHAT HISTORY API
# =====================================================
@app.route("/chat-history/<int:user_id>", methods=["GET"])
def get_chat_history(user_id):
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
            "user_id": user_id,
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
            SELECT risk_level, created_at
            FROM chats
            WHERE user_id=%s
            ORDER BY created_at DESC
        """, (user_id,))

        rows = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify({
            "total_chats": len(rows),
            "high_risk_count": sum(1 for r in rows if r["risk_level"] == "high"),
            "recent_trend": [
                {"risk": r["risk_level"], "time": r["created_at"].isoformat()}
                for r in rows[:5]
            ]
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
