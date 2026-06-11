import json
import re
import random
import io
import os
import urllib.parse
import streamlit as st
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types
from pydantic import BaseModel

# --- THEME & PRESENTATION STYLING ---
st.set_page_config(
    page_title="BrainCrunch Gizmo", 
    page_icon="🧠", 
    layout="centered"
)

# Custom premium stylesheet injection
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Premium card modules styled like Gizmo AI */
    .gizmo-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    
    .flashcard-inner {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        color: white;
        border-radius: 20px;
        padding: 40px;
        text-align: center;
        min-height: 220px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        font-weight: 500;
        box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.3);
    }
    
    /* Styled metric rows */
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #4f46e5;
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

# --- PYDANTIC SCHEMA SPECIFICATION ---
class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct: str
    explanation: str

class FlashcardItem(BaseModel):
    concept_or_term: str
    definition_or_context: str

# --- STATE LIFECYCLE ---
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "questions" not in st.session_state:
    st.session_state.questions = []
if "flashcards" not in st.session_state:
    st.session_state.flashcards = []
if "review_notes" not in st.session_state:
    st.session_state.review_notes = ""
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
if "quiz_host_persona" not in st.session_state:
    st.session_state.quiz_host_persona = "Enthusiastic School Teacher"

if "nested_folders" not in st.session_state:
    st.session_state.nested_folders = load_local_storage()

# Attempt to look up secrets block silently
try:
    if hasattr(st, "secrets") and "gemini" in st.secrets:
        st.session_state.api_key = st.secrets["gemini"]["api_key"]
except Exception:
    pass

# --- FILE PARSING ENGINE ---
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

# --- HIGH REASONING AI CORES ---
def generate_questions_with_ai(study_material, num_questions, persona):
    # Uses secure standard fallback string key if secrets are currently empty
    key = st.session_state.api_key if st.session_state.api_key else "AI_KEY_FALLBACK"
    prompt = f"""
    You are an expert tutor modeling this specific personality profile: "{persona}".
    TASK: Analyze the document and generate exactly {num_questions} unique multiple-choice questions.
    
    CRITICAL: Ensure options match the question content accurately. Each option must be descriptive and directly extracted from the real context of the material.
    
    Study Material:
    {study_material}
    """
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[QuizQuestion],
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Engine Error Connection Refused: {e}. Please add or verify your Gemini Key in Admin Mode.")
        return None

def generate_flashcards_with_ai(study_material):
    key = st.session_state.api_key if st.session_state.api_key else "AI_KEY_FALLBACK"
    prompt = f"""
    Extract major core terms, formulas, historical events, or core definitions from this text. 
    Format them into a collection of structured flashcard pairs (Concept/Term vs Definition/Context).
    
    Text:
    {study_material}
    """
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
    except Exception:
        return None

# --- FRONTEND INTERFACE ---
st.markdown("<h2 style='text-align: center; color: #1e293b; font-weight: 700;'>⚡ BrainCrunch Gizmo</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748b;'>An advanced adaptive learning arena for students</p>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Workspace Configuration")
    user_role = st.selectbox("Current Profile:", ["Player / Student", "Admin / Creator"])
    
    if user_role == "Admin / Creator":
        admin_pass = st.text_input("Admin Key Verification:", type="password")
        if admin_pass == "studio123":
            st.success("Authorized Panel Unlocked")
            st.session_state.api_key = st.text_input("Active Gemini API Key:", value=st.session_state.api_key, type="password")
            st.session_state.quiz_host_persona = st.selectbox(
                "AI Voice Engine Persona:",
                ["Enthusiastic School Teacher", "Strict Academic Coach", "Tech Tech Innovator"]
            )
            
    st.write("---")
    st.markdown("### 🧙‍♂️ Gizmo Mode Selector")
    output_type = st.radio("Choose Study Mode:", ["Gizmo Flashcards AI", "Gamified Performance Quizzes"])
    
    if output_type == "Gamified Performance Quizzes":
        question_count = st.number_input("Target Total Question Count:", min_value=5, max_value=50, value=5, step=5)
        
    st.write("---")
    input_mode = st.radio("Material Source:", ["Upload Files (PDF, TXT)", "YouTube Video Link"])
    
    study_text = ""
    run_generation = False
    
    if input_mode == "Upload Files (PDF, TXT)":
        uploaded_files = st.file_uploader("Drop PDF or Text materials:", type=["pdf", "txt"], accept_multiple_files=True)
        if uploaded_files and st.button("🚀 Synthesize Materials", use_container_width=True):
            for f in uploaded_files:
                study_text += extract_text_from_file(f) + "\n"
            run_generation = True
            
    elif input_mode == "YouTube Video Link":
        yt_url = st.text_input("Paste YouTube URL:")
        if yt_url and st.button("🚀 Transcribe & Synthesize", use_container_width=True):
            vid = get_youtube_id(yt_url)
            if vid:
                study_text = get_youtube_transcript(vid)
                run_generation = True

    if run_generation and study_text.strip():
        with st.spinner("Processing documents with advanced AI stream models..."):
            if output_type == "Gamified Performance Quizzes":
                generated_qs = generate_questions_with_ai(study_text, question_count, st.session_state.quiz_host_persona)
                if generated_qs:
                    st.session_state.questions = generated_qs
                    st.session_state.active_mode = "Quiz"
                    st.session_state.current_index = 0
                    st.session_state.score = 0
                    st.session_state.answered = False
                    st.rerun()
            else:
                cards = generate_flashcards_with_ai(study_text)
                if cards:
                    st.session_state.flashcards = cards
                    st.session_state.active_mode = "Flashcards"
                    st.session_state.current_index = 0
                    st.session_state.reveal_card = False
                    st.rerun()

    st.write("---")
    st.markdown("### 🗂️ Subject Cabinets")
    if st.session_state.nested_folders:
        active_track = st.selectbox("Saved Binders:", list(st.session_state.nested_folders.keys()))
        if st.button("📥 Load Topic Content", use_container_width=True):
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

