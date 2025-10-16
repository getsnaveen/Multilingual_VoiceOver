import os
import ffmpeg
from typing import List, Dict

def time_to_seconds(time_str: str) -> float:
    """Convert HH:MM:SS to seconds."""
    h, m, s = map(float, time_str.split(":"))
    return h * 3600 + m * 60 + s


def extract_segments(video_path: str, segments: List[Dict], output_dir: str = "clips"):
    """
    Extract video segments (same format as input).
    Output filenames include start and end timestamps.
    """
    os.makedirs(output_dir, exist_ok=True)
    outputs = []
    ext = os.path.splitext(video_path)[1].lstrip(".")
    movie_name = os.path.splitext(os.path.basename(video_path))[0]

    for seg in segments:
        start, end = seg["start"], seg["end"]

        # calculate exact duration
        duration = time_to_seconds(end) - time_to_seconds(start)

        # filename with start and end timestamps
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

    return outputs

def concat_videos(video_list: list, output_file: str):
    """
    Concatenate multiple video files into one using filter_complex.
    Always re-encodes to preserve audio + video sync.
    """
    inputs = []
    streams = []

    for idx, item in enumerate(video_list):
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
    return output_file

def get_story_segments(song_segments: List[Dict], video_duration: str):
    """
    Derive story segments (everything between songs).
    """
    story_segments = []
    prev_end = "00:00:00"

    for seg in song_segments:
        if prev_end != seg["start"]:
            story_segments.append({"start": prev_end, "end": seg["start"]})
        prev_end = seg["end"]

    if prev_end != video_duration:
        story_segments.append({"start": prev_end, "end": video_duration})

    return story_segments


def get_video_duration(video_path: str) -> str:
    """
    Get video duration in HH:MM:SS format using ffprobe.
    """
    probe = ffmpeg.probe(video_path)
    duration = float(probe['format']['duration'])

    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


if __name__ == "__main__":
    subtitle_video = "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/rishtey/rishtey_Final_Bhasa.mp4"
    dubbed_video = "/home/csc/Documents/Multilingual-Transcriber/shared_data/DubbingMovies/Rishtey_Bahsa_Dubbed.mp4"

    song_segments = [
        	{"start": "00:06:23", "end": "00:14:15"},
            {"start": "00:31:31", "end": "00:34:59"},
            {"start": "00:48:37", "end": "00:52:05"},
            {"start": "01:26:27", "end": "01:31:09"},
            {"start": "01:53:18", "end": "01:54:39"}	
            ]

    # get total movie duration dynamically
    video_duration = get_video_duration(subtitle_video)
    print(f"Total duration: {video_duration}")

    # get story segments
    story_segments = get_story_segments(song_segments, video_duration)

    # extract both
    print("Extracting song segments...")
    song_clips = extract_segments(subtitle_video, song_segments, output_dir="songs")

    print("Extracting story segments...")
    story_clips = extract_segments(dubbed_video, story_segments, output_dir="stories")

    # merge in chronological order
    all_segments = story_clips + song_clips
    # sort by start timestamp
    all_segments_sorted = sorted(all_segments, key=lambda x: time_to_seconds(x["start"]))

    print("Merging all clips in time order...",all_segments_sorted)
    merged = concat_videos(all_segments_sorted, "Rishtey_Bahsa_Dubbed.mp4")
    print(f"✅ Final movie saved at {merged}")

    import time
    time.sleep(5)
