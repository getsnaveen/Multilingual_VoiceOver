import os
import json
import ffmpeg
import logging
from typing import List, Dict


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
        """Convert seconds to HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02}:{minutes:02}:{secs:02}"

    @staticmethod
    def time_to_seconds(time_str: str) -> float:
        """Convert HH:MM:SS to seconds."""
        h, m, s = map(float, time_str.split(":"))
        return h * 3600 + m * 60 + s


# ---------------------------------------------------------------------
# Data Extractor Class
# ---------------------------------------------------------------------
class SegmentExtractor:
    """Extracts segments by label from JSON input."""

    def __init__(self, json_file: str):
        self.json_file = json_file

    def extract_segments_by_label(self, label: str) -> List[Dict[str, str]]:
        """Extract start/end segments for a given label."""
        try:
            with open(self.json_file, "r") as f:
                data = json.load(f)

            segments = []
            for entry in data:
                if entry.get("label") == label:
                    start_time = TimeUtils.seconds_to_hms(entry["start"])
                    end_time = TimeUtils.seconds_to_hms(entry["end"])
                    segments.append({"start": start_time, "end": end_time})

            logger.info(f"Extracted {len(segments)} '{label}' segments from JSON.")
            return segments

        except Exception as e:
            logger.exception(f"Error extracting segments: {e}")
            raise


# ---------------------------------------------------------------------
# FFmpeg Handler Class
# ---------------------------------------------------------------------
class FFmpegHandler:
    """Handles video segment extraction, concatenation, and duration."""

    def __init__(self):
        pass

    def extract_segments(self, video_path: str, segments: List[Dict], output_dir: str = "clips") -> List[Dict]:
        """Extract multiple segments from a video."""
        os.makedirs(output_dir, exist_ok=True)
        outputs = []
        ext = os.path.splitext(video_path)[1].lstrip(".")
        movie_name = os.path.splitext(os.path.basename(video_path))[0]

        for seg in segments:
            start, end = seg["start"], seg["end"]
            duration = TimeUtils.time_to_seconds(end) - TimeUtils.time_to_seconds(start)

            start_str = start.replace(":", "-")
            end_str = end.replace(":", "-")
            out_file = os.path.join(output_dir, f"{movie_name}_{start_str}_to_{end_str}.{ext}")

            (
                ffmpeg
                .input(video_path, ss=start, t=duration)
                .output(out_file, c="copy")
                .overwrite_output()
                .run(quiet=True)
            )
            outputs.append({"file": out_file, "start": start, "end": end})

        logger.info(f"Extracted {len(outputs)} clips into '{output_dir}/'.")
        return outputs

    def concat_videos(self, video_list: list, output_file: str) -> str:
        """Concatenate multiple clips into one video file."""
        inputs = []
        streams = []

        for item in video_list:
            inp = ffmpeg.input(item["file"])
            inputs.append(inp)
            streams.extend([inp.video, inp.audio])

        n = len(video_list)
        out = (
            ffmpeg
            .concat(*streams, v=1, a=1, n=n)
            .output(output_file, vcodec="libx264", acodec="aac", audio_bitrate="192k")
            .overwrite_output()
        )
        out.run(quiet=True)
        logger.info(f"Merged {n} clips into {output_file}")
        return output_file

    def get_video_duration(self, video_path: str) -> str:
        """Return video duration as HH:MM:SS."""
        probe = ffmpeg.probe(video_path)
        duration = float(probe['format']['duration'])
        return TimeUtils.seconds_to_hms(duration)


# ---------------------------------------------------------------------
# Segment Logic Class
# ---------------------------------------------------------------------
class SegmentLogic:
    """Computes derived segment data like story (non-song) segments."""

    @staticmethod
    def get_story_segments(song_segments: List[Dict], video_duration: str) -> List[Dict]:
        """Get story segments (everything not in song segments)."""
        story_segments = []
        prev_end = "00:00:00"

        for seg in song_segments:
            if prev_end != seg["start"]:
                story_segments.append({"start": prev_end, "end": seg["start"]})
            prev_end = seg["end"]

        if prev_end != video_duration:
            story_segments.append({"start": prev_end, "end": video_duration})

        logger.info(f"Generated {len(story_segments)} story segments.")
        return story_segments


# ---------------------------------------------------------------------
# Main Orchestrator Class
# ---------------------------------------------------------------------
class VideoProcessor:
    """Coordinates entire video processing pipeline."""

    def __init__(self, json_file: str, input_video: str):
        self.extractor = SegmentExtractor(json_file)
        self.ffmpeg = FFmpegHandler()
        self.logic = SegmentLogic()
        self.input_video = input_video
        
    def process(self, label: str, output_file: str):
        """Main orchestration method."""
        # 1. Extract labeled segments
        song_segments = self.extractor.extract_segments_by_label(label)

        # 2. Get total video duration
        video_duration = self.ffmpeg.get_video_duration(self.subtitle_video)
        logger.info(f"Total duration of subtitle video: {video_duration}")

        # 3. Derive story (non-labeled) segments
        story_segments = self.logic.get_story_segments(song_segments, video_duration)

        # 4. Extract song & story segments
        logger.info("Extracting song segments...")
        song_clips = self.ffmpeg.extract_segments(self.input_video, song_segments, output_dir="songs")

        logger.info("Extracting story segments...")
        story_clips = self.ffmpeg.extract_segments(self.input_video, story_segments, output_dir="stories")

        # 5. Merge in chronological order
        all_segments = story_clips + song_clips
        all_segments_sorted = sorted(all_segments, key=lambda x: TimeUtils.time_to_seconds(x["start"]))

        logger.info("Merging all clips in chronological order...")
        merged_output = self.ffmpeg.concat_videos(all_segments_sorted, output_file)

        logger.info(f"✅ Final merged video saved at: {merged_output}")


# ---------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------
if __name__ == "__main__":
    json_file = "/home/csc/Downloads/labeled_chunks (1).json"
    input_video = "/home/csc/Documents/Backup/shared_data/movieslist/rishtey/rishtey_Final_Bhasa.mp4"
    output_file = "Rishtey_Bahsa_Dubbed_Final_new.mp4"

    processor = VideoProcessor(json_file, input_video)
    processor.process(label="song", output_file=output_file)
