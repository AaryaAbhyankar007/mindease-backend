from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import datetime
import os
import re
import random
import openai
from dotenv import load_dotenv

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

openai.api_key = OPENAI_API_KEY

# =====================================================
# DATABASE
# =====================================================
def get_db():
    return psycopg2.connect(DATABASE_URL)

# =====================================================
# HEALTH & HOME
# =====================================================
@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "MindEase Backend Running 🚀"

# =====================================================
# RISK DETECTION
# =====================================================
def detect_risk(text):
    text = text.lower()

    critical_phrases = [
        "i want to die", "kill myself", "end my life", "suicide", "hurt myself",
        "मुझे मरना है", "आत्महत्या", "खुद को नुकसान पहुँचाना",
        "मला मरायचं आहे", "आत्महत्या करणार", "स्वतःला इजा करणार"
    ]

    if any(p in text for p in critical_phrases):
        return "critical"

    negative_words = [
        "sad", "depressed", "alone", "hopeless", "worthless",
        "उदास", "निराश", "अकेला",
        "एकटा", "निरर्थक"
    ]

    score = sum(1 for w in negative_words if re.search(r'\b' + w + r'\b', text))

    if score >= 2:
        return "high"
    elif score == 1:
        return "medium"
    return "low"

# =====================================================
# STREAK SYSTEM
# =====================================================
def update_streak(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    today = datetime.date.today()

    cur.execute("SELECT streak, last_active FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()

    if not user:
        return 0

    last_active = user["last_active"]
    streak = user["streak"] or 0

    if last_active == today:
        return streak

    if last_active == today - datetime.timedelta(days=1):
        streak += 1
    else:
        streak = 1

    cur.execute("""
        UPDATE users
        SET streak=%s, last_active=%s
        WHERE id=%s
    """, (streak, today, user_id))

    conn.commit()
    cur.close()
    conn.close()

    return streak

# =====================================================
# AI PERSONAL AFFIRMATION
# =====================================================
def generate_personal_affirmation(message):
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Generate a short positive mental health affirmation."},
                {"role": "user", "content": message}
            ]
        )
        return completion.choices[0].message["content"]
    except:
        return "You are capable of overcoming this moment."

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
        return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# CHAT
# =====================================================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        message = data.get("message")
        location = data.get("location", "")

        risk_level = detect_risk(message)
        streak = update_streak(user_id)
        personal_affirmation = generate_personal_affirmation(message)

        try:
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a supportive mental health assistant."},
                    {"role": "user", "content": message}
                ]
            )
            ai_response = completion.choices[0].message["content"]
        except:
            ai_response = "I'm here for you. Take a deep breath — you're not alone."

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO chats (user_id, message, response, risk_level, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, message, ai_response, risk_level, datetime.datetime.utcnow()))

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
            "streak": streak,
            "personal_affirmation": personal_affirmation,
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
            FROM chats
            WHERE user_id=%s
            ORDER BY created_at DESC
        """, (user_id,))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify({"history": rows})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# MOOD GRAPH
# =====================================================
@app.route("/mood-graph/<int:user_id>", methods=["GET"])
def mood_graph(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("""
            SELECT DATE(created_at) as date, risk_level
            FROM chats
            WHERE user_id=%s
            ORDER BY created_at ASC
        """, (user_id,))

        rows = cur.fetchall()

        mood_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}

        graph_data = [
            {"date": str(r["date"]), "mood_score": mood_map.get(r["risk_level"], 1)}
            for r in rows
        ]

        cur.close()
        conn.close()

        return jsonify({"graph": graph_data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# ANALYTICS + ACHIEVEMENTS
# =====================================================
@app.route("/analytics/<int:user_id>", methods=["GET"])
def analytics(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("SELECT risk_level FROM chats WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()

        total_chats = len(rows)
        high_risk_count = sum(1 for r in rows if r["risk_level"] in ["high", "critical"])

        overall_risk = "low"
        if total_chats > 0:
            ratio = high_risk_count / total_chats
            if ratio >= 0.5:
                overall_risk = "high"
            elif ratio >= 0.25:
                overall_risk = "medium"

        cur.execute("SELECT streak FROM users WHERE id=%s", (user_id,))
        streak_data = cur.fetchone()
        streak = streak_data["streak"] if streak_data else 0

        achievements = []
        if streak >= 7:
            achievements.append("🔥 7-Day Streak!")
        if total_chats >= 20:
            achievements.append("💬 20 Chats Completed!")
        if high_risk_count == 0 and total_chats >= 10:
            achievements.append("🌤 Stable Mood!")

        cur.close()
        conn.close()

        return jsonify({
            "total_chats": total_chats,
            "high_risk_count": high_risk_count,
            "overall_risk": overall_risk,
            "streak": streak,
            "achievements": achievements
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# DAILY MOTIVATION
# =====================================================
@app.route("/daily-motivation/<int:user_id>", methods=["GET"])
def daily_motivation(user_id):
    messages = [
        "Today is a new opportunity to grow.",
        "Small progress is still progress.",
        "You are stronger than yesterday.",
        "Keep moving forward — you’re doing great."
    ]
    return jsonify({"message": random.choice(messages)})

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
