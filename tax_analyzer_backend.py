# --- Part 1: Backend Server (tax_analyzer_backend.py) ---
# To run this:
# 1. Install dependencies: pip install Flask Flask-Cors psycopg2-binary Werkzeug PyMuPDF requests python-dotenv
# 2. Create a .env file in the same directory with your database credentials (see below)
# 3. Run the script: python tax_analyzer_backend.py

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import fitz  # PyMuPDF
import requests 
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- Database Connection Details (Read from Environment Variables) ---
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_SSL_MODE = os.getenv("DB_SSL_MODE", "require")

# --- Gemini API Details (Read from Environment Variables) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"


# --- Database Helper Functions ---

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    if not all([DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME]):
        print("Error: Database environment variables are not fully set.")
        return None
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, dbname=DB_NAME, sslmode=DB_SSL_MODE,
            cursor_factory=RealDictCursor
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def create_users_table():
    """Creates the users table in the database if it doesn't already exist."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        first_name VARCHAR(100) NOT NULL,
                        last_name VARCHAR(100) NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                print("'users' table checked/created successfully.")
        except psycopg2.Error as e:
            print(f"Error creating table: {e}")
        finally:
            conn.close()

# --- PDF & AI Helper Functions ---

def extract_text_from_pdf(pdf_bytes):
    """Extracts text from a PDF."""
    text_content = ""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf_document:
            for page in pdf_document:
                text_content += page.get_text()
        return text_content
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return None

def call_gemini_api(text):
    """Calls the Gemini API to summarize the extracted text."""
    prompt = f"""
    You are an expert tax notice summarizer. Analyze the following text extracted from an IRS tax notice and return a JSON object with the summary.
    The JSON object must have the following keys: "noticeFor", "address", "ssn", "amountDue", "payBy", "reason", "details", "fixSteps", "paymentOptions", "helpNumber".
    - "noticeFor": The full name of the taxpayer.
    - "address": The full address of the taxpayer, with newlines as \\n.
    - "ssn": The Social Security Number, masked (e.g., XXX-XX-1234).
    - "amountDue": The total amount due as a string (e.g., "$4,760.91").
    - "payBy": The payment due date as a string (e.g., "June 10, 2019").
    - "reason": A single, clear sentence explaining the primary reason for the notice.
    - "details": An array of strings providing specific bullet points about the changes.
    - "fixSteps": An object with two keys, "agree" and "disagree", explaining what to do in each case.
    - "paymentOptions": An object with keys "online", "mail", and "plan".
    - "helpNumber": The main contact number provided in the notice.

    Here is the text:
    ---
    {text}
    ---
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(GEMINI_API_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        summary_json_string = result['candidates'][0]['content']['parts'][0]['text']
        if summary_json_string.strip().startswith("```json"):
            summary_json_string = summary_json_string.strip()[7:-3]
        return summary_json_string
    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        return None


# --- API Endpoints ---

@app.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if not data or not all(k in data for k in ['firstName', 'lastName', 'email', 'password']):
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    first_name, last_name, email, password = data['firstName'], data['lastName'], data['email'], data['password']
    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database connection error."}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            if cur.fetchone():
                return jsonify({"success": False, "message": "This email address is already in use."}), 409
            
            cur.execute(
                "INSERT INTO users (first_name, last_name, email, password_hash) VALUES (%s, %s, %s, %s) RETURNING id, first_name, email;",
                (first_name, last_name, email, password_hash)
            )
            new_user = cur.fetchone()
            conn.commit()
            return jsonify({"success": True, "user": new_user}), 201
    except psycopg2.Error as e:
        print(f"Database error during registration: {e}")
        return jsonify({"success": False, "message": "An internal error occurred."}), 500
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data or not all(k in data for k in ['email', 'password']):
        return jsonify({"success": False, "message": "Missing email or password."}), 400
    
    email, password = data['email'], data['password']
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database connection error."}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
            user = cur.fetchone()
            if user and check_password_hash(user['password_hash'], password):
                user_data = {"id": user['id'], "firstName": user['first_name'], "email": user['email']}
                return jsonify({"success": True, "user": user_data}), 200
            else:
                return jsonify({"success": False, "message": "Invalid email or password."}), 401
    except psycopg2.Error as e:
        print(f"Database error during login: {e}")
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

# --- Main Execution ---
if __name__ == '__main__':
    create_users_table()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
