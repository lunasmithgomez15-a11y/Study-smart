import json
import re
import random
import base64
import streamlit as st
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types
from pydantic import BaseModel

# Safe fallbacks for document processing libraries
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
    page_title="BrainCrunch AI Game Studio", 
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
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "score" not in st.session_state:
    st.session_state.score = 0
if "answered" not in st.session_state:
    st.session_state.answered = False
if "selected_option" not in st.session_state:
    st.session_state.selected_option = None
if "streak" not in st.session_state:
    st.session_state.streak = 0
if "leaderboard" not in st.session_state:
    st.session_state.leaderboard = []
if "quiz_folders" not in st.session_state:
    st.session_state.quiz_folders = {} # Schema: {"Subject Name": [list of quiz questions]}

# --- DECODE SHARE LINKS INSTANTLY ---
if "challenge" in st.query_params and not st.session_state.questions:
    try:
        decoded_bytes = base64.b64decode(st.query_params["challenge"])
        shared_quiz = json.loads(decoded_bytes.decode("utf-8"))
        st.session_state.questions = shared_quiz
        st.toast("🎯 Challenge Quiz Loaded From Link Successfully!", icon="🔥")
    except Exception:
        st.error("Could not parse the challenge link correctly.")

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
        else:
            st.error("Add python-pptx to requirements.txt to parse presentations!")
            
    elif filename.endswith(".docx"):
        if docx:
            doc = docx.Document(file)
            text += "\n".join([p.text for p in doc.paragraphs])
        else:
            st.error("Add python-docx to requirements.txt to parse Word files!")
            
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
    except Exception as e:
        st.error(f"⚠️ YouTube Extraction Failed! CC required. Error: {e}")
        return None

def generate_questions_with_ai(study_material, api_key):
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are a fun school teacher making a gamified quiz for a student.
        Based on the following material, generate 5 high-quality multiple-choice questions.
        Provide exactly 3 options (A, B, C), a 'correct' field ('A', 'B', or 'C'),
        and a funny child-friendly vivid analogy 'explanation'.
        
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

# --- WEB APP FRONTEND ---

st.title("🧠 BrainCrunch AI Studio")
st.caption("Organize study material folders and battle friends inside your personalized mobile arcade arena!")

# --- SIDEBAR CONTROL UNIT ---
with st.sidebar:
    st.header("🔑 Authentication")
    api_key_input = st.text_input("Gemini API Key:", type="password", value=st.session_state.api_key)
    if api_key_input:
        st.session_state.api_key = api_key_input
        
    st.write("---")
    st.header("🎮 Generator Dashboard")
    mode = st.radio("Choose Input Type:", ["Upload Files (PDF, PPT, DOCX)", "YouTube Video Link", "Enter Friend's Share Code"])
    
    # 1. FILE UPLOAD FACTORY
    if mode == "Upload Files (PDF, PPT, DOCX)":
        st.subheader("📁 Study Locker")
        uploaded_files = st.file_uploader("Drop notes, presentations, or papers:", type=["pdf", "pptx", "docx", "txt"], accept_multiple_files=True)
        
        if uploaded_files and st.button("🧙‍♂️ Bake Files to Levels!", use_container_width=True):
            if not st.session_state.api_key:
                st.error("Please provide your API key first!")
            else:
                with st.spinner("AI processing your study material vault... 🍳"):
                    combined_text = ""
                    for f in uploaded_files:
                        combined_text += extract_text_from_file(f) + "\n"
                    
                    ai_questions = generate_questions_with_ai(combined_text, st.session_state.api_key)
                    if ai_questions:
                        st.session_state.questions = ai_questions
                        st.session_state.current_index = 0
                        st.session_state.score = 0
                        st.session_state.streak = 0
                        st.session_state.answered = False
                        st.sidebar.success(f"Generated {len(ai_questions)} levels!")
                        st.rerun()

    # 2. YOUTUBE FACTORY
    elif mode == "YouTube Video Link":
        st.subheader("📺 Paste Video Stream")
        yt_url = st.text_input("YouTube Video URL:")
        
        if yt_url and st.button("🎬 Convert Video to Levels!", use_container_width=True):
            if not st.session_state.api_key:
                st.error("Please provide your API key first!")
            else:
                with st.spinner("Analyzing video transcript strings... 🍿"):
                    v_id = get_youtube_id(yt_url)
                    if v_id:
                        transcript_text = get_youtube_transcript(v_id)
                        if transcript_text:
                            ai_questions = generate_questions_with_ai(transcript_text, st.session_state.api_key)
                            if ai_questions:
                                st.session_state.questions = ai_questions
                                st.session_state.current_index = 0
                                st.session_state.score = 0
                                st.session_state.streak = 0
                                st.session_state.answered = False
                                st.sidebar.success("Video levels initialized!")
                                st.rerun()

    # 3. CODE INJECTOR
    elif mode == "Enter Friend's Share Code":
        st.subheader("📥 Enter Study Circle Code")
        input_code = st.text_area("Paste code block here:")
        if st.button("⚡ Inject Circle Quiz", use_container_width=True):
            if input_code:
                try:
                    decoded_bytes = base64.b64decode(input_code.strip())
                    st.session_state.questions = json.loads(decoded_bytes.decode("utf-8"))
                    st.session_state.current_index = 0
                    st.session_state.score = 0
                    st.session_state.streak = 0
                    st.session_state.answered = False
                    st.sidebar.success("Friend's quiz successfully synchronized!")
                    st.rerun()
                except Exception:
                    st.sidebar.error("Invalid share code pattern.")

    st.write("
    
