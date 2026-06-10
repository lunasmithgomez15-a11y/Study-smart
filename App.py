import json
import re
import random
import base64
import urllib.parse
import streamlit as st
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types
from pydantic import BaseModel

# Safe fallbacks for optional document processing libraries
try:
    from pptx import Presentation
except ImportError:
    Presentation = None

try:
    import docx
except ImportError:
    docx = None

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="BrainCrunch Game Arena", 
    page_icon="🎮", 
    layout="centered"
)

# --- PYDANTIC BLUEPRINT MODELS ---
class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct: str
    explanation: str

# --- INITIALIZE STATE VARIABLES ---
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "questions" not in st.session_state:
    st.session_state.questions = []
if "review_notes" not in st.session_state:
    st.session_state.review_notes = ""
if "active_mode" not in st.session_state:
    st.session_state.active_mode = "Welcome" 
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "score" not in st.session_state:
    st.session_state.score = 0
if "correct_answers_count" not in st.session_state:
    st.session_state.correct_answers_count = 0
if "answered" not in st.session_state:
    st.session_state.answered = False
if "selected_option" not in st.session_state:
    st.session_state.selected_option = None
if "streak" not in st.session_state:
    st.session_state.streak = 0
if "max_streak" not in st.session_state:
    st.session_state.max_streak = 0
if "leaderboard" not in st.session_state:
    st.session_state.leaderboard = []
if "nested_folders" not in st.session_state:
    st.session_state.nested_folders = {} 
if "quiz_host_persona" not in st.session_state:
    st.session_state.quiz_host_persona = "Enthusiastic School Teacher"
if "app_language" not in st.session_state:
    st.session_state.app_language = "English"

# Student Lifeline Tracking Configurations
if "lifeline_5050_used" not in st.session_state:
    st.session_state.lifeline_5050_used = False
if "lifeline_hint_used" not in st.session_state:
    st.session_state.lifeline_hint_used = False
if "hidden_options" not in st.session_state:
    st.session_state.hidden_options = []

# AUTOMATIC SECRET API KEY CHECK 
if "gemini" in st.secrets:
    st.session_state.api_key = st.secrets["gemini"]["api_key"]

# --- SFX AUDIO INJECTION MECHANISM ---
def play_sfx(audio_url):
    st.components.v1.html(
        f"""
        <audio autoplay style="display:none;">
            <source src="{audio_url}" type="audio/mp3">
        </audio>
        """,
        height=0,
    )

CORRECT_SFX = "https://actions.google.com/sounds/v1/alarms/digital_watch_alarm_long.ogg"
WRONG_SFX = "https://actions.google.com/sounds/v1/cartoon/slide_whistle_down.ogg"

# --- FILE EXTRACTOR MECHANISM ---
def extract_text_from_file(file):
    filename = file.name.lower()
    text = ""
    if filename.endswith(".pdf"):
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
    elif filename.endswith(".pptx"):
        if Presentation:
            prs = Presentation(file)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
    elif filename.endswith(".docx"):
        if docx:
            doc = docx.Document(file)
            text += "\n".join([p.text for p in doc.paragraphs])
    elif filename.endswith(".txt"):
        text += file.read().decode("utf-8", errors="ignore")
    return text

def get_youtube_id(url):
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([item['text'] for item in transcript_list])
    except Exception:
        return None

# --- UPGRADED DEEP AI CORE ENGINES ---
def generate_questions_with_ai(study_material, api_key, num_questions, persona, language):
    try:
        client = genai.Client(api_key=api_key)
        
        lang_instruction = "All outputs must be written entirely in English."
        if language == "Tagalog / Filipino":
            lang_instruction = "CRITICAL: You are teaching a Filipino/Tagalog class. All questions, options, and explanations MUST be written in clear, natural Tagalog."

        prompt = f"""
        You are a smart game host playing with a student. Use this personality profile: "{persona}".
        {lang_instruction}
        
        TASK: Parse the provided text material thoroughly. Perform maximum deep information extraction—do not skip technical details, math variables, or niche terms. Create exactly {num_questions} high-quality multiple-choice questions.
        
        MATH RULE: If the question or options involve complex formulas, chemical equations, or mathematical expressions, format them cleanly using standard LaTeX notation (wrap with single '$' for inline math or double '$$' for large block equations) so they render beautifully on screen.
        
        Study Material:
        {study_material}
        """
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
        st.error(f"🛑 AI System Error: {e}")
        return None

