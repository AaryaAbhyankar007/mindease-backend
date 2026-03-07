from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import datetime
import os
import re
import requests
from dotenv import load_dotenv

# =====================================================
# LOAD ENV
# =====================================================

load_dotenv()
app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_KEY")

if not DATABASE_URL:
    raise Exception("DATABASE_URL not set")
if not GOOGLE_MAPS_KEY:
    raise Exception("GOOGLE_MAPS_KEY not set")

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
# REGISTER & LOGIN
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
# NONSENSE DETECTION
# =====================================================

def is_nonsense(text):
    if len(text) < 2:
        return True
    if re.fullmatch(r"[a-zA-Z]{6,}", text) and len(set(text)) <= 2:
        return True
    return False

# =====================================================
# EMOTION DETECTION
# =====================================================

def detect_emotion(text):
    text = text.lower()
    happy = ["happy","great","good","excited","awesome"]
    sad = ["sad","lonely","cry","hurt","down"]
    breakup = ["breakup","heartbroken","she left me","he left me"]
    anger = ["angry","mad","furious","hate"]
    stress = ["stress","pressure","anxiety","overthinking","tired"]

    if any(w in text for w in happy):
        return "happy"
    if any(w in text for w in breakup):
        return "breakup"
    if any(w in text for w in sad):
        return "sad"
    if any(w in text for w in anger):
        return "angry"
    if any(w in text for w in stress):
        return "stress"
    return "normal"

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
# GOOGLE MAPS NEARBY THERAPISTS (WORLDWIDE)
# =====================================================

def get_nearby_therapists(city):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"psychologist OR therapist in {city}",
        "key": GOOGLE_MAPS_KEY
    }
    res = requests.get(url, params=params)
    therapists = []
    if res.status_code == 200:
        results = res.json().get("results", [])
        for r in results:
            therapists.append({
                "name": r.get("name"),
                "address": r.get("formatted_address"),
                "lat": r.get("geometry", {}).get("location", {}).get("lat"),
                "lng": r.get("geometry", {}).get("location", {}).get("lng"),
                "rating": r.get("rating", None)
            })
    return therapists

# =====================================================
# RESPONSE GENERATOR (SMART)
# =====================================================

def generate_response(message):
    if is_nonsense(message):
        return "I didn't quite understand that. Could you tell me a bit more?"

    emotion = detect_emotion(message)
    risk = detect_risk(message)

    if risk == "critical":
        return (
            "I'm really sorry you're feeling this way 💙 "
            "You are not alone. It might help to talk to someone you trust "
            "or a professional helpline."
        )
    if risk == "high":
        return "That sounds really difficult. I'm here to listen. What happened?"

    if emotion == "happy":
        return "That's great to hear! 😊 What made your day good?"
    if emotion == "breakup":
        return (
            "Breakups can be really painful. "
            "It's okay to feel hurt. Do you want to talk about what happened?"
        )
    if emotion == "sad":
        return "I'm sorry you're feeling sad. I'm here to listen."
    if emotion == "angry":
        return "It sounds like you're feeling angry. What happened?"
    if emotion == "stress":
        return "Stress can feel overwhelming. What's been causing the pressure?"

    return "I'm listening. Tell me more 😊"

# =====================================================
# CHAT (ANDROID COMPATIBLE + INTELLIGENT)
# =====================================================

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data["user_id"]
        message = data["message"]
        city = data.get("city")  # optional, for therapist search

        risk = detect_risk(message)
        response_text = generate_response(message)
        therapists = []

        if risk == "critical" and city:
            therapists = get_nearby_therapists(city)

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
            "therapists": therapists,
            "recommendations": [
                "Take deep breaths",
                "Talk to someone you trust",
                "Practice mindfulness or meditation",
                "Stay hydrated"
            ]
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
        game_name = data["game_name"]
        score = data["score"]

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
# ANALYTICS
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
