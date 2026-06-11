import json
import re
import random
import io
import os
import streamlit as st
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types
from pydantic import BaseModel

# --- THEME & GIZMO PRESENTATION STYLING ---
st.set_page_config(
    page_title="BrainCrunch Gizmo Studio", 
    page_icon="🧠", 
    layout="centered"
)

# Custom sleek styling injection
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #f8fafc;
    }
    
    /* Gizmo Premium Interactive Flashcards */
    .flashcard-box {
        background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
        color: white;
        border-radius: 24px;
        padding: 40px 24px;
        text-align: center;
        min-height: 250px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        font-weight: 600;
        box-shadow: 0 10px 25px -5px rgba(79, 70, 229, 0.4);
        margin: 20px 0;
        transition: transform 0.2s ease;
    }
    
    .flashcard-back {
        background: linear-gradient(135deg, #059669 0%, #065f46 100%) !important;
        box-shadow: 0 10px 25px -5px rgba(5, 150, 105, 0.4) !important;
    }
    
    /* Global Card Wrapper */
    .gizmo-container {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

STORAGE_FILE = "storage.json"

def load_local_storage():
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except Exception:
            return {}
    return {}

def save_local_storage(data):
    try:
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Storage Error: {e}")

# --- AI DATA OBJECT SCHEMAS ---
class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct: str
    explanation: str

class FlashcardItem(BaseModel):
    concept_or_term: str
    definition_or_context: str

# --- SYSTEM STATE LIFECYCLE ---
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "questions" not in st.session_state:
    st.session_state.questions = []
if "flashcards" not in st.session_state:
    st.session_state.flashcards = []
if "active_mode" not in st.session_state:
    st.session_state.active_mode = "Welcome" 
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "score" not in st.session_state:
    st.session_state.score = 0
if "answered" not in st.session_state:
    st.session_state.answered = False
if "selected_option" not in st.session_state:
    st.session_state.selected_option = None
if "reveal_card" not in st.session_state:
    st.session_state.reveal_card = False

if "nested_folders" not in st.session_state:
    st.session_state.nested_folders = load_local_storage()

# Automatically fetch deployment secrets if they exist
try:
    if hasattr(st, "secrets") and "gemini" in st.secrets:
        st.session_state.api_key = st.secrets["gemini"]["api_key"]
except Exception:
    pass

# --- PARSING AND TEXT EXTRACTION ---
def extract_text_from_file(file):
    filename = file.name.lower()
    text = ""
    if filename.endswith(".pdf"):
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
    elif filename.endswith(".txt"):
        text += file.read().decode("utf-8", errors="ignore")
    return text

def get_youtube_id(url):
    match = re.search(r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None

def get_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([item['text'] for item in transcript_list])
    except Exception:
        return None

# --- CORE ADVANCED AI ENGINES ---
def generate_questions_with_ai(study_material, num_questions):
    key = st.session_state.api_key if st.session_state.api_key else "FALLBACK_KEY"
    prompt = f"Create exactly {num_questions} clear multiple-choice questions from this text material. Make sure all choices/options match the true content of the text realistically. Text:\n{study_material}"
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Fixed the 404 model string mismatch error
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[QuizQuestion],
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Connection Refused: {e}. Please ensure your Gemini Key is active in Admin settings.")
        return None

def generate_flashcards_with_ai(study_material):
    key = st.session_state.api_key if st.session_state.api_key else "FALLBACK_KEY"
    prompt = f"Extract all important terms, vocabulary rules, or technical concepts from this text. Transform them into crisp flashcard pairs. Text:\n{study_material}"
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[FlashcardItem],
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Connection Refused: {e}")
        return None

# --- MAIN ENGINE CONTROL INTERFACE ---
st.markdown("<h1 style='text-align: center; color: #1e3a8a;'>⚡ BrainCrunch Studio Pro</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Control Center")
    user_role = st.selectbox("Role Profile:", ["Player / Student", "Admin / Creator"])
    
    if user_role == "Admin / Creator":
        admin_pass = st.text_input("Enter Configuration Password:", type="password")
        if admin_pass == "studio123":
            st.success("Admin Panel Access Granted")
            st.session_state.api_key = st.text_input("Gemini API Key Override:", value=st.session_state.api_key, type="password")
            
    st.write("---")
    st.markdown("### 🛠️ Study Setup Mode")
    output_type = st.radio("App Task Goal:", ["Gizmo Flashcards AI", "Gamified Performance Quizzes"])
    
    # 📌 RE-ADDED THE MISSING CONFIGURATION FEATURES HERE
    if output_type == "Gamified Performance Quizzes":
        question_count = st.slider("🎯 Question Count:", min_value=3, max_value=50, value=5, step=1)
        
    st.write("---")
    creation_method = st.radio("Creation Style:", ["🤖 Automatically from Source", "✍️ Manually Create Cards"])
    
    if creation_method == "🤖 Automatically from Source":
        input_mode = st.radio("Input Source:", ["Upload Files (PDF, TXT)", "YouTube Video Link"])
        
        study_text = ""
        run_generation = False
        
        if input_mode == "Upload Files (PDF, TXT)":
            uploaded_files = st.file_uploader("Upload reference documents here:", type=["pdf", "txt"], accept_multiple_files=True)
            if uploaded_files and st.button("🚀 Process & Generate Set", use_container_width=True):
                for f in uploaded_files:
                    study_text += extract_text_from_file(f) + "\n"
                run_generation = True
                
        elif input_mode == "YouTube Video Link":
            yt_url = st.text_input("Paste YouTube Video URL:")
            if yt_url and st.button("🚀 Convert Video Streams", use_container_width=True):
                vid = get_youtube_id(yt_url)
                if vid:
                    study_text = get_youtube_transcript(vid)
                    run_generation = True

        if run_generation and study_text.strip():
            if output_type == "Gamified Performance Quizzes":
                res = generate_questions_with_ai(study_text, question_count)
                if res:
                    st.session_state.questions = res
                    st.session_state.active_mode = "Quiz"
                    st.session_state.current_index = 0
                    st.session_state.score = 0
                    st.session_state.answered = False
                    st.rerun()
            else:
                res = generate_flashcards_with_ai(study_text)
                if res:
                    st.session_state.flashcards = res
                    st.session_state.active_mode = "Flashcards"
                    st.session_state.current_index = 0
                    st.session_state.reveal_card = False
                    st.rerun()
                    
    # ✍️ MANUAL CREATION INTERFACE
    elif creation_method == "✍️ Manually Create Cards":
        st.markdown("#### 📝 Manual Deck Composer")
        with st.form("manual_entry_form"):
            term_input = st.text_input("Concept Label / Flashcard Question:")
            definition_input = st.text_area("Term Definition / Flashcard Back:")
            submitted = st.form_submit_button("➕ Add Card to Deck Collection")
            
            if submitted and term_input and definition_input:
                new_card = {"concept_or_term": term_input, "definition_or_context": definition_input}
                st.session_state.flashcards.append(new_card)
                st.toast("Card registered inside current collection workflow!")
                st.session_state.active_mode = "Flashcards"

        if st.session_state.flashcards:
            st.caption(f"Current Manual Items: {len(st.session_state.flashcards)} cards in play.")
            if st.button("🎮 Start Reviewing Open Deck", use_container_width=True):
                st.session_state.active_mode = "Flashcards"
                st.session_state.current_index = 0
                st.session_state.reveal_card = False
                st.rerun()

    st.write("---")
    st.markdown("### 🗂️ Load Saved Track Cabinets")
    if st.session_state.nested_folders:
        active_track = st.selectbox("Saved Sets Database:", list(st.session_state.nested_folders.keys()))
        if st.button("📥 Load Selected Set", use_container_width=True):
            saved_meta = st.session_state.nested_folders[active_track]
            if saved_meta["type"] == "Quiz":
                st.session_state.questions = saved_meta["data"]
                st.session_state.active_mode = "Quiz"
            else:
                st.session_state.flashcards = saved_meta["data"]
                st.session_state.active_mode = "Flashcards"
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.answered = False
            st.rerun()

# --- CONTENT DISPLAY RUNTIME HOOKS ---
if st.session_state.active_mode == "Welcome":
    st.markdown("""
    <div class='gizmo-container' style='text-align: center; border-top: 5px solid #4f46e5;'>
        <h3 style='margin-top:0; color: #1e293b;'>👋 Hello! Welcome to Gizmo Engine.</h3>
        <p style='color: #64748b;'>Use the control options in the sidebar panel to generate flashcard learning stacks or performance multiple choice evaluation sets instantly.</p>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.active_mode == "Flashcards":
    idx = st.session_state.current_index
    if idx < len(st.session_state.flashcards):
        card = st.session_state.flashcards[idx]
        
        st.markdown(f"<p style='color:#64748b; font-weight:600; text-align:right; margin-bottom:0;'>🏷️ Card Track: {idx+1} of {len(st.session_state.flashcards)}</p>", unsafe_allow_html=True)
        
        # Flashcard flip structural layout
        if not st.session_state.reveal_card:
            st.markdown(f"<div class='flashcard-box'>{card['concept_or_term']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='flashcard-box flashcard-back'>{card['definition_or_context']}</div>", unsafe_allow_html=True)
            
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if st.button("🔄 Flip/Reveal", use_container_width=True):
                st.session_state.reveal_card = not st.session_state.reveal_card
                st.rerun()
        with col_f2:
            if st.button("Next Card ➡️", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.reveal_card = False
                st.rerun()
    else:
        st.success("🏆 Excellent work! You have finished reviewing all the flashcards in this track.")
        
        # Save Track Cabinet Module
        st.write("---")
        save_path = st.text_input("Store flashcards to local cabinet track name:", value="My Flashcard Set")
        if st.button("💾 Save Flashcards to Cabinet Storage", use_container_width=True):
            st.session_state.nested_folders[save_path] = {"type": "Flashcards", "data": st.session_state.flashcards}
            save_local_storage(st.session_state.nested_folders)
            st.toast("Saved successfully!")
            
        if st.button("🏠 Head Back Home", use_container_width=True):
            st.session_state.active_mode = "Welcome"
            st.rerun()

elif st.session_state.active_mode == "Quiz":
    idx = st.session_state.current_index
    if idx < len(st.session_state.questions):
        q_item = st.session_state.questions[idx]
        
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            st.markdown(f"Accumulated Score: <b style='color:#4f46e5; font-size:20px;'>{st.session_state.score}</b> Pts", unsafe_allow_html=True)
        with col_h2:
            st.markdown(f"<p style='text-align:right; color:#64748b;'>Progress: <b>{idx+1}/{len(st.session_state.questions)}</b></p>", unsafe_allow_html=True)
            
        st.progress((idx) / len(st.session_state.questions))
        st.write("---")
        
        st.markdown(f"#### ❓ {q_item['question']}")
        st.write("")
        
        for opt in q_item['options']:
            if not st.session_state.answered:
                if st.button(opt, key=f"qopt_{idx}_{opt}", use_container_width=True):
                    st.session_state.answered = True
                    st.session_state.selected_option = opt
                    st.rerun()
                    
        if st.session_state.answered:
            if st.session_state.selected_option == q_item['correct'] or st.session_state.selected_option[0] == q_item['correct'][0]:
                st.success(f"🎯 Right Answer! — {st.session_state.selected_option}")
                if f"scored_{idx}" not in st.session_state:
                    st.session_state.score += 10
                    st.session_state[f"scored_{idx}"] = True
            else:
                st.error(f"❌ Incorrect. Chosen: {st.session_state.selected_option}. Correct choice: {q_item['correct']}")
                
            st.info(f"💡 **Gizmo Context Guide:** {q_item['explanation']}")
            st.write("---")
            
            if st.button("Advance to Next Concept ➡️", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.answered = False
                st.session_state.selected_option = None
                st.rerun()
    else:
        st.balloons()
        st.markdown("<div class='gizmo-container' style='text-align:center;'><h3>🏆 Complete Module Evaluation Set Finished!</h3></div>", unsafe_allow_html=True)
        st.metric("Total Acquired Points:", f"{st.session_state.score} Pts")
        
        st.write("---")
        save_path = st.text_input("Store quiz to local cabinet track name:", value="My Quiz Set")
        if st.button("💾 Save Quiz to Cabinet Storage", use_container_width=True):
            st.session_state.nested_folders[save_path] = {"type": "Quiz", "data": st.session_state.questions}
            save_local_storage(st.session_state.nested_folders)
            st.toast("Saved successfully!")
            
        if st.button("🏠 Back to Home Screen", use_container_width=True):
            st.session_state.active_mode = "Welcome"
            st.rerun()