def generate_summary_with_ai(study_material, api_key, persona, language):
    try:
        client = genai.Client(api_key=api_key)
        
        lang_instruction = "Write the summary sheet in English."
        if language == "Tagalog / Filipino":
            lang_instruction = "CRITICAL: Write the entire summary sheet in fluent Tagalog/Filipino language."

        prompt = f"""
        You are an expert academic tutor with this personality profile: "{persona}".
        {lang_instruction}
        
        TASK: Read the uploaded file text and perform an exhaustive deep information extraction. Pull out all definitions, key historical dates, core concepts, formulas, and laws. 
        
        FORMAT RULES:
        - Organize using neat Markdown bullet points and bold headers.
        - For mathematical formulas, equations, matrices, or variable fractions, use beautiful, readable standard LaTeX tags ($...$ or $$...$$). Make numbers and step-by-step math breakdowns perfectly organized.
        
        Study Material:
        {study_material}
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        st.error(f"🛑 AI Summary Error: {e}")
        return None

# --- APP FRONTEND ---
st.markdown("<h1 style='text-align: center;'>🧠 BrainCrunch Studio Pro</h1>", unsafe_allow_html=True)

# --- SIDEBAR CONTROL UNIT ---
with st.sidebar:
    st.header("⚙️ Global Settings")
    user_role = st.selectbox("I am a...", ["Player / Student", "Admin / Creator"])
    
    st.write("---")
    st.subheader("💾 Restore Cabinet Backup")
    backup_file = st.file_uploader("Upload cabinet_backup.json:", type=["json"])
    if backup_file:
        try:
            st.session_state.nested_folders = json.load(backup_file)
            st.toast("Cabinet Data Restored Successfully! 🗂️")
        except Exception:
            st.error("Invalid file layout.")

    # ADMIN / CREATOR DASHBOARD
    if user_role == "Admin / Creator":
        st.write("---")
        st.subheader("🔑 Admin Access")
        admin_pass = st.text_input("Enter Admin Password:", type="password")
        
        if admin_pass == "studio123":
            st.success("Access Verified!")
            
            if not st.session_state.api_key:
                st.session_state.api_key = st.text_input("Fallback Gemini API Key:", type="password")
            
            st.write("---")
            st.subheader("🌐 Language & Topic Filter")
            st.session_state.app_language = st.selectbox("Subject Focus Language:", ["English", "Tagalog / Filipino"])
            
            st.subheader("🧙‍♂️ Game Host Persona")
            st.session_state.quiz_host_persona = st.selectbox(
                "Choose AI Game Master:",
                ["Enthusiastic School Teacher", "Sarcastic Pirate Coach", "Strict Drill Sergeant", "Whimsical Fantasy Wizard"]
            )
            
            st.write("---")
            st.subheader("🧙‍♂️ AI Content Engine")
            output_type = st.radio("What should the AI build?", ["Gamified Quiz Decks", "Clean Review Summaries"])
            
            if output_type == "Gamified Quiz Decks":
                question_count = st.number_input("How many questions?", min_value=1, max_value=150, value=5, step=5)
            
            st.write("---")
            input_mode = st.radio("Input Source:", ["Upload Files (PDF, PPTX, DOCX, TXT)", "Voice Lesson Record / Audio Note", "YouTube Video Link"])
            
            study_text = ""
            triggered_generation = False
            
            if input_mode == "Upload Files (PDF, PPTX, DOCX, TXT)":
                uploaded_files = st.file_uploader("Drop slides or files:", type=["pdf", "pptx", "docx", "txt"], accept_multiple_files=True)
                if uploaded_files and st.button("🚀 Process Study Material", use_container_width=True):
                    with st.spinner("Extracting content strings... 📂"):
                        for f in uploaded_files:
                            study_text += extract_text_from_file(f) + "\n"
                        triggered_generation = True

            elif input_mode == "Voice Lesson Record / Audio Note":
                recorded_audio = st.file_uploader("Upload audio lesson clip:", type=["mp3", "wav", "m4a", "ogg"])
                if recorded_audio and st.button("🎙️ Process Lesson Audio Track", use_container_width=True):
                    if not st.session_state.api_key:
                        st.error("API Key required for audio extraction transcript tasks.")
                    else:
                        with st.spinner("Transcribing lesson audio... 💬"):
                            try:
                                client = genai.Client(api_key=st.session_state.api_key)
                                audio_upload_res = client.files.upload(file
                                
