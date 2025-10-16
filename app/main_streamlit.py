import streamlit as st
import socket
from streamlit.runtime.scriptrunner import add_script_run_ctx
import threading, os, time
import base64
from pathlib import Path
from utils.config import AppSettings
from pipeline import TranscriberApp
from utils.logger import SingletonLogger
import torch, types
torch.classes.__path__ = types.SimpleNamespace(_path=[])

# ------------------ LOGO FROM LOCAL FILE ------------------
def get_base64_image(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode()
        return f"data:image/png;base64,{encoded}"

logo_data_uri = get_base64_image("plugins/Nimix It.jpg")

# ------------------ UI CONFIGURATION ------------------
st.set_page_config(
    page_title="Multilingual Video Transcriber",
    layout="wide",
    page_icon="🎬",
)

st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: linear-gradient(to right, #e0f7fa, #f1f8e9);
        background-size: cover;
        font-family: 'Arial', sans-serif;
    }}
    .main > div:first-child {{
        padding-top: 2rem;
    }}
    </style>
    <div style="text-align:center; padding-bottom:1rem">
        <img src="{logo_data_uri}" alt="Company Logo" width="180"/>
        <h1 style="margin-top:0.5rem;">🎙️ Multilingual Movie Transcriber</h1>
        <p style="font-size:1.2rem; color:#444;">
            From Transcription to Dubbing – Your Multilingual Video Assistant
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# ------------------ SIDEBAR INFO ------------------
st.sidebar.markdown("## 📋 Full Pipeline Overview")
st.sidebar.info(
    """
    The pipeline includes:
    - 🎞️ Video splitting  
    - 🎧 Audio extraction  
    - 📝 Transcription  
    - 🌍 Subtitle translation  
    - 🎬 Subtitle embedding  
    - 📦 Final merged video per language  
    - 📊 Evaluation
    """
)

# --- Display container details ---
container_id = socket.gethostname()
st.sidebar.markdown("---")
st.sidebar.markdown(f"🆔 *Container ID:* {container_id}")
st.sidebar.caption("(This shows which container instance you are connected to)")

# ------------------ FORM INPUT ------------------
with st.form("transcriber_form"):
    st.subheader("Upload & Configuration")

    input_video = st.text_input("🎥 Input Video Path", value="/media/csc/cb6528c8-34d9-4c57-9c9b-02dfb3a3daea/nfs_share/movielist/ahista_ahista.mp4")
    segment_length = st.number_input("⏱️ Segment Length (seconds)", min_value=60, value=600)
    languages = st.multiselect(
        "🌐 Languages to Convert",
        options=[
            "English", "Spanish", "Bhasa", "Hindi", "Malay", "Tamil",
            "Malayalam", "Kannada", "Marathi", "Gujarati", "Bhojpuri"],
        default=["Kannada"]
    )

    st.markdown("**✅ Select Pipeline Steps**")

    video_split = st.checkbox("🎞️ Video splitting", value=True)
    audio_extract = st.checkbox("🎧 Audio extraction", value=True)
    transcription = st.checkbox("📝 Transcription", value=True)
    subtitle_translation = st.checkbox("🌍 Subtitle translation", value=True)
    subtitle_embedding = st.checkbox("🎬 Subtitle embedding", value=True)
    final_merge = st.checkbox("📦 Final merged video per language", value=True)
    evaluation = st.checkbox("📊 Evaluation", value=True)

    steps_selected = []
    if video_split: steps_selected.append("video_split")
    if audio_extract: steps_selected.append("audio_extract")
    if transcription: steps_selected.append("transcription")
    if subtitle_translation: steps_selected.append("subtitle_translation")
    if subtitle_embedding: steps_selected.append("subtitle_embedding")
    if final_merge: steps_selected.append("final_merge")
    if evaluation: steps_selected.append("evaluation")

    submitted = st.form_submit_button("▶ Run Selected Pipeline")

# ------------------ PIPELINE EXECUTION ------------------
def reset_pipeline():
    """Clears session state to allow for a new run."""
    st.session_state.pop("pipeline_started", None)
    st.session_state.pop("pipeline_done", None)
    st.session_state.pop("pipeline_error", None)
    st.session_state.pop("output_dir", None)
    st.session_state.pop("languages_done", None)

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
        logger.exception("❌ Streamlit Pipeline failed")
        st.session_state["pipeline_error"] = str(e)

if submitted and "pipeline_started" not in st.session_state:
    st.session_state["pipeline_started"] = True
    st.session_state["pipeline_done"] = False
    st.session_state["pipeline_error"] = None

    st.warning("⏳ Running the transcription pipeline. This may take several minutes...")

    thread = threading.Thread(target=run_pipeline, args=(steps_selected,))
    add_script_run_ctx(thread)
    thread.start()

# ✅ Show live progress with non-blocking polling
if st.session_state.get("pipeline_started") and not st.session_state.get("pipeline_done") and not st.session_state.get("pipeline_error"):
    st.info("⏳ Pipeline is running... please wait. This page will auto-refresh.")
    # This non-blocking sleep + rerun creates a polling effect
    time.sleep(5) 
    st.rerun()

# ------------------ RESULTS & DOWNLOADS ------------------
if st.session_state.get("pipeline_error"):
    st.error(f"❌ Pipeline failed: {st.session_state['pipeline_error']}")
    st.button("Try Again", on_click=reset_pipeline) # Add reset button on error

elif st.session_state.get("pipeline_done"):
    st.success("✅ Pipeline completed successfully!")
    st.info("📁 Outputs are ready!")

    # Add a reset button to allow the user to run another pipeline
    st.button("✨ Run a New Pipeline", on_click=reset_pipeline)
    
    st.markdown("---") # Add a separator

    output_dir = st.session_state["output_dir"] # e.g., "static/ahista_ahista"
    languages = st.session_state["languages_done"]

    st.subheader("Download Your Files")

    for lang in languages:
        video_filename = f"{Path(input_video).stem}_Final_{lang}.mp4"
        csv_filename = f"{Path(input_video).stem}__final_eval_{lang}.csv"

        final_video_path = os.path.join(output_dir, video_filename)
        eval_csv_path = os.path.join(output_dir, "evaluation", csv_filename)

        # --- Video Path Link ---
        if os.path.exists(final_video_path):
            file_size_mb = os.path.getsize(final_video_path) / (1024 * 1024)
            st.markdown(
                f"""
                <p>
                    <strong>{lang} Subtitled Video:</strong><br>
                    <a href="file://{os.path.abspath(final_video_path)}" target="_blank">
                        📂 Open {video_filename} ({file_size_mb:.2f} MB)
                    </a>
                </p>
                """,
                unsafe_allow_html=True
            )
        else:
            st.warning(f"Video file for {lang} not found at: {final_video_path}")

        # --- CSV Path Link ---
        if os.path.exists(eval_csv_path):
            st.markdown(
                f"""
                <p>
                    <strong>{lang} Evaluation CSV:</strong><br>
                    <a href="file://{os.path.abspath(eval_csv_path)}" target="_blank">
                        📂 Open {csv_filename}
                    </a>
                </p>
                """,
                unsafe_allow_html=True
            )