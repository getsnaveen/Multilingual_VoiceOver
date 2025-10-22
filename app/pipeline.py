import os, time
from pathlib import Path
from shutil import rmtree
from natsort import natsorted

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
from evalutions.evalution import TranslationEvaluator
from models.diarization import ElevenLabsTranscriber
from utils.storageconnector import S3ProjectUploader
from utils.config import get_settings
local_settings = get_settings()

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
        self.base_lang = manager.base_language

        # Input folders
        self.input_paths = {
            "songs": {
                "video": self.input_root / self.base_lang /"songs"/ "song_files",
                "audio": self.input_root / self.base_lang /"songs" / "audio_files",
                "srt": self.input_root / self.base_lang /"songs" /  "srt_files",
            },
            "story": {
                "video": self.input_root /self.base_lang / "story" / "story_files",
                "audio": self.input_root /self.base_lang / "story" /  "audio_files",
                "srt": self.input_root /self.base_lang /  "story" / "srt_files",
            }
        }

        # Output folders per language
        self.output_paths = {
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
        self.logger.info("🎬 Starting multilingual Transcriber & Voiceover pipeline")
        selected_steps = set(selected_steps or [
            "audio_extract", "transcription", "subtitle_translation",
            "subtitle_embedding", "evaluation", "diarization", "upload_to_s3", "download_from_s3", "final_merge" ])

        # -------------------- SONGS PIPELINE --------------------
        song_video_dir = self.input_paths["songs"]["video"]
        song_audio_dir = self.input_paths["songs"]["audio"]
        song_srt_dir = self.input_paths["songs"]["srt"]

        song_segments = FileUtils.list_mp4_files(dirpath=song_video_dir)
        song_input_output_pairs = [
            (os.path.join(song_video_dir, seg), os.path.join(song_audio_dir, f"{Path(seg).stem}__audio.mp3"))
            for seg in song_segments
        ]
       
        if "audio_extract" in selected_steps:
            AudioExtractor().extract_audio_batch(input_output_pairs=song_input_output_pairs)

        for seg in song_segments:
            base_name = Path(seg).stem
            video_path = os.path.join(song_video_dir, seg)
            audio_path = os.path.join(song_audio_dir, f"{base_name}__audio.mp3")
          
            # --- Base language transcribing ---
            if "transcription" in selected_steps:
                AudioTranscriptor().AudioTranscriptiontoFile(
                    model=self.model,
                    inputpath=audio_path,
                    base_lnaguage = self.base_lang,
                    tgt_lang=self.base_lang,
                    outputfolder=song_srt_dir,  
                    outputpath=f"{base_name}__{self.base_lang}_SRTfile.srt",
                    do_transcription=True,
                    do_translation=False
                )

            for lang in self.settings.languages_to_convert:

                # --- Translated subtitle generation ---
                if "subtitle_translation" in selected_steps:                
                    AudioTranscriptor().AudioTranscriptiontoFile(
                        model=self.model,
                        inputpath=song_srt_dir,
                        base_lnaguage = self.base_lang,
                        tgt_lang=lang,
                        outputfolder=self.output_paths[lang]["songs"]["srt"],  
                        outputpath=f"{base_name}__{self.base_lang}_SRTfile.srt",
                        do_transcription=False,
                        do_translation=True
                    )

                # Subtitle embedding
                if "subtitle_embedding" in selected_steps:              
                    VideoProcessor().burn_subtitles(
                        lang=lang,
                        video_path=video_path,
                        subtitle_filename=f"{base_name}__SRTfile.srt",
                        subtitle_dir=self.output_paths[lang]["songs"]["srt"],
                        output_filename=f"{base_name}__subtitled.mp4",
                        output_dir=self.output_paths[lang]["songs"]["subtitle"]
                    )
                    time.sleep(1)
        
        # -------------------- STORY PIPELINE --------------------
        story_video_dir = self.input_paths["story"]["video"]
        story_audio_dir = self.input_paths["story"]["audio"]
        story_srt_dir = self.input_paths["story"]["srt"]

        story_segments = FileUtils.list_mp4_files(dirpath=story_video_dir)
        story_input_output_pairs = [
            (os.path.join(story_video_dir, seg), os.path.join(story_audio_dir, f"{Path(seg).stem}__audio.mp3"))
            for seg in story_segments
        ]

        if "audio_extract" in selected_steps:
            AudioExtractor().extract_audio_batch(input_output_pairs=story_input_output_pairs)

        for seg in story_segments:
            base_name = Path(seg).stem
            srt_path = os.path.join(story_srt_dir, f"{base_name}__hi_SRTfile.srt")
            audio_path = os.path.join(story_audio_dir, f"{base_name}__audio.mp3")
            
            # --- Base language transcribing ---
            if "diarization" in selected_steps:  
                transcriber = ElevenLabsTranscriber()
                transcriber.run_transcription(file_path=audio_path, output_file=srt_path)
                    
        if "upload_to_s3" in selected_steps:
            uploader = S3ProjectUploader(
                bucket_name=local_settings.s3_bucket_name,
                s3_prefix=self.movie_name,
                dry_run=False) # ✅ Set to True to simulate uploads safely
            uploader.upload_project(self.project_base)

        # -------------------- SONGS EVALUATION --------------------
        if "evaluation1" in selected_steps:
            self.logger.info("📊 Starting evaluation for SONGS")

            for lang in self.settings.languages_to_convert:
                if lang == self.base_lang:
                    continue

                eval_dir_base = self.output_paths[lang]["songs"]["evaluation"]
                base_srt_dir = self.input_paths["songs"]["srt"]
                tgt_srt_dir = self.output_paths[lang]["songs"]["srt"]

                for srt_file in natsorted(os.listdir(base_srt_dir)):
                    if not srt_file.endswith(".srt"):
                        continue

                    src_file = os.path.join(base_srt_dir, srt_file)
                    tgt_file = os.path.join(
                        tgt_srt_dir,
                        srt_file.replace(f"__{self.base_lang}_", f"__{lang}_")
                    )
                    out_csv = os.path.join(
                        eval_dir_base,
                        srt_file.replace(".srt", f"__{LANGUAGES[lang]}_eval.csv")
                    )

                    if os.path.exists(tgt_file):
                        self.logger.info(f"📝 Evaluating SONG subtitle: {src_file} vs {tgt_file}")
                        TranslationEvaluator().validate_pair_gemini(
                            src_file=src_file,
                            tgt_file=tgt_file,
                            out_csv=out_csv,
                            src_lang=self.base_lang,
                            tgt_lang=lang
                        )
                    else:
                        self.logger.warning(f"⚠️ Missing SONG target SRT for evaluation: {tgt_file}")

                final_eval_csv = os.path.join(
                    eval_dir_base,
                    f"{self.movie_name}__songs_final_eval_{lang}.csv"
                )
                TranslationEvaluator().merge_all_csvs(
                    input_dir=eval_dir_base, output_file=final_eval_csv
                )

                # try:
                #     rmtree(eval_dir_base)
                #     self.logger.info(f"🧹 Deleted SONG evaluation temp folder: {eval_dir_base}")
                # except Exception as e:
                #     self.logger.warning(f"⚠️ Failed to delete SONG evaluation folder {eval_dir_base}: {e}")

        # -------------------- STORY EVALUATION --------------------
        if "evaluation_story" in selected_steps:
            self.logger.info("📊 Starting evaluation for STORY")

            for lang in self.settings.languages_to_convert:
                if lang == self.base_lang:
                    continue

                eval_dir_base = self.output_paths[lang]["story"]["evaluation"]
                base_srt_dir = self.input_paths["story"]["srt"]
                tgt_srt_dir = self.output_paths[lang]["story"]["srt"]


                for srt_file in natsorted(os.listdir(base_srt_dir)):
                    if not srt_file.endswith(".srt"):
                        continue

                    src_file = os.path.join(base_srt_dir, srt_file)
                    tgt_file = os.path.join(
                        tgt_srt_dir,
                        srt_file.replace(f"__{self.base_lang}_", f"__{lang}_")
                    )
                    out_csv = os.path.join(
                        eval_dir_base,
                        srt_file.replace(".srt", f"__{LANGUAGES[lang]}_eval.csv")
                    )

                    if os.path.exists(tgt_file):
                        self.logger.info(f"📝 Evaluating STORY subtitle: {src_file} vs {tgt_file}")
                        TranslationEvaluator().validate_pair_gemini(
                            src_file=src_file,
                            tgt_file=tgt_file,
                            out_csv=out_csv,
                            src_lang=self.base_lang,
                            tgt_lang=lang
                        )
                    else:
                        self.logger.warning(f"⚠️ Missing STORY target SRT for evaluation: {tgt_file}")

                final_eval_csv = os.path.join(
                    eval_dir_base,
                    f"{self.movie_name}__story_final_eval_{lang}.csv"
                )
                TranslationEvaluator().merge_all_csvs(
                    input_dir=eval_dir_base, output_file=final_eval_csv
                )

                # try:
                #     rmtree(eval_dir_base)
                #     self.logger.info(f"🧹 Deleted STORY evaluation temp folder: {eval_dir_base}")
                # except Exception as e:
                #     self.logger.warning(f"⚠️ Failed to delete STORY evaluation folder {eval_dir_base}: {e}")

 