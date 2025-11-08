from flask import Flask, render_template, request, jsonify, session
import cv2
import face_recognition
import os
import pickle
import pandas as pd
import sqlite3
from datetime import datetime
import openai
import threading
from twilio.rest import Client
import base64
import numpy as np
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================
# CONFIG & DIRECTORIES
# ============================
EMPLOYEE_DIR = "employee_data"
ENCODING_FILE = "encodings.pkl"
DB_FILE = "attendance.db"

os.makedirs(EMPLOYEE_DIR, exist_ok=True)

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Global for WhatsApp replies
whatsapp_replies = {}

# Global for visitor chatbot states
visitor_states = {}

# Global queue for pending visitor IDs waiting for WhatsApp replies
pending_vids = []

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ============================
# DATABASE SETUP
# ============================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            date TEXT,
            time TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            whom_to_meet TEXT,
            status TEXT,
            date TEXT,
            time TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            encoding BLOB
        )
    """)
    conn.commit()
    conn.close()

# ============================
# ENCODING STORAGE
# ============================
def load_encodings():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name, encoding FROM employees")
    rows = cur.fetchall()
    conn.close()
    names = [row[0] for row in rows]
    encodings = [pickle.loads(row[1]) for row in rows]
    return encodings, names

def save_encodings(encodings, names):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM employees")  # Clear existing
    for name, encoding in zip(names, encodings):
        cur.execute("INSERT INTO employees (name, encoding) VALUES (?, ?)", (name, pickle.dumps(encoding)))
    conn.commit()
    conn.close()

# ============================
# EMPLOYEE REGISTRATION
# ============================
@app.route('/add_employee', methods=['POST'])
def add_employee():
    try:
        data = request.json
        name = data.get('name')
        image_data = data.get('image')

        if not name or not image_data:
            return jsonify({'success': False, 'message': 'Name and image required'})

        # Decode base64 image
        image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        image = np.array(image)

        # Ensure RGB (PIL is RGB, but convert if needed)
        if image.shape[2] == 4:  # RGBA
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        elif image.shape[2] == 3:  # RGB
            pass
        else:
            return jsonify({'success': False, 'message': 'Unsupported image format'})

        # Encode face
        encodings = face_recognition.face_encodings(image)
        if not encodings:
            return jsonify({'success': False, 'message': 'No face detected'})

        encoding = encodings[0]
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO employees (name, encoding) VALUES (?, ?)", (name, pickle.dumps(encoding)))
            conn.commit()
            return jsonify({'success': True, 'message': f'Employee {name} added'})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': 'Employee name already exists'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# ============================
# ATTENDANCE MARKING
# ============================
def mark_attendance(name):
    now = datetime.now()
    date, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT * FROM attendance WHERE name=? AND date=?", (name, date))
    if cur.fetchone():
        conn.close()
        return

    cur.execute("INSERT INTO attendance (name, date, time) VALUES (?, ?, ?)", (name, date, time_str))
    conn.commit()
    conn.close()

# ============================
# VISITOR HANDLING
# ============================
def send_message(to, message, visitor_id):
    phone_number = "+916260065139"  # Hardcoded for demo
    try:
        # Assuming app is running on localhost:5000, but for Twilio, need public URL (e.g., via ngrok)
        status_callback_url = "https://your-ngrok-url.ngrok.io/whatsapp/status"  # Replace with actual public URL
        twilio_message = twilio_client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{phone_number}",
            status_callback=status_callback_url
        )
        whatsapp_replies[visitor_id] = None  # Initialize
        pending_vids.append(visitor_id)  # Add to queue
        print(f"WhatsApp message sent to {to}: {twilio_message.body}")
    except Exception as e:
        print(f"Failed to send WhatsApp message: {e}")

def get_ai_approval(visitor_name, whom_to_meet, reply=None):
    prompt = f"""
    Visitor {visitor_name} wants to meet {whom_to_meet}.
    {f'Reply from {whom_to_meet}: {reply}' if reply else 'No reply yet.'}
    Decide approval: yes or no, with reason.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an AI assistant deciding visitor access."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50
        )
        reply_text = response.choices[0].message.content.strip().lower()
        return "yes" in reply_text
    except Exception as e:
        print(f"AI Error: {e}")
        return False

# ============================
# ATTENDANCE CAPTURE
# ============================
@app.route('/live_capture', methods=['POST'])
def capture_attendance():
    try:
        data = request.json
        image_data = data.get('image')

        if not image_data:
            return jsonify({'success': False, 'message': 'Image required'})

        # Decode base64 image
        image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        frame = np.array(image)

        # Ensure RGB
        if frame.shape[2] == 4:  # RGBA
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        elif frame.shape[2] == 3:  # RGB
            pass
        else:
            return jsonify({'success': False, 'message': 'Unsupported image format'})

        known_encodings, known_names = load_encodings()
        if not known_encodings:
            return jsonify({'success': False, 'message': 'No employees registered'})

        face_locations = face_recognition.face_locations(frame)
        face_encodings = face_recognition.face_encodings(frame, face_locations)

        results = []
        for face_encoding in face_encodings:
            distances = face_recognition.face_distance(known_encodings, face_encoding)
            match_index = distances.argmin() if len(distances) > 0 else None

            if match_index is not None and distances[match_index] < 0.5:
                name = known_names[match_index]
                mark_attendance(name)
                results.append({'type': 'employee', 'name': name})
            else:
                # Visitor
                visitor_id = f"visitor_{datetime.now().timestamp()}"
                results.append({'type': 'visitor', 'id': visitor_id})

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# ============================
# WHATSAPP STATUS CALLBACK
# ============================
@app.route('/whatsapp/status', methods=['POST'])
def whatsapp_status():
    message_sid = request.values.get('MessageSid')
    message_status = request.values.get('MessageStatus')
    to_number = request.values.get('To')

    print(f"Status update for {message_sid}: {message_status} to {to_number}")

    # Here you can log to DB or handle based on status (e.g., delivered, failed)
    # For now, just print/log

    return '', 200

# ============================
# WHATSAPP WEBHOOK
# ============================
@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    from_number = request.values.get('From')
    body = request.values.get('Body')

    # Remove whatsapp: prefix if present
    if from_number.startswith('whatsapp:'):
        from_number = from_number[+9:]

    print(f"Incoming WhatsApp message from {from_number}: {body}")

    # Search for visitor or employee based on phone number
    # For demo, assume phone_number is hardcoded, but in real app, store phone numbers in DB
    # Check if from_number matches any known employee or visitor

    # Check if reply is from the hardcoded employee phone number
    phone_number = "+916260065139"  # Hardcoded for demo
    if from_number == phone_number and pending_vids:
        vid = pending_vids.pop(0)  # Get the first pending visitor ID
        whatsapp_replies[vid] = body
        print(f"WhatsApp reply stored for visitor {vid}: {body}")
    else:
        # If no active visitor or not from expected number, treat as new message or general query
        # Could search DB for employee/visitor by phone number
        print(f"No active visitor found for reply from {from_number}")

    return '', 200

# ============================
# CHATBOT STATUS
# ============================
@app.route('/chatbot/status', methods=['GET'])
def chatbot_status():
    visitor_id = request.args.get('visitor_id')
    if not visitor_id:
        return jsonify({'reply': None})

    reply = whatsapp_replies.get(visitor_id)
    if reply:
        # Process the reply once received
        state = visitor_states.get(visitor_id)
        if state and state['step'] == 'process':
            state['step'] = 'done'
            visitor_name = state['visitor_name']
            whom_to_meet = state['visitor_whom']
            approved = get_ai_approval(visitor_name, whom_to_meet, reply)
            status = "Approved" if approved else "Denied"
            # Save to DB
            now = datetime.now()
            date, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("INSERT INTO visitors (name, whom_to_meet, status, date, time) VALUES (?, ?, ?, ?, ?)",
                        (visitor_name, whom_to_meet, status, date, time_str))
            conn.commit()
            conn.close()
            response = f"Reply from {whom_to_meet}: {reply}\nAI Decision: {status}"
            if approved:
                response += "\nGate opened."
            else:
                response += "\nAccess denied."
            return jsonify({'reply': response})
    return jsonify({'reply': None})

# ============================
# CHATBOT
# ============================
@app.route('/chatbot', methods=['POST'])
def chatbot():
    try:
        data = request.json
        user_input = data.get('message')
        visitor_id = data.get('visitor_id')

        if not visitor_id:
            # Generate a new visitor_id for visitor flow
            visitor_id = f"visitor_{datetime.now().timestamp()}"
            visitor_states[visitor_id] = {'step': 'greeting'}

        # Always use visitor flow
        if visitor_id not in visitor_states:
            visitor_states[visitor_id] = {'step': 'greeting'}

        state = visitor_states[visitor_id]
        step = state['step']

        if step == 'greeting':
            state['step'] = 'ask_both'
            return jsonify({'reply': 'What is your name? Kisse milna hai? (Whom do you want to meet?)', 'visitor_id': visitor_id})
        elif step == 'ask_both':
            # Use AI to parse name and whom from user_input
            prompt = f"Extract the visitor's name and whom they want to meet from this message: '{user_input}'. Respond with 'Name: [name], Whom: [whom]'."
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an AI assistant that extracts information from text."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=50
                )
                parsed = response.choices[0].message.content.strip()
                # Simple parse, assume format "Name: ..., Whom: ..."
                if "Name:" in parsed and "Whom:" in parsed:
                    name_part = parsed.split("Name:")[1].split(",")[0].strip()
                    whom_part = parsed.split("Whom:")[1].strip()
                    state['visitor_name'] = name_part
                    state['visitor_whom'] = whom_part
                    state['step'] = 'process'
                    visitor_name = state['visitor_name']
                    whom_to_meet = state['visitor_whom']
                    message = f"Visitor {visitor_name} is here to meet you."
                    send_message(whom_to_meet, message, visitor_id)
                    return jsonify({'reply': 'WhatsApp message sent. Waiting for response...', 'visitor_id': visitor_id})
                else:
                    return jsonify({'reply': 'Please provide your name and whom you want to meet clearly.', 'visitor_id': visitor_id})
            except Exception as e:
                return jsonify({'reply': f'Error parsing input: {str(e)}', 'visitor_id': visitor_id})
        elif step == 'process':
            # Reply will be checked via polling in frontend
            return jsonify({'reply': 'Still waiting for WhatsApp reply...', 'visitor_id': visitor_id})
        else:
            # After done, allow additional queries
            reply = chatbot_query(user_input)
            return jsonify({'reply': reply, 'visitor_id': visitor_id})
    except Exception as e:
        return jsonify({'reply': f'Error: {str(e)}'})

def chatbot_query(user_input):
    today_entries = get_today_entries()
    employee_count = count_registered_employees()
    _, known_names = load_encodings()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name, whom_to_meet, status, date, time FROM visitors ORDER BY id DESC LIMIT 10")
    visitor_entries = cur.fetchall()
    conn.close()

    context = f"""
    Current data:
    - Today's entries: {today_entries}
    - Number of registered employees: {employee_count}
    - Registered employees: {known_names}
    - Recent visitors: {visitor_entries}

    User query: {user_input}

    Respond naturally.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for an attendance system."},
                {"role": "user", "content": context}
            ],
            max_tokens=150
        )
        reply = response.choices[0].message.content.strip()

        if "mark attendance" in user_input.lower() and "for" in user_input.lower():
            name = user_input.split("for")[-1].strip()
            if mark_manual_attendance(name):
                reply += f"\nAttendance marked for {name}."
            else:
                reply += f"\nAttendance already marked for {name} today."

        return reply
    except Exception as e:
        return f"Error: {str(e)}"

def get_today_entries():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name, time FROM attendance WHERE date=?", (today,))
    rows = cur.fetchall()
    conn.close()
    return rows

def count_registered_employees():
    known_encodings, known_names = load_encodings()
    return len(known_names)

def mark_manual_attendance(name):
    now = datetime.now()
    date, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT * FROM attendance WHERE name=? AND date=?", (name, date))
    if cur.fetchone():
        conn.close()
        return False

    cur.execute("INSERT INTO attendance (name, date, time) VALUES (?, ?, ?)", (name, date, time_str))
    conn.commit()
    conn.close()
    return True

# ============================
# WEB ROUTES
# ============================
@app.route('/')
def home():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, name, date, time FROM attendance ORDER BY id DESC LIMIT 100")
    rows = cur.fetchall()
    conn.close()
    return render_template('home.html', attendance=rows)

@app.route('/admin_dashboard')
def hr_dashboard():
    name_filter = request.args.get('name', '')
    date_filter = request.args.get('date', '')

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    query = "SELECT id, name, date, time FROM attendance WHERE 1=1"
    params = []
    if name_filter:
        query += " AND name LIKE ?"
        params.append(f'%{name_filter}%')
    if date_filter:
        query += " AND date = ?"
        params.append(date_filter)
    query += " ORDER BY id DESC LIMIT 100"

    cur.execute(query, params)
    attendance_rows = cur.fetchall()

    cur.execute("SELECT id, name FROM employees ORDER BY name")
    employee_rows = cur.fetchall()

    conn.close()
    return render_template('hr_dashboard.html', attendance=attendance_rows, employees=employee_rows, name_filter=name_filter, date_filter=date_filter)

# ============================
# WEB ROUTES
# ============================
@app.route('/manage_employee', methods=['POST'])
def manage_employee():
    action = request.form.get('action')
    employee_id = request.form.get('id')
    name = request.form.get('name')

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if action == 'add':
        # Add new employee (requires image, but for simplicity, assume name only, encoding later)
        # In real, need to handle image upload
        return jsonify({'success': False, 'message': 'Add via home page'})

    elif action == 'update':
        if not employee_id or not name:
            return jsonify({'success': False, 'message': 'ID and name required'})
        cur.execute("UPDATE employees SET name=? WHERE id=?", (name, employee_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Employee updated'})

    elif action == 'delete':
        if not employee_id:
            return jsonify({'success': False, 'message': 'ID required'})
        cur.execute("DELETE FROM employees WHERE id=?", (employee_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Employee deleted'})

    conn.close()
    return jsonify({'success': False, 'message': 'Invalid action'})

@app.route('/chatbot_page')
def chatbot_page():
    return render_template('chatbot.html')

# ============================
# MAIN
# ============================
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
