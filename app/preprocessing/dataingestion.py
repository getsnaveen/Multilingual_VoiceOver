import os, yt_dlp
from abc import ABC, abstractmethod
from typing import Optional
from preprocessing import minio_client
from utils.logger import SingletonLogger, log_exceptions


class Loader(ABC):
    """
    Abstract base class for video loading operations from various sources.
    """

    def __init__(self):
        pass

    @abstractmethod
    def video_loader(self, filepath: str, *args, **kwargs):
        """
        Placeholder for file-based video loading logic.
        """
        pass

    @abstractmethod
    def youtube_downloader(self, url: str, *args, **kwargs):
        """
        Download video content from a YouTube URL.
        """
        pass

    @abstractmethod
    def minio_downloader(self, bucket_name: str, filename: str, destination_path: str, *args, **kwargs) -> str:
        """
        Download a file from MinIO to a local path.
        """
        pass


class VideoLoader(Loader):
    """
    Concrete implementation of Loader interface for YouTube, MinIO, and local video files.
    """

    def __init__(self):
        super().__init__()
        self.logger = SingletonLogger.getInstance("VideoLoader").logger

    @log_exceptions("Video loading not yet implemented")
    def video_loader(self, filepath: str, *args, **kwargs):
        """
        Placeholder for loading a video from a local file path.
        
        Args:
            filepath (str): Local path to the video file.
        """
        self.logger.info(f"Loading local video from: {filepath}")
        # Implement loading logic if needed
        pass

    @log_exceptions("YouTube download failed")
    def youtube_downloader(self, url: str, *args, **kwargs):
        """
        Downloads a video from the given YouTube URL using yt_dlp.

        Args:
            url (str): The full YouTube video URL.
        """
        self.logger.info(f"Starting YouTube download: {url}")
        ydl_opts = {}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        self.logger.info(f"Download complete: {url}")

    @log_exceptions("MinIO download failed")
    def minio_downloader(self, bucket_name: str, filename: str, destination_path: str, *args, **kwargs) -> str:
        """
        Downloads a file from a MinIO bucket and saves it to a local path.

        Args:
            bucket_name (str): Name of the MinIO bucket.
            filename (str): The name of the file in the bucket.
            destination_path (str): The directory to save the downloaded file.

        Returns:
            str: Full path to the downloaded file.
        """
        self.logger.info(f"Downloading from MinIO: bucket={bucket_name}, file={filename}")

        client = minio_client()

        full_path = os.path.join(destination_path, filename)
        client.fget_object(bucket_name=bucket_name, object_name=filename, file_path=full_path)

        self.logger.info(f"File downloaded to: {full_path}")
        return full_path

# if __name__ == "__main__":
#     loader = VideoLoader()
#     loader.youtube_downloader("https://youtube.com/some-video")
#     loader.minio_downloader("my-bucket", "video.mp4", "/tmp/videos/")
