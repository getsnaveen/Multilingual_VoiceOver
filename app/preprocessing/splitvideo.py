import os , time, subprocess
from abc import ABC, abstractmethod
from typing import Union
from moviepy import VideoFileClip
from utils.logger import SingletonLogger, log_exceptions
from concurrent.futures import ProcessPoolExecutor

class Splitter(ABC):
    """
    Abstract base class defining the interface for video splitting functionality.
    """

    def __init__(self):
        pass

    @abstractmethod
    def video_splitter(self, filepath: str, segment_length: Union[int, float], output_dir: str, *args, **kwargs):
        """
        Abstract method to split a video into segments.

        Args:
            filepath (str): Path to the input video file.
            segment_length (int | float): Length of each segment in seconds.
            output_dir (str): Directory to store the output segments.
        """
        pass


class VideoSplitter(Splitter):
    """
    Concrete implementation of Splitter that splits videos using MoviePy.
    """

    def __init__(self):
        """
        Initializes the VideoSplitter with a logger.
        """
        super().__init__()
        self.logger = SingletonLogger.getInstance(self.__class__.__name__).logger

    @log_exceptions("Video splitting failed")
    def video_splitter(self, filepath: str, segment_length: Union[int, float], output_dir: str, *args, **kwargs):
        """
        Splits the input video into segments of specified duration and saves them to the output directory.

        Args:
            filepath (str): Full path to the input video file.
            segment_length (int | float): Duration of each split segment in seconds.
            output_dir (str): Directory to save the split video parts.
        """
        self.logger.info(f"Starting video split for: {filepath}")
        os.makedirs(output_dir, exist_ok=True)

        clip = VideoFileClip(filepath)
        duration = clip.duration
        self.logger.info(f"Video file clip duration is  {duration}.")

        start_time = 0
        end_time = segment_length
        index = 1
        base_name = os.path.splitext(os.path.basename(filepath))[0]

        while start_time < duration:
            output_path = os.path.join(output_dir, f"{base_name}_part{index}.mp4")
            self.logger.info(f"Writing part {index}: {start_time:.2f}s to {min(end_time, duration):.2f}s -> {output_path}")
            subclip = clip.subclipped(start_time, min(end_time, duration))
            subclip.write_videofile(output_path, audio=True)
            
            start_time = end_time
            end_time += segment_length
            index += 1
            time.sleep(1)

        self.logger.info(f"Video split into {index - 1} parts successfully.")

class FFmpegVideoSplitter(VideoSplitter):
    def __init__(self):
        self.logger = SingletonLogger.getInstance(self.__class__.__name__).logger

    @log_exceptions("ffmpeg video splitter ")
    def ffmpeg_split_video(self, input_path: str, start_time: float, duration: float, output_path: str):
        """
        Splits a video segment using FFmpeg without re-encoding (fast and lossless).

        Args:
            input_path (str): Source video file.
            start_time (float): Start time in seconds.
            duration (float): Duration of the segment.
            output_path (str): Path to save the split video.
        """
        command = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", input_path,
            "-t", str(duration),
            "-c", "copy",
            output_path
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    @log_exceptions("FFmpeg parallel splitting failed")
    def split_video_fast(
        self,
        filepath: str,
        segment_length: float,
        output_dir: str,
        max_workers: int = 16
    ):
        """
        Split video into chunks using FFmpeg and ProcessPoolExecutor.

        Args:
            filepath (str): Full path to video file.
            segment_length (float): Segment length in seconds.
            output_dir (str): Output directory to save chunks.
            max_workers (int): Number of parallel FFmpeg processes.
        """
        import ffmpeg
        import math

        os.makedirs(output_dir, exist_ok=True)
        self.logger.info(f"🎬 Starting fast FFmpeg split for: {filepath}")

        # Get video duration using ffmpeg.probe
        try:
            probe = ffmpeg.probe(filepath)
            duration = float(probe["format"]["duration"])
        except Exception as e:
            self.logger.error(f"❌ Failed to probe video duration: {e}")
            return

        self.logger.info(f"⏱️ Video duration: {duration:.2f}s")
        total_parts = math.ceil(duration / segment_length)
        base_name = os.path.splitext(os.path.basename(filepath))[0]

        tasks = []
        for i in range(total_parts):
            start = i * segment_length
            end = min(start + segment_length, duration)
            out_name = os.path.join(output_dir, f"{base_name}_part{i+1}.mp4")
            tasks.append((filepath, start, end - start, out_name))

        # ProcessPoolExecutor for parallel execution
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.ffmpeg_split_video, *task)
                for task in tasks
            ]
            for f in futures:
                f.result()  # wait for all

        self.logger.info(f"✅ Split into {len(tasks)} parts saved to {output_dir}")

# if __name__ == "__main__":
#     splitter = VideoSplitter()
#     splitter.video_splitter("shared_data/movieslist/Ahista/ahista_ahista.mp4", segment_length=600, output_dir="./splits/")

