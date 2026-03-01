from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import datetime
import os
import random
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

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
# ERROR HANDLER
# =====================================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

# =====================================================
# HOME & HEALTH
# =====================================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "MindEase Backend Running 🚀"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "OK"})

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
# LANGUAGE SUPPORT
# =====================================================
def detect_language(text):
    try:
        translator = GoogleTranslator(source='auto', target='en')
        translator.translate(text)
        return translator.source
    except:
        return "en"

def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except:
        return text

# =====================================================
# RISK DETECTION
# =====================================================
def detect_risk(text):
    text = text.lower()

    if any(x in text for x in ["i want to die", "kill myself", "suicide"]):
        return "critical"
    if any(x in text for x in ["hopeless", "worthless"]):
        return "high"
    if any(x in text for x in ["sad", "alone", "depressed"]):
        return "medium"
    return "low"

# =====================================================
# PERSONALIZED ENGINE
# =====================================================
def get_user_emotional_stats(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT risk_level FROM chats WHERE user_id=%s", (user_id,))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {
        "total": len(rows),
        "critical": sum(1 for r in rows if r["risk_level"] == "critical"),
        "high": sum(1 for r in rows if r["risk_level"] == "high"),
        "medium": sum(1 for r in rows if r["risk_level"] == "medium")
    }

def generate_personalized_affirmation(risk, stats):
    if risk == "critical":
        return "You matter more than you realize. Please seek help immediately."
    if stats["high"] > stats["medium"]:
        return "You've been handling a lot. That shows strength."
    if stats["medium"] > 3:
        return "You're trying even when it's hard. That matters."
    return "You are growing stronger every day."

def generate_personalized_recommendations(risk, stats):
    if risk == "critical":
        return [
            "Contact emergency services immediately",
            "Reach out to someone you trust right now",
            "Use the helpline below"
        ]
    if risk == "high":
        return [
            "Consider speaking to a counselor",
            "Avoid staying alone today",
            "Write your thoughts in a journal"
        ]
    if stats["medium"] > 2:
        return [
            "Practice mindful breathing",
            "Take a short walk outside",
            "Listen to calming music"
        ]
    return [
        "Maintain your routine",
        "Practice gratitude",
        "Do something you enjoy"
    ]

# =====================================================
# EMERGENCY LINKS
# =====================================================
def get_psychologist_link():
    return "https://www.google.com/maps/search/psychologist+near+me"

def get_helpline_link():
    return "https://www.iasp.info/resources/Crisis_Centres/"

# =====================================================
# CHAT
# =====================================================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data["user_id"]
        message = data["message"]

        user_lang = detect_language(message)
        message_en = translate_text(message, "en")

        risk = detect_risk(message_en)
        stats = get_user_emotional_stats(user_id)

        affirmation_en = generate_personalized_affirmation(risk, stats)
        recommendations_en = generate_personalized_recommendations(risk, stats)

        emergency_links = None
        if risk == "critical":
            emergency_links = {
                "nearest_psychologist": get_psychologist_link(),
                "global_helpline_directory": get_helpline_link()
            }

        affirmation = translate_text(affirmation_en, user_lang)
        recommendations = [translate_text(r, user_lang) for r in recommendations_en]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chats (user_id, message, response, risk_level, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, message, affirmation, risk, datetime.datetime.utcnow()))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "response": affirmation,
            "risk_level": risk,
            "language_detected": user_lang,
            "recommendations": recommendations,
            "emergency_resources": emergency_links
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
        "mental_state": "Improving" if total == 0 or high_risk < total/2 else "Needs Attention"
    })

# =====================================================
# GAME SCORE
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
