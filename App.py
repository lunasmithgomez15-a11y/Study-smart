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
    st.session_state.quiz_folders = {}

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

def generate_questions_with_ai(study_material, api_key, num_questions):
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are a fun school teacher making a gamified quiz for a student.
        Based on the following material, generate exactly {num_questions} high-quality multiple-choice questions.
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
st.caption("Organize your subjects into custom folders, choose your test size, and challenge your friends!")

# --- SIDEBAR CONTROL UNIT ---
with st.sidebar:
    st.header("🔑 Authentication")
    api_key_input = st.text_input("Gemini API Key:", type="password", value=st.session_state.api_key)
    if api_key_input:
        st.session_state.api_key = api_key_input
        
    st.write("---")
    st.header("🎮 Generator Dashboard")
    
    # 🌟 NEW FEATURE: QUESTION LENGTH SELECTOR 🌟
    st.subheader("📏 Session Length")
    question_count = st.number_input(
        "How many questions do you want?", 
        min_value=1, 
        max_value=150, 
        value=5, 
        step=5,
        help="Type or select any amount up to 150 questions!"
    )
    
    st.write("---")
    mode = st.radio("Choose Input Type:", ["Upload Files (PDF, PPTX, DOCX, TXT)", "YouTube Video Link", "Enter Friend's Share Code"])
    
    # 1. THE FILE ENGINE
    if mode == "Upload Files (PDF, PPTX, DOCX, TXT)":
        st.subheader("📁 Study Locker")
        uploaded_files = st.file_uploader("Drop notes, presentations, or papers:", type=["pdf", "pptx", "docx", "txt"], accept_multiple_files=True)
        
        if uploaded_files and st.button("🧙‍♂️ Bake Files to Levels!", use_container_width=True):
            if not st.session_state.api_key:
                st.error("Please provide your API key first!")
            else:
                with st.spinner(f"AI reading materials to create {question_count} levels... 🍳"):
                    combined_text = ""
                    for f in uploaded_files:
                        combined_text += extract_text_from_file(f) + "\n"
                    
                    ai_questions = generate_questions_with_ai(combined_text, st.session_state.api_key, question_count)
                    if ai_questions:
                        st.session_state.questions = ai_questions
                        st.session_state.current_index = 0
                        st.session_state.score = 0
                        st.session_state.streak = 0
                        st.session_state.answered = False
                        st.sidebar.success(f"Generated {len(ai_questions)} levels!")
                        st.rerun()

    # 2. THE YOUTUBE ENGINE
    elif mode == "YouTube Video Link":
        st.subheader("📺 Paste Video Stream")
        yt_url = st.text_input("YouTube Video URL:")
        
        if yt_url and st.button("🎬 Convert Video to Levels!", use_container_width=True):
            if not st.session_state.api_key:
                st.error("Please provide your API key first!")
            else:
                with st.spinner(f"Analyzing video to bake {question_count} levels... 🍿"):
                    v_id = get_youtube_id(yt_url)
                    if v_id:
                        transcript_text = get_youtube_transcript(v_id)
                        if transcript_text:
                            ai_questions = generate_questions_with_ai(transcript_text, st.session_state.api_key, question_count)
                            if ai_questions:
                                st.session_state.questions = ai_questions
                                st.session_state.current_index = 0
                                st.session_state.score = 0
                                st.session_state.streak = 0
                                st.session_state.answered = False
                                st.sidebar.success(f"Video levels initialized with {len(ai_questions)} tasks!")
                                st.rerun()

    # 3. SHARE CODE INJECTOR
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

    st.write("---")
    st.header("🗂️ Subject Folders")
    
    # Save active deck to folder segregation area
    if st.session_state.questions:
        st.write("**File Current Quiz Away:**")
        folder_name = st.text_input("Subject / Topic Title:", value="Science 101", key="folder_save_input")
        if st.button("📂 Save Quiz to Folder", use_container_width=True):
            st.session_state.quiz_folders[folder_name] = st.session_state.questions
            st.toast(f"Saved into folder: {folder_name}! 📁")
            st.rerun()
            
    # Display current available folders
    if st.session_state.quiz_folders:
        st.write("**Your Saved Folders:**")
        for f_name, saved_q in st.session_state.quiz_folders.items():
            col_load, col_del = st.columns([3, 1])
            with col_load:
                if st.button(f"📁 {f_name} ({len(saved_q)} Qs)", key=f"load_f_{f_name}", use_container_width=True):
                    st.session_state.questions = saved_q
                    st.session_state.current_index = 0
                    st.session_state.score = 0
                    st.session_state.streak = 0
                    st.session_state.answered = False
                    st.toast(f"Loaded folder: {f_name}! 🎮")
                    st.rerun()
            with col_del:
                if st.button("❌", key=f"del_f_{f_name}"):
                    del st.session_state.quiz_folders[f_name]
                    st.rerun()
    else:
        st.caption("No folders created yet. Generate a quiz and save it here!")

    st.write("---")
    if st.button("🔄 Full Arena Reset", use_container_width=True):
        st.session_state.questions = []
        st.session_state.quiz_folders = {}
        st.session_state.current_index = 0
        st.session_state.score = 0
        st.session_state.streak = 0
        st.session_state.answered = False
        st.session_state.selected_option = None
        st.query_params.clear()
        st.rerun()

# --- MAIN RUNTIME ARENA ---
if not st.session_state.questions:
    st.info("💡 **Welcome to BrainCrunch Studio!**\n\n1. Open the left control panel using the `>>` button.\n2. Paste your Gemini API key.\n3. **Choose your desired question count.**\n4. Drop notes, PPTX slides, word files, or video links to start!")
else:
    idx = st.session_state.current_index
    if idx < len(st.session_state.questions):
        current_q = st.session_state.questions[idx]
        
        # UI Header Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="🏆 Score", value=f"{st.session_state.score} pts")
        with col2:
            st.metric(label="🔥 Streak", value=f"{st.session_state.streak} Wins")
        with col3:
            st.write(f"Stage {idx + 1} / {len(st.session_state.questions)}")
            
        st.progress((idx) / len(st.session_state.questions))
        st.write("---")
        
        st.markdown(f"### ❓ {current_q['question']}")
        
        # Tap options for fast phone execution
        for option in current_q['options']:
            if not st.session_state.answered:
                if st.button(option, key=f"btn_{idx}_{option}", use_container_width=True):
                    st.session_state.answered = True
                    st.session_state.selected_option = option
                    st.rerun()
                    
        if st.session_state.answered:
            user_letter = st.session_state.selected_option[0]
            correct_letter = current_q["correct"]
            
            if user_letter == correct_letter:
                st.balloons()
                st.success(f"🌟 **CORRECT HIT!** You chose: {st.session_state.selected_option}")
                if f"scored_{idx}" not in st.session_state:
                    st.session_state.score += 10 + (st.session_state.streak * 2)
                    st.session_state.streak += 1
                    st.session_state[f"scored_{idx}"] = True
            else:
                st.snow()
                st.error(f"💔 **DEFLECTED.** You chose {user_letter}. Correct answer path: **{correct_letter}**.")
                st.session_state.streak = 0
                
            st.info(f"💡 **Memory Scoop:**\n\n{current_q['explanation']}")
            
            if st.button("➡️ Advance to Next Level", use_container_width=True):
                st.session_state.current_index += 1
                st.session_state.answered = False
                st.session_state.selected_option = None
                st.rerun()
    else:
        # --- END RUN LOBBY & SHARING UNIT ---
        st.success("🏆 **CAMP RUN COMPLETED!** 🏆")
        
        st.subheader("📊 Performance Scorecard")
        st.metric(label="🎖️ Your Final Score", value=f"{st.session_state.score} Points")
        
        player_name = st.text_input("Enter your name for the Score Matrix Board:", value="Player 1")
        if st.button("💾 Log Score", use_container_width=True):
            st.session_state.leaderboard.append({"name": player_name, "score": st.session_state.score})
            st.toast("Score added to local bracket session!", icon="🛡️")
            
        if st.session_state.leaderboard:
            st.write("### 🏁 Local Session Ranking")
            sorted_board = sorted(st.session_state.leaderboard, key=lambda x: x['score'], reverse=True)
            for place, entry in enumerate(sorted_board, 1):
                st.write(f"**#{place}** {entry['name']} — `{entry['score']} pts`")

        st.write("---")
        st.subheader("📢 Challenge Your Friends!")
        st.write("Text this unique share code to your friends. They can paste it on their app to play this exact deck!")
        
        raw_json = json.dumps(st.session_state.questions)
        encoded_string = base64.b64encode(raw_json.encode('utf-8')).decode('utf-8')
        
        st.text_area("📋 Copy this Share Code:", value=encoded_string)
        
        if st.button("🔄 Reset & Replay This Session", use_container_width=True):
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.streak = 0
            st.session_state.answered = False
            st.session_state.selected_option = None
            st.rerun()
                
