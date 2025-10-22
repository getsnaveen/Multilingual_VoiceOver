import os
import json
import ffmpeg
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union

# ---------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ---------------------------------------------------------------------
# Utility Class: Time Conversion
# ---------------------------------------------------------------------
class TimeUtils:
    """Helper class for time conversions."""

    @staticmethod
    def seconds_to_hms(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02}:{minutes:02}:{secs:02}"

    @staticmethod
    def time_to_seconds(time_str: str) -> float:
        h, m, s = map(float, time_str.split(":"))
        return h * 3600 + m * 60 + s

# ---------------------------------------------------------------------
# Data Extractor Class
# ---------------------------------------------------------------------
class SegmentExtractor:
    def __init__(self, json_file: str):
        self.json_file = json_file

    def extract_segments_by_label(self, label: str) -> List[Dict[str, str]]:
        try:
            with open(self.json_file, "r") as f:
                data = json.load(f)

            segments = []
            for entry in data:
                if entry.get("label") == label:
                    start_time = TimeUtils.seconds_to_hms(entry["start"])
                    end_time = TimeUtils.seconds_to_hms(entry["end"])
                    segments.append({
                        "id": entry.get("id"),       # ✅ include id
                        "label": label,
                        "start": start_time,
                        "end": end_time
                    })

            logger.info(f"Extracted {len(segments)} '{label}' segments from JSON.")
            return segments

        except Exception as e:
            logger.exception(f"Error extracting segments: {e}")
            raise

# ---------------------------------------------------------------------
# FFmpeg Handler Class
# ---------------------------------------------------------------------
class FFmpegHandler:
    def extract_segments(self, video_path: str, segments: List[Dict], output_dir: str = "clips", lang_suffix: str = "") -> List[Dict]:
        os.makedirs(output_dir, exist_ok=True)
        outputs = []
        ext = os.path.splitext(video_path)[1].lstrip(".")
        movie_name = os.path.splitext(os.path.basename(video_path))[0]

        for seg in segments:
            seg_id = seg.get("id")        # ✅ use id if present
            start, end = seg["start"], seg["end"]
            duration = TimeUtils.time_to_seconds(end) - TimeUtils.time_to_seconds(start)
            start_str = start.replace(":", "-")
            end_str = end.replace(":", "-")

            # ✅ Include id in filename
            try:
                seg_id_num = int(seg_id)
            except (ValueError, TypeError):
                raise ValueError(f"❌ Invalid segment ID '{seg_id}' — expected a numeric value.")
            
            out_file = os.path.join(
                            output_dir,
                            f"{movie_name}_{seg_id_num:03d}_{start_str}_to_{end_str}_{lang_suffix}.{ext}"
                        )

            ffmpeg.input(video_path, ss=start, t=duration).output(out_file, c="copy").overwrite_output().run(quiet=True)
            outputs.append({
                "file": out_file,
                "id": seg_id,
                "start": start,
                "end": end
            })

        logger.info(f"Extracted {len(outputs)} clips into '{output_dir}/'.")
        return outputs

    def concat_videos(self, video_list: list, output_file: str) -> str:
        inputs = []
        streams = []
        for item in video_list:
            inp = ffmpeg.input(item["file"])
            inputs.append(inp)
            streams.extend([inp.video, inp.audio])
        n = len(video_list)
        ffmpeg.concat(*streams, v=1, a=1, n=n).output(output_file, vcodec="libx264", acodec="aac", audio_bitrate="192k").overwrite_output().run(quiet=True)
        logger.info(f"Merged {n} clips into {output_file}")
        return output_file

    def get_video_duration(self, video_path: str) -> str:
        probe = ffmpeg.probe(video_path)
        duration = float(probe['format']['duration'])
        return TimeUtils.seconds_to_hms(duration)

# ---------------------------------------------------------------------
# Segment Logic Class
# ---------------------------------------------------------------------
class SegmentLogic:
    @staticmethod
    def get_story_segments(song_segments: List[Dict], all_segments: List[Dict], video_duration: str) -> List[Dict]:
        """
        Generate story segments by finding gaps between song segments,
        while preserving IDs for voice segments from JSON.
        """
        story_segments = []
        prev_end = "00:00:00"

        # Convert song segments to start/end times for easier comparison
        song_times = [(seg["start"], seg["end"]) for seg in song_segments]

        for seg in all_segments:
            # Only consider voice/story segments
            if seg["label"].lower() != "song":
                start, end = seg["start"], seg["end"]
                # Ensure gap is captured
                if prev_end != start:
                    story_segments.append({
                        "id": seg.get("id"),  # preserve ID from JSON
                        "label": seg.get("label", "voice"),
                        "start": prev_end,
                        "end": start
                    })
                prev_end = end

        # Catch any final segment till end of video
        if prev_end != video_duration:
            story_segments.append({
                "id": None,  # optional, can assign fallback ID here if needed
                "label": "voice",
                "start": prev_end,
                "end": video_duration
            })

        logger.info(f"Generated {len(story_segments)} story segments.")
        return story_segments

# ---------------------------------------------------------------------
# Project Structure Manager
# ---------------------------------------------------------------------
class ProjectStructureManager:
    def __init__(self, input_movie_path: Union[str, Path], base_language: str, target_languages: Optional[List[str]] = None, story_json_path: Optional[Union[str, Path]] = None):
        self.input_movie_path = Path(input_movie_path)
        self.movie_name = self.input_movie_path.stem
        self.upload_dir = self.input_movie_path.parent
        self.base_language = "BaseLanguage"
        self.target_languages = target_languages or []
        self.story_json_path = Path(story_json_path) if story_json_path else None
        self.project_root = self.upload_dir / self.movie_name
        self.input_root = self.project_root / "Input"
        self.output_root = self.project_root / "Output"

    def _parse_json_chunks(self) -> dict:
        result = {"songs": [], "voice": []}
        if not self.story_json_path or not self.story_json_path.exists():
            print(f"⚠️ JSON path missing or not found: {self.story_json_path}")
            return result
        try:
            with open(self.story_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for chunk in data:
                label = chunk.get("label", "").lower()
                chunk_id = chunk.get("id")
                if label == "song":
                    result["songs"].append(chunk_id)
                elif label == "voice":
                    result["voice"].append(chunk_id)
            print(f"📘 Parsed JSON → Songs: {len(result['songs'])}, Voice Chunks: {len(result['voice'])}")
            return result
        except Exception as e:
            print(f"⚠️ Error parsing JSON: {e}")
            return result

    def create_structure(self, move_files: bool = True) -> Path:
        # Parse JSON to know how many song/voice segments
        chunk_data = self._parse_json_chunks()

        # Base Input folders
        songs_base = self.input_root / self.base_language / "songs"
        story_base = self.input_root / self.base_language / "story"

        # Create Input folders
        for base, subs, chunk_list in [
            (songs_base, ["audio_files", "song_files", "srt_files"], chunk_data["songs"]),
            (story_base, ["audio_files", "story_files", "srt_files"], chunk_data["voice"])
        ]:
            for sub in subs:
                os.makedirs(base / sub, exist_ok=True)

        # Create Output folders per target language
        for lang in self.target_languages:
            lang_root = self.output_root / lang
            songs_out = lang_root / "songs"
            story_out = lang_root / "story"

            # Songs output
            for sub in ["srt_files", "subtitle_files", "evaluation"]:
                os.makedirs(songs_out / sub, exist_ok=True)

            # Story output
            for sub in ["dubbed_files", "srt_files", "evaluation"]:
                os.makedirs(story_out / sub, exist_ok=True)

        # Move movie and JSON into Input
        if move_files:
            if not self.input_movie_path.exists():
                raise FileNotFoundError(f"❌ Movie not found: {self.input_movie_path}")
            dest_movie_path = self.input_root / f"{self.movie_name}.mp4"
            if not dest_movie_path.exists():
                shutil.move(self.input_movie_path, dest_movie_path)

            if self.story_json_path and self.story_json_path.exists():
                dest_json_path = self.input_root / self.story_json_path.name
                if not dest_json_path.exists():
                    shutil.move(self.story_json_path, dest_json_path)

        print(f"✅ Project structure created successfully under: {self.project_root}")
        return self.project_root

    
# ---------------------------------------------------------------------
# Video Processor
# ---------------------------------------------------------------------    
class VideoProcessor:
    """
    Handles extraction of video segments and optional concatenation,
    triggered manually after human validation (e.g., from Streamlit UI).
    """

    def __init__(self, project_manager: ProjectStructureManager):
        self.project_manager = project_manager

        # Use JSON path and movie path from created structure
        json_candidates = list(self.project_manager.input_root.glob("*.json"))
        if not json_candidates:
            raise FileNotFoundError("❌ JSON definition not found in Input folder.")
        self.json_path = json_candidates[0]

        self.extractor = SegmentExtractor(self.json_path)
        self.ffmpeg = FFmpegHandler()
        self.logic = SegmentLogic()
        self.input_video = self.project_manager.input_root / f"{self.project_manager.movie_name}.mp4"

        # Store extracted segments in memory for later concatenation
        self.extracted_segments = []

    # ---------------------------------------------------------------
    # Phase 1: Extract Segments Only (No Concatenation)
    # ---------------------------------------------------------------
    def extract_segments(self, label: str, lang_suffix:str):
        """
        Extracts video segments by label and saves them into the project folder.
        This phase runs first and can be validated by a human.
        """
        # 🔹 Extract segments of the requested label
        label_segments = self.extractor.extract_segments_by_label(label)
        video_duration = self.ffmpeg.get_video_duration(str(self.input_video))
        logger.info(f"🎞️ Total video duration: {video_duration}")

        # 🔹 Always fetch both sets for clarity
        song_segments = self.extractor.extract_segments_by_label("song")
        voice_segments = self.extractor.extract_segments_by_label("voice")

         # 🔹 Assign based on what we’re processing
        song_clips, story_clips = [], []

        base_lang = self.project_manager.base_language
        song_dir = self.project_manager.input_root / base_lang / "songs" / "song_files"
        story_dir = self.project_manager.input_root / base_lang / "story" / "story_files"

        # -----------------------------------------------------------------
        # SONG SEGMENTS
        # -----------------------------------------------------------------
        if song_segments:
            logger.info(f"🎶 Found {len(song_segments)} song segments. Extracting...")
            song_clips = self.ffmpeg.extract_segments(
                str(self.input_video),
                song_segments,
                str(song_dir),
                lang_suffix = lang_suffix
            )
        else:
            logger.warning("⚠️ No song segments found in JSON.")

        # -----------------------------------------------------------------
        # STORY / VOICE SEGMENTS
        # -----------------------------------------------------------------
        if voice_segments:
            logger.info(f"🗣️ Found {len(voice_segments)} story segments. Extracting...")
            story_clips = self.ffmpeg.extract_segments(
                str(self.input_video),
                voice_segments,
                str(story_dir),
                lang_suffix = lang_suffix
            )
        else:
            logger.warning("⚠️ No voice/story segments found in JSON.")

        all_segments = song_clips + story_clips
        # ✅ Sort by ID first, then start time (for consistency)
        all_segments_sorted = sorted(
            all_segments,
            key=lambda x: (int(x.get("id", 0)), TimeUtils.time_to_seconds(x["start"])))

        self.extracted_segments = all_segments_sorted
        logger.info(f"✅ Extracted total {len(all_segments_sorted)} clips (songs + story).")
        logger.info("✅ Segment extraction completed successfully (no concatenation yet).")

        return all_segments_sorted

    # ---------------------------------------------------------------
    # Phase 2: Explicit Concatenation (Triggered After Human Validation)
    # ---------------------------------------------------------------
    def concatenate_segments(self, concat_output: Optional[str] = None):
        """
        Concatenates previously extracted segments into one video.
        Should be invoked explicitly after human validation (e.g. from Streamlit).
        """
        if not self.extracted_segments:
            raise ValueError("⚠️ No extracted segments found. Run extract_segments() first.")

        concat_output = concat_output or "merged_output"
        concat_output_path = self.project_manager.output_root / f"{concat_output}.mp4"

        logger.info("🔗 Concatenating validated segments...")
        merged_output = self.ffmpeg.concat_videos(self.extracted_segments, str(concat_output_path))
        logger.info(f"✅ Final merged video saved at: {merged_output}")

        return merged_output


# ---------------------------------------------------------------------
# Example Usage
# ---------------------------------------------------------------------
if __name__ == "__main__":
    manager = ProjectStructureManager(
        input_movie_path="/home/csc/Documents/Test1/rishtey.mp4",
        base_language="BaseLanguage",
        target_languages=[
            "Malay",
            "Bhasa",
            "Arabic",
            "Swahili",
            "Sinhala",
            "Telugu",
            "Tamil",
            "Kannada",
            "Malayalam",
            "Marathi",
            "Gujarati",
            "Bhojpuri",
        ],
        story_json_path="/home/csc/Documents/Test1/rishtey_labeled_chunks.json",
    )

    # Create full structured folder tree and move files
    project_root = manager.create_structure(move_files=True)
    print(f"✅ Project ready at: {project_root}")

    # Initialize Video Processor using existing structure
    processor = VideoProcessor(manager)
    processor.extract_segments(label="song",lang_suffix="hi")
