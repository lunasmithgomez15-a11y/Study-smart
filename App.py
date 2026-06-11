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

# --- GIZMO LUXURY DARK THEME STYLING ---
st.set_page_config(
    page_title="BrainCrunch Premium Studio", 
    page_icon="🧠", 
    layout="centered"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    /* Global Overrides */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    
    .stApp {
        background-color: #0b0f19;
    }
    
    /* Premium Containers */
    .gizmo-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 20px;
        padding: 28px;
        box-shadow: 0 10px 30px -10px rgba(0,0,0,0.7);
        margin-bottom: 24px;
    }
    
    /* Interactive Deluxe Flashcard Container */
    .flashcard-wrapper {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        color: #ffffff;
        border-radius: 24px;
        padding: 60px 32px;
        text-align: center;
        min-height: 260px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        font-weight: 600;
        box-shadow: 0 20px 40px -15px rgba(99, 102, 241, 0.5);
        margin: 25px 0;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid rgba(255,255,255,0.1);
    }
    
    .flashcard-back {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        box-shadow: 0 20px 40px -15px rgba(16, 185, 129, 0.5) !important;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #070a13 !important;
        border-right: 1px solid #1f2937;
    }
    
    /* Custom Header Accents */
    .gradient-text {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        text-align: center;
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
        st.error(f"Storage Sync Error: {e}")

# --- STRICT SCHEMA BLUEPRINTS ---
class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct: str
    explanation: str

class FlashcardItem(BaseModel):
    concept_or_term: str
    definition_or_context: str

# --- PERSISTENT LIFECYCLE STATES ---
states = {
    "api_key": "", "questions": [], "flashcards": [], 
    "active_mode": "Welcome", "current_index": 0, "score": 0, 
    "answered": False, "selected_option": None, "reveal_card": False
}
for key, value in states.items():
    if key not in st.session_state:
        st.session_state[key] = value

if "nested_folders" not in st.session_state:
    st.session_state.nested_folders = load_local_storage()

try:
    if hasattr(st, "secrets") and "gemini" in st.secrets:
        st.session_state.api_key = st.secrets["gemini"]["api_key"]
except Exception:
    pass

# --- PARSING ENGINES ---
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

# --- INTELLIGENT CONTEXTUAL FALLBACK ENGINES ---
def generate_smart_fallback_questions(text, count):
    # Fixed the choices: Splits paragraphs to pull sentence items instead of broken templates
    sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 25]
    if len(sentences) < 5:
        sentences = [
            "National education guidelines coordinate institutional administrative directives.",
            "Economic policies influence financial subsidies provided across administrative regions.",
            "Structural variables determine operational framework efficiency metrics over cycles."
        ]
        
    questions = []
    for i in range(count):
        base_sentence = sentences[i % len(sentences)]
        words = [w for w in re.split(r'\W+', base_sentence) if len(w) > 5]
        target_word = random.choice(words) if words else "Framework"
        
        # Build contextual questions
        questions.append({
            "question": f"Given the source study asset excerpt: \"{base_sentence}\" — What does this document identify as a key driver?",
            "options": [
                f"The systematic integration of {target_word} structures.",
                f"A secondary reduction in standard {target_word} implementation parameters.",
                f"External modifications completely independent of {target_word}.",
                "An administrative adjustment variant omitting baseline metrics."
            ],
            "correct": f"The systematic integration of {target_word} structures.",
            "explanation": "The processed document directly relates this phrase structure to active execution requirements."
        })
    return questions

def generate_smart_fallback_flashcards(text):
    sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 20]
    if len(sentences) < 3:
        sentences = ["Subsidy Allotment Rules", "Administrative Frameworks", "Operational Metrics"]
        
    cards = []
    for idx, item in enumerate(sentences[:8]):
        words = [w for w in re.split(r'\W+', item) if len(w) > 4]
        title_term = words[0] if words else f"Concept Focus {idx+1}"
        cards.append({
            "concept_or_term": f"🔍 {title_term}",
            "definition_or_context": f"Document context profile highlights: \"{item}\""
        })
    return cards

# --- CORE ADVANCED AI STREAM CONNECTORS ---
def generate_questions_with_ai(study_material, num_questions):
    if not st.session_state.api_key or len(st.session_state.api_key) < 10:
        return generate_smart_fallback_questions(study_material, num_questions)
        
    prompt = f"Generate exactly {num_questions} clear multiple choice questions based on this text. Text:\n{study_material}"
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
        
    prompt = f"Analyze this material and extract flashcard entries. Text:\n{study_material}"
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

# --- WORKSPACE CONTROL PANEL ---
st.markdown("<h1 class='gradient-text'>🧠 BrainCrunch Studio Pro</h1>", unsafe_allow_html=True)
st.write("")

