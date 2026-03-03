from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import datetime
import os
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
# HOME
# =====================================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "MindEase Backend Running 🚀"})

# =====================================================
# HEALTH CHECK
# =====================================================
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
# SMART FRIENDLY RESPONSE SYSTEM
# =====================================================
def generate_response(risk, message):

    message = message.lower()

    if risk == "critical":
        return (
            "I'm really sorry you're feeling this way. 💙 "
            "You are not alone. I'm here with you. "
            "Would you like to talk about what's making you feel this way?"
        )

    if risk == "high":
        return (
            "That sounds really heavy. Thank you for sharing it with me. "
            "What’s been bothering you lately?"
        )

    if risk == "medium":
        return (
            "I understand. Feel free to tell me more. "
            "I'm listening carefully."
        )

    # Positive messages
    if "happy" in message or "good" in message:
        return "That’s amazing! I’m really happy for you 😊"

    if "thank" in message:
        return "You’re welcome! I’m always here for you."

    return "Tell me more. I’m here to listen."

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
        response_text = generate_response(risk, message)

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
            "response": response_text,
            "risk_level": risk,
            "show_help_option": risk == "critical"
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
            SELECT message, response, risk_level, created_at
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
        high_risk = sum(1 for r in rows if r["risk_level"] in ["high", "critical"])

        cur.close()
        conn.close()

        return jsonify({
            "total_chats": total,
            "high_risk_count": high_risk
        })

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
            SELECT risk_level
            FROM chats
            WHERE user_id=%s
            ORDER BY created_at ASC
        """, (user_id,))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        graph = []

        for r in rows:
            if r["risk_level"] == "low":
                score = 5
            elif r["risk_level"] == "medium":
                score = 3
            elif r["risk_level"] == "high":
                score = 2
            else:
                score = 1

            graph.append({"mood_score": score})

        return jsonify({"graph": graph})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
