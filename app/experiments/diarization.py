
#!/usr/bin/env python3
"""
ElevenLabs Speech-to-Text with Speaker Diarization

This script:
1. Sends an audio file to ElevenLabs' transcription API.
2. Retrieves full transcript and word-level diarization.
3. Groups transcript into speaker segments, with a max number of words per line.
4. Logs results in a clean, structured format.

"""

import os
import logging
import requests
from typing import List, Dict, Any

# ---------------------- CONFIG ----------------------
API_KEY = os.getenv("ELEVENLABS_API_KEY", "")  # Replace with your key or set in env
AUDIO_PATH = "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/rishtey/audio_files/rishtey_part5__audio.mp3"  # Supports MP3, WAV, etc.
MAX_WORDS_PER_LINE = 12
MODEL_ID = "scribe_v1"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/speech-to-text"
# -----------------------------------------------------

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def transcribe_audio(file_path: str, diarize: bool = True) -> Dict[str, Any]:
    """
    Sends audio to ElevenLabs API for transcription.

    Args:
        file_path (str): Path to audio file.
        diarize (bool): Whether to enable speaker diarization.

    Returns:
        dict: JSON response from the API.
    """
    if not os.path.exists(file_path):
        logging.error("Audio file not found: %s", file_path)
        return {}

    headers = {"xi-api-key": API_KEY}
    data = {"model_id": MODEL_ID, "diarize": str(diarize).lower()}

    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            logging.info("Sending request to ElevenLabs API...")
            response = requests.post(ELEVENLABS_URL, headers=headers, data=data, files=files)
        
        response.raise_for_status()
        logging.info("Transcription successful.")
        return response.json()

    except requests.exceptions.RequestException as e:
        logging.error("API request failed: %s", e)
        return {}


def group_speaker_segments(words: List[Dict[str, Any]], max_words_per_line: int) -> List[Dict[str, Any]]:
    """
    Groups transcript by speaker and wraps lines after max_words_per_line.

    Args:
        words (list): List of word-level transcript dicts.
        max_words_per_line (int): Maximum words per subtitle line.

    Returns:
        list: List of grouped transcript segments.
    """
    grouped_transcript = []
    current_speaker = None
    current_line = []
    start_time = None
    end_time = None

    for w in words:
        speaker = w.get("speaker", w.get("speaker_id", "Unknown"))
        word_text = w.get("text", "").strip()
        word_start = w.get("start")
        word_end = w.get("end")

        if not word_text or word_start is None or word_end is None:
            continue

        if current_speaker is None:
            current_speaker = speaker
            start_time = word_start
            end_time = word_end
            current_line = [word_text]
        elif speaker == current_speaker:
            current_line.append(word_text)
            end_time = word_end

            if len(current_line) >= max_words_per_line:
                grouped_transcript.append({
                    "speaker": current_speaker,
                    "start": start_time,
                    "end": end_time,
                    "text": " ".join(current_line)
                })
                current_line = []
                start_time = word_start
        else:
            if current_line:
                grouped_transcript.append({
                    "speaker": current_speaker,
                    "start": start_time,
                    "end": end_time,
                    "text": " ".join(current_line)
                })

            current_speaker = speaker
            current_line = [word_text]
            start_time = word_start
            end_time = word_end

    if current_line:
        grouped_transcript.append({
            "speaker": current_speaker,
            "start": start_time,
            "end": end_time,
            "text": " ".join(current_line)
        })

    return grouped_transcript


def main():
    """Main execution flow."""
    logging.info("Starting transcription process...")

    result = transcribe_audio(AUDIO_PATH, diarize=True)
    if not result:
        logging.error("No result returned from API.")
        return

    logging.info("\nFull Transcript:\n%s", result.get("text", ""))

    if "words" in result:
        grouped_transcript = group_speaker_segments(result["words"], max_words_per_line=MAX_WORDS_PER_LINE)

        logging.info("\nDiarized Transcript (Max %d words per line):", MAX_WORDS_PER_LINE)
        for segment in grouped_transcript:
            start = f"{segment['start']:.2f}" if segment['start'] is not None else "?"
            end = f"{segment['end']:.2f}" if segment['end'] is not None else "?"
            logging.info("Speaker %s (%ss - %ss): %s", segment['speaker'], start, end, segment['text'])
    else:
        logging.warning("No word-level data found in response.")


if __name__ == "__main__":
    main()
