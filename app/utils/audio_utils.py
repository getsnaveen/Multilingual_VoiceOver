# utils/audio_utils.py
import subprocess,shutil
from utils.logger import SingletonLogger, log_exceptions
from types import SimpleNamespace

class AudioUtils:
    """
    Utility class for audio preprocessing, segment filtering,
    SRT formatting, and file generation.
    """
    def __init__(self):
        self.logger = SingletonLogger.getInstance(self.__class__.__name__).logger

    @log_exceptions("Failed to preprocess audio")
    def preprocess_audio(self, input_path: str, output_path: str) -> str:
        """
        Preprocesses audio by converting to 16kHz mono and applying dynamic normalization.

        Args:
            input_path (str): Path to input audio file.
            output_path (str): Output path for cleaned audio file.

        Returns:
            str: Path to the cleaned audio file.
        """
        temp_output = output_path + ".tmp.wav"

        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-ar", "16000", "-ac", "1",
            "-af", "dynaudnorm",
            temp_output
        ]

        subprocess.run(command, check=True)

        # Replace original file if required
        shutil.move(temp_output, output_path)
        self.logger.info(f"✅ Audio preprocessed and saved at: {output_path}")
        return output_path
    
    @log_exceptions("Formating Time")
    def format_time(self, seconds: float) -> str:
        """
        Converts a time in seconds to the SRT-friendly format HH:MM:SS,ms.
        """
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    @log_exceptions("Converting words to SRT failed")
    def words_to_srt(self, words: list[dict], max_words_per_line = 12) -> list[dict]:
        """
        Converts word-level dicts into SRT subtitle segments.
        """
        srt = []
        idx = 1
        current_line = []
        start_time = None
        end_time = None

        for word in words:
            if word.get("type") != "word":
                continue

            word_text = word.get("text", "").strip()
            word_start = word.get("start")
            word_end = word.get("end")

            if not word_text or word_start is None or word_end is None:
                continue

            if start_time is None:
                start_time = word_start
            end_time = word_end
            current_line.append(word_text)

            if len(current_line) >= max_words_per_line:
                srt.append({
                    "idx": idx,
                    "start": start_time,
                    "end": end_time,
                    "text": " ".join(current_line)
                })
                idx += 1
                current_line = []
                start_time = None

        if current_line:
            srt.append({
                "idx": idx,
                "start": start_time,
                "end": end_time,
                "text": " ".join(current_line)
            })

        return srt

    @log_exceptions("Writing SRT file failed")
    def write_srt_file(self, words: list[dict], output_path: str):
        """
        Writes filtered SRT subtitles from word-level input.
        """
        # Step 1: Convert words to raw subtitle segments
        srt_entries = self.words_to_srt(words)

        # Step 2: Convert each dict entry to an object-like structure so `.text`, `.start`, `.end` can be accessed
        segments = [SimpleNamespace(text=e["text"], start=e["start"], end=e["end"]) for e in srt_entries]

        # Step 3: Filter hallucinated/repetitive segments
        filtered_segments = self.filter_repeated_segments(segments, min_gap=1.0, max_repeats=2)

        # Step 4: Write final filtered SRT
        with open(output_path, "w", encoding="utf-8") as f:
            for idx, entry in enumerate(filtered_segments, 1):
                start = self.format_time(entry.start)
                end = self.format_time(entry.end)
                f.write(f"{idx}\n{start} --> {end}\n{entry.text}\n\n")

        print(f"✅ SRT subtitles saved to {output_path}")
    
    @log_exceptions("Filtering Repeted text")
    def filter_repeated_segments(self,segments, min_gap=1.0, max_repeats=2):
        """
        Filters out segments that repeat too often in close succession.

        Args:
            segments (list): List of segments with `.text`, `.start`, and `.end`.
            min_gap (float): Minimum time gap to allow same text again.
            max_repeats (int): Max allowed repetitions of the same text.

        Returns:
            list: Filtered list of segments.
        """
        filtered = []
        prev_text = ""
        prev_end = 0
        repeat_count = 0

        for seg in segments:
            current_text = seg.text.strip()
            if current_text == prev_text.strip() and (seg.start - prev_end) < min_gap:
                repeat_count += 1
                if repeat_count >= max_repeats:
                    continue  # Skip this repeated segment
            else:
                repeat_count = 0  # Reset for a new phrase

            filtered.append(seg)
            prev_text = current_text
            prev_end = seg.end

        return filtered