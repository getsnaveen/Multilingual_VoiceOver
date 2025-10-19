import os, time
from pathlib import Path
from utils.logger import SingletonLogger, log_exceptions
from models.transcribe import AudioTranscriptor
from preprocessing.audioextraction import AudioExtractor
from postprocessing.integrating_srtfile import VideoProcessor
from preprocessing.splitvideo import FFmpegVideoSplitter
from utils.file_utils import FileUtils
from faster_whisper import WhisperModel
from utils.config import AppSettings
from utils.chunk_structure import ProjectStructureManager
from utils.language_const import LANGUAGES
from natsort import natsorted
from shutil import rmtree
from evalutions.evalution import TranslationEvaluator

class TranscriberApp:
    def __init__(self, settings: AppSettings, manager: ProjectStructureManager):
        self.settings = settings
        self.manager = manager
        self.logger = SingletonLogger.getInstance(self.__class__.__name__).logger
        self.model = WhisperModel('turbo', compute_type="int8", device="cpu")

        # Use the same movie name and paths from the ProjectStructureManager
        self.movie_name = manager.movie_name
        self.project_base = manager.project_root
        self.input_root = manager.input_root
        self.output_root = manager.output_root

        base_lang = manager.base_language

        # ✅ Input folders (songs + story)
        self.song_video_path = self.input_root / "songs" / base_lang / "song_files"
        self.story_video_path = self.input_root / "story" / base_lang / "story_files"

        self.song_audio_path = self.input_root / "songs" / base_lang / "audio_files"
        self.story_audio_path = self.input_root / "story" / base_lang / "audio_files"

        self.song_srt_path = self.input_root / "songs" / base_lang / "srt_files"
        self.story_srt_path = self.input_root / "story" / base_lang / "srt_files"

        # ✅ Output folders per language
        self.lang_output_paths = {
            lang: {
                "songs": {
                    "srt": self.output_root / lang / "songs" / "srt_files",
                    "subtitle": self.output_root / lang / "songs" / "subtitle_files",
                    "evaluation": self.output_root / lang / "songs" / "evaluation",
                },
                "story": {
                    "srt": self.output_root / lang / "story" / "srt_files",
                    "dubbed": self.output_root / lang / "story" / "dubbed_files",
                    "evaluation": self.output_root / lang / "story" / "evaluation",
                },
            }
            for lang in self.settings.languages_to_convert
        }

    @log_exceptions("Video processing pipeline failed")
    def run(self, selected_steps: list[str] = None):
        self.logger.info("🎬 Starting multilingual transcription pipeline")

        selected_steps = set(selected_steps or [
            "audio_extract", "transcription", "subtitle_translation",
             "subtitle_embedding", "evaluation"])

        # Example: process only songs
        song_segments = FileUtils.list_mp4_files(dirpath=self.song_video_path)
        input_output_path_song = [
            (
                os.path.join(self.song_video_path, seg),
                os.path.join(self.song_audio_path, f"{Path(seg).stem}__audio.mp3")
            )
            for seg in song_segments
        ]

        story_segments = FileUtils.list_mp4_files(dirpath=self.story_video_path)
        input_output_path_story= [
            (
                os.path.join(self.story_video_path, seg),
                os.path.join(self.story_audio_path, f"{Path(seg).stem}__audio.mp3")
            )
            for seg in story_segments
        ]


        if "audio_extract" in selected_steps:
            AudioExtractor().extract_audio_batch(input_output_pairs=input_output_path_song)
            AudioExtractor().extract_audio_batch(input_output_pairs=input_output_path_story)

        for seg in song_segments:
            base_name = Path(seg).stem
            video_path = os.path.join(self.song_video_path, seg)
            audio_path = os.path.join(self.song_audio_path, f"{base_name}__audio.mp3")
            srt_path = os.path.join(self.song_srt_path, f"{base_name}__SRTfile.srt")

            # Use transcription as before
            if "transcription" in selected_steps:
                AudioTranscriptor().AudioTranscriptiontoFile(
                    model=self.model,
                    inputpath=audio_path,
                    languagestoconvert=self.settings.languages_to_convert,
                    outputfolder=self.song_srt_path,
                    outputpath=f"{base_name}__SRTfile.srt",
                    do_transcription=True,
                    do_translation=False 
                )

            if "subtitle_translation" in selected_steps:
                AudioTranscriptor().AudioTranscriptiontoFile(
                    model=self.model,
                    inputpath=audio_path,
                    languagestoconvert=self.settings.languages_to_convert,
                    outputfolder=self.song_srt_path,
                    outputpath=f"{base_name}__SRTfile.srt",
                    do_transcription=False,
                    do_translation=True 
                )

            if "subtitle_embedding" in selected_steps:
                VideoProcessor().burn_subtitles(
                    languages=self.settings.languages_to_convert,
                    video_path=video_path,
                    subtitle_filename=f"{base_name}__SRTfile.srt",
                    subtitle_dir=self.song_srt_path,
                    output_filename=f"{base_name}__subtitled.mp4",
                    output_dir=self.subtitle_base_path
                )
                time.sleep(2)

        if "evaluation" in selected_steps:
            self.logger.info("📊 Starting evaluation using Gemini")

            for lang in self.settings.languages_to_convert:
                if lang == "Base":
                    continue

                base_srt_dir = os.path.join(self.srt_base_path, "Base")
                tgt_srt_dir = os.path.join(self.srt_base_path, lang)
                eval_dir = os.path.join(self.evaluation_base_path, lang)
                lang_code = LANGUAGES[lang]

                for srt_file in natsorted(os.listdir(base_srt_dir)):
                    if not srt_file.endswith(".srt"):
                        continue
                                        
                    src_file = os.path.join(base_srt_dir, srt_file)
                    tgt_file = os.path.join(tgt_srt_dir, srt_file.replace("__hi_", f"__{lang_code}_"))
                    out_csv = os.path.join(eval_dir, srt_file.replace(".srt", f"__{lang_code}_eval.csv"))

                    if os.path.exists(tgt_file):
                        self.logger.info(f"📝 Evaluating {src_file} vs {tgt_file}")
                        TranslationEvaluator().validate_pair_gemini(
                            src_file=src_file,
                            tgt_file=tgt_file,
                            out_csv=out_csv,
                            src_lang="Hindi",
                            tgt_lang=lang
                        )
                    else:
                        self.logger.warning(f"⚠️ Missing target SRT file for evaluation: {tgt_file}")

            for lang in self.settings.languages_to_convert:
                eval_dir = os.path.join(self.evaluation_base_path, lang)
                final_eval_csv = os.path.join(self.evaluation_base_path, f"{self.movie_name}__final_eval_{lang}.csv")
                TranslationEvaluator().merge_all_csvs(input_dir=eval_dir, output_file=final_eval_csv)

                try:
                    rmtree(eval_dir)
                    self.logger.info(f"🧹 Deleted evaluation temp folder: {eval_dir}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to delete folder {eval_dir}: {e}")
        

        for seg in story_segments:
            base_name = Path(seg).stem
            video_path = os.path.join(self.song_video_path, seg)
            audio_path = os.path.join(self.song_audio_path, f"{base_name}__audio.mp3")
            srt_path = os.path.join(self.song_srt_path, f"{base_name}__SRTfile.srt")

            # Use transcription as before
            if "transcription" in selected_steps:
                AudioTranscriptor().AudioTranscriptiontoFile(
                    model=self.model,
                    inputpath=audio_path,
                    languagestoconvert=self.settings.languages_to_convert,
                    outputfolder=self.song_srt_path,
                    outputpath=f"{base_name}__SRTfile.srt",
                    do_transcription=True,
                    do_translation=False 
                )