with st.sidebar:
    st.markdown("<h3 style='color:#6366f1;'>⚙️ Configuration</h3>", unsafe_allow_html=True)
    user_role = st.selectbox("Current Profile:", ["Player / Student", "Admin / Creator"])
    
    if user_role == "Admin / Creator":
        admin_pass = st.text_input("Admin Password:", type="password")
        if admin_pass == "studio123":
            st.success("Admin Controls Unlocked")
            st.session_state.api_key = st.text_input("Gemini API Key:", value=st.session_state.api_key, type="password")
            
    st.write("---")
    st.markdown("<h3 style='color:#6366f1;'>🎯 Learning Goal</h3>", unsafe_allow_html=True)
    output_type = st.radio("Select Target:", ["Gizmo Flashcards AI", "Gamified Performance Quizzes"])
    
    # 🎯 PERMANENT QUESTION COUNT SELECTOR
    if output_type == "Gamified Performance Quizzes":
        question_count = st.slider("🎯 Number of Questions:", min_value=3, max_value=25, value=5, step=1)
        
    st.write("---")
    creation_method = st.radio("Creation Engine Style:", ["🤖 Automatically from Source", "✍️ Manually Create Cards"])
    
    if creation_method == "🤖 Automatically from Source":
        input_mode = st.radio("Source Material Channel:", ["Upload Files (PDF, TXT)", "YouTube Video Link"])
        study_text = ""
        run_generation = False
        
        if input_mode == "Upload Files (PDF, TXT)":
            uploaded_files = st.file_uploader("Drop study docs here:", type=["pdf", "txt"], accept_multiple_files=True)
            if uploaded_files and st.button("🚀 Process & Generate", use_container_width=True):
                for f in uploaded_files:
                    study_text += extract_text_from_file(f) + "\n"
                run_generation = True
                
        elif input_mode == "YouTube Video Link":
            yt_url = st.text_input("Paste YouTube Link:")
            if yt_url and st.button("🚀 Scan Video Streams", use_container_width=True):
                vid = get_youtube_id(yt_url)
                if vid:
                    study_text = get_youtube_transcript(vid)
                    run_generation = True

        if run_generation and study_text.strip():
            with st.spinner("Synthesizing information..."):
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
                        
    elif creation_method == "✍️ Manually Create Cards":
        st.markdown("#### 📝 Card Composer")
        with st.form("manual_entry_form"):
            term_input = st.text_input("Card Question / Front Word:")
            definition_input = st.text_area("Card Explanation / Back Text:")
            submitted = st.form_submit_button("➕ Append Card to Collection Deck")
            
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
    st.markdown("### 🗂️ Cabinets Storage")
    if st.session_state.nested_folders:
        active_track = st.selectbox("Open Folders:", list(st.session_state.nested_folders.keys()))
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

# --- RENDERING PORT ---
if st.session_state.active_mode == "Welcome":
    st.markdown("""
    <div class='gizmo-card' style='text-align: center; border-top: 4px solid #6366f1;'>
        <h3 style='color:#ffffff; margin-top:0;'>👋 Welcome to your Gizmo Environment</h3>
        <p style='color: #9ca3af;'>Configure your parameters inside the sidebar workspace to automatically break down files into interactive study decks or custom quizzes.</p>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.active_mode == "Flashcards":
    idx = st.session_state.current_index
    if idx < len(st.session_state.flashcards):
        card = st.session_state.flashcards[idx]
        st.markdown(f"<p style='color:#9ca3af; font-weight:600; text-align:right;'>Card Progress: {idx+1} / {len(st.session_state.flashcards)}</p>", unsafe_allow_html=True)
        
        if not st.session_state.reveal_card:
            st.markdown(f"<div class='flashcard-wrapper'>{card['concept_or_term']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='flashcard-wrapper flashcard-back'>{card['definition_or_context']}</div>", unsafe_allow_html=True)
            
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if st.button("🔄 Flip/Reveal", use_container_width=True):
                st.session_state.reveal_card = not st.session_state.reveal_card
                st.rerun()
        with col_f2:
            if st.button("Next Concept ➡️", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.reveal_card = False
                st.rerun()
    else:
        st.success("🏆 Review Session Completed!")
        save_path = st.text_input("Name folder to save flashcard deck:", value="My Custom Flashcards")
        if st.button("💾 Archive Deck Pack to Storage", use_container_width=True):
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
            st.markdown(f"Running Score: <b style='color:#10b981; font-size:20px;'>{st.session_state.score}</b> Pts", unsafe_allow_html=True)
        with col_h2:
            st.markdown(f"<p style='text-align:right; color:#9ca3af;'>Progress Tracker: <b>{idx+1}/{len(st.session_state.questions)}</b></p>", unsafe_allow_html=True)
            
        st.progress((idx) / len(st.session_state.questions))
        st.write("---")
        
        st.markdown(f"<div class='gizmo-card'><h4>❓ {q_item['question']}</h4></div>", unsafe_allow_html=True)
        
        for opt in q_item['options']:
            if not st.session_state.answered:
                if st.button(opt, key=f"qopt_{idx}_{opt}", use_container_width=True):
                    st.session_state.answered = True
                    st.session_state.selected_option = opt
                    st.rerun()
                    
        if st.session_state.answered:
            if st.session_state.selected_option == q_item['correct'] or st.session_state.selected_option[0] == q_item['correct'][0]:
                st.success(f"🎯 Correct Answer Selected — {st.session_state.selected_option}")
                if f"scored_{idx}" not in st.session_state:
                    st.session_state.score += 10
                    st.session_state[f"scored_{idx}"] = True
            else:
                st.error(f"❌ Selection Missed. Correct Answer was: {q_item['correct']}")
                
            st.info(f"💡 **Context breakdown:** {q_item['explanation']}")
            st.write("---")
            
            if st.button("Advance to Next Concept ➡️", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.answered = False
                st.session_state.selected_option = None
                st.rerun()
    else:
        st.balloons()
        st.markdown("<div class='gizmo-card' style='text-align:center;'><h3>🏆 Module Session Complete!</h3></div>", unsafe_allow_html=True)
        st.metric("Total Evaluation Score:", f"{st.session_state.score} Pts")
        
        save_path = st.text_input("Name folder to save quiz:", value="My Custom Quiz")
        if st.button("💾 Archive Quiz to Storage", use_container_width=True):
            st.session_state.nested_folders[save_path] = {"type": "Quiz", "data": st.session_state.questions}
            save_local_storage(st.session_state.nested_folders)
            st.toast("Archived successfully!")
            
        if st.button("🏠 Back to Home Screen", use_container_width=True):
            st.session_state.active_mode = "Welcome"
            st.rerun()
