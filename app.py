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
# Database Connection (Postgres)
# -------------------------------
def get_db():
    conn = psycopg2.connect(
        host="localhost",              # or your Render/Postgres host
        database="mindease_db_l1pr",   # your DB name
        user="postgres",               # your DB username
        password="your_password"       # your DB password
    )
    return conn

# -------------------------------
# Home Route (fixes 404 at /)
# -------------------------------
@app.route("/", methods=["GET"])
def home():
    return "MindEase Backend is running 🚀"

# -------------------------------
# Risk Escalation Logic
# -------------------------------
def check_risk_escalation(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT risk_level FROM chats WHERE user_id=%s ORDER BY created_at DESC LIMIT 3", (user_id,))
    risks = [row[0] for row in cur.fetchall()]
    conn.close()
    return risks.count("high") >= 2

# -------------------------------
# Global Helpline Integration
# -------------------------------
def get_global_helpline(location):
    helplines = {
        "India": "📞 National Suicide Helpline (India): 9152987821",
        "US": "📞 National Suicide Prevention Lifeline: 988",
        "UK": "📞 Samaritans: 116 123",
        "Japan": "📞 Tokyo English Lifeline: 03-5774-0992"
    }
    for country, number in helplines.items():
        if country.lower() in location.lower():
            return number
    return "📞 International Helpline: Please search your local emergency number"

# -------------------------------
# Mood Analytics
# -------------------------------
@app.route("/analytics/<int:user_id>", methods=["GET"])
def analytics(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT risk_level, created_at FROM chats WHERE user_id=%s", (user_id,))
    rows = cur.fetchall()
    conn.close()

    summary = {
        "total_chats": len(rows),
        "high_risk_count": sum(1 for r in rows if r["risk_level"] == "high"),
        "trend": [{"risk": r["risk_level"], "time": r["created_at"].isoformat()} for r in rows[-5:]]
    }
    return jsonify(summary)

# -------------------------------
# Gamification
# -------------------------------
@app.route("/game-score", methods=["POST"])
def game_score():
    data = request.json
    user_id = data["user_id"]
    score = data["score"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO scores (user_id, score, created_at) VALUES (%s, %s, %s)",
                (user_id, score, datetime.datetime.now()))
    conn.commit()
    conn.close()

    badge = None
    if score >= 80:
        badge = "Resilience Badge 🏅"
    elif score >= 50:
        badge = "Balance Badge 🌱"

    return jsonify({"message": "Score saved successfully", "badge": badge})

# -------------------------------
# Multilanguage Support
# -------------------------------
def translate_message(message, target_lang="en"):
    return GoogleTranslator(source="auto", target=target_lang).translate(message)

# -------------------------------
# Voice Input/Output
# -------------------------------
@app.route("/voice-to-text", methods=["POST"])
def voice_to_text():
    audio_file = request.files["file"]
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
    return jsonify({"text": text})

@app.route("/text-to-voice", methods=["POST"])
def text_to_voice():
    data = request.json
    text = data["text"]
    lang = data.get("lang", "en")
    tts = gTTS(text, lang=lang)
    filename = "response.mp3"
    tts.save(filename)

    # Log into voice_logs
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO voice_logs (user_id, transcript, audio_file, created_at) VALUES (%s, %s, %s, %s)",
                (data["user_id"], text, filename, datetime.datetime.now()))
    conn.commit()
    conn.close()

    return jsonify({"audio_file": filename})

# -------------------------------
# Chat Endpoint
# -------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_id = data["user_id"]
    message = data["message"]
    location = data.get("location", "")

    translated_msg = translate_message(message, "en")
    ai_response = f"I understand you said: {translated_msg}"

    risk_level = "high" if "die" in translated_msg.lower() else "low"

    support = {}
    if risk_level == "high":
        support["helpline"] = get_global_helpline(location)

        try:
            nominatim_url = f"https://nominatim.openstreetmap.org/search?format=json&q=psychologist+near+{location}"
            response = requests.get(nominatim_url, headers={"User-Agent": "MindEaseApp/1.0"})
            results = response.json()
            nearby = []
            for place in results[:3]:
                lat, lon = place.get("lat"), place.get("lon")
                osm_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
                nearby.append({
                    "name": place.get("display_name"),
                    "link": osm_link
                })
            support["nearby_psychologists"] = nearby
            support["maps_link"] = f"https://www.openstreetmap.org/search?query=psychologist+near+{location}"
        except Exception:
            support["maps_link"] = f"https://www.openstreetmap.org/search?query=psychologist+near+{location}"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO chats (user_id, message, response, risk_level, created_at) VALUES (%s, %s, %s, %s, %s)",
                (user_id, message, ai_response, risk_level, datetime.datetime.now()))
    conn.commit()
    conn.close()

    emergency = check_risk_escalation(user_id)
    final_response = translate_message(ai_response, "auto")

    return jsonify({
        "response": final_response,
        "risk_level": risk_level,
        "emergency": emergency,
        "support": support
    })

if __name__ == "__main__":
    app.run(debug=True)
