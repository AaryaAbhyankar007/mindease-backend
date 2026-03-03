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
# RESPONSE GENERATOR
# =====================================================
def generate_response(risk):

    if risk == "critical":
        return "I'm really sorry you're feeling this way 💙 You're not alone. Would you like to talk about it?"

    if risk == "high":
        return "That sounds heavy. I'm here to listen. Tell me more."

    if risk == "medium":
        return "I understand. Share more with me."

    return "I'm listening. Tell me more 😊"

# =====================================================
# CHAT (UPDATED FOR ANDROID)
# =====================================================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data["user_id"]
        message = data["message"]

        risk = detect_risk(message)
        response_text = generate_response(risk)

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO chats (user_id, message, response, risk_level, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, message, response_text, risk, datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        # 🔥 IMPORTANT: Match Android Keys
        return jsonify({
            "reply": response_text,
            "risk": risk
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
        chat_rows = cur.fetchall()

        cur.execute("""
            SELECT score
            FROM game_scores
            WHERE user_id=%s
            ORDER BY created_at ASC
        """, (user_id,))
        game_rows = cur.fetchall()

        cur.close()
        conn.close()

        graph = []

        score_map = {
            "low": 5,
            "medium": 3,
            "high": 2,
            "critical": 1
        }

        for r in chat_rows:
            graph.append({"mood_score": score_map.get(r["risk_level"], 5)})

        for g in game_rows:
            if g["score"] >= 80:
                graph.append({"mood_score": 5})
            elif g["score"] >= 50:
                graph.append({"mood_score": 3})
            else:
                graph.append({"mood_score": 1})

        return jsonify({"graph": graph})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
