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
from utils.language_const import LANGUAGES
from natsort import natsorted
from shutil import rmtree
from evalutions.evalution_new import TranslationEvaluator

class TranscriberApp:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.logger = SingletonLogger.getInstance("TranscriberApp").logger
        self.model = WhisperModel('turbo', compute_type="int8", device="cpu")

        self.movie_name = Path(self.settings.input_movie_path).stem
        self.project_base = f"shared_data/movieslist/{self.movie_name}"

        self.video_split_path = os.path.join(self.project_base, "split_files")
        self.audio_file_path = os.path.join(self.project_base, "audio_files")
        self.srt_base_path = os.path.join(self.project_base, "srt_files")
        self.subtitle_base_path = os.path.join(self.project_base, "subtitle_files")
        self.evaluation_base_path = os.path.join(self.project_base, "evaluation")

    @log_exceptions()
    def create_folder_structure(self):
        base_dirs = [
            self.video_split_path,
            self.audio_file_path,
            self.srt_base_path
        ]

        lang_dirs = []
        for lang in self.settings.languages_to_convert:
            lang_dirs.extend([
                os.path.join(self.project_base, "srt_files", lang),
                os.path.join(self.subtitle_base_path, lang),
                os.path.join(self.evaluation_base_path, lang)
            ])

        FileUtils.ensure_directories(base_dirs + lang_dirs)

    @log_exceptions("Video processing pipeline failed")
    def run(self, selected_steps: list[str] = None):
        self.logger.info("🎬 Starting multilingual transcription pipeline")
        selected_steps = set(selected_steps or [
            "video_split", "audio_extract", "transcription",
            "subtitle_translation", "subtitle_embedding", "final_merge", "evaluation"
        ])

        self.create_folder_structure()

        if "video_split" in selected_steps:
            self.logger.info(f"🎞️ Splitting video: {self.settings.input_movie_path}")
            FFmpegVideoSplitter().split_video_fast(
                filepath=self.settings.input_movie_path,
                segment_length=int(self.settings.segment_length),
                output_dir=self.video_split_path
            )

        segments = FileUtils.list_mp4_files(dirpath=self.video_split_path)
        input_output_paths = [
            (
                os.path.join(self.video_split_path, segment),
                os.path.join(self.audio_file_path, f"{os.path.splitext(segment)[0]}__audio.mp3")
            ) for segment in segments
        ]

        if "audio_extract" in selected_steps:
            AudioExtractor().extract_audio_batch(input_output_pairs=input_output_paths)

        for segment in segments:
            base_name, _ = os.path.splitext(segment)
            video_path = os.path.join(self.video_split_path, segment)
            audio_path = os.path.join(self.audio_file_path, f"{base_name}__audio.mp3")
            srt_path = os.path.join(self.srt_base_path, f"{base_name}__SRTfile.srt")

            if "transcription" in selected_steps:
                AudioTranscriptor().AudioTranscriptiontoFile(
                    model=self.model,
                    inputpath=audio_path,
                    languagestoconvert=self.settings.languages_to_convert,
                    outputfolder=self.srt_base_path,
                    outputpath=f"{base_name}__SRTfile.srt",
                    do_transcription=True,
                    do_translation=False 
                )

            if "subtitle_translation" in selected_steps:
                AudioTranscriptor().AudioTranscriptiontoFile(
                    model=self.model,
                    inputpath=audio_path,
                    languagestoconvert=self.settings.languages_to_convert,
                    outputfolder=self.srt_base_path,
                    outputpath=f"{base_name}__SRTfile.srt",
                    do_transcription=False,
                    do_translation=True 
                )

            if "subtitle_embedding" in selected_steps:
                VideoProcessor().burn_subtitles(
                    languages=self.settings.languages_to_convert,
                    video_path=video_path,
                    subtitle_filename=f"{base_name}__SRTfile.srt",
                    subtitle_dir=self.srt_base_path,
                    output_filename=f"{base_name}__subtitled.mp4",
                    output_dir=self.subtitle_base_path
                )
                time.sleep(2)

        if "final_merge" in selected_steps:
            for lang in self.settings.languages_to_convert:
                lang_path = os.path.join(self.subtitle_base_path, lang)
                merged_output = os.path.join(self.project_base, f"{self.movie_name}_Final_{lang}.mp4")
                videos = sorted(FileUtils.list_mp4_files(lang_path))
                VideoProcessor().merge_videos_ffmpeg_fast(videos, lang_path, merged_output)
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
