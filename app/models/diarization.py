import os
import logging
import requests
from typing import List, Dict, Any, Optional
from utils.config import get_settings
local_settings = get_settings()

# ---------------------------------------------------------------------
# Logger Configuration
# ---------------------------------------------------------------------
logger = logging.getLogger("TranscriptionApp")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


# ---------------------------------------------------------------------
# Transcription Service Class
# ---------------------------------------------------------------------
class ElevenLabsTranscriber:
    """
    Handles audio transcription using ElevenLabs API.
    Provides transcription, speaker diarization, and transcript formatting.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "scribe_v1",
        base_url: str = "https://api.elevenlabs.io/v1/speech-to-text"
    ):
        """
        Initialize the transcriber with API details.
        Args:
            api_key (str): ElevenLabs API key.
            model_id (str): Model ID for transcription.
            base_url (str): API endpoint.
        """
        self.api_key = local_settings.elevenlabs_key
        self.model_id = model_id
        self.base_url = base_url

        if not self.api_key:
            logger.warning("⚠️ ELEVENLABS_API_KEY not found. Please set it as an environment variable.")

    # ----------------------------------------------------------
    def transcribe_audio(self, file_path: str, diarize: bool = True) -> Dict[str, Any]:
        """
        Sends an audio file to the ElevenLabs transcription API.

        Args:
            file_path (str): Path to the audio file (e.g., .mp3, .wav).
            diarize (bool): Enable or disable speaker diarization.

        Returns:
            dict: Parsed JSON response containing transcription and metadata.
        """
        if not os.path.exists(file_path):
            logger.error("Audio file not found: %s", file_path)
            return {}

        headers = {"xi-api-key": self.api_key}
        data = {"model_id": self.model_id, "diarize": str(diarize).lower()}

        try:
            with open(file_path, "rb") as audio_file:
                files = {"file": audio_file}
                logger.info("Uploading '%s' to ElevenLabs for transcription...", file_path)

                response = requests.post(
                    self.base_url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=600  # 10 minutes timeout for large audio
                )

            response.raise_for_status()
            result = response.json()
            logger.info("✅ Transcription successful (%d chars).", len(result.get("text", "")))
            return result

        except requests.exceptions.RequestException as e:
            logger.exception("API request failed: %s", e)
            return {}
        except MemoryError:
            logger.critical("MemoryError while processing large file: %s", file_path)
            return {}
        except Exception as e:
            logger.exception("Unexpected error during transcription: %s", e)
            return {}

    # ----------------------------------------------------------
    def group_speaker_segments(
        self, words: List[Dict[str, Any]], max_words_per_line: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Groups transcript words by speaker and wraps lines after `max_words_per_line`.

        Args:
            words (List[Dict[str, Any]]): Word-level transcript entries.
            max_words_per_line (int): Maximum words per subtitle line.

        Returns:
            List[Dict[str, Any]]: Grouped transcript with speaker, timestamps, and text.
        """
        grouped_transcript = []
        current_speaker, current_line = None, []
        start_time, end_time = None, None

        try:
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
                    # Speaker changed — save the previous segment
                    if current_line:
                        grouped_transcript.append({
                            "speaker": current_speaker,
                            "start": start_time,
                            "end": end_time,
                            "text": " ".join(current_line)
                        })

                    # Reset for new speaker
                    current_speaker = speaker
                    current_line = [word_text]
                    start_time = word_start
                    end_time = word_end

            # Final pending segment
            if current_line:
                grouped_transcript.append({
                    "speaker": current_speaker,
                    "start": start_time,
                    "end": end_time,
                    "text": " ".join(current_line)
                })

            logger.info("Grouped %d transcript segments by speaker.", len(grouped_transcript))
            return grouped_transcript

        except Exception as e:
            logger.exception("Error grouping speaker segments: %s", e)
            return []

    # ----------------------------------------------------------
    def run_transcription(self, file_path: str, max_words_per_line: int = 15, output_file: str = None) -> None:
        """
        Execute transcription, optionally saving results to a file.
        
        Args:
            file_path (str): Path to the audio file.
            max_words_per_line (int): Max words per transcript line.
            output_file (str): Path to save transcript (optional).
        """
        try:
            logger.info("🎧 Starting transcription process for file: %s", file_path)
            result = self.transcribe_audio(file_path, diarize=True)
            if not result:
                logger.error("❌ No valid transcription returned.")
                return

            full_text = result.get("text", "")
            logger.info("\n📜 Full Transcript:\n%s", full_text[:800] + "..." if len(full_text) > 800 else full_text)

            grouped = []
            if "words" in result:
                grouped = self.group_speaker_segments(result["words"], max_words_per_line)
                logger.info("\n🗣️ Speaker Diarization (Max %d words per line):", max_words_per_line)
                for seg in grouped:
                    start = f"{seg['start']:.2f}" if seg['start'] is not None else "?"
                    end = f"{seg['end']:.2f}" if seg['end'] is not None else "?"
                    logger.info("Speaker %s (%ss - %ss): %s", seg['speaker'], start, end, seg['text'])
            else:
                logger.warning("No word-level data found in transcription result.")

            # Save to file if specified
            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    # f.write("FULL TRANSCRIPT:\n")
                    # f.write(full_text + "\n\n")
                    if grouped:
                        f.write("DIARIZED SEGMENTS:\n")
                        for seg in grouped:
                            start = f"{seg['start']:.2f}" if seg['start'] is not None else "?"
                            end = f"{seg['end']:.2f}" if seg['end'] is not None else "?"
                            f.write(f"Speaker {seg['speaker']} ({start}s - {end}s): {seg['text']}\n")
                logger.info("✅ Transcript saved to %s", output_file)

        except MemoryError:
            logger.critical("MemoryError during transcription. Try splitting the audio file.")
        except Exception as e:
            logger.exception("Unexpected error during transcription workflow: %s", e)


# ---------------------------------------------------------------------
# Script Entry Point
# ---------------------------------------------------------------------
if __name__ == "__main__":
    AUDIO_FILE_PATH = ("/home/csc/Documents/Backup/shared_data/movieslist/rishtey/audio_files/rishtey_part5__audio.mp3" )    
    OUTPUT_PATH = "/home/csc/Documents/Backup/shared_data/movieslist/rishtey/audio_files/rishtey_part5__transcript.txt"

    transcriber = ElevenLabsTranscriber()
    transcriber.run_transcription(AUDIO_FILE_PATH, max_words_per_line=15, output_file=OUTPUT_PATH)

   