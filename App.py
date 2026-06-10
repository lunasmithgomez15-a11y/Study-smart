import json
import re
import random
import base64
import io
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
    from docx import Document
except ImportError:
    docx = None
    Document = None

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

# --- SFX AUDIO INJECTION ---
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
WRONG_SFX = "
