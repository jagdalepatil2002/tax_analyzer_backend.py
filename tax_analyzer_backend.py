# --- Part 1: Backend Server (tax_analyzer_backend.py) ---
# To run this:
# 1. Install dependencies: pip install Flask Flask-Cors psycopg2-binary Werkzeug PyMuPDF Pillow requests python-dotenv
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
    app.run(debug=True, port=5000)

```react
// --- Part 2: Frontend Application (App.js) ---
// This React code is now designed to communicate with the Python backend server.

import React, { useState, useEffect } from 'react';

// --- API Functions (Now making real fetch calls) ---
const API_BASE_URL = 'http://127.0.0.1:5000'; // URL of our Python backend

const api = {
  async register(payload) {
    const response = await fetch(`${API_BASE_URL}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return response.json();
  },

  async login(payload) {
    const response = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return response.json();
  },
  
  async summarize(file) {
    const formData = new FormData();
    formData.append('notice_pdf', file);
    
    const response = await fetch(`${API_BASE_URL}/summarize`, {
      method: 'POST',
      body: formData,
    });
    return response.json();
  },
};


// --- Helper Components & Icons (Same as before) ---
const FileHeart = (props) => (
  <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 22h14a2 2 0 0 0 2-2V7.5L14.5 2H6a2 2 0 0 0-2 2v4" />
    <path d="M14 2v6h6" />
    <path d="M10.3 12.3c.8-1 2-1.5 3.2-1.5 2.2 0 4 1.8 4 4 0 2.5-3.4 4.9-5.2 6.2a.5.5 0 0 1-.6 0C10 19.4 6 17 6 14.5c0-2.2 1.8-4 4-4 .8 0 1.5.3 2.1.8" />
  </svg>
);
const LoadingSpinner = () => (
    <div className="flex flex-col items-center justify-center space-y-4">
        <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-purple-600"></div>
        <p className="text-purple-700 font-semibold">Analyzing your notice...</p>
    </div>
);


// --- Screen Components (AuthScreen, UploadScreen, SummaryScreen - mostly unchanged) ---
const AuthScreen = ({ isLogin, handleLogin, handleRegister, error, firstName, setFirstName, lastName, setLastName, email, setEmail, password, setPassword, confirmPassword, setConfirmPassword, setView, clearFormFields}) => (
    <div className="bg-white p-8 sm:p-10 rounded-2xl shadow-lg border border-gray-100 max-w-md w-full" style={{ backgroundColor: '#F9F5FF' }}>
        <h2 className="text-3xl font-bold text-center text-purple-800 mb-1">{isLogin ? "Hello There!" : "Create Your Account"}</h2>
        <p className="text-center text-purple-600 mb-8">{isLogin ? "Let's get you signed in." : "Join us to simplify your tax notices."}</p>
        <form onSubmit={isLogin ? handleLogin : handleRegister} className="space-y-4">
            {!isLogin && (
                <div className="grid grid-cols-2 gap-4">
                    <input type="text" placeholder="First Name" value={firstName} onChange={e => setFirstName(e.target.value)} className="w-full px-4 py-3 bg-white border-2 border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500" required />
                    <input type="text" placeholder="Last Name" value={lastName} onChange={e => setLastName(e.target.value)} className="w-full px-4 py-3 bg-white border-2 border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500" required />
                </div>
            )}
            <input type="email" placeholder="Your Email" value={email} onChange={e => setEmail(e.target.value)} className="w-full px-4 py-3 bg-white border-2 border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500" required />
            <input type="password" placeholder="Your Password" value={password} onChange={e => setPassword(e.target.value)} className="w-full px-4 py-3 bg-white border-2 border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500" required />
            {!isLogin && ( <input type="password" placeholder="Confirm Password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} className="w-full px-4 py-3 bg-white border-2 border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500" required /> )}
            {error && <p className="text-red-500 text-sm text-center">{error}</p>}
            <button type="submit" className="w-full bg-purple-600 text-white font-semibold py-3 rounded-lg hover:bg-purple-700 transition-colors shadow-md shadow-purple-200 !mt-6">{isLogin ? "Let's Go!" : "Create Account"}</button>
        </form>
        <p className="text-center text-sm text-purple-600 mt-6">
            {isLogin ? "First time here?" : "Already have an account?"}
            <button onClick={() => { setView(isLogin ? 'register' : 'login'); clearFormFields(); }} className="font-semibold text-purple-700 hover:underline ml-1">{isLogin ? "Join us!" : "Sign in"}</button>
        </p>
    </div>
);
const UploadScreen = ({ handleLogout, handleFileUpload }) => {
    const handleDragOver = (e) => e.preventDefault();
    const handleDrop = (e) => { e.preventDefault(); if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0]); };
    const handleFileSelect = (e) => { if (e.target.files.length > 0) handleFileUpload(e.target.files[0]); };
    return (
        <div className="bg-white p-8 sm:p-10 rounded-2xl shadow-lg border border-gray-100 max-w-2xl w-full" style={{ backgroundColor: '#F9F5FF' }}>
            <div className="flex justify-between items-center mb-6"> <h2 className="text-3xl font-bold text-purple-800">Tax Helper</h2> <button onClick={handleLogout} className="text-purple-600 hover:text-purple-800 font-semibold">Sign Out</button> </div>
            <p className="text-purple-600 mb-8">Don't stress! Just upload your notice and we'll make sense of it for you.</p>
            <div className="border-2 border-dashed border-purple-300 rounded-xl p-12 text-center bg-purple-50 cursor-pointer hover:bg-purple-100 transition-colors" onDragOver={handleDragOver} onDrop={handleDrop} onClick={() => document.getElementById('file-input').click()}>
                <FileHeart className="mx-auto h-16 w-16 text-purple-400" />
                <p className="mt-4 text-lg text-purple-700">Drop your PDF file here</p>
                <p className="text-sm text-purple-500 mt-1">or</p>
                <button className="mt-4 bg-white border-2 border-purple-200 text-purple-700 font-semibold py-2 px-4 rounded-lg hover:bg-purple-100">Pick a File</button>
                <input type="file" id="file-input" className="hidden" accept=".pdf" onChange={handleFileSelect} />
            </div>
        </div>
    );
};
const SummaryScreen = ({ summaryData, resetApp }) => (
    <div className="bg-white p-8 sm:p-10 rounded-2xl shadow-lg border border-gray-100 max-w-3xl w-full" style={{ backgroundColor: '#F9F5FF' }}>
        <h2 className="text-3xl font-bold text-purple-800 mb-6 text-center">Your Notice Summary</h2>
        <div className="bg-purple-50/50 p-6 rounded-xl border-2 border-purple-100 mb-6">
             <h3 className="font-bold text-purple-900">Notice For:</h3> <p className="text-purple-700">{summaryData.noticeFor}</p>
             <p className="text-purple-700 whitespace-pre-wrap">{summaryData.address}</p>
             <p className="text-purple-700 mt-2"><span className="font-semibold">Social Security Number:</span> {summaryData.ssn}</p>
        </div>
        <div className="grid md:grid-cols-2 gap-4 text-center bg-purple-600 text-white p-6 rounded-xl mb-6 shadow-md shadow-purple-200">
            <div> <p className="text-sm uppercase font-bold tracking-wider opacity-80">Amount Due</p> <p className="text-3xl font-bold">{summaryData.amountDue}</p> </div>
            <div> <p className="text-sm uppercase font-bold tracking-wider opacity-80">Pay By</p> <p className="text-3xl font-bold">{summaryData.payBy}</p> </div>
        </div>
        <div className="text-center mt-8"> <button onClick={resetApp} className="bg-purple-600 text-white font-semibold py-2 px-6 rounded-lg hover:bg-purple-700 transition-colors">Analyze Another Notice</button> </div>
    </div>
);