# --- RUNTIME RENDER HOOKS ---
if st.session_state.active_mode == "Welcome":
    st.markdown("""
    <div class='gizmo-card' style='text-align: center; border-top: 4px solid #4f46e5;'>
        <h3 style='color: #1e293b; margin-top:0;'>👋 Drop in your files to get started!</h3>
        <p style='color: #64748b;'>Upload study materials or paste YouTube links in the left sidebar to automatically build custom Gizmo flashcards or diagnostic quizzes.</p>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.active_mode == "Flashcards":
    idx = st.session_state.current_index
    if idx < len(st.session_state.flashcards):
        card = st.session_state.flashcards[idx]
        
        st.markdown(f"<p style='color:#64748b; font-weight:500; text-align:right;'>Card {idx+1} of {len(st.session_state.flashcards)}</p>", unsafe_allow_html=True)
        
        # Flashcard visual logic
        if not st.session_state.reveal_card:
            st.markdown(f"<div class='flashcard-inner'>{card['concept_or_term']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='flashcard-inner' style='background:linear-gradient(135deg, #10b981 0%, #059669 100%);'>{card['definition_or_context']}</div>", unsafe_allow_html=True)
            
        st.write("")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("🔄 Flip Card", use_container_width=True):
                st.session_state.reveal_card = not st.session_state.reveal_card
                st.rerun()
        with col_c2:
            if st.button("➡️ Next Term", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.reveal_card = False
                st.rerun()
    else:
        st.success("🎉 You have reviewed all the cards for this set!")
        if st.button("🏠 Finish and Go Home", use_container_width=True):
            st.session_state.active_mode = "Welcome"
            st.rerun()

elif st.session_state.active_mode == "Quiz":
    idx = st.session_state.current_index
    if idx < len(st.session_state.questions):
        q_item = st.session_state.questions[idx]
        
        # Render clean dashboard headers
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown(f"Score: <span class='metric-value'>{st.session_state.score}</span>", unsafe_allow_html=True)
        with col_m2:
            st.markdown(f"<p style='text-align:right; color:#64748b;'>Progress: <b>{idx+1}/{len(st.session_state.questions)}</b></p>", unsafe_allow_html=True)
            
        st.progress((idx) / len(st.session_state.questions))
        st.write("---")
        
        st.markdown(f"#### ❓ {q_item['question']}")
        st.write("")
        
        for opt in q_item['options']:
            if not st.session_state.answered:
                if st.button(opt, key=f"opt_{idx}_{opt}", use_container_width=True):
                    st.session_state.answered = True
                    st.session_state.selected_option = opt
                    st.rerun()
                    
        if st.session_state.answered:
            user_ans = st.session_state.selected_option[0]
            target_ans = q_item['correct'][0]
            
            if user_ans == target_ans:
                st.success(f"🎉 Correct choice: {st.session_state.selected_option}")
                if f"calculated_{idx}" not in st.session_state:
                    st.session_state.score += 10
                    st.session_state[f"calculated_{idx}"] = True
            else:
                st.error(f"❌ Incorrect. You selected {user_ans}. Correct option was: {q_item['correct']}")
                
            st.markdown(f"**ℹ️ Explanatory Summary:** {q_item['explanation']}")
            st.write("---")
            
            if st.button("Advance to Next Concept ➡️", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.answered = False
                st.session_state.selected_option = None
                st.rerun()
    else:
        st.balloons()
        st.markdown("<div class='gizmo-card' style='text-align:center;'><h3>🏆 Module Session Complete!</h3></div>", unsafe_allow_html=True)
        st.metric("Final Performance Rating Score:", f"{st.session_state.score} Pts")
        
        # Save to Cabinet Path 
        save_path = st.text_input("Enter Topic Label to save this deck to storage:", value="General Revision")
        if st.button("💾 Save Session Deck", use_container_width=True):
            st.session_state.nested_folders[save_path] = {"type": "Quiz", "data": st.session_state.questions}
            save_local_storage(st.session_state.nested_folders)
            st.toast("Saved successfully.")
            
        if st.button("🏠 Finish and Return Home", use_container_width=True):
            st.session_state.active_mode = "Welcome"
            st.rerun()
