import json
import re
import random
import streamlit as st
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types
from pydantic import BaseModel

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="BrainCrunch AI Game Studio", 
    page_icon="🎮", 
    layout="centered"
)

# --- PYDANTIC BLUEPRINT MODELS ---
# This serves as a solid structural contract for the AI's response schema
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

# --- CORE UTILITY FUNCTIONS ---

def get_youtube_id(url):
    """Slices open a YouTube link to pull out its unique 11-character video ID."""
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_youtube_transcript(video_id):
    """Reaches into YouTube, steals the video script/subtitles, and returns it as a paragraph."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        full_script = " ".join([item['text'] for item in transcript_list])
        return full_script
    except Exception as e:
        st.error(f"⚠️ YouTube Extraction Failed! Make sure the video has Subtitles/CC enabled. Error: {e}")
        return None

def generate_questions_with_ai(study_material, api_key):
    """Feeds text to the Gemini AI Engine and extracts structured quiz objects."""
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        You are a fun, witty school teacher making a gamified quiz for a student.
        Based on the following study material, generate 5 high-quality multiple-choice questions.
        
        CRITICAL INSTRUCTIONS:
        1. Make the questions highly engaging and interactive.
        2. Provide exactly 3 diverse options (A, B, C).
        3. Provide a 'correct' field which must be just the letter 'A', 'B', or 'C'.
        4. Provide an 'explanation' that explains the answer like the user is a child, connecting it to something funny, silly, or a vivid analogy so it leaves a permanent mark in their mind.
        
        Study Material:
        {study_material}
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[QuizQuestion], # Clean list blueprint declaration
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"🛑 AI System Error: {e}")
        return None

# --- WEB APP FRONTEND ---

st.title("🧠 BrainCrunch AI Game Studio")
st.caption("Transform dry PDFs, complex notes, and YouTube videos into an addictive arcade arena!")

# --- SIDEBAR CONTROL UNIT ---
with st.sidebar:
    st.header("🔑 Authentication")
    api_key_input = st.text_input("Gemini API Key:", type="password", value=st.session_state.api_key)
    if api_key_input:
        st.session_state.api_key = api_key_input
    st.write("[Grab a free API key instantly from Google AI Studio](https://aistudio.google.com/)")
    
    st.write("---")
    st.header("🎮 Generator Dashboard")
    mode = st.radio("Choose Input Type:", ["Multiple PDFs", "YouTube Video Link", "Custom Manual Question"])
    
    # 1. THE PDF ENGINE
    if mode == "Multiple PDFs":
        st.subheader("📁 Upload Materials")
        uploaded_files = st.file_uploader("Upload essays, articles, or lecture notes:", type=["pdf"], accept_multiple_files=True)
        
        if uploaded_files and st.button("🧙‍♂️ AI, Convert PDFs to Levels!"):
            if not st.session_state.api_key:
                st.error("Please provide your API key first!")
            else:
                with st.spinner("AI is reading through your documents... 🍳"):
                    combined_text = ""
                    for uploaded_file in uploaded_files:
                        reader = PdfReader(uploaded_file)
                        for page in reader.pages:
                            combined_text += page.extract_text() + "\n"
                    
                    ai_questions = generate_questions_with_ai(combined_text, st.session_state.api_key)
                    if ai_questions:
                        st.session_state.questions = ai_questions
                        st.session_state.current_index = 0
                        st.session_state.score = 0
                        st.session_state.streak = 0
                        st.session_state.answered = False
                        st.sidebar.success(f"Successfully baked {len(ai_questions)} levels!")
                        st.rerun()

    # 2. THE YOUTUBE ENGINE
    elif mode == "YouTube Video Link":
        st.subheader("📺 Paste Stream")
        yt_url = st.text_input("YouTube Video URL:")
        
        if yt_url and st.button("🎬 Convert Video to Levels!"):
            if not st.session_state.api_key:
                st.error("Please provide your API key first!")
            else:
                with st.spinner("Siphoning video transcript and generating quiz maps... 🍿"):
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
                                st.sidebar.success(f"Successfully baked {len(ai_questions)} video levels!")
                                st.rerun()
                    else:
                        st.error("Could not parse YouTube link. Verify it is correct!")

    # 3. MANUAL PICTURE CREATOR ENGINE
    elif mode == "Custom Manual Question":
        st.subheader("📝 Manual Level Editor")
        q_text = st.text_input("Your Question:")
        opt_a = st.text_input("Choice A:")
        opt_b = st.text_input("Choice B:")
        opt_c = st.text_input("Choice C:")
        correct_letter = st.selectbox("Designate Correct Letter:", ["A", "B", "C"])
        expl_text = st.text_area("Child-Friendly Dynamic Explanation:")
        q_image = st.file_uploader("📸 Bind Graphic Image (Optional)", type=["png", "jpg", "jpeg"])
        
        if st.button("➕ Inject Custom Question"):
            if q_text and opt_a and opt_b:
                new_q = {
                    "question": q_text,
                    "options": [f"A) {opt_a}", f"B) {opt_b}", f"C) {opt_c}" if opt_c else ""],
                    "correct": correct_letter,
                    "explanation": expl_text if expl_text else "It's magic!",
                    "image": q_image.read() if q_image else None
                }
                new_q["options"] = [o for o in new_q["options"] if o]
                st.session_state.questions.append(new_q)
                st.sidebar.success("Custom question injected into stack!")
            else:
                st.sidebar.error("Fill out at least Question text, Option A, and Option B!")

    st.write("---")
    if st.session_state.questions and st.button("🔀 Shuffle Current Deck"):
        random.shuffle(st.session_state.questions)
        st.session_state.current_index = 0
        st.session_state.answered = False
        st.success("Deck shuffled!")
        st.rerun()

    if st.button("🔄 Full System Reset"):
        st.session_state.questions = []
        st.session_state.current_index = 0
        st.session_state.score = 0
        st.session_state.streak = 0
        st.session_state.answered = False
        st.session_state.selected_option = None
        st.rerun()

# --- MAIN RUNTIME ARENA ---
if not st.session_state.questions:
    st.info("👋 **Welcome to BrainCrunch Studio!** To launch your game:\n1. Provide your free Gemini key on the left panel.\n2. Pick a study file, paste a YouTube video link, or write custom picture cards!\n3. Start dominating the high score matrix!")
else:
    idx = st.session_state.current_index
    if idx < len(st.session_state.questions):
        current_q = st.session_state.questions[idx]
        
        # UI Header Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="🏆 Total Score", value=f"{st.session_state.score} pts")
        with col2:
            st.metric(label="🔥 Win Streak", value=f"{st.session_state.streak} Wins")
        with col3:
            st.write(f"**Level Progression**")
            st.write(f"Stage {idx + 1} / {len(st.session_state.questions)}")
            
        st.progress((idx) / len(st.session_state.questions))
        st.write("---")
        
        # Display Current Question text
        st.markdown(f"### ❓ {current_q['question']}")
        
        # Check and paint user loaded custom images
        if "image" in current_q and current_q["image"]:
            st.image(current_q["image"], caption="Analyze the image structure closely!", use_container_width=True)
            
        # Form Handling Answers
        with st.form(key=f"game_form_stage_{idx}"):
            choice = st.radio("Choose your weapon:", current_q["options"])
            submit_btn = st.form_submit_button("💥 Confirm Selection!")
            
            if submit_btn and not st.session_state.answered:
                st.session_state.answered = True
                st.session_state.selected_option = choice
                
        # Post-Submission Evaluation
        if st.session_state.answered:
            user_letter = st.session_state.selected_option[0]
            correct_letter = current_q["correct"]
            
            if user_letter == correct_letter:
                st.balloons()
                st.success("🌟 **BINGO! PERFECT HIT!** You knocked that out of the park!")
                if f"scored_{idx}" not in st.session_state:
                    st.session_state.score += 10 + (st.session_state.streak * 2) # Combo multipliers!
                    st.session_state.streak += 1
                    st.session_state[f"scored_{idx}"] = True
            else:
                st.snow()
                st.error(f"💔 **Ouch! Deflected.** The correct path was **{correct_letter}**.")
                st.session_state.streak = 0 # Breaks streak combo
                
            # Child-friendly punchy explanation display
            st.info(f"💡 **Mind-Stick Memory Scoop:**\n\n{current_q['explanation']}")
            
            if st.button("➡️ Advance to Next Level"):
                st.session_state.current_index += 1
                st.session_state.answered = False
                st.session_state.selected_option = None
                st.rerun()
    else:
        st.success("🏆 **VICTORY ACHIEVED! YOU TOTALLY CRUSHED THE ENTIRE RUN!** 🏆")
        st.metric(label="🎖️ Final Record Score", value=f"{st.session_state.score} Total Points")
        st.balloons()
        if st.button("🎮 Replay This Deck"):
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.streak = 0
            st.session_state.answered = False
            st.rerun()
        
