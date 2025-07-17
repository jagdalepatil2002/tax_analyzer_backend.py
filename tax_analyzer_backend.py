# --- Final Backend Server (tax_analyzer_backend.py) ---
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
    """Creates or alters the users table to include new fields."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                # Create table if it doesn't exist
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
                # Add new columns if they don't exist
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS dob DATE;")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(25);")
                conn.commit()
                print("'users' table checked/updated successfully.")
        except psycopg2.Error as e:
            print(f"Error creating/altering table: {e}")
        finally:
            conn.close()

# --- PDF & AI Helper Functions (Unchanged) ---
def extract_text_from_pdf(pdf_bytes):
    text_content = ""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf_document:
            for page in pdf_document: text_content += page.get_text()
        return text_content
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return None

def call_gemini_api(text):
    prompt = f"""
    You are an expert tax notice summarizer. Analyze the following text extracted from an IRS tax notice and return a JSON object with the summary.
    The JSON object must have the following keys: "noticeFor", "address", "ssn", "amountDue", "payBy", "reason", "details", "fixSteps", "paymentOptions", "helpNumber".
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
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

# --- API Endpoints ---
@app.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    required_fields = ['firstName', 'lastName', 'email', 'password', 'dob', 'mobileNumber']
    if not data or not all(k in data for k in required_fields):
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    first_name = data['firstName']
    last_name = data['lastName']
    email = data['email']
    password = data['password']
    dob = data['dob']
    mobile_number = data['mobileNumber']
    
    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database connection error."}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            if cur.fetchone():
                return jsonify({"success": False, "message": "This email address is already in use."}), 409
            
            cur.execute(
                "INSERT INTO users (first_name, last_name, email, password_hash, dob, mobile_number) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, first_name, email;",
                (first_name, last_name, email, password_hash, dob, mobile_number)
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
    # Use the PORT environment variable provided by Render
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
