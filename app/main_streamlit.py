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
from utils.config import AppSettings
from utils.logger import SingletonLogger
from utils.chunk_structure import ProjectStructureManager,VideoProcessor
from pipeline import TranscriberApp
from utils.config import get_settings
local_settings = get_settings()

# =======================================================
# APP SETUP
# =======================================================

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
tab1, tab2 = st.tabs(["🎼 Mark & Export (Create JSON)", "🎬 Transcription & Dubbing Pipeline"])

# =======================================================
# TAB 1 — MARK & EXPORT JSON
# =======================================================
with tab1:
    st.subheader("🎵 Step 1: Mark SONG spans and export labeled chunks")

    # Load HTML annotator (index.html)
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_raw = f.read()

        # Optional: replace placeholder with logo
        if logo_data_uri:
            html_raw = html_raw.replace("__LOGO_DATA_URL__", logo_data_uri)

        # Render HTML tool inside Streamlit
        st_html(html_raw, height=800, scrolling=True)
    else:
        st.warning("⚠️ index.html not found — please add your marker HTML file here.")

    st.divider()
    st.info(
        "💡 Use the above annotator to mark 'song' and 'voice' segments, "
        "then export JSON once done."
    )

# =======================================================
# TAB 2 — TRANSCRIPTION PIPELINE
# =======================================================
with tab2:
    st.subheader("🎬 Step 2: Multilingual Video Transcription & Dubbing")

    # --- Input Section ---
    with st.form("transcriber_form"):
        st.markdown("Set video configuration below:")

        input_video = st.text_input(
            "🎥 Input Video Path",
            value=" Please Enter .mp4 File Path"
        )

        languages = st.multiselect(
            "🌍 Target Languages",
            options=["Hindi", "Malay", "Bhasa", "Arabic", "Swahili", "Sinhala", 
                     "Telugu", "Tamil", "Kannada", "Malayalam", "Marathi", "Gujarati", "Bhojpuri"],
            default=["Hindi"]
        )

        st.markdown("**✅ Select Pipeline Steps**")
        steps = {
            "split_songs_stories": st.checkbox("🎼 Split to Songs & Stories", True),
            "audio_extract": st.checkbox("🎧 Audio extraction", True),
            "transcription": st.checkbox("📝 Transcription", True),
            "subtitle_translation": st.checkbox("🌍 Subtitle translation", True),
            "subtitle_embedding": st.checkbox("🎬 Subtitle embedding", True),
            "evaluation": st.checkbox("📊 Evaluation", True),
            "diarization": st.checkbox("🗣️ Speaker Diarization", True),
            "upload_to_s3": st.checkbox("☁️ Upload Outputs to S3", True),
            "download_from_s3": st.checkbox("⬇️ Download from S3", True),
            "final_merge": st.checkbox("🎞️ Final Merge", True),
        }
        selected_steps = [k for k, v in steps.items() if v]
        submitted = st.form_submit_button("▶ Run Selected Pipeline")

    # ==========================================================
    # Helper Functions
    # ==========================================================
    def reset_pipeline():
        for k in ["pipeline_started", "pipeline_done", "pipeline_error", "output_dir", "languages_done"]:
            st.session_state.pop(k, None)
    
    def load_labeled_json_from_video(video_path: str) -> str:
        """
        Load labeled_chunks.json from the same folder as the video.
        Returns JSON content as string, or None if file not found.
        """
        if not video_path or not os.path.exists(video_path):
            st.error(f"❌ Video path does not exist: {video_path}")
            return None

        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        json_file = os.path.join(video_dir, f"{video_name}_labeled_chunks.json")

        if os.path.exists(json_file):
            with open(json_file, "r", encoding="utf-8") as f:
                content = f.read()
            st.success(f"✅ Loaded JSON automatically: {os.path.basename(json_file)}")
            return content
        else:
            st.error(f"⚠️ JSON file not found. Expected: {os.path.basename(json_file)}")
            return None

    def run_songs_pipeline(movie_path, songs, settings):
        """Run transcription + translation pipeline for songs."""
        from pipeline import TranscriberApp
        logger = SingletonLogger.getInstance("SongsPipeline").logger
        try:
            st.info(f"🎵 Processing {len(songs)} song segments in parallel...")

            # Derive story JSON path dynamically based on input movie name
            video_dir = os.path.dirname(movie_path)
            video_name = os.path.splitext(os.path.basename(movie_path))[0]
            story_json_path = os.path.join(video_dir, f"{video_name}_labeled_chunks.json")

            if not os.path.exists(story_json_path):
                st.warning(f"⚠️ Story JSON not found at {story_json_path}, using songs only.")

            # Initialize manager with the dynamically computed JSON path
            manager = ProjectStructureManager(
                input_movie_path=settings.input_movie_path,
                base_language="BaseLanguage",
                target_languages=settings.languages_to_convert,
                story_json_path=story_json_path
            )
            project_root = manager.create_structure(move_files=True)
            processor = VideoProcessor(manager)
            processor.extract_segments(label="song")


            # Initialize TranscriberApp
            app = TranscriberApp(settings, manager)

            # Steps specific to songs
            steps = [
                "audio_extract",
                "transcription",
                "subtitle_translation",
                "subtitle_embedding",
                "evaluation"
            ]
            app.run(selected_steps=steps)
            logger.info("✅ Songs pipeline completed successfully.")
        except Exception as e:
            logger.exception("Songs pipeline failed")
            st.error(f"❌ Songs pipeline failed: {e}")    
   
    def run_stories_pipeline(movie_path, stories, settings):
        """Run diarization + S3 + merge pipeline for stories."""
        from utils.storageconnector import S3Uploader
        logger = SingletonLogger.getInstance("StoriesPipeline").logger
        try:
            st.info(f"🎬 Processing {len(stories)} story segments in parallel...")

            # --- Diarization Step ---
            from models.diarization import ElevenLabsTranscriber
            st.info("🗣 Performing speaker diarization...")
            ElevenLabsTranscriber(movie_path)
            st.success("✅ Diarization completed!")

            # --- Upload to S3 ---
            st.info("☁️ Uploading story outputs to S3...")
            s3 = S3Uploader(access_key=local_settings.aws_access_key, 
                          secret_key=local_settings.aws_secret_key, 
                          region=local_settings.aws_region)

            output_dir = f"{Path(movie_path).stem}"
            for root, _, files in os.walk(output_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    key = f"{Path(movie_path).stem}/stories/{file}"
                    s3.upload_file(full_path, "test-bucket", key)
            st.success("✅ Story files uploaded to S3.")

            # --- Optional: Download back for merging ---
            st.info("⬇️ Downloading story outputs for final merge...")
            for file in files:
                s3.download_file("test-bucket", key, os.path.join(output_dir, file))
            st.success("✅ Story files downloaded.")

            # --- Merge Songs + Stories ---
            st.info("🎞️ Merging songs and stories...")
            time.sleep(2)
            logger.info("✅ Final merge completed.")

        except Exception as e:
            logger.exception("Stories pipeline failed")
            st.error(f"❌ Stories pipeline failed: {e}")

    def run_parallel_pipelines(movie_path, json_data):
        """Split JSON and run songs/stories pipelines in parallel threads."""
        logger = SingletonLogger.getInstance("ParallelPipeline").logger
        try:
            data = json.loads(json_data)
            songs = [d for d in data if d.get("label") == "song"]
            stories = [d for d in data if d.get("label") == "voice"]

            settings = AppSettings(
                input_movie_path=movie_path,
                languages_to_convert=languages
            )

            st.info(f"🎵 Found {len(songs)} song segments | 🎬 {len(stories)} story segments")

            # Create threads
            t1 = threading.Thread(target=run_songs_pipeline, args=(movie_path, songs, settings))
            t2 = threading.Thread(target=run_stories_pipeline, args=(movie_path, stories, settings))

            # Attach Streamlit runtime contexts
            add_script_run_ctx(t1)
            add_script_run_ctx(t2)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            st.success("✅ Both song and story pipelines completed successfully!")

        except Exception as e:
            logger.exception("Parallel pipeline failed")
            st.error(f"❌ Parallel pipeline failed: {e}")

    # ==========================================================
    # Execution Control
    # ==========================================================

    if submitted and "pipeline_started" not in st.session_state:
        if not input_video or not os.path.exists(input_video):
            st.error("❌ Invalid movie path. Please provide a valid video file.")
        else:
            st.session_state["pipeline_started"] = True
            st.warning("⏳ Pipeline running... please wait.")

            # Load JSON automatically from same folder
            json_content = load_labeled_json_from_video(input_video)
            if json_content:
                thread = threading.Thread(target=run_parallel_pipelines, args=(input_video, json_content))
                add_script_run_ctx(thread)
                thread.start()

    # --- Progress Display ---
    if st.session_state.get("pipeline_started") and not st.session_state.get("pipeline_done"):
        st.info("⚙️ Processing both pipelines... please wait.")
        time.sleep(5)
        st.rerun()

    elif st.session_state.get("pipeline_done"):
        st.success("✅ All pipelines completed successfully!")
        st.button("✨ Run Again", on_click=reset_pipeline)
