from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import requests
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
    return "MindEase Backend is running 🚀"


# -------------------------------
# Risk Escalation Logic
# -------------------------------
def check_risk_escalation(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT risk_level FROM chats WHERE user_id=%s ORDER BY created_at DESC LIMIT 3",
            (user_id,),
        )
        risks = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return risks.count("high") >= 2
    except Exception:
        return False


# -------------------------------
# Helpline
# -------------------------------
def get_global_helpline(location):
    helplines = {
        "india": "📞 National Suicide Helpline (India): 9152987821",
        "us": "📞 National Suicide Prevention Lifeline: 988",
        "uk": "📞 Samaritans: 116 123",
        "japan": "📞 Tokyo English Lifeline: 03-5774-0992"
    }

    location = location.lower()
    for country in helplines:
        if country in location:
            return helplines[country]

    return "📞 Please contact your local emergency helpline"


# -------------------------------
# Analytics
# -------------------------------
@app.route("/analytics/<int:user_id>", methods=["GET"])
def analytics(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(
            "SELECT risk_level, created_at FROM chats WHERE user_id=%s",
            (user_id,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify({
            "total_chats": len(rows),
            "high_risk_count": sum(1 for r in rows if r["risk_level"] == "high"),
            "recent_trend": [
                {
                    "risk": r["risk_level"],
                    "time": r["created_at"].isoformat()
                }
                for r in rows[-5:]
            ]
        })

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
        cur.execute(
            "INSERT INTO scores (user_id, score, created_at) VALUES (%s, %s, %s)",
            (user_id, score, datetime.datetime.utcnow())
        )
        conn.commit()
        cur.close()
        conn.close()

        badge = None
        if score >= 80:
            badge = "Resilience Badge 🏅"
        elif score >= 50:
            badge = "Balance Badge 🌱"

        return jsonify({"message": "Score saved", "badge": badge})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# Translation
# -------------------------------
def translate_message(message, target_lang="en"):
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(message)
    except Exception:
        return message


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
        lang = data.get("lang", "en")
        user_id = data.get("user_id")

        tts = gTTS(text=text, lang=lang)
        filename = "response.mp3"
        tts.save(filename)

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO voice_logs (user_id, transcript, audio_file, created_at) VALUES (%s, %s, %s, %s)",
            (user_id, text, filename, datetime.datetime.utcnow())
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"audio_file": filename})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# Chat Endpoint
# -------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        message = data.get("message")
        location = data.get("location", "")

        translated = translate_message(message, "en")
        ai_response = f"I understand you said: {translated}"

        risk_level = "high" if any(word in translated.lower() for word in ["die", "suicide", "kill"]) else "low"

        support = {}
        if risk_level == "high":
            support["helpline"] = get_global_helpline(location)

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chats (user_id, message, response, risk_level, created_at) VALUES (%s, %s, %s, %s, %s)",
            (user_id, message, ai_response, risk_level, datetime.datetime.utcnow())
        )
        conn.commit()
        cur.close()
        conn.close()

        emergency = check_risk_escalation(user_id)

        return jsonify({
            "response": ai_response,
            "risk_level": risk_level,
            "emergency": emergency,
            "support": support
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# Run (local only)
# -------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
