from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
from deep_translator import GoogleTranslator
from gtts import gTTS
import speech_recognition as sr
import datetime
import os

app = Flask(__name__)

# -------------------------------
# Database Connection
# -------------------------------
def get_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not set")
    return psycopg2.connect(db_url)


# -------------------------------
# Home Route
# -------------------------------
@app.route("/", methods=["GET"])
def home():
    return "MindEase Backend Running 🚀"


# -------------------------------
# REGISTER
# -------------------------------
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


# -------------------------------
# LOGIN
# -------------------------------
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
                "name": user["name"],
                "email": user["email"]
            })
        else:
            return jsonify({"error": "Invalid email or password"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# CHAT
# -------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        message = data.get("message")
        location = data.get("location", "")

        translated = GoogleTranslator(source="auto", target="en").translate(message)

        risk_keywords = ["die", "suicide", "kill"]
        risk_level = "high" if any(word in translated.lower() for word in risk_keywords) else "low"

        response_text = f"I understand: {translated}"

        conn = get_db()
        cur = conn.cursor()

        # Save in chats
        cur.execute("""
            INSERT INTO chats (user_id, message, response, risk_level, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, message, response_text, risk_level, datetime.datetime.utcnow()))

        # Save in chat_history
        cur.execute("""
            INSERT INTO chat_history (user_id, message, response, created_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, message, response_text, datetime.datetime.utcnow()))

        # Create alert if high risk
        if risk_level == "high":
            cur.execute("""
                INSERT INTO alerts (user_id, message, created_at)
                VALUES (%s, %s, %s)
            """, (user_id, "High risk detected", datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "response": response_text,
            "risk_level": risk_level
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# GAME SCORE
# -------------------------------
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


# -------------------------------
# VOICE TO TEXT
# -------------------------------
@app.route("/voice-to-text", methods=["POST"])
def voice_to_text():
    try:
        audio_file = request.files.get("file")
        recognizer = sr.Recognizer()

        with sr.AudioFile(audio_file) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)

        return jsonify({"text": text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# TEXT TO VOICE
# -------------------------------
@app.route("/text-to-voice", methods=["POST"])
def text_to_voice():
    try:
        data = request.get_json()
        text = data.get("text")
        user_id = data.get("user_id")

        tts = gTTS(text=text, lang="en")
        filename = "response.mp3"
        tts.save(filename)

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO voice_logs (user_id, transcript, audio_file, created_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, text, filename, datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"audio_file": filename})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
