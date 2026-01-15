import streamlit as st
import pandas as pd
import os
import time
import json
import sys

# Ensure project root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.epub_parser import EpubParser
from src.audio_analyzer import AudioAnalyzer
from src.models import Chapter
from src.utils import setup_logging

# Page Config
st.set_page_config(
    page_title="Audiobook Timestamp Extractor",
    page_icon="📖",
    layout="wide"
)

# Initialize Session State
if 'chapters' not in st.session_state:
    st.session_state.chapters = []
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'logs' not in st.session_state:
    st.session_state.logs = []

def log(message):
    st.session_state.logs.append(message)

# Sidebar
st.sidebar.title("Configuration")
model_size = st.sidebar.selectbox("Whisper Model Size", ["base", "small", "medium", "large"], index=0)
search_window = st.sidebar.slider("Initial Search Window (min)", 10, 60, 30) * 60
confidence_score = st.sidebar.slider("Confidence Score", 0, 100, 80)

st.title("Audiobook Timestamp Extractor 🎧")
st.markdown("Extract chapter timestamps from M4B files using EPUB correlation.")

# --- Step 1: Upload ---
st.header("1. Upload Files")
col1, col2 = st.columns(2)
with col1:
    epub_file = st.file_uploader("Upload EPUB", type=["epub"])
with col2:
    audio_file = st.file_uploader("Upload Audio (M4B)", type=["m4b", "mp3", "m4a"])

# --- Step 2: Parse ---
if epub_file and audio_file:
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    
    epub_path = os.path.join(temp_dir, epub_file.name)
    audio_path = os.path.join(temp_dir, audio_file.name)
    
    # Save if not exists
    if not os.path.exists(epub_path):
        with open(epub_path, "wb") as f:
            f.write(epub_file.getbuffer())
    
    if not os.path.exists(audio_path):
        with open(audio_path, "wb") as f:
            f.write(audio_file.getbuffer())
            
    st.success(f"Files ready: {epub_file.name}, {audio_file.name}")
    
    if st.button("Parse EPUB"):
        with st.spinner("Parsing EPUB..."):
            parser = EpubParser(epub_path)
            chapters = parser.parse()
            st.session_state.chapters = chapters
            st.session_state.processing_complete = False
            st.success(f"Found {len(chapters)} chapters.")

# --- Step 3: Verify ---
if st.session_state.chapters:
    st.header("2. Verify Chapters")
    
    data = []
    for c in st.session_state.chapters:
        data.append({
            "Index": c.index,
            "Title": c.toc_title,
            "Snippet": c.search_phrase[:80] + "...",
            "Ignore": c.status == "IGNORED"
        })
    
    df = pd.DataFrame(data)
    
    edited_df = st.data_editor(
        df,
        column_config={
            "Ignore": st.column_config.CheckboxColumn(
                "Ignore",
                help="Check to exclude this chapter from processing",
                default=False,
            )
        },
        disabled=["Index", "Title", "Snippet"],
        hide_index=True,
        width='stretch'
    )
    
    ignore_indices = edited_df[edited_df["Ignore"] == True]["Index"].tolist()
    valid_chapters = [c for c in st.session_state.chapters if c.index not in ignore_indices]
    
    st.info(f"Selected {len(valid_chapters)} chapters for processing.")

    # --- Step 4: Process ---
    st.header("3. Process Audio")
    
    if st.button("Start Extraction"):
        st.session_state.processing_complete = False
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        analyzer = AudioAnalyzer(audio_path, model_size=model_size)
        duration = analyzer.get_duration()
        st.caption(f"Audio Duration: {duration/60:.2f} minutes")
        
        last_confirmed_time = 0.0
        current_search_window = search_window
        
        for i, chap in enumerate(valid_chapters):
            status_text.text(f"Processing: {chap.toc_title}...")
            
            # Pass min_confidence from slider
            found = analyzer.find_chapter_linear(
                chap, 
                last_confirmed_time, 
                max_search_duration=current_search_window,
                min_confidence=confidence_score
            )
            
            if found:
                if chap.confirmed_time:
                    last_confirmed_time = chap.confirmed_time
                status_text.text(f"Found: {chap.toc_title} at {chap.confirmed_time:.2f}s")
                current_search_window = search_window # Reset
            else:
                status_text.text(f"Failed to find: {chap.toc_title}")
                current_search_window += search_window # Expand
                
            # Update Progress
            progress = (i + 1) / len(valid_chapters)
            progress_bar.progress(progress)
            
        st.session_state.processing_complete = True
        st.session_state.valid_chapters = valid_chapters
        st.success("Processing Complete!")

# --- Step 5: Download ---
if st.session_state.processing_complete:
    st.header("4. Download Results")
    
    output_data = []
    
    # Intro Check logic
    valid_chapters = st.session_state.valid_chapters
    
    if valid_chapters and valid_chapters[0].status == "FOUND":
        first_chap = valid_chapters[0]
        if first_chap.confirmed_time and first_chap.confirmed_time > 10.0:
            output_data.append({
                "title": "Intro / Prologue",
                "start_time": "00:00:00",
                "seconds": 0.0
            })
            
    for chap in valid_chapters:
        if chap.status == "FOUND" and chap.confirmed_time is not None:
             m, s = divmod(chap.confirmed_time, 60)
             h, m = divmod(m, 60)
             time_str = f"{int(h):02d}:{int(m):02d}:{s:05.2f}"
             output_data.append({
                 "title": chap.toc_title,
                 "start_time": time_str,
                 "seconds": chap.confirmed_time
             })

    json_str = json.dumps(output_data, indent=4)
    
    st.download_button(
        label="Download timestamps.json",
        data=json_str,
        file_name="chapter_timestamps.json",
        mime="application/json"
    )
    
    st.json(output_data)
