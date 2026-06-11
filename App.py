import json
import re
import random
import io
import os
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# --- SAFETY WRAPPERS FOR OPTIONAL LIBRARIES ---
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

# --- UI INITIALIZATION & PLATFORM STYLING ---
st.set_page_config(
    page_title="StudySmart Pro AI", 
    page_icon="⚡", 
    layout="centered"
)

# Custom responsive CSS design matching premium gamified mobile study apps
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght=400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #f8fafc;
        color: #0f172a;
    }
    
    .stApp {
        background-color: #f8fafc;
    }
    
    .mobile-container {
        max-width: 480px;
        margin: 0 auto;
        padding: 8px;
    }
    
    .app-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 4px;
        margin-bottom: 10px;
    }
    
    .deck-badge {
        font-size: 14px;
        font-weight: 700;
        color: #0284c7;
        background: #e0f2fe;
        padding: 6px 14px;
        border-radius: 20px;
    }
    
    .game-stats-bar {
        display: flex;
        gap: 16px;
        margin-bottom: 20px;
        padding: 0 4px;
    }
    
    .stat-pill {
        display: flex;
        align-items: center;
        gap: 6px;
        font-weight: 700;
        font-size: 15px;
    }
    
    .pill-key { color: #eab308; }
    .pill-heart { color: #ef4444; }
    .pill-xp { 
        margin-left: auto; 
        background: #e2e8f0; 
        color: #475569; 
        padding: 4px 12px; 
        border-radius: 12px;
        font-size: 13px;
    }
    
    .question-box {
        background: #ffffff;
        border-radius: 24px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(15, 23, 42, 0.04);
        border: 1px solid #e2e8f0;
        margin-bottom: 24px;
    }
    
    .card-tag {
        color: #22c55e;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    
    .question-main-text {
        font-size: 18px;
        font-weight: 700;
        line-height: 1.5;
        color: #0f172a;
    }
    
    .hero-section {
        text-align: center;
        padding: 40px 10px;
    }
    
    .hero-text {
        font-size: 26px;
        font-weight: 800;
        color: #0f172a;
        margin-top: 12px;
    }
    
    .search-mock {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        padding: 16px;
        color: #94a3b8;
        font-size: 15px;
        margin-bottom: 24px;
    }
    
    .deck-row-item {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .border-blue { border-left: 5px solid #3b82f6; }
    .border-teal { border-left: 5px solid #14b8a6; }
    
    /* Interactive Choice Buttons Formatting Override */
    div.stButton > button {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 16px !important;
        padding: 14px 20px !important;
        font-size: 15px !important;
        font-weight: 500 !important;
        text-align: left !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.01) !important;
        width: 100%;
        transition: all 0.2s ease;
    }
    
    div.stButton > button:hover {
        border-color: #cbd5e1 !important;
        background-color: #f8fafc !important;
    }
    
    /* Utility Pills Design Override */
    .utility-pill button {
        background-color: #e2e8f0 !important;
        border-radius: 20px !important;
        font-weight: 600 !important;
        text-align: center !important;
        padding: 8px 16px !important;
    }
    
    .footer-navigation {
        display: flex;
        justify-content: space-around;
        padding: 16px 0;
        background: #ffffff;
        border-top: 1px solid #e2e8f0;
        margin-top: 60px;
    }
    
    .footer-tab {
        text-align: center;
        font-size: 11px;
        color: #94a3b8;
        font-weight: 600;
    }
    .footer-tab.active { color: #3b82f6; }
    </style>
""", unsafe_allow_html=True)

# --- STRICT SCHEMA STRUCTURING ENFORCEMENT ---
# This replicates Gizmo's core processing loop: it prevents the AI from returning broken arrays or numbers as questions.
class EnforcedQuizQuestion(BaseModel):
    question: str = Field(description="The actual full conceptual question string extracted or created from the text.")
    options: list[str] = Field(description="Exactly 3 unique, short, independent alternative answer choice variations.")
    correct: str = Field(description="The exact character matching variant present inside the options array list.")
    explanation: str = Field(description="A comprehensive sentence clearing up why this fact is correct.")

# --- STATE MACHINE ARCHITECTURE ---
if "state_machine" not in st.session_state:
    st.session_state.state_machine = {
        "current_screen": "DASHBOARD",  # DASHBOARD, DECK_PREVIEW, PLAYING, END_SCREEN
        "active_deck_title": "",
        "questions_pool": [],
        "current_index": 0,
        "keys": 5,
        "hearts": 15,
        "xp": 0,
        "selected_option": None,
        "answered_status": False,
        "show_explanation_drawer": False
    }

sm = st.session_state.state_machine

# --- SECURE BUILT-IN BACKUP DECK REPOSITORY ---
MOCK_DATABASE = {
    "DOST Exam Reviewer": [
        {"question": "What logical conclusion can be drawn from the statement: 'Some actors are singers, and all singers are dancers'?", "options": ["Some actors are dancers", "All actors are dancers", "No actors can be dancers"], "correct": "Some actors are dancers", "explanation": "Since the entire group of singers is enclosed inside dancers, any actor who is a singer is also a dancer."},
        {"question": "Which historic scientist is credited with developing infinitesimal calculus independently during the 17th century?", "options": ["Sir Isaac Newton", "Albert Einstein", "Nikola Tesla"], "correct": "Sir Isaac Newton", "explanation": "Sir Isaac Newton developed calculus alongside Gottfried Wilhelm Leibniz during the late 1600s."},
        {"question": "What specific ability is evaluated by comprehensive Verbal Reasoning examinations?", "options": ["Analyze, interpret, and logically process text data", "Memorize complicated formulas perfectly", "Perform speed-reading sequences on simple words"], "correct": "Analyze, interpret, and logically process text data", "explanation": "Verbal reasoning measures constructive logic rather than simple word memorization patterns."}
    ],
    "NAT Core Math": [
        {"question": "What occurs when two linear equations share identical slopes but maintain different y-intercepts?", "options": ["They are parallel and never intersect", "They overlap perfectly on all coordinate sets", "They cross perpendicularly at the coordinate origin"], "correct": "They are parallel and never intersect", "explanation": "Identical slopes mean the lines travel in the exact same direction, meaning they can never cross."}
    ]
}

# --- DOCUMENT PARSING METHODS ---
def read_uploaded_files(files):
    text_content = ""
    for f in files:
        if f.name.lower().endswith(".pdf") and PdfReader:
            try:
                pdf_reader = PdfReader(f)
                for page in pdf_reader.pages:
                    text_content += page.extract_text() or ""
            except Exception:
                pass
        else:
            text_content += f.read().decode("utf-8", errors="ignore") + "\n"
    return text_content

def run_ai_quiz_generation(text_material):
    # Checks if secret configurations exist inside your server pipeline safely
    if not hasattr(st, "secrets") or "gemini" not in st.secrets:
        return client_side_fallback_parser(text_material)
        
    try:
        client = genai.Client(api_key=st.secrets["gemini"]["api_key"])
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Analyze this material and create an advanced multi-choice quiz stack:\n{text_material}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[EnforcedQuizQuestion],
                temperature=0.3
            )
        )
        return json.loads(response.text)
    except Exception:
        return client_side_fallback_parser(text_material)

def client_side_fallback_parser(text):
    # This matches the Gizmo logic: it instantly cleans up raw text strings to prevent errors if the API hits a network limit
    clean_text = re.sub(r'\s+', ' ', text)
    sentences = [s.strip() for s in re.split(r'[.!?]', clean_text) if len(s.strip()) > 45]
    
    if len(sentences) < 2:
        return MOCK_DATABASE["DOST Exam Reviewer"]
        
    results = []
    for i in range(min(5, len(sentences))):
        fact = sentences[i]
        results.append({
            "question": f"Based on the processed study file, which statement represents a verified factual point?",
            "options": [fact, "An alternative incorrect evaluation statement.", "A secondary parameter choice omitting baseline data."],
            "correct": fact,
            "explanation": f"The source text directly explicitly confirms: '{fact}'"
        })
    return results

# --- SCREEN CONTROLLER: HOME DASHBOARD ---
if sm["current_screen"] == "DASHBOARD":
    st.markdown("""
    <div class="mobile-container">
        <div class="hero-section">
            <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f98b/512.webp" width="75" height="75">
            <h2 class="hero-text">What shall we study?</h2>
        </div>
        <div class="search-mock">Search study sets, topics... 🔍</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Material Creator Utility Portal
    with st.expander("📥 Drag & Drop Material to Create Custom Sets"):
        uploaded_files = st.file_uploader("Upload files (.pdf, .txt)", accept_multiple_files=True)
        if uploaded_files and st.button("🚀 Process & Generate Quiz Set", use_container_width=True):
            with st.spinner("Analyzing data schemas..."):
                extracted_data = read_uploaded_files(uploaded_files)
                new_quiz = run_ai_quiz_generation(extracted_data)
                if new_quiz:
                    MOCK_DATABASE["Custom Generated Deck"] = new_quiz
                    sm["active_deck_title"] = "Custom Generated Deck"
                    sm["questions_pool"] = new_quiz
                    sm["current_screen"] = "DECK_PREVIEW"
                    st.rerun()

    st.write("")
    st.markdown("### Active Decks")
    
    # Render Core Topic Iterations
    available_decks = [("DOST Exam Reviewer", "3 Active Modules", "border-blue"), ("NAT Core Math", "1 Module Load", "border-teal")]
    if "Custom Generated Deck" in MOCK_DATABASE:
        available_decks.insert(0, ("Custom Generated Deck", "AI Extracted Set", "border-blue"))
        
    for name, subtitle, style_class in available_decks:
        col_txt, col_act = st.columns([4, 1])
        with col_txt:
            st.markdown(f"""
            <div class="deck-row-item {style_class}" style="margin-bottom:0; height:68px; display:flex; align-items:center;">
                <div>
                    <b style="color:#0f172a; font-size:15px;">{name}</b><br>
                    <span style="color:#64748b; font-size:13px;">{subtitle}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_act:
            st.write("")
            if st.button("Open", key=f"open_deck_{name}"):
                sm["active_deck_title"] = name
                sm["questions_pool"] = MOCK_DATABASE[name] if name != "Custom Generated Deck" else MOCK_DATABASE["Custom Generated Deck"]
                sm["current_screen"] = "DECK_PREVIEW"
                st.rerun()

# --- SCREEN CONTROLLER: DECK SELECTION PREVIEW ---
elif sm["current_screen"] == "DECK_PREVIEW":
    st.markdown(f"""
    <div class="app-header">
        <div class="deck-badge">📁 {sm['active_deck_title']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("⬅️ Back to Main Dashboard"):
        sm["current_screen"] = "DASHBOARD"
        st.rerun()
        
    st.write("---")
    st.markdown(f"### Undergraduate Assessment modules ({len(sm['questions_pool'])} cards loaded)")
    
    st.markdown(f"""
    <div class="deck-row-item border-blue">
        <div>
            <b style="font-size:15px; color:#1e293b;">Active Learning Subdeck Alpha</b><br>
            <span style="font-size:13px; color:#64748b;">Complete standard interactive choice format options</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    if st.button("🎮 Start Study Session", use_container_width=True):
        sm["current_screen"] = "PLAYING"
        sm["current_index"] = 0
        sm["selected_option"] = None
        sm["answered_status"] = False
        sm["show_explanation_drawer"] = False
        st.rerun()

# --- SCREEN CONTROLLER: LIVE SYSTEM GAMEPLAY ---
elif sm["current_screen"] == "PLAYING":
    pool = sm["questions_pool"]
    idx = sm["current_index"]
    
    if idx < len(pool):
        current_card = pool[idx]
        
        # Game Metric Counters Subsystem Header Layout
        st.markdown(f"""
        <div class="app-header">
            <div class="deck-badge">⭐ Review Module</div>
        </div>
        <div class="game-stats-bar">
            <span class="stat-pill pill-key">🔑 {sm['keys']}</span>
            <span class="stat-pill pill-heart">❤️ {sm['hearts']}</span>
            <span class="stat-xp">+{sm['xp']} XP</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Native Progression Visualizer 
        st.progress((idx + 1) / len(pool))
        
        # Primary Structural Card Frame Ingestion
        st.markdown(f"""
        <div class="question-box">
            <div class="card-tag">Question {idx + 1} of {len(pool)}</div>
            <div class="question-main-text">{current_card['question']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Option Selection Evaluation Loop
        for option_variant in current_card['options']:
            if st.button(option_variant, key=f"choice_node_{idx}_{option_variant}", disabled=sm["answered_status"]):
                sm["selected_option"] = option_variant
                sm["answered_status"] = True
                if option_variant == current_card['correct']:
                    sm["xp"] += 15
                else:
                    sm["hearts"] = max(0, sm["hearts"] - 1)
                st.rerun()
                
        # Interactive Real-Time Evaluation Validation Message Boxes
        if sm["answered_status"]:
            st.write("---")
            if sm["selected_option"] == current_card['correct']:
                st.success("🎯 Correct! Splendid operational choice.")
            else:
                st.error(f"❌ Incorrect. The accurate target factual point was: {current_card['correct']}")
                
            if sm["show_explanation_drawer"]:
                st.info(f"💡 **Conceptual Logic:** {current_card['explanation']}")
                
            # Functional Action Panel Drawer Buttons Layout
            col_key, col_rev, col_expl = st.columns(3)
            with col_key:
                st.markdown('<div class="utility-pill">', unsafe_allow_html=True)
                if st.button("🔑 Hint", key="action_hint"):
                    st.toast("Think about the primary context mentioned in the source paragraphs!")
                st.markdown('</div>', unsafe_allow_html=True)
            with col_rev:
                st.markdown('<div class="utility-pill">', unsafe_allow_html=True)
                if st.button("👁️ Reveal", key="action_reveal"):
                    sm["selected_option"] = current_card['correct']
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with col_expl:
                st.markdown('<div class="utility-pill">', unsafe_allow_html=True)
                if st.button("🔮 Explain", key="action_explain"):
                    sm["show_explanation_drawer"] = True
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
                
            st.write("")
            if st.button("Advance to Next Concept ➡️", use_container_width=True):
                if sm["hearts"] <= 0:
                    sm["current_screen"] = "END_SCREEN"
                else:
                    sm["current_index"] += 1
                    sm["selected_option"] = None
                    sm["answered_status"] = False
                    sm["show_explanation_drawer"] = False
                st.rerun()
    else:
        sm["current_screen"] = "END_SCREEN"
        st.rerun()

# --- SCREEN CONTROLLER: REWARD EVALUATION END SCREEN ---
elif sm["current_screen"] == "END_SCREEN":
    st.markdown("""
    <div class="question-box" style="text-align:center; padding:40px 20px;">
        <h2 style="color:#22c55e; margin-bottom:12px;">🏆 Session Finished!</h2>
        <p style="color:#475569; font-size:16px;">Your training loop has logged all tracking parameters accurately.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.metric(label="Total Score Output", value=f"{sm['xp']} XP Points")
    
    st.write("")
    if st.button("🏠 Return to Home Dashboard", use_container_width=True):
        sm["current_screen"] = "DASHBOARD"
        st.rerun()

# --- STRUCTURAL APP SYSTEM UTILITY NAVIGATION BAR FOOTER ---
st.markdown("""
    <div class="footer-navigation">
        <div class="footer-tab active">🏠<br>Home</div>
        <div class="footer-tab">🔥<br>Streak</div>
        <div class="footer-tab">➕<br>Add</div>
        <div class="footer-tab">🗂️<br>Decks</div>
        <div class="footer-tab">👤<br>Profile</div>
    </div>
""", unsafe_allow_html=True)
