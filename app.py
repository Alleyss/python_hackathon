from flask import Flask, render_template, request, jsonify
from chatbot import chatbot_response
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__)

# Initialize Firebase Admin SDK
# TODO: Download your Service Account Key from Firebase Console -> Project Settings -> Service Accounts
# and save it as 'serviceAccountKey.json' in this folder.
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    print("Firebase Admin Initialized")
except Exception as e:
    print(f"Warning: Firebase Admin not initialized. Token verification will fail. {e}")

import sqlite3
import os
import time
import uuid
import json
import requests
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

# Database Setup
DB_NAME = "chatbot_v2.db"
UPLOAD_FOLDER = "uploads"
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Chats Table
    c.execute('''CREATE TABLE IF NOT EXISTS chats
                 (id TEXT PRIMARY KEY,
                  user_id TEXT,
                  title TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Messages Table (Updated with chat_id)
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  chat_id TEXT,
                  user_id TEXT,
                  sender TEXT,
                  content TEXT,
                  file_path TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(chat_id) REFERENCES chats(id))''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return render_template("index.html")

# --- API Endpoints ---

@app.route("/new_chat", methods=["POST"])
def new_chat():
    token = request.form.get("token")
    user_id = "anonymous"
    try:
        if token:
            decoded_token = auth.verify_id_token(token)
            user_id = decoded_token['uid']
    except:
        pass

    chat_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO chats (id, user_id, title) VALUES (?, ?, ?)", (chat_id, user_id, "New Chat"))
    conn.commit()
    conn.close()
    return jsonify({"chat_id": chat_id})

@app.route("/get_chats", methods=["POST"])
def get_chats():
    token = request.form.get("token")
    user_id = "anonymous"
    try:
        if token:
            decoded_token = auth.verify_id_token(token)
            user_id = decoded_token['uid']
    except:
        pass # Return empty or anon chats

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, title FROM chats WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    chats = [{"id": row[0], "title": row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify(chats)

@app.route("/get_messages", methods=["POST"])
def get_messages():
    chat_id = request.form.get("chat_id")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT sender, content, file_path, timestamp FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    messages = [{"sender": row[0], "content": row[1], "file_path": row[2], "timestamp": row[3]} for row in c.fetchall()]
    conn.close()
    return jsonify(messages)

@app.route("/get_weather", methods=["POST"])
def get_weather():
    city = request.form.get("city")
    if not city:
        return jsonify({"error": "City is required"}), 400
    
    try:
        url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={city}&aqi=no"
        response = requests.get(url)
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_response", methods=["POST"])
def get_response():
    user_input = request.form.get("user_input")
    token = request.form.get("token")
    chat_id = request.form.get("chat_id")
    file = request.files.get("file")
    
    # Verify Token
    user_id = "anonymous"
    try:
        if token:
            decoded_token = auth.verify_id_token(token)
            user_id = decoded_token['uid']
    except Exception as e:
        print(f"Token verification failed: {e}")

    # Handle File Upload
    file_path = None
    mime_type = None
    if file and file.filename:
        filename = secure_filename(f"{int(time.time())}_{file.filename}")
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        mime_type = file.mimetype

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Ensure Chat ID exists (or create if missing/invalid)
    if not chat_id:
        chat_id = str(uuid.uuid4())
        c.execute("INSERT INTO chats (id, user_id, title) VALUES (?, ?, ?)", (chat_id, user_id, "New Chat"))
    
    # Update Title if it's "New Chat" and this is the first user message
    c.execute("SELECT count(*) FROM messages WHERE chat_id = ?", (chat_id,))
    count = c.fetchone()[0]
    if count == 0:
        # Generate simple title from first few words
        new_title = (user_input[:30] + '...') if len(user_input) > 30 else user_input
        c.execute("UPDATE chats SET title = ? WHERE id = ?", (new_title, chat_id))
        conn.commit() # Commit title change immediately

    # Fetch Chat History for Context
    c.execute("SELECT sender, content FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    rows = c.fetchall()
    history = []
    for row in rows:
        role = "user" if row[0] == "user" else "model"
        history.append({"role": role, "parts": [row[1]]})

    # Save User Message
    c.execute("INSERT INTO messages (chat_id, user_id, sender, content, file_path) VALUES (?, ?, ?, ?, ?)",
              (chat_id, user_id, "user", user_input, file_path))
    conn.commit()

    # Get Bot Response (Pass history)
    response_text = chatbot_response(user_input, file_path, mime_type, history)

    # Save Bot Message
    c.execute("INSERT INTO messages (chat_id, user_id, sender, content, file_path) VALUES (?, ?, ?, ?, ?)",
              (chat_id, user_id, "bot", response_text, None))
    conn.commit()
    conn.close()

    return jsonify({"response": response_text, "chat_id": chat_id})

if __name__ == "__main__":
    app.run(debug=True)
