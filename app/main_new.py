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

logo_data_uri = get_base64_image("plugins/Nimix It.jpg")

st.markdown(
    f"""
    <div style="text-align:center; padding-bottom:1rem">
        <img src="{logo_data_uri}" alt="Company Logo" width="180"/>
        <h1 style="margin-top:0.5rem;">🎙️ Multilingual Video Transcriber Suite</h1>
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

    with st.form("transcriber_form"):
        st.markdown("Upload or set video configuration below:")

        input_video = st.text_input("🎥 Input Video Path",
            value="/media/csc/nfs_share/movielist/ahista_ahista.mp4")
        segment_length = st.number_input("⏱️ Segment Length (seconds)", min_value=60, value=600)
        languages = st.multiselect(
            "🌍 Target Languages",
            options=["English","Hindi","Tamil","Kannada","Malayalam","Marathi"],
            default=["Kannada"]
        )

        st.markdown("**✅ Select Pipeline Steps**")
        steps = {
            "video_split": st.checkbox("🎞️ Video splitting", True),
            "audio_extract": st.checkbox("🎧 Audio extraction", True),
            "transcription": st.checkbox("📝 Transcription", True),
            "subtitle_translation": st.checkbox("🌍 Subtitle translation", True),
            "subtitle_embedding": st.checkbox("🎬 Subtitle embedding", True),
            "final_merge": st.checkbox("📦 Final merge per language", True),
            "evaluation": st.checkbox("📊 Evaluation", True),
        }
        selected_steps = [k for k, v in steps.items() if v]

        submitted = st.form_submit_button("▶ Run Selected Pipeline")

    def reset_pipeline():
        for k in ["pipeline_started", "pipeline_done", "pipeline_error", "output_dir", "languages_done"]:
            st.session_state.pop(k, None)

    def run_pipeline(selected_steps):
        logger = SingletonLogger.getInstance("StreamlitApp").logger
        try:
            settings = AppSettings(
                segment_length=segment_length,
                input_movie_path=input_video,
                languages_to_convert=languages
            )
            app = TranscriberApp(settings)
            app.run(selected_steps=selected_steps)
            st.session_state["pipeline_done"] = True
            st.session_state["output_dir"] = f"shared_data/movieslist/{Path(input_video).stem}"
            st.session_state["languages_done"] = languages
        except Exception as e:
            logger.exception("Pipeline failed")
            st.session_state["pipeline_error"] = str(e)

    if submitted and "pipeline_started" not in st.session_state:
        st.session_state["pipeline_started"] = True
        st.warning("⏳ Pipeline running... please wait.")
        thread = threading.Thread(target=run_pipeline, args=(selected_steps,))
        add_script_run_ctx(thread)
        thread.start()

    if st.session_state.get("pipeline_started") and not st.session_state.get("pipeline_done"):
        st.info("⚙️ Processing... this may take several minutes.")
        time.sleep(5)
        st.rerun()

    elif st.session_state.get("pipeline_done"):
        st.success("✅ Pipeline completed successfully!")
        st.button("✨ Run Again", on_click=reset_pipeline)

        output_dir = st.session_state["output_dir"]
        langs = st.session_state["languages_done"]
        st.subheader("📂 Output Files")

        for lang in langs:
            base = Path(input_video).stem
            final_video = os.path.join(output_dir, f"{base}_Final_{lang}.mp4")
            eval_csv = os.path.join(output_dir, "evaluation", f"{base}__final_eval_{lang}.csv")

            if os.path.exists(final_video):
                st.markdown(f"🎬 [{lang} Video]({final_video})")
            if os.path.exists(eval_csv):
                st.markdown(f"📊 [{lang} Evaluation CSV]({eval_csv})")

    elif st.session_state.get("pipeline_error"):
        st.error(f"❌ Error: {st.session_state['pipeline_error']}")
        st.button("Try Again", on_click=reset_pipeline)
