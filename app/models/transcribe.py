import time, os, torch, requests
from abc import ABC, abstractmethod
from utils.logger import SingletonLogger, log_exceptions
from models.translate import TranslationUtils
from utils.language_const import LANGUAGES
from utils.audio_utils import AudioUtils
from utils.srt_parser import SRTTranslator
from utils.config import get_settings
local_settings = get_settings()

class Transcribe(ABC):
    """
    Abstract base class for audio transcription implementations.
    """

    @abstractmethod
    def AudioTranscriptiontoFile(
        self,
        model,
        inputpath: str,
        languagestoconvert: list,
        outputfolder: str,
        outputpath: str,
        do_transcription: bool = True,
        do_translation: bool = True,
        *args, **kwargs
    ):
        """
        Abstract method to perform transcription and save results to a file.

        Args:
            model: The transcription model to use.
            inputpath (str): Path to the input audio file.
            languagestoconvert (list): List of language codes to translate into.
            outputfolder (str): Root folder to save output files.
            outputpath (str): Name of the output SRT file.
            *args, **kwargs: Additional optional parameters.
        """
        pass


class AudioTranscriptor(Transcribe):
    """
    Concrete implementation of Transcribe interface for performing
    multilingual audio transcription and subtitle generation.
    """

    def __init__(self):
        """
        Initializes the AudioTranscriptor with a logger instance.
        """
        self.logger = SingletonLogger.getInstance("AudioTranscriptor").logger
        self.translator = TranslationUtils()
        self.srt_trnaslator = SRTTranslator(self.translator)

    @log_exceptions("Failed to transcribe and translate audio file")
    def AudioTranscriptiontoFile(
        self,
        model,
        inputpath: str,
        languagestoconvert: list,
        outputfolder: str,
        outputpath: str,
        do_transcription: bool = True,
        do_translation: bool = True,
        *args, **kwargs
    ):
        """
        Transcribes the given audio file and generates subtitles in multiple languages.

        This function performs the following:
        - Transcribes audio to text using a given model (default language: Hindi).
        - Generates a base SRT subtitle file.
        - Translates subtitles into each target language.
        - Creates corresponding translated SRT files.
        - Logs processing steps and clears CUDA cache if available.

        Args:
            model: Transcription model object with `.transcribe()` method.
            inputpath (str): Path to the input audio file.
            languagestoconvert (list): List of language codes to translate the text into.
            outputfolder (str): Path to the folder to save output subtitles.
            outputpath (str): Filename (with extension) for subtitle output.
            *args, **kwargs: Additional keyword arguments (currently unused).
        """
       
        self.logger.info("Starting transcription")
        filename_prefix = outputpath.split("__")[0]
        outputpath_updated = f"{filename_prefix}__hi_SRTfile.srt"
        basepath = os.path.join(outputfolder, "Base", outputpath_updated)
        os.makedirs(os.path.dirname(basepath), exist_ok=True)

        if do_transcription:
            self.logger.info("🎙️ Starting transcription")
            AudioTranscriptorElevenLabs().AudioTranscriptiontoSRT(
                inputpath=inputpath,
                outputpath=basepath
            )
            self.logger.info(f"✅ Base SRT file generated at {basepath}")
            time.sleep(1)
        else:
            self.logger.info("ℹ️ Skipping transcription – using existing base SRT")

        if do_translation:
            self.logger.info("🌍 Starting translation to target languages")
            for to_lang in languagestoconvert:
                lang_code = LANGUAGES[to_lang]
                translated_filename = f"{filename_prefix}__{lang_code}_SRTfile.srt"
                translated_folder = os.path.join(outputfolder, to_lang)
                os.makedirs(translated_folder, exist_ok=True)
                translated_path = os.path.join(translated_folder, translated_filename)

                self.srt_trnaslator.translate_srt_file_batch_with_google_translate(
                    input_path=basepath,
                    output_path=translated_path,
                    target_language=lang_code
                )
                self.logger.info(f"✅ SRT file generated for '{to_lang}' at {translated_path}")
                time.sleep(1)
        else:
            self.logger.info("ℹ️ Skipping translation")

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            self.logger.info("🧹 Cleared CUDA cache")


class AudioTranscriptorElevenLabs(ABC):
    """
    Concrete implementation of Transcribe interface for performing
    multilingual audio transcription and subtitle generation with ElevenLabs API.
    """

    def __init__(self):
        self.logger = SingletonLogger.getInstance("AudioTranscriptor").logger
        self.elevenlabs_key = local_settings.elevenlabs_key
        self.elevenlabs_modelid = local_settings.elevenlabs_modelid
        self.elevenlabs_url = local_settings.elevenlabs_url
        self.audio_utils = AudioUtils()

    @log_exceptions("Failed to transcribe and translate audio file")
    def AudioTranscriptiontoSRT(
        self,
        inputpath: str,
        outputpath: str,
        *args, **kwargs
    ):
        """
        Transcribes the given audio file and generates subtitles in multiple languages.
        """
        self.logger.info("📤 Uploading file to ElevenLabs Speech-to-Text API...")

        with open(inputpath, "rb") as audio_file:
            response = requests.post(
                url=self.elevenlabs_url,
                headers={"xi-api-key": self.elevenlabs_key},
                files={"file": audio_file},
                data={
                    "model_id": self.elevenlabs_modelid,
                    "task": "translate",
                    "output_format": "verbose_json",
                    "language": 'en'
                }
            )
            if response.status_code != 200:
                self.logger.error(f"API Error: {response.status_code} - {response.text}")
                return

            result = response.json()
            self.logger.info("✅ Transcription and translation completed")

            # Generate SRT segments
            self.audio_utils.write_srt_file(words=result["words"],
                                            output_path= outputpath)
            

        