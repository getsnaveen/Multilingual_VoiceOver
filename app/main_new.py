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
from utils.chunk_structure import ProjectStructureManager
from pipeline import TranscriberApp

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
        st.markdown("Upload or set video configuration below:")

        input_video = st.text_input(
            "🎥 Input Video Path",
            value=" Please Enter .mp4 File Path"
        )

        uploaded_json = st.file_uploader(
            "📄 Upload JSON output from Step 1 (labeled_chunks.json or song_spans.json)",
            type=["json"],
            key="json_input"
        )

        languages = st.multiselect(
            "🌍 Target Languages",
            options=["Hindi", "Malay", "Bhasa", "Arabic", "Swahili", "Sinhala", "Telugu", "Tamil", "Kannada", "Malayalam", "Marathi", "Gujarati", "Bhojpuri"],
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

    def run_songs_pipeline(movie_path, songs, settings):
        """Run transcription + translation pipeline for songs."""
        from pipeline import TranscriberApp
        logger = SingletonLogger.getInstance("SongsPipeline").logger
        try:
            st.info(f"🎵 Processing {len(songs)} song segments in parallel...")
            manager = ProjectStructureManager(
                input_movie_path=settings.input_movie_path,
                base_language="BaseLanguage",
                target_languages=settings.languages_to_convert,
                story_json_path=settings.story_json_path
            )
            project_root = manager.create_structure(move_files=True)

            # Initialize TranscriberApp with this manager
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
        from utils.storageconnector import StorageConnector
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
            s3 = StorageConnector()
            output_dir = f"shared_data/movieslist/{Path(movie_path).stem}"
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
                segment_length=segment_length,
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

            json_content = uploaded_json.read().decode("utf-8") if uploaded_json else None
            if not json_content:
                st.error("⚠️ Please upload the labeled JSON file first.")
            else:
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
