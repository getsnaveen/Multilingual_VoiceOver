import os
import math
from typing import List
from utils.logger import SingletonLogger, log_exceptions


class FileUtils:
    """
    Utility class for common file and time formatting operations.
    """

    def __init__(self):
        """
        Initializes the logger for FileUtils.
        """
        self.logger = SingletonLogger.getInstance("FileUtils").logger

    @log_exceptions("Failed to format time")
    def format_time(self, seconds: float) -> str:
        """
        Converts a time in seconds to the SRT-friendly format HH:MM:SS,ms.

        Args:
            seconds (float): Time in seconds.

        Returns:
            str: Formatted time string.
        """
        hours = math.floor(seconds / 3600)
        seconds %= 3600
        minutes = math.floor(seconds / 60)
        seconds %= 60
        milliseconds = round((seconds - math.floor(seconds)) * 1000)
        seconds = math.floor(seconds)
        formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
        return formatted_time

    @staticmethod
    @log_exceptions("Failed to list .mp4 files")
    def list_mp4_files(dirpath: str) -> List[str]:
        """
        Lists all .mp4 files in the given directory.

        Args:
            dirpath (str): Path to the directory.

        Returns:
            List[str]: List of .mp4 filenames.
        """
        return [f for f in os.listdir(dirpath) if f.endswith(".mp4")]

    @staticmethod
    @log_exceptions("Failed to list .mp3 files")
    def list_mp3_files(dirpath: str) -> List[str]:
        """
        Lists all .mp3 files in the given directory.

        Args:
            dirpath (str): Path to the directory.

        Returns:
            List[str]: List of .mp3 filenames.
        """
        return [f for f in os.listdir(dirpath) if f.endswith(".mp3")]

    @staticmethod
    @log_exceptions("Failed to list .srt files")
    def list_srt_files(dirpath: str) -> List[str]:
        """
        Lists all .srt files in the given directory.

        Args:
            dirpath (str): Path to the directory.

        Returns:
            List[str]: List of .srt filenames.
        """
        return [f for f in os.listdir(dirpath) if f.endswith(".srt")]
    
    @staticmethod
    @log_exceptions("Directory creation failed")
    def ensure_directories(paths: List[str]):
        """
        Ensures that a list of directory paths exist, and creates them if not.

        Args:
            paths (List[str]): List of directory paths to ensure.
        """
        logger = SingletonLogger.getInstance("PathUtils").logger
        for path in paths:
            os.makedirs(path, exist_ok=True)
            logger.info(f"✅ Directory ready: {path}")
        
# if __name__ == "__main__":
#     futils = FileUtils()
#     print(futils.format_time(3661.75))  # 01:01:01,750
#     print(futils.list_mp4_files("./videos"))
