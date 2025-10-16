import os , time
from moviepy import VideoFileClip
from moviepy import  CompositeVideoClip
from models.transcribe import AudioTranscriptor
from preprocessing.audioextraction import AudioExtractor
from postprocessing.integrating_srtfile import burn_subtitles, merge_videos_ffmpeg_fast
# from faster_whisper import WhisperModel
from preprocessing import local_settings
from preprocessing.dataingestion import VideoLoader
from preprocessing.splitvideo import VideoSplitter
from utils import list_mp4_files, list_mp3_files,list_srt_files
from faster_whisper import WhisperModel, BatchedInferencePipeline
import streamlit as st
import warnings
warnings.filterwarnings("ignore")
# model = WhisperModel('turbo', compute_type="float16", device= "cuda")
model = ""

languages  = ['Kannada']



print(model)

if __name__ == "__main__":
    
    INPUT_PATH = "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/BablooBachelor/babloo_bachelor.mp4"
    SEGMENT_LENGTH = 600
    VIDEO_SPLIT_PATH = "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/BablooBachelor/splitdata/"
    AUDIO_FILE_PATH = "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/BablooBachelor/audiofiles/"
    SRT_FILE_PATH = "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/BablooBachelor/srtfiles/"
    SUB_TITLE_PATH = "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/BablooBachelor/subtitled/"
    

    VideoSplitter.Video_Splitter(filename = INPUT_PATH, 
                                 segment_length = SEGMENT_LENGTH,
                                 output_dir = VIDEO_SPLIT_PATH)
    entities = list_mp4_files(VIDEO_SPLIT_PATH)
    for entity in entities:
        file_name_without_extension, _ = os.path.splitext(entity)   

        print('AUDIO_FILE_PATH+file_name_without_extension"   :::' , AUDIO_FILE_PATH+file_name_without_extension+"_audio.mp3")

        print('SRT_FILE_PATH+file_name_without_extension+"__SRTfile.srt"', SRT_FILE_PATH+file_name_without_extension+"__SRTfile.srt")
        print ('SUB_TITLE_PATH+file_name_without_extension+ "_subtitled.mp4"',SUB_TITLE_PATH+file_name_without_extension+ "_subtitled.mp4")

        AudioExtractor.AudioExtraction(inputpath = VIDEO_SPLIT_PATH+entity, 
                                        outputpath = AUDIO_FILE_PATH+file_name_without_extension+"_audio.mp3") 
        time.sleep(3)
        AudioTranscriptor.AudioTranscriptiontoFile(model= model, 
                                                inputpath=AUDIO_FILE_PATH+file_name_without_extension+"_audio.mp3", 
                                                languagestoconvert= languages,
                                                outputfolder = SRT_FILE_PATH,
                                                outputpath = file_name_without_extension+"__SRTfile.srt")
        time.sleep(3)
        burn_subtitles(languages, video_path = VIDEO_SPLIT_PATH+entity,
                       subtitle_path = file_name_without_extension+"__SRTfile.srt",
                       subtitle_path_folder = SRT_FILE_PATH,
                       output_path = file_name_without_extension+"_subtitled.mp4",
                       output_path_folder = SUB_TITLE_PATH)
        time.sleep(2)  # Pause execution for 2 seconds
   
    time.sleep(10)  # Pause execution for 2 seconds
   
    entities = list_mp4_files("/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/BablooBachelor/subtitled/Kannada/")
    print(sorted(entities))
    merge_videos_ffmpeg_fast(sorted(entities), "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/BablooBachelor/subtitled/Kannada/",
                 "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/BablooBachelor/babloo_bachelor_Final_Kannada.mp4")
    
    time.sleep(10)
    entities = list_mp4_files("/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/Ahista/subtitled/Marathi/")
    print(sorted(entities))
    merge_videos_ffmpeg_fast(sorted(entities), "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/Ahista/subtitled/Marathi/",
                  "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/Ahista/ahista_ahista_Final_Marathi.mp4")
    time.sleep(10)
    entities = list_mp4_files("/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/Ahista/subtitled/Spanish/")
    print(sorted(entities))
    merge_videos_ffmpeg_fast(sorted(entities), "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/Ahista/subtitled/Spanish/",
                  "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/Ahista/ahista_ahista_Final_Spanish.mp4")
    time.sleep(10)