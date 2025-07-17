# --- Part 1: Final Backend Server (tax_analyzer_backend.py) ---
# This file should be in your GitHub repository connected to Render.

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import fitz
import requests 
import json
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

# --- Database Connection Details (from Environment Variables) ---
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_SSL_MODE = os.getenv("DB_SSL_MODE", "require")

# --- Gemini API Details (from Environment Variables) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

def get_db_connection():
    """Establishes a secure connection to the PostgreSQL database."""
    if not all([DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME]):
        print("FATAL ERROR: Database environment variables are not fully set.")
        return None
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, dbname=DB_NAME, sslmode=DB_SSL_MODE,
            cursor_factory=RealDictCursor
        )
        return conn
    except psycopg2.Error as e:
        print(f"DATABASE CONNECTION FAILED: {e}")
        return None

def initialize_database():
    """Creates or alters the users table to include new fields."""
    conn = get_db_connection()
    if not conn:
        print("Could not initialize database, connection failed.")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    dob DATE,
                    mobile_number VARCHAR(25)
                );
            """)
            conn.commit()
            print("Database schema verified successfully.")
    except psycopg2.Error as e:
        print(f"DATABASE SCHEMA ERROR: {e}")
    finally:
        conn.close()

def extract_text_from_pdf(pdf_bytes):
    """Extracts text from a PDF."""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return "".join(page.get_text() for page in doc)
    except Exception as e:
        print(f"PDF EXTRACTION ERROR: {e}")
        return None

def call_gemini_api(text):
    """Calls the Gemini API to summarize the extracted text."""
    # FIX: Updated prompt to request the final detailed JSON structure.
    prompt = f"""
    You are an expert tax notice summarizer. Analyze the following text from an IRS notice. Your task is to extract specific information and format it as a single JSON object.

    Based on the text provided, find the following fields:
    1.  `noticeType`: The notice code, like "CP503C".
    2.  `noticeFor`: The full name of the taxpayer.
    3.  `address`: The full address of the taxpayer, with newlines as \\n.
    4.  `ssn`: The Social Security Number, masked (e.g., NNN-NN-NNNN).
    5.  `amountDue`: The final total amount due as a string (e.g., "$9,533.53").
    6.  `payBy`: The payment due date as a string (e.g., "August 20, 2018").
    7.  `breakdown`: An array of objects, where each object has an "item" and "amount" key, detailing the charges. Example: [{{"item": "Amount you previously owed", "amount": "$9,444.07"}}, {{"item": "Failure-to-Pay Penalty", "amount": "+ $34.98"}}]
    8.  `noticeMeaning`: A concise, 2-line explanation of what this specific notice type means.
    9.  `whyText`: A paragraph explaining why the user received this notice.
    10. `fixSteps`: An object with two keys, "agree" and "disagree", each containing a string explaining what to do.
    11. `paymentOptions`: An object with keys "online", "mail", and "plan", each containing a string with the payment instructions.
    12. `helpInfo`: An object with keys "contact" and "advocate", each containing a string with the help information.

    Here is the text:
    ---
    {text}
    ---
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(GEMINI_API_URL, json=payload, timeout=45)
        response.raise_for_status()
        result = response.json()
        summary_json_string = result['candidates'][0]['content']['parts'][0]['text']
        if summary_json_string.strip().startswith("```json"):
            summary_json_string = summary_json_string.strip()[7:-3]
        return summary_json_string
    except Exception as e:
        print(f"GEMINI API ERROR: {e}")
        return None

@app.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    required_fields = ['firstName', 'lastName', 'email', 'password', 'dob', 'mobileNumber']
    if not data or not all(k in data for k in required_fields):
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    password_hash = generate_password_hash(data['password'])
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database connection error."}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s;", (data['email'],))
            if cur.fetchone():
                return jsonify({"success": False, "message": "This email address is already in use."}), 409
            
            sql = """
                INSERT INTO users (first_name, last_name, email, password_hash, dob, mobile_number) 
                VALUES (%s, %s, %s, %s, %s, %s) 
                RETURNING id, first_name, email;
            """
            cur.execute(sql, (data['firstName'], data['lastName'], data['email'], password_hash, data['dob'], data['mobileNumber']))
            new_user = cur.fetchone()
            conn.commit()
            return jsonify({"success": True, "user": new_user}), 201
    except psycopg2.Error as e:
        print(f"REGISTRATION DB ERROR: {e}")
        return jsonify({"success": False, "message": "An internal error occurred."}), 500
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data or not all(k in data for k in ['email', 'password']):
        return jsonify({"success": False, "message": "Missing email or password."}), 400
    
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database connection error."}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s;", (data['email'],))
            user = cur.fetchone()
            if user and check_password_hash(user['password_hash'], data['password']):
                user_data = {"id": user['id'], "firstName": user['first_name'], "email": user['email']}
                return jsonify({"success": True, "user": user_data}), 200
            else:
                return jsonify({"success": False, "message": "Invalid email or password."}), 401
    except psycopg2.Error as e:
        print(f"LOGIN DB ERROR: {e}")
        return jsonify({"success": False, "message": "An internal error occurred."}), 500
    finally:
        conn.close()

@app.route('/summarize', methods=['POST'])
def summarize_notice():
    if 'notice_pdf' not in request.files:
        return jsonify({"success": False, "message": "No PDF file provided."}), 400
    
    file = request.files['notice_pdf']
    pdf_bytes = file.read()
    raw_text = extract_text_from_pdf(pdf_bytes)
    if not raw_text:
        return jsonify({"success": False, "message": "Could not read text from PDF."}), 500

    summary_json = call_gemini_api(raw_text)
    if not summary_json:
        return jsonify({"success": False, "message": "Failed to get summary from AI."}), 500
        
    try:
        summary_data = json.loads(summary_json)
        return jsonify({"success": True, "summary": summary_data}), 200
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "AI returned an invalid format."}), 500

with app.app_context():
    initialize_database()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
```react