// --- Main Application Component ---
export default function App() {
    const [view, setView] = useState('login');
    const [user, setUser] = useState(null);
    const [error, setError] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [summaryData, setSummaryData] = useState(null);

    const clearFormFields = () => {
        setEmail('');
        setPassword('');
        setConfirmPassword('');
        setFirstName('');
        setLastName('');
        setError('');
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        setError('');
        if (password !== confirmPassword) { setError("Passwords do not match."); return; }
        const result = await api.register({ firstName, lastName, email, password });
        if (result.success) { setUser(result.user); setView('upload'); } 
        else { setError(result.message); }
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');
        const result = await api.login({ email, password });
        if (result.success) { setUser(result.user); setView('upload'); }
        else { setError(result.message); }
    };

    const handleLogout = () => { setUser(null); setView('login'); };
    
    const handleFileUpload = async (file) => {
        if (file) {
            setView('analyzing');
            const result = await api.summarize(file);
            if (result.success) {
                setSummaryData(result.summary);
                setView('summary');
            } else {
                setError(result.message);
                setView('upload'); 
            }
        }
    };

    const resetApp = () => { setView('upload'); setSummaryData(null); };

    const renderView = () => {
        switch (view) {
            case 'register': return <AuthScreen isLogin={false} handleRegister={handleRegister} error={error} firstName={firstName} setFirstName={setFirstName} lastName={lastName} setLastName={setLastName} email={email} setEmail={setEmail} password={password} setPassword={setPassword} confirmPassword={confirmPassword} setConfirmPassword={setConfirmPassword} setView={setView} clearFormFields={clearFormFields} />;
            case 'login': return <AuthScreen isLogin={true} handleLogin={handleLogin} error={error} email={email} setEmail={setEmail} password={password} setPassword={setPassword} setView={setView} clearFormFields={clearFormFields} />;
            case 'upload': return <UploadScreen handleLogout={handleLogout} handleFileUpload={handleFileUpload} />;
            case 'analyzing': return <LoadingSpinner />;
            case 'summary': return <SummaryScreen summaryData={summaryData} resetApp={resetApp} />;
            default: return <div className="text-purple-500">Loading...</div>;
        }
    };

    return (
        <div className="min-h-screen bg-purple-100 flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #EDE9FE, #F3E8FF)'}}>
            {renderView()}
        </div>
    );
}
