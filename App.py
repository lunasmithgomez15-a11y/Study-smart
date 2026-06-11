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

# Optional file format handlers
try:
    from docx import Document
except ImportError:
    Document = None

try:
    from pptx import Presentation
except ImportError:
    Presentation = None

# --- GIZMO PREMIUM DARK WORKSPACE THEME ---
st.set_page_config(
    page_title="BrainCrunch Workspace Pro", 
    page_icon="🧠", 
    layout="centered"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght=400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    
    .stApp {
        background-color: #0b0f19;
    }
    
    .gizmo-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        margin-bottom: 20px;
    }
    
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

# --- STRICT UNTRUNCATED DATA STRUC ---
class QuizQuestion(BaseModel):
    question: str
    options: list[str]  # Must always contain exactly 4 unique choices parsed from file
    correct: str       # Must match one of the exact strings inside options
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

# --- CLEAN RAW DATA STREAMERS ---
def extract_text_from_file(file):
    filename = file.name.lower()
    text = ""
    try:
        if filename.endswith(".pdf"):
            reader = PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
        elif filename.endswith(".docx"):
            if Document is not None:
                doc = Document(io.BytesIO(file.read()))
                text += "\n".join([para.text for para in doc.paragraphs])
            else:
                text += "Error: python-docx library missing.\n"
        elif filename.endswith(".pptx"):
            if Presentation is not None:
                prs = Presentation(io.BytesIO(file.read()))
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            text += shape.text + "\n"
            else:
                text += "Error: python-pptx library missing.\n"
        elif filename.endswith(".txt"):
            text += file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        st.error(f"Error reading file {file.name}: {e}")
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

# --- SUPER SMART REASONING RECONSTRUCTION PLATFORM ---
def intelligent_quiz_synthesis(study_material, num_questions):
    """
    100% AI-Driven Parsing. No regular expressions can break or truncate questions anymore.
    """
    if not st.session_state.api_key or len(st.session_state.api_key) < 10:
        st.warning("⚠️ Running on local engine fallback. Provide an API key for advanced AI features.")
        return emergency_fallback_generator(study_material, num_questions)
        
    prompt = f"""
    You are a super smart AI exam parser. Read and understand everything in the provided document material.
    
    DIRECTIONS:
    1. Scan the text to see if there are already multiple-choice questions present. 
    2. Look at the end of the document, margins, or inline lines for an Answer Key (e.g., '1. A', '2. C' or bold markers). 
    3. If there are existing questions, copy them EXACTLY. You must extract the complete question text and ALL 4 choices (A, B, C, D). Do not truncate them or cut off options C and D!
    4. Map the true correct option based on the file's answer key. Do NOT default to making option A the correct answer. Mix up the positions naturally.
    5. If the document is just an informational study guide with NO existing questions, read it carefully, pick out the most important facts, data, configurations, or dates, and generate {num_questions} advanced multiple-choice questions.
    6. Never include verification stickers, emojis, or checkmarks (✅, ❌) inside the options array.
    
    Document Material Text:
    {study_material}
    """
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
    except Exception as e:
        st.error(f"AI Synthesis Interface Error: {e}")
        return emergency_fallback_generator(study_material, num_questions)

# --- EMERGENCY STABLE LOCAL BACKUP ---
def emergency_fallback_generator(text, count):
    clean_text = re.sub(r'\s+', ' ', text)
    sentences = [s.strip() for s in re.split(r'[.!?]', clean_text) if len(s.strip()) > 40]
    if len(sentences) < 4:
        sentences = ["Document fact reference alpha segment.", "Document fact reference beta segment.", "Document fact reference gamma segment.", "Document fact reference delta segment."]
        
    fallback_deck = []
    for i in range(min(count, len(sentences))):
        tgt = sentences[i]
        opts = [tgt, "Alternative option text choice X", "Alternative option text choice Y", "Alternative option text choice Z"]
        random.shuffle(opts)
        fallback_deck.append({
            "question": f"Which statement cleanly matches verified parameters within the text document context?",
            "options": opts,
            "correct": tgt,
            "explanation": f"Document explicitly notes: {tgt}"
        })
    return fallback_deck

