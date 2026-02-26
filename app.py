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
# Home
# -------------------------------
@app.route("/", methods=["GET"])
def home():
    return "MindEase Backend Running 🚀"


# -------------------------------
# Risk Check
# -------------------------------
def check_risk_escalation(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT risk_level FROM chats
            WHERE user_id=%s
            ORDER BY created_at DESC
            LIMIT 3
        """, (user_id,))
        risks = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return risks.count("high") >= 2
    except:
        return False


# -------------------------------
# Helpline
# -------------------------------
def get_helpline(location):
    helplines = {
        "india": "National Suicide Helpline (India): 9152987821",
        "us": "988 - US Suicide & Crisis Lifeline",
        "uk": "116 123 - Samaritans",
    }

    location = location.lower()
    for country in helplines:
        if country in location:
            return helplines[country]

    return "Please contact your local emergency helpline."


# -------------------------------
# Register User
# -------------------------------
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (username, email, password)
            VALUES (%s, %s, %s)
        """, (username, email, password))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "User registered successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# Save Language Preference
# -------------------------------
@app.route("/set-language", methods=["POST"])
def set_language():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        language = data.get("language")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO languages (user_id, language)
            VALUES (%s, %s)
        """, (user_id, language))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Language saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# Game Score
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
# Chat
# -------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        message = data.get("message")
        location = data.get("location", "")

        # Translation
        translated = GoogleTranslator(source="auto", target="en").translate(message)

        # Risk detection
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

        # Also save in chat_history
        cur.execute("""
            INSERT INTO chat_history (user_id, message, response, created_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, message, response_text, datetime.datetime.utcnow()))

        # If high risk → create alert
        if risk_level == "high":
            cur.execute("""
                INSERT INTO alerts (user_id, message, created_at)
                VALUES (%s, %s, %s)
            """, (user_id, "High risk detected", datetime.datetime.utcnow()))

        conn.commit()
        cur.close()
        conn.close()

        emergency = check_risk_escalation(user_id)

        support = {}
        if risk_level == "high":
            support["helpline"] = get_helpline(location)

        return jsonify({
            "response": response_text,
            "risk_level": risk_level,
            "emergency": emergency,
            "support": support
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# Voice to Text
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
# Text to Voice
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
# Run
# -------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
