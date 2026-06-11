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

# --- GIZMO MODERN PREMIUM DARK THEME ---
st.set_page_config(
    page_title="BrainCrunch Workspace Pro", 
    page_icon="🧠", 
    layout="centered"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    
    .stApp {
        background-color: #0b0f19;
    }
    
    /* Sleek Container Cards */
    .gizmo-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        margin-bottom: 20px;
    }
    
    /* Interactive Flashcards */
    .flashcard-box {
        background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
        color: white;
        border-radius: 20px;
        padding: 50px 24px;
        text-align: center;
        min-height: 220px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        font-weight: 600;
        box-shadow: 0 10px 25px -5px rgba(79, 70, 229, 0.4);
        margin: 20px 0;
        border: 1px solid rgba(255,255,255,0.1);
    }
    
    .flashcard-back {
        background: linear-gradient(135deg, #059669 0%, #065f46 100%) !important;
        box-shadow: 0 10px 25px -5px rgba(5, 150, 105, 0.4) !important;
    }
    
    .studio-title {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-weight: 700;
        margin-bottom: 25px;
    }
    
    [data-testid="stSidebar"] {
        background-color: #070a13 !important;
        border-right: 1px solid #1f2937;
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
        st.error(f"Storage System Error: {e}")

# --- DATA SCHEMAS ---
class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct: str
    explanation: str

class FlashcardItem(BaseModel):
    concept_or_term: str
    definition_or_context: str

# --- LIFECYCLE STATE MANAGEMENT ---
session_vars = {
    "api_key": "", "questions": [], "flashcards": [], 
    "active_mode": "Welcome", "current_index": 0, "score": 0, 
    "answered": False, "selected_option": None, "reveal_card": False,
    "temp_selection": None
}
for key, val in session_vars.items():
    if key not in st.session_state:
        st.session_state[key] = val

if "nested_folders" not in st.session_state:
    st.session_state.nested_folders = load_local_storage()

try:
    if hasattr(st, "secrets") and "gemini" in st.secrets:
        st.session_state.api_key = st.secrets["gemini"]["api_key"]
except Exception:
    pass

# --- DOCUMENT PARSERS ---
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

# --- HIGH-FIDELITY OFFLINE CONTEXT GENERATOR (NO EMOJIS PRE-INJECTED) ---
def generate_smart_fallback_questions(text, count):
    clean_text = re.sub(r'\s+', ' ', text)
    sentences = [s.strip() for s in re.split(r'[.!?]', clean_text) if len(s.strip()) > 40]
    
    if len(sentences) < 4:
        sentences = [
            "DANAO CITY SCHOLARSHIP EXAMINATION Comprehensive Core Reviewer & 100-Question Practice Test Tailored for Local Government & Academic Excellence Grants",
            "This upgraded volume incorporates explicit localized history, infrastructure data, political leadership configurations, and economic trends specific to Danao City, Cebu.",
            "Danao City sits exactly within the 5th Congressional District of the Province of Cebu and is bounded by Camotes Sea.",
            "The questions in this material reflect the core architectural style, patterns, and content tracking of regional entrance tests."
        ]
        
    questions = []
    for i in range(count):
        target_sentence = sentences[i % len(sentences)]
        
        # Pull separate factual chunks cleanly without appending formatting emojis
        other_sentences = [s for s in sentences if s != target_sentence]
        if len(other_sentences) < 3:
            other_sentences = sentences * 3
            
        correct_ans = target_sentence
        wrong_1 = other_sentences[0]
        wrong_2 = other_sentences[1]
        wrong_3 = other_sentences[2]
        
        options_pool = [correct_ans, wrong_1, wrong_2, wrong_3]
        random.shuffle(options_pool)
        
        questions.append({
            "question": f"Based on your analyzed study material context, which of the following choices accurately expresses a documented statement?",
            "options": options_pool,
            "correct": correct_ans,
            "explanation": f"Verified text parameters explicitly note: \"{target_sentence}\""
        })
    return questions

def generate_smart_fallback_flashcards(text):
    clean_text = re.sub(r'\s+', ' ', text)
    sentences = [s.strip() for s in re.split(r'[.!?]', clean_text) if len(s.strip()) > 25]
    if len(sentences) < 3:
        sentences = ["Danao City Context", "Scholarship Metrics", "Territorial Bounds"]
        
    cards = []
    for idx, item in enumerate(sentences[:10]):
        words = [w for w in re.split(r'\W+', item) if len(w) > 4]
        keyword = words[0] if words else f"Concept Focus {idx+1}"
        cards.append({
            "concept_or_term": f"🔍 Focus Term: {keyword}",
            "definition_or_context": item
        })
    return cards

# --- PRODUCTION API HANDLERS ---
def generate_questions_with_ai(study_material, num_questions):
    if not st.session_state.api_key or len(st.session_state.api_key) < 10:
        return generate_smart_fallback_questions(study_material, num_questions)
        
    prompt = f"Generate exactly {num_questions} reading comprehension multiple choice questions based on this text. Choices must be full, distinct contextual sentences from the text scope. Do not include answers, labels, or indicators in the options array. Text:\n{study_material}"
    try:
        client = genai.Client(api_key=st.session_state.api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[QuizQuestion],
            ),
        )
        return json.loads(response.text)
    except Exception:
        return generate_smart_fallback_questions(study_material, num_questions)

def generate_flashcards_with_ai(study_material):
    if not st.session_state.api_key or len(st.session_state.api_key) < 10:
        return generate_smart_fallback_flashcards(study_material)
        
    prompt = f"Analyze this material and return structured flashcards. Text:\n{study_material}"
    try:
        client = genai.Client(api_key=st.session_state.api_key)
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
        return generate_smart_fallback_flashcards(study_material)

# --- WORKSPACE INTERFACE ---
st.markdown("<h1 class='studio-title'>🧠 BrainCrunch Studio</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Identity Settings")
    user_role = st.selectbox("Current Workspace Profile:", ["Player / Student", "Admin / Creator"])
    
    if user_role == "Admin / Creator":
        admin_pass = st.text_input("Enter Pass Code:", type="password")
        if admin_pass == "studio123":
            st.success("Admin Panel Enabled")
            st.session_state.api_key = st.text_input("System API Key Override:", value=st.session_state.api_key, type="password")
            
    st.write("---")
    st.markdown("### 🛠️ Study Mode Strategy")
    output_type = st.radio("Target Element:", ["Gizmo Flashcards AI", "Gamified Performance Quizzes"])
    
    if output_type == "Gamified Performance Quizzes":
        question_count = st.slider("🎯 Select Number of Questions:", min_value=3, max_value=25, value=5, step=1)
        
    st.write("---")
    creation_method = st.radio("Creation Style:", ["🤖 Automatically from Source", "✍️ Manually Create Cards"])
    
    if creation_method == "🤖 Automatically from Source":
        input_mode = st.radio("Input Source Channel:", ["Upload Files (PDF, TXT)", "YouTube Video Link"])
        study_text = ""
        run_generation = False
        
        if input_mode == "Upload Files (PDF, TXT)":
            uploaded_files = st.file_uploader("Drop study docs here:", type=["pdf", "txt"], accept_multiple_files=True)
            if uploaded_files and st.button("🚀 Process & Generate Set", use_container_width=True):
                for f in uploaded_files:
                    study_text += extract_text_from_file(f) + "\n"
                run_generation = True
                
        elif input_mode == "YouTube Video Link":
            yt_url = st.text_input("Paste YouTube URL Link:")
            if yt_url and st.button("🚀 Gather Video Subtitles", use_container_width=True):
                vid = get_youtube_id(yt_url)
                if vid:
                    study_text = get_youtube_transcript(vid)
                    run_generation = True

        if run_generation and study_text.strip():
            with st.spinner("Synthesizing context strings..."):
                if output_type == "Gamified Performance Quizzes":
                    res = generate_questions_with_ai(study_text, question_count)
                    if res:
                        st.session_state.questions = res
                        st.session_state.active_mode = "Quiz"
                        st.session_state.current_index = 0
                        st.session_state.score = 0
                        st.session_state.answered = False
                        st.session_state.temp_selection = None
                        st.rerun()
                else:
                    res = generate_flashcards_with_ai(study_text)
                    if res:
                        st.session_state.flashcards = res
                        st.session_state.active_mode = "Flashcards"
                        st.session_state.current_index = 0
                        st.session_state.reveal_card = False
                        st.rerun()
                    
    elif creation_method == "✍️ Manually Create Cards":
        st.markdown("#### 📝 Custom Card Composer")
        with st.form("manual_entry_form"):
            term_input = st.text_input("Front Face Question:")
            definition_input = st.text_area("Back Face Explanation:")
            submitted = st.form_submit_button("➕ Add Card To Deck")
            
            if submitted and term_input and definition_input:
                st.session_state.flashcards.append({"concept_or_term": term_input, "definition_or_context": definition_input})
                st.toast("Card compiled successfully!")
                st.session_state.active_mode = "Flashcards"

        if st.session_state.flashcards:
            if st.button("🎮 Launch Review Session Now", use_container_width=True):
                st.session_state.active_mode = "Flashcards"
                st.session_state.current_index = 0
                st.session_state.reveal_card = False
                st.rerun()

    st.write("---")
    st.markdown("### 🗂️ Saved Track Cabinets")
    if st.session_state.nested_folders:
        active_track = st.selectbox("Open Folders:", list(st.session_state.nested_folders.keys()))
        if st.button("📥 Retrieve Saved Set", use_container_width=True):
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
            st.session_state.temp_selection = None
            st.rerun()

# --- MAIN CONTROLLER PORT ---
if st.session_state.active_mode == "Welcome":
    st.markdown("""
    <div class='gizmo-card' style='text-align: center; border-top: 4px solid #6366f1;'>
        <h3 style='margin-top:0; color: #ffffff;'>👋 Welcome to BrainCrunch Studio</h3>
        <p style='color: #9ca3af;'>Configure your strategy preferences inside the side panel to break down files into interactive study decks instantly.</p>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.active_mode == "Flashcards":
    idx = st.session_state.current_index
    if idx < len(st.session_state.flashcards):
        card = st.session_state.flashcards[idx]
        st.markdown(f"<p style='color:#9ca3af; font-weight:600; text-align:right; margin-bottom:0;'>🏷️ Card: {idx+1} / {len(st.session_state.flashcards)}</p>", unsafe_allow_html=True)
        
        if not st.session_state.reveal_card:
            st.markdown(f"<div class='flashcard-box'>{card['concept_or_term']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='flashcard-box flashcard-back'>{card['definition_or_context']}</div>", unsafe_allow_html=True)
            
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if st.button("🔄 Flip / Reveal Face", use_container_width=True):
                st.session_state.reveal_card = not st.session_state.reveal_card
                st.rerun()
        with col_f2:
            if st.button("Next Concept ➡️", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.reveal_card = False
                st.rerun()
    else:
        st.success("🏆 Collection Review Session Finished!")
        st.write("---")
        save_path = st.text_input("Name folder to archive flashcards:", value="My Custom Flashcards")
        if st.button("💾 Archive Cards Pack to Storage", use_container_width=True):
            st.session_state.nested_folders[save_path] = {"type": "Flashcards", "data": st.session_state.flashcards}
            save_local_storage(st.session_state.nested_folders)
            st.toast("Archived successfully!")
        if st.button("🏠 Head Back Home", use_container_width=True):
            st.session_state.active_mode = "Welcome"
            st.rerun()

elif st.session_state.active_mode == "Quiz":
    idx = st.session_state.current_index
    if idx < len(st.session_state.questions):
        q_item = st.session_state.questions[idx]
        
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            st.markdown(f"Running Score Count: <b style='color:#6366f1; font-size:20px;'>{st.session_state.score}</b> Points", unsafe_allow_html=True)
        with col_h2:
            st.markdown(f"<p style='text-align:right; color:#9ca3af;'>Progress: <b>{idx+1}/{len(st.session_state.questions)}</b></p>", unsafe_allow_html=True)
            
        st.progress((idx) / len(st.session_state.questions))
        st.write("---")
        
        st.markdown(f"<div class='gizmo-card'><h4>❓ {q_item['question']}</h4></div>", unsafe_allow_html=True)
        st.write("")
        
        # Clean Radio selection matrix without checking results beforehand
        selected_radio = st.radio(
            "Choose your option answer variant:", 
            options=q_item['options'], 
            index=None if st.session_state.temp_selection is None else q_item['options'].index(st.session_state.temp_selection),
            disabled=st.session_state.answered,
            key=f"quiz_radio_{idx}"
        )
        
        if selected_radio:
            st.session_state.temp_selection = selected_radio

        st.write("")
        
        # Process Actions
        if not st.session_state.answered:
            if st.button("📥 Submit Answer Selection", use_container_width=True, disabled=(st.session_state.temp_selection is None)):
                st.session_state.answered = True
                st.session_state.selected_option = st.session_state.temp_selection
                if st.session_state.selected_option == q_item['correct']:
                    st.session_state.score += 10
                st.rerun()
                
        if st.session_state.answered:
            if st.session_state.selected_option == q_item['correct']:
                st.success(f"🎯 Magnificent! Correct Response Selected")
            else:
                st.error(f"❌ Missed Selection. Target Answer was: {q_item['correct']}")
                
            st.info(f"💡 **Context Breakdown:** {q_item['explanation']}")
            st.write("---")
            
            if st.button("Advance to Next Concept ➡️", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.answered = False
                st.session_state.selected_option = None
                st.session_state.temp_selection = None
                st.rerun()
    else:
        st.balloons()
        st.markdown("<div class='gizmo-card' style='text-align:center;'><h3>🏆 Assessment Session Finished!</h3></div>", unsafe_allow_html=True)
        st.metric("Total Evaluation Score:", f"{st.session_state.score} Pts")
        
        st.write("---")
        save_path = st.text_input("Name folder to save quiz:", value="My Custom Quiz")
        if st.button("💾 Archive Quiz to Storage", use_container_width=True):
            st.session_state.nested_folders[save_path] = {"type": "Quiz", "data": st.session_state.questions}
            save_local_storage(st.session_state.nested_folders)
            st.toast("Archived successfully!")
            
        if st.button("🏠 Back to Home Screen", use_container_width=True):
            st.session_state.active_mode = "Welcome"
            st.rerun()
