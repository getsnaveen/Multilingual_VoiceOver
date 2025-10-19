import os, time
from abc import ABC, abstractmethod
from typing import Optional, Any
from audio_extract import extract_audio
from utils.logger import SingletonLogger, log_exceptions
from utils.audio_utils import AudioUtils
from concurrent.futures import ThreadPoolExecutor, as_completed


class Extraction(ABC):
    """
    Abstract base class for implementing different types of extraction logic.
    """

    def __init__(self):
        """
        Initializes the base Extraction class.
        """
        pass

    @abstractmethod
    def AudioExtraction(self, inputpath: str, outputpath: str, *args, **kwargs):
        """
        Abstract method for extracting audio from an input file and saving to output path.

        Args:
            inputpath (str): Path to the source video file.
            outputpath (str): Destination path for the extracted audio.
        """
        pass


class AudioExtractor(Extraction):
    """
    Concrete implementation of audio extraction using a standard audio extraction utility.
    """

    def __init__(self):
        """
        Initializes the AudioExtractor with logging support.
        """
        super().__init__()
        self.logger = SingletonLogger.getInstance(self.__class__.__name__).logger

    @log_exceptions("Audio extraction failed")
    def AudioExtraction(self, inputpath: str, outputpath: str, *args, **kwargs):
        """
        Extracts audio from the given input file and saves it to the specified output path.

        Args:
            inputpath (str): Path to the video or multimedia file.
            outputpath (str): Path to save the extracted audio file.
        """
        self.logger.info(f"Starting audio extraction from: {inputpath}")
        extract_audio(input_path=inputpath, output_path=outputpath)
        time.sleep(1)
        AudioUtils().preprocess_audio(input_path=outputpath, output_path=outputpath)
        time.sleep(1)
        self.logger.info(f"Audio successfully extracted to: {outputpath}")

    @log_exceptions("Batch audio extraction failed")
    def extract_audio_batch(self, input_output_pairs: list[tuple[str, str]], max_workers: int = 16):
        """
        Extracts audio from multiple files in parallel using threads.

        Args:
            input_output_pairs (List[Tuple[str, str]]): List of (input_video, output_audio) pairs.
            max_workers (int): Number of threads to use.
        """
        self.logger.info(f"🧵 Starting batch extraction with {max_workers} workers")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.AudioExtraction, inp, out): (inp, out)
                for inp, out in input_output_pairs
            }
            for future in as_completed(futures):
                inp, out = futures[future]
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"❌ Error processing {inp} → {out}: {e}")

    # if __name__ == "__main__":
    # audio_utils = AudioUtils()
    # input_output_paths = [
    #     ("movie1.mp4", "movie1.wav"),
    #     ("movie2.mp4", "movie2.wav"),
    #     ("movie3.mp4", "movie3.wav"),
    #     # add more files here
    # ]
    # audio_utils.extract_audio_batch(input_output_paths, max_workers=4)


