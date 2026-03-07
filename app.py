from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import datetime
import os
import re
import openai
from dotenv import load_dotenv

# =====================================================
# LOAD ENV VARIABLES
# =====================================================
load_dotenv()
app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_KEY")

if not DATABASE_URL:
    raise Exception("DATABASE_URL not set")
if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set")
if not GOOGLE_MAPS_KEY:
    raise Exception("GOOGLE_MAPS_KEY not set")

openai.api_key = OPENAI_API_KEY

# =====================================================
# DATABASE CONNECTION
# =====================================================
def get_db():
    return psycopg2.connect(DATABASE_URL)

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
            SELECT id, name FROM users WHERE email=%s AND password=%s
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
# NONSENSE / GIBBERISH DETECTION
# =====================================================
def is_nonsense(text):
    text = text.strip()
    if len(text) < 2:
        return True
    if len(set(text)) / len(text) > 0.7 and text.isalpha():
        return True
    return False

# =====================================================
# RISK DETECTION
# =====================================================
def detect_risk(text):
    text = text.lower()
    suicide_patterns = ["i want to die","kill myself","suicide","end my life"]
    violence_patterns = ["kill someone","hurt someone","attack someone"]
    if any(x in text for x in suicide_patterns):
        return "critical"
    if any(x in text for x in violence_patterns):
        return "high"
    if any(x in text for x in ["hopeless","worthless"]):
        return "high"
    if any(x in text for x in ["sad","alone","depressed"]):
        return "medium"
    return "low"

# =====================================================
# NEARBY THERAPISTS (SIMULATED)
# =====================================================
def get_nearby_therapists():
    return [
        {"name": "Therapist A", "location": "123 Main St, City"},
        {"name": "Therapist B", "location": "456 Elm St, City"}
    ]

# =====================================================
# GPT RESPONSE GENERATOR
# =====================================================
def gpt_response(user_message):
    try:
        prompt = f"You are a friendly supportive mental health chatbot. Respond naturally and empathetically to the user message: '{user_message}'"
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":"You are a friendly supportive mental health chatbot."},
                      {"role":"user","content":user_message}],
            max_tokens=150,
            temperature=0.7
        )
        reply = completion.choices[0].message.content.strip()
        return reply
    except Exception as e:
        return "I'm listening. Tell me more 😊"

# =====================================================
# CHAT ENDPOINT
# =====================================================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data["user_id"]
        message = data["message"]

        risk = detect_risk(message)
        response_text = gpt_response(message)

        recommendations = []
        if risk in ["medium","high","critical"]:
            recommendations = [
                "Take deep breaths",
                "Talk to someone you trust",
                "Practice mindfulness or meditation",
                "Stay hydrated"
            ]

        therapists = get_nearby_therapists() if risk == "critical" else []

        # Save chat in DB
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chats (user_id, message, response, risk_level, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, message, response_text, risk, datetime.datetime.utcnow()))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "reply": response_text,
            "risk": risk,
            "recommendations": recommendations,
            "therapists": therapists
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# SAVE GAME SCORE
# =====================================================
@app.route("/game-score", methods=["POST"])
def save_game_score():
    try:
        data = request.get_json()
        user_id = data["user_id"]
        game_name = data.get("game_name","Unknown")
        score = data.get("score",0)

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO game_scores (user_id, game_name, score, created_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, game_name, score, datetime.datetime.utcnow()))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Game score saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# ANALYTICS ENDPOINT
# =====================================================
@app.route("/analytics/<int:user_id>", methods=["GET"])
def analytics(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT risk_level FROM chats WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        total = len(rows)
        high_risk = sum(1 for r in rows if r["risk_level"] in ["high","critical"])
        cur.close()
        conn.close()
        return jsonify({"total_chats": total,"high_risk_count": high_risk})
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
        cur.execute("SELECT risk_level FROM chats WHERE user_id=%s ORDER BY created_at ASC", (user_id,))
        rows = cur.fetchall()
        score_map = {"low":5,"medium":3,"high":2,"critical":1}
        graph = [{"mood_score": score_map.get(r["risk_level"],5)} for r in rows]
        cur.close()
        conn.close()
        return jsonify({"graph": graph})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# RUN SERVER
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
