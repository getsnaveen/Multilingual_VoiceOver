import os
import json
import base64
import time
import threading
from pathlib import Path
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx
from streamlit.components.v1 import html as st_html

# --- App Imports ---
from utils.config import AppSettings, get_settings
from utils.logger import SingletonLogger
from utils.chunk_structure import ProjectStructureManager, VideoProcessor
from pipeline import TranscriberApp

# =======================================================
# APP SETUP
# =======================================================
local_settings = get_settings()
st.set_page_config(
    page_title="🎬 Multilingual Dubbing & Marking Suite",
    layout="wide",
    page_icon="🎥"
)

# =======================================================
# HELPER: LOGO DISPLAY
# =======================================================
def get_base64_image(image_path: str) -> str:
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
            return f"data:image/png;base64,{encoded}"
    except FileNotFoundError:
        return ""

logo_data_uri = get_base64_image("app/Nimix It.jpg")

st.markdown(
    f"""
    <div style="text-align:center; padding-bottom:1rem">
        <img src="{logo_data_uri}" alt="Company Logo" width="180"/>
        <h1 style="margin-top:0.5rem;">🎙️▶️🔊 Nimix Poly Media Suite</h1>
        <p style="font-size:1.1rem; color:#555;">
            Combine labeling + transcription + dubbing from one UI
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# =======================================================
# DEFINE MAIN TABS
# =======================================================
tab1, tab2 = st.tabs(["🎼 Mark & Export (Create JSON)", "🎬 Unified Transcription & Dubbing Pipeline"])

# =======================================================
# TAB 1 — MARK & EXPORT JSON
# =======================================================
with tab1:
    st.subheader("🎵 Step 1: Mark SONG spans and export labeled chunks")

    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_raw = f.read()
        if logo_data_uri:
            html_raw = html_raw.replace("__LOGO_DATA_URL__", logo_data_uri)
        st_html(html_raw, height=800, scrolling=True)
    else:
        st.warning("⚠️ index.html not found — please add your marker HTML file here.")

    st.divider()
    st.info(
        "💡 Use the above annotator to mark 'song' and 'voice' segments, "
        "then export JSON once done."
    )

# =======================================================
# TAB 2 — UNIFIED PIPELINE
# =======================================================
with tab2:
    st.subheader("🎬 Step 2: Unified Transcription, Translation & Dubbing")

    with st.form("unified_pipeline_form"):
        st.markdown("Set video configuration below:")

        input_video = st.text_input(
            "🎥 Input Video Path",
            value="/home/csc/Documents/Test1/rishtey.mp4"
        )

        languages = st.multiselect(
            "🌍 Target Languages",
            options=["Malay", "Bhasa", "Arabic", "Swahili", "Sinhala",
                     "Telugu", "Tamil", "Kannada", "Malayalam", "Gujarati", "Bhojpuri"],
            default=["Malay", "Bhasa", "Arabic", "Swahili", "Sinhala",
                     "Telugu", "Tamil", "Kannada", "Malayalam", "Gujarati", "Bhojpuri"]
        )
        
        st.markdown("**✅ Select Pipeline Steps**")
        steps = {
            "split_songs_stories": st.checkbox("🎼 Split Songs & Stories", True),
            "audio_extract": st.checkbox("🎧 Audio Extraction", True),
            "transcription": st.checkbox("📝 Transcription", True),
            "subtitle_translation": st.checkbox("🌍 Subtitle Translation", True),
            "subtitle_embedding": st.checkbox("🎬 Subtitle Embedding", True),
            "evaluation": st.checkbox("📊 Evaluation", True),
            "diarization": st.checkbox("🗣️ Speaker Diarization", True),
            "upload_to_s3": st.checkbox("☁️ Upload Outputs to S3", True),
            "download_from_s3": st.checkbox("⬇️ Download from S3", True),
            "final_merge": st.checkbox("🎞️ Final Merge", True),
        }
        selected_steps = [k for k, v in steps.items() if v]
        submitted = st.form_submit_button("▶ Run Unified Pipeline")

    # =======================================================
    # Helper Functions
    # =======================================================
    def reset_pipeline():
        for k in ["pipeline_started", "pipeline_done", "pipeline_error", "output_dir", "languages_done"]:
            st.session_state.pop(k, None)
   
    def run_unified_pipeline(movie_path: str, selected_steps: list):
        """Run the unified pipeline that handles songs + stories internally."""
        logger = SingletonLogger.getInstance("UnifiedPipeline").logger
        try:
            st.info("🚀 Starting unified pipeline (songs + stories)...")

            # Derive story JSON path dynamically based on input movie name
            video_dir = os.path.dirname(movie_path)
            video_name = os.path.splitext(os.path.basename(movie_path))[0]
            story_json_path = os.path.join(video_dir, f"{video_name}_labeled_chunks.json")

            if not os.path.exists(story_json_path):
                st.warning(f"⚠️ Story JSON not found at {story_json_path}, using songs only.")


            settings = AppSettings(
                input_movie_path=movie_path,
                languages_to_convert=languages
            )

            # Initialize project structure
            manager = ProjectStructureManager(
                input_movie_path=settings.input_movie_path,
                base_language="Hindi",
                target_languages=settings.languages_to_convert,
                story_json_path=story_json_path
            )
            manager.create_structure(move_files=True)
            processor = VideoProcessor(manager)
            processor.extract_segments(label="song",lang_suffix="hi")

            # Run unified TranscriberApp pipeline
            app = TranscriberApp(settings, manager)
            app.run(selected_steps=selected_steps)

            # ✅ Save session success data
            st.session_state["pipeline_done"] = True
            st.session_state["output_dir"] = str(manager.project_root / "output")
            st.session_state["languages_done"] = settings.languages_to_convert
            logger.info("Unified pipeline completed successfully.")

        except Exception as e:
            logger.exception("Unified pipeline failed")
            st.session_state["pipeline_error"] = str(e)

    # =======================================================
    # Execution Control
    # =======================================================
    if submitted and "pipeline_started" not in st.session_state:
        if not input_video or not os.path.exists(input_video):
            st.error("❌ Invalid movie path. Please provide a valid video file.")
        else:            
            st.session_state["pipeline_started"] = True
            st.warning("⏳ Running unified pipeline... please wait.")

            thread = threading.Thread(target=run_unified_pipeline, args=(input_video, selected_steps))
            add_script_run_ctx(thread)
            thread.start()

    # =======================================================
    # ✅ Live Progress + Results Display
    # =======================================================
    if st.session_state.get("pipeline_started") and not st.session_state.get("pipeline_done") and not st.session_state.get("pipeline_error"):
        st.info("⏳ Pipeline is running... please wait. This page will auto-refresh.")
        time.sleep(5)
        st.rerun()

    elif st.session_state.get("pipeline_error"):
        st.error(f"❌ Pipeline failed: {st.session_state['pipeline_error']}")
        st.button("Try Again", on_click=reset_pipeline)

    elif st.session_state.get("pipeline_done"):
        st.success("✅ Pipeline completed successfully!")
        st.info("🎬 All files have been processed and saved in your output directory.")
        st.button("✨ Run a New Pipeline", on_click=reset_pipeline)
        st.markdown("---")
