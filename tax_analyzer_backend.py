// --- Part 2: Final Frontend Application (App.js) ---
// This file should be in your GitHub repository connected to Vercel.

import React, { useState } from 'react';

const API_BASE_URL = 'https://tax-analyzer-backend.onrender.com'; 

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

// --- Helper Components & Icons ---
const FileHeart = (props) => ( <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 22h14a2 2 0 0 0 2-2V7.5L14.5 2H6a2 2 0 0 0-2 2v4" /><path d="M14 2v6h6" /><path d="M10.3 12.3c.8-1 2-1.5 3.2-1.5 2.2 0 4 1.8 4 4 0 2.5-3.4 4.9-5.2 6.2a.5.5 0 0 1-.6 0C10 19.4 6 17 6 14.5c0-2.2 1.8-4 4-4 .8 0 1.5.3 2.1.8" /></svg> );
const LoadingSpinner = () => ( <div className="flex flex-col items-center justify-center space-y-4"><div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-purple-600"></div><p className="text-purple-700 font-semibold">Analyzing your notice...</p></div> );

// --- Screen Components ---
const AuthScreen = ({ isLogin, handleLogin, handleRegister, error, firstName, setFirstName, lastName, setLastName, email, setEmail, password, setPassword, confirmPassword, setConfirmPassword, dob, setDob, mobileNumber, setMobileNumber, countryCode, setCountryCode, setView, clearFormFields}) => {
    const countryCodes = [
        { name: 'United States', code: 'US', dial_code: '+1' },
        { name: 'India', code: 'IN', dial_code: '+91' },
        { name: 'United Kingdom', code: 'GB', dial_code: '+44' },
    ].sort((a,b) => a.name.localeCompare(b.name));

    return (
    <div className="bg-white p-8 sm:p-10 rounded-2xl shadow-lg border border-gray-100 max-w-md w-full" style={{ backgroundColor: '#F9F5FF' }}>
        <h2 className="text-3xl font-bold text-center text-purple-800 mb-1">{isLogin ? "Hello There!" : "Create Your Account"}</h2>
        <p className="text-center text-purple-600 mb-8">{isLogin ? "Let's get you signed in." : "Join us to simplify your tax notices."}</p>
        <form onSubmit={isLogin ? handleLogin : handleRegister} className="space-y-4">
            {!isLogin && (
                <>
                    <div className="grid grid-cols-2 gap-4">
                        <input type="text" placeholder="First Name" value={firstName} onChange={e => setFirstName(e.target.value)} className="w-full px-4 py-3 bg-white border-2 border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500" required />
                        <input type="text" placeholder="Last Name" value={lastName} onChange={e => setLastName(e.target.value)} className="w-full px-4 py-3 bg-white border-2 border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500" required />
                    </div>
                    <input type="text" placeholder="Date of Birth" onFocus={(e) => e.target.type='date'} onBlur={(e) => { if(!e.target.value) e.target.type='text'}} value={dob} onChange={e => setDob(e.target.value)} className="w-full px-4 py-3 bg-white border-2 border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-700" required />
                    <div className="flex">
                        <select value={countryCode} onChange={e => setCountryCode(e.target.value)} className="bg-gray-50 border-2 border-r-0 border-purple-200 rounded-l-lg focus:outline-none focus:ring-2 focus:ring-purple-500 px-2 text-gray-700">
                            {countryCodes.map(country => ( <option key={country.code} value={country.dial_code}>{country.name} ({country.dial_code})</option> ))}
                        </select>
                        <input type="tel" placeholder="Mobile Number" value={mobileNumber} onChange={e => setMobileNumber(e.target.value)} className="w-full px-4 py-3 bg-white border-2 border-purple-200 rounded-r-lg focus:outline-none focus:ring-2 focus:ring-purple-500" required />
                    </div>
                </>
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
    )
};
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

// FIX: Rebuilt SummaryScreen to render the final detailed format.
const SummaryScreen = ({ summaryData, resetApp }) => (
    <div className="bg-white p-8 sm:p-10 rounded-2xl shadow-lg border border-gray-100 max-w-3xl w-full" style={{ backgroundColor: '#F9F5FF' }}>
        <h1 className="text-3xl font-bold text-purple-800 mb-2 text-center">Summary of Your IRS Notice {summaryData.noticeType}</h1>
        
        <div className="bg-purple-50/50 p-6 rounded-xl border-2 border-purple-100 my-6">
             <h3 className="font-bold text-purple-900">Notice For:</h3>
             <p className="text-purple-700">{summaryData.noticeFor || 'Not found'}</p>
             <p className="text-purple-700 whitespace-pre-wrap">{summaryData.address || 'Not found'}</p>
             <p className="text-purple-700 mt-2"><span className="font-semibold">Social Security Number:</span> {summaryData.ssn || 'Not found'}</p>
        </div>

        <div className="grid md:grid-cols-2 gap-4 text-center bg-purple-600 text-white p-6 rounded-xl mb-8 shadow-md shadow-purple-200">
            <div>
                <p className="text-sm uppercase font-bold tracking-wider opacity-80">Amount Due</p>
                <p className="text-3xl font-bold">{summaryData.amountDue || 'N/A'}</p>
            </div>
             <div>
                <p className="text-sm uppercase font-bold tracking-wider opacity-80">Pay By</p>
                <p className="text-3xl font-bold">{summaryData.payBy || 'N/A'}</p>
            </div>
        </div>

        <div className="space-y-8">
            {summaryData.noticeMeaning && (
            <div>
                <h3 className="flex items-center text-xl font-bold text-purple-800 mb-3">Understanding Your Notice ({summaryData.noticeType})</h3>
                <p className="text-purple-700 bg-purple-50 p-4 rounded-lg border border-purple-100">{summaryData.noticeMeaning}</p>
            </div>
            )}

            {summaryData.whyText && (
            <div>
                <h3 className="flex items-center text-xl font-bold text-purple-800 mb-3">
                    <span className="text-2xl mr-3">❓</span> Why did I receive this?
                </h3>
                <p className="text-purple-700">{summaryData.whyText}</p>
                {summaryData.breakdown && summaryData.breakdown.length > 0 && (
                    <table className="min-w-full bg-white mt-4 rounded-lg border border-purple-200">
                        <thead className="bg-purple-50">
                            <tr>
                                <th className="text-left py-2 px-4 font-semibold text-purple-800">Item</th>
                                <th className="text-right py-2 px-4 font-semibold text-purple-800">Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            {summaryData.breakdown.map((item, index) => (
                                <tr key={index} className="border-t border-purple-200">
                                    <td className="py-2 px-4 text-purple-700">{item.item}</td>
                                    <td className="py-2 px-4 text-purple-700 text-right font-mono">{item.amount}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
            )}
            
            {summaryData.fixSteps && (
            <div>
                <h3 className="flex items-center text-xl font-bold text-purple-800 mb-3">
                    <span className="text-2xl mr-3">✔️</span> How should I fix this?
                </h3>
                <div className="bg-green-50 border border-green-200 p-4 rounded-lg mb-3">
                     <p className="font-semibold text-green-800">If You Agree:</p>
                     <p className="text-green-700 text-sm">{summaryData.fixSteps.agree || 'Information not available.'}</p>
                </div>
                 <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-lg">
                     <p className="font-semibold text-yellow-800">If You Disagree:</p>
                     <p className="text-yellow-700 text-sm">{summaryData.fixSteps.disagree || 'Information not available.'}</p>
                </div>
            </div>
            )}

             {summaryData.paymentOptions && (
             <div>
                <h3 className="flex items-center text-xl font-bold text-purple-800 mb-3">
                    <span className="text-2xl mr-3">💳</span> How do I pay?
                </h3>
                 <ul className="space-y-2 text-purple-700 text-sm bg-purple-50 p-4 rounded-lg border border-purple-100">
                    <li><strong>Online:</strong> <a href={`https://${summaryData.paymentOptions.online}`} target="_blank" rel="noopener noreferrer" className="text-purple-600 font-semibold hover:underline">{summaryData.paymentOptions.online || 'Not specified'}</a></li>
                    <li><strong>By Mail:</strong> {summaryData.paymentOptions.mail || 'Not specified'}</li>
                    <li><strong>Payment Plan:</strong> <a href={`https://${summaryData.paymentOptions.plan}`} target="_blank" rel="noopener noreferrer" className="text-purple-600 font-semibold hover:underline">{summaryData.paymentOptions.plan || 'Not specified'}</a></li>
                 </ul>
            </div>
            )}

             {summaryData.helpInfo && (
             <div>
                <h3 className="flex items-center text-xl font-bold text-purple-800 mb-3">
                    <span className="text-2xl mr-3">🙋</span> I need more help!
                </h3>
                 <ul className="space-y-2 text-purple-700 text-sm bg-purple-50 p-4 rounded-lg border border-purple-100">
                    <li>{summaryData.helpInfo.contact || 'Contact info not found.'}</li>
                    <li>{summaryData.helpInfo.advocate || 'Advocate info not found.'}</li>
                 </ul>
            </div>
            )}
        </div>
        
        <div className="text-center mt-10">
             <button onClick={resetApp} className="bg-purple-600 text-white font-semibold py-2 px-6 rounded-lg hover:bg-purple-700 transition-colors">
                Analyze Another Notice
             </button>
        </div>
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
    const [dob, setDob] = useState('');
    const [countryCode, setCountryCode] = useState('+91');
    const [mobileNumber, setMobileNumber] = useState('');
    const [summaryData, setSummaryData] = useState(null);

    const clearFormFields = () => {
        setEmail(''); setPassword(''); setConfirmPassword('');
        setFirstName(''); setLastName(''); setError('');
        setDob(''); setMobileNumber(''); setCountryCode('+91');
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        setError('');
        if (password !== confirmPassword) { setError("Passwords do not match."); return; }
        const fullMobileNumber = `${countryCode}${mobileNumber}`;
        const result = await api.register({ firstName, lastName, email, password, dob, mobileNumber: fullMobileNumber });
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
            try {
                const result = await api.summarize(file);
                if (result.success) {
                    setSummaryData(result.summary);
                    setView('summary');
                } else {
                    setError(result.message || "An error occurred during analysis.");
                    setView('upload'); 
                }
            } catch (e) {
                console.error("File upload/summary error:", e);
                setError("Could not connect to the analysis server. Please try again later.");
                setView('upload');
            }
        }
    };

    const resetApp = () => { setView('upload'); setSummaryData(null); };

    const renderView = () => {
        switch (view) {
            case 'register': return <AuthScreen isLogin={false} handleRegister={handleRegister} error={error} firstName={firstName} setFirstName={setFirstName} lastName={lastName} setLastName={setLastName} email={email} setEmail={setEmail} password={password} setPassword={setPassword} confirmPassword={confirmPassword} setConfirmPassword={setConfirmPassword} dob={dob} setDob={setDob} mobileNumber={mobileNumber} setMobileNumber={setMobileNumber} countryCode={countryCode} setCountryCode={setCountryCode} setView={setView} clearFormFields={clearFormFields} />;
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
