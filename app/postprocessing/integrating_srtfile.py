import os, pysrt, subprocess, ffmpeg, json
from moviepy import TextClip,VideoFileClip,CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip
from moviepy.video.compositing.CompositeVideoClip import  concatenate_videoclips
from natsort import natsorted
from pathlib import Path
from utils.logger import SingletonLogger, log_exceptions
from utils.language_const import LANGUAGES, LANGUAGE_CONFIG
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict

class VideoProcessor:
    def __init__(self, font_path: str = "app/Arial.ttf"):
        self.logger = SingletonLogger.getInstance(self.__class__.__name__).logger
        self.font_path = font_path

    @staticmethod
    def time_to_seconds(srt_time):
        return (
            srt_time.hours * 3600
            + srt_time.minutes * 60
            + srt_time.seconds
            + srt_time.milliseconds / 1000.0
        )

    @log_exceptions(" this fucntion create_subtitle_clips failed ")
    def create_subtitle_clips(self, video_path, srt_path, output_path, debug=False):
        video = VideoFileClip(video_path)
        width, height = video.size
        subtitles = pysrt.open(srt_path)
        subtitle_clips = []

        for subtitle in subtitles:
            start = self.time_to_seconds(subtitle.start)
            end = self.time_to_seconds(subtitle.end)
            duration = end - start

            if debug:
                self.logger.info(f"Subtitle: {subtitle.text.strip()} | Start: {start}s | Duration: {duration}s")

            clip = (
                TextClip(
                    subtitle.text,
                    fontsize=24,
                    font=self.font_path,
                    color='yellow',
                    bg_color='black',
                    size=(int(width * 0.9), None),
                    method='caption',
                )
                .set_start(start)
                .set_duration(duration)
                .set_position(('center', height * 0.85))
            )
            subtitle_clips.append(clip)

        final = CompositeVideoClip([video] + subtitle_clips)
        final.write_videofile(output_path, codec='libx264', audio_codec='aac')
        video.close()
        final.close()

    @log_exceptions()
    def synchronize_and_embed_subtitles(self, video_path, subtitle_path, output_path):
        synced_subtitle_path = f"synced_{os.path.basename(subtitle_path)}"
        subprocess.run(["ffsubsync", video_path, "-i", subtitle_path, "-o", synced_subtitle_path], check=True)

        ffmpeg.input(video_path).output(output_path, vf=f"subtitles={synced_subtitle_path}").run()

        os.remove(synced_subtitle_path)
        self.logger.info(f"Embedded subtitles saved to {output_path}")

    @log_exceptions()
    def merge_videos(self, video_paths, video_dir, output_path):
        clips = []
        for path in video_paths:
            full_path = os.path.join(video_dir, path)
            if os.path.isfile(full_path):
                clips.append(VideoFileClip(full_path))
            else:
                self.logger.warning(f"File not found: {full_path}")

        if not clips:
            self.logger.error("No valid video files found to merge.")
            return

        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_path, codec="libx264", audio_codec="aac")
        for clip in clips:
            clip.close()
        self.logger.info(f"Merged video saved to {output_path}")

    @log_exceptions()
    def get_video_info(self, path):
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height",
            "-of", "json", path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed on {path}: {result.stderr}")
        stream = json.loads(result.stdout)["streams"][0]
        return stream["codec_name"], stream["width"], stream["height"]

    @log_exceptions()
    def validate_video_formats(self, video_paths, base_dir):
        baseline = None
        for path in video_paths:
            full_path = os.path.join(base_dir, path)
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"File not found: {full_path}")
            info = self.get_video_info(full_path)
            if baseline is None:
                baseline = info
            elif info != baseline:
                raise ValueError(f"Incompatible video format: {path} has {info}, expected {baseline}")

    @log_exceptions(" Merging videos failed ")
    def merge_videos_ffmpeg_fast(self, video_paths, base_dir, output_path):
        
        video_paths = natsorted(video_paths)
        self.validate_video_formats(video_paths, base_dir)
        self.logger.info(f":::::::::::: {video_paths}")
        self.logger.info(f":::::::::::: {base_dir}")
        self.logger.info(f":::::::::::: {output_path}")

        concat_file = os.path.join(base_dir, "concat_list.txt")
        with open(concat_file, "w") as f:
            for video in video_paths:
                rel_path = os.path.relpath(os.path.join(base_dir, video), start=base_dir)
                f.write(f"file '{rel_path}'\n")

        result = subprocess.run(
            ["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg merge failed: {result.stderr}")
        self.logger.info(f"Merged video saved to {output_path}")

    @log_exceptions()
    def burn_subtitles(self, lang, video_path, subtitle_filename, subtitle_dir, output_filename, output_dir):
        
        filename_prefix = subtitle_filename.rsplit('_', 1)[0].replace('.srt', '')
        filename_prefix_output = subtitle_filename.rsplit('_', 1)[0].replace('.srt', '')
        self.logger.info(f"✅ filename_prefix: {filename_prefix}")
        self.logger.info(f"✅ filename_prefix_output  : {filename_prefix_output}")
        # for lang in languages:
        lang_code = LANGUAGES[lang]
        translated_filename = f"{filename_prefix}_{lang_code}.srt"
        output_filename = f"{filename_prefix_output}_{lang_code}_subtitled.mp4"
        subtitle_path = os.path.join(subtitle_dir, translated_filename)
        output_path = os.path.join(output_dir, output_filename)
        translated_filename_ass = f"{filename_prefix}_{lang_code}.ass"
        ass_path = os.path.join(subtitle_dir, translated_filename_ass)
        
        self.logger.info(f"✅ subtitle_path: {subtitle_path}")
        self.logger.info(f"✅ ass_path  : {ass_path}")

        self.create_ass_file(subtitle_path, ass_path, lang_code)
        self.logger.info(f"✅ ASS file created: {ass_path}")

        self.logger.info(f"Burning subtitles for {lang} -> {subtitle_path}")
        command = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"ass={ass_path}",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(command)
        self.logger.info(f"Output saved to: {output_path}")
    
    @log_exceptions()
    def convert_srt_time_to_ass(self, srt_time: str) -> str:
        """Convert SRT timestamp to ASS format (H:MM:SS.mm)"""
        if ',' in srt_time:
            time_part, ms_part = srt_time.split(',')
            ms_part = ms_part[:2].ljust(2, '0')  # Keep only 2 digits
        else:
            time_part = srt_time
            ms_part = "00"
        hours, minutes, seconds = time_part.split(':')
        hours = str(int(hours))  # Remove leading zeros
        return f"{hours}:{minutes}:{seconds}.{ms_part}"


    @log_exceptions()
    def create_ass_file(self, srt_path: Path, ass_path: Path, language: str):
        """Create ASS file with styles based on language"""
        config = LANGUAGE_CONFIG[language]
        srt_path = Path(srt_path)
        ass_path = Path(ass_path)

        with srt_path.open('r', encoding='utf-8') as srt_file, \
            ass_path.open('w', encoding='utf-8') as ass_file:

            # Write header
            ass_file.write(
                "[Script Info]\n"
                "ScriptType: v4.00+\n"
                "PlayResX: 384\n"
                "PlayResY: 288\n"
                "ScaledBorderAndShadow: yes\n\n"

                "[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, Bold, Italic, "
                "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                f"Style: Default,{config['font_name']},{config['font_size']},{config['font_color']},"
                "0,0,1,0.5,2,10,10,10,0\n\n"

                "[Events]\n"
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            )

            blocks = srt_file.read().strip().split('\n\n')
            previous_end = "0:00:00.00"

            for block in blocks:
                lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
                if len(lines) < 3 or '-->' not in lines[1]:
                    continue

                start, end = [self.convert_srt_time_to_ass(t.strip()) for t in lines[1].split('-->')]

                # Fill gap with transparent line if gap exists
                if previous_end != start:
                    ass_file.write(
                        f"Dialogue: 0,{previous_end},{start},Default,,0,0,0,,{{\\alpha&HFF&}} \n"
                    )

                # Write actual subtitle
                text = '\\N'.join(lines[2:])
                ass_file.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")
                previous_end = end

            