def generate_flashcards_with_ai(study_material):
    if not st.session_state.api_key or len(st.session_state.api_key) < 10:
        clean_text = re.sub(r'\s+', ' ', study_material)
        sentences = [s.strip() for s in re.split(r'[.!?]', clean_text) if len(s.strip()) > 25]
        return [{"concept_or_term": f"🔍 Core Point {idx+1}", "definition_or_context": item} for idx, item in enumerate(sentences[:10])]
        
    prompt = f"Extract important terms and clear concepts into flashcards from this text:\n{study_material}"
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
        return [{"concept_or_term": "Concept Focus", "definition_or_context": "Sample overview description context data."}]

# --- APPLICATION INTERFACE CONTROLS ---
st.markdown("<h1 class='studio-title'>🧠 BrainCrunch Studio</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Identity Settings")
    user_role = st.selectbox("Current Workspace Profile:", ["Player / Student", "Admin / Creator"])
    
    if user_role == "Admin / Creator":
        admin_pass = st.text_input("Enter Pass Code:", type="password")
        if admin_pass == "studio123":
            st.success("Admin Control Enabled")
            st.session_state.api_key = st.text_input("System API Key Override:", value=st.session_state.api_key, type="password")
            
    st.write("---")
    st.markdown("### 🛠️ Study Mode Strategy")
    output_type = st.radio("Target Element:", ["Gizmo Flashcards AI", "Gamified Performance Quizzes"])
    
    if output_type == "Gamified Performance Quizzes":
        question_count = st.slider("🎯 Target Quiz Limit:", min_value=3, max_value=50, value=10, step=1)
        
    st.write("---")
    creation_method = re.sub("", "", st.radio("Creation Style:", ["🤖 Automatically from Source", "✍️ Manually Create Cards"]))
    
    if creation_method == "🤖 Automatically from Source":
        input_mode = st.radio("Input Source Channel:", ["Upload Files (PDF, DOCX, PPTX, TXT)", "YouTube Video Link"])
        study_text = ""
        run_generation = False
        
        if input_mode == "Upload Files (PDF, DOCX, PPTX, TXT)":
            uploaded_files = st.file_uploader("Drop study docs here:", type=["pdf", "txt", "docx", "pptx"], accept_multiple_files=True)
            if uploaded_files and st.button("🚀 Process & Parse Material", use_container_width=True):
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
            with st.spinner("Advanced AI reading document & checking answer keys..."):
                if output_type == "Gamified Performance Quizzes":
                    res = intelligent_quiz_synthesis(study_text, question_count)
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
        <p style='color: #9ca3af;'>Upload any document, presentation, or test questionnaire. The advanced AI engine analyzes the content, links back-end answer keys, and ensures complete formatting layout visibility.</p>
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
            if st.button("🔄 Flip Face", use_container_width=True):
                st.session_state.reveal_card = not st.session_state.reveal_card
                st.rerun()
        with col_f2:
            if st.button("Next Concept ➡️", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.reveal_card = False
                st.rerun()

elif st.session_state.active_mode == "Quiz":
    idx = st.session_state.current_index
    if idx < len(st.session_state.questions):
        q_item = st.session_state.questions[idx]
        
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            st.markdown(f"Running Score: <b style='color:#6366f1; font-size:20px;'>{st.session_state.score}</b> Pts", unsafe_allow_html=True)
        with col_h2:
            st.markdown(f"<p style='text-align:right; color:#9ca3af;'>Question: <b>{idx+1}/{len(st.session_state.questions)}</b></p>", unsafe_allow_html=True)
            
        st.progress((idx) / len(st.session_state.questions))
        st.write("---")
        
        # Super clean question container box
        st.markdown(f"<div class='gizmo-card'><p style='font-size: 18px; line-height: 1.6; margin: 0;'>{q_item['question']}</p></div>", unsafe_allow_html=True)
        st.write("")
        
        # High-Fidelity Radio Selector Component
        selected_radio = st.radio(
            "Select the correct option:", 
            options=q_item['options'], 
            index=None if st.session_state.temp_selection is None else q_item['options'].index(st.session_state.temp_selection),
            disabled=st.session_state.answered,
            key=f"quiz_radio_pro_{idx}"
        )
        
        if selected_radio:
            st.session_state.temp_selection = selected_radio

        st.write("")
        
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
