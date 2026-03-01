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
# RISK DETECTION
# =====================================================
def detect_risk(text):
    text = text.lower()

    critical_phrases = [
        "i want to die", "kill myself", "suicide", "hurt myself",
        "मुझे मरना है", "आत्महत्या", "खुद को नुकसान पहुँचाना",
        "मला मरायचं आहे", "आत्महत्या करणार", "स्वतःला इजा करणार",
        "quiero morir", "suicidio", "matarme", "hacerme daño"
    ]

    if any(p in text for p in critical_phrases):
        return "critical"

    negative_words = [
        "sad", "depressed", "alone", "hopeless", "worthless",
        "उदास", "निराश", "अकेला", "बेकार",
        "एकटा", "निरर्थक",
        "triste", "deprimido", "solo", "sin esperanza", "inútil"
    ]

    score = sum(1 for w in negative_words if w in text)

    if score >= 2:
        return "high"
    elif score == 1:
        return "medium"
    return "low"

# =====================================================
# FETCH USER HISTORY CONTEXT
# =====================================================
def get_user_recent_messages(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT message
        FROM chats
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [r["message"] for r in rows]

# =====================================================
# AI PERSONALIZED QUOTE
# =====================================================
def generate_personalized_quote(user_history, current_message):
    try:
        context = "\n".join(user_history)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You generate short, powerful, emotionally supportive motivational quotes based on user's emotional history."
                },
                {
                    "role": "user",
                    "content": f"User previous emotions:\n{context}\n\nCurrent message:\n{current_message}\n\nGenerate 1 short personalized motivational quote."
                }
            ]
        )

        return response.choices[0].message.content.strip()

    except:
        return "You are stronger than this moment."

# =====================================================
# AI DYNAMIC RECOMMENDATIONS
# =====================================================
def generate_dynamic_recommendations(user_history, current_message, risk_level):
    try:
        context = "\n".join(user_history)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a mental health assistant. Give 3 short practical self-care recommendations. Keep them simple and safe."
                },
                {
                    "role": "user",
                    "content": f"""
User emotional history:
{context}

Current message:
{current_message}

Risk level: {risk_level}

Generate 3 short personalized recommendations.
"""
                }
            ]
        )

        text = response.choices[0].message.content.strip()
        recommendations = [r.strip("-•1234567890. ") for r in text.split("\n") if r.strip()]

        return recommendations[:3]

    except:
        return [
            "Take a few slow deep breaths.",
            "Reach out to someone you trust.",
            "Be gentle with yourself today."
        ]

# =====================================================
# AI CHAT RESPONSE
# =====================================================
def generate_ai_response(message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a deeply empathetic mental health support assistant."},
                {"role": "user", "content": message}
            ]
        )
        return response.choices[0].message.content
    except:
        return "I'm here for you. You’re not alone."

# =====================================================
# CHAT (FULLY UPGRADED)
# =====================================================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        message = data.get("message")

        risk_level = detect_risk(message)
        user_history = get_user_recent_messages(user_id)

        ai_response = generate_ai_response(message)
        personalized_quote = generate_personalized_quote(user_history, message)
        dynamic_recommendations = generate_dynamic_recommendations(user_history, message, risk_level)

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO chats (user_id, message, response, risk_level, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, message, ai_response, risk_level, datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "response": ai_response,
            "risk_level": risk_level,
            "personalized_quote": personalized_quote,
            "recommendations": dynamic_recommendations
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# ANALYTICS WITH AFFIRMATIONS, QUOTES & RECOMMENDATIONS
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

        total_chats = len(rows)
        high_risk_count = sum(1 for r in rows if r["risk_level"] in ["high", "critical"])

        affirmations = [
            "You are stronger than you think.",
            "Every day is a new beginning.",
            "Your feelings are valid, and you matter.",
            "Keep going — you’re doing better than you realize.",
            "Hope is always within reach.",
            "You are not alone on this journey."
        ]

        quotes = [
            "The best way out is always through. – Robert Frost",
            "Believe you can and you're halfway there. – Theodore Roosevelt",
            "Keep your face always toward the sunshine—and shadows will fall behind you. – Walt Whitman"
        ]

        recommendations = [
            "Try a short mindfulness exercise today.",
            "Take a walk outside and notice your surroundings.",
            "Write down three things you’re grateful for.",
            "Listen to calming music for 10 minutes."
        ]

        suggestion = random.choice(affirmations)

        return jsonify({
            "total_chats": total_chats,
            "high_risk_count": high_risk_count,
            "suggestion": suggestion,
            "quotes": random.sample(quotes, 2),
            "recommendations": random.sample(recommendations, 2)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
