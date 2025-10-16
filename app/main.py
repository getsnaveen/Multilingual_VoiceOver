import os, pysrt 
from moviepy import VideoFileClip
from moviepy import  CompositeVideoClip
from models.transcribe import AudioTranscriptor
from preprocessing.audioextraction import AudioExtractor
from postprocessing.integrating_srtfile import create_subtitle_clips
# from faster_whisper import WhisperModel
from preprocessing import local_settings
from preprocessing.dataingestion import VideoLoader
from preprocessing.splitvideo import VideoSplitter
import streamlit as st
import warnings
warnings.filterwarnings("ignore")

# st.title(" Multilingual transcriber ")
# with st.form("my_form"):
#     uploaded_file = st.text_input(label = "video path for movie title creation" , value = "")  
#     # uploaded_file = r"F:\Data Science Pro\Multilingual-Transcriber\Input\9.mp4"
#     # print("#######", uploaded_file)
#     submitted = st.form_submit_button("Submit")    
#     base_name = os.path.basename(uploaded_file)
#     file_name_without_extension, _ = os.path.splitext(base_name)
#     # print("#######",file_name_without_extension)
        
#     if submitted:        
#         output_filename = file_name_without_extension+ "_audiofile"
#         # output_filename = "output\\audiofiles\\"+output_filename     
#         output_filename = "output/audiofiles/"+output_filename   
#         st.info("Audio extraction is in progress")
#         output_filename = output_filename+".mp3"
#         AudioExtractor.AudioExtraction(inputpath = uploaded_file, outputpath = output_filename)     
#         st.info("Transcribe is inprogress ")
#         srtfilename = file_name_without_extension+"_SRTfile"  
#         # srtfilename = "output\\srtfiles\\"+srtfilename+".srt"   
#         srtfilename = "output/srtfiles/"+srtfilename+".srt"                     
#         AudioTranscriptor.AudioTranscriptiontoFile(inputpath=output_filename, languatetoconvert= "en",outputpath = srtfilename)
#         st.info("SRT file integration is in progress ")
#         video = VideoFileClip(uploaded_file)
#         subtitles = pysrt.open(srtfilename)
#         output_final = file_name_without_extension+ "_subtitled.mp4"
#         # output_final = "output\\final\\"+output_final 
#         output_final = "output/final/"+output_final 
        
#         print ("Output file name: ",output_final)

#         # Create subtitle clips
#         subtitle_clips = create_subtitle_clips(subtitles,video.size)

#         # Add subtitles to the video
#         final_video = CompositeVideoClip([video] + subtitle_clips)

#         # Write output video file
#         final_video.write_videofile(output_final)

#         st.info("Completed subtitle creation ")
if __name__ == "__main__":
    minio_bucket_name  = local_settings.BUCKET_NAME
    minio_file_to_download = local_settings.FILE_NAME
    input_path = os.path.abspath(local_settings.INPUT_PATH+local_settings.FILE_NAME)
   

    SEGMENT_LENGTH = 60
    
    VideoLoader.minio_Downloader(bucketname=minio_bucket_name,
                                 filename=minio_file_to_download)
    
    print("#########################################",input_path)
    VideoSplitter.Video_Splitter(filename = input_path, 
                                 segment_length = SEGMENT_LENGTH,
                                 output_dir = "splitdata")
    
    

    uploaded_file = print(label = "video path for movie title creation" , value = "") 
    uploaded_file = r"F:\Data Science Pro\Multilingual-Transcriber\Input\9.mp4"
    print("#######", uploaded_file)
    
    base_name = os.path.basename(uploaded_file)
    file_name_without_extension, _ = os.path.splitext(base_name)
    print("#######",file_name_without_extension)    
        
    output_filename = file_name_without_extension+ "_audiofile"
    output_filename = "output\\audiofiles\\"+output_filename        
    
    print("Audio extraction is in progress")
    output_filename = output_filename+".mp3"
    AudioExtractor.AudioExtraction(inputpath = uploaded_file, outputpath = output_filename)     
    print("Transcribe is inprogress ")
    srtfilename = file_name_without_extension+"_SRTfile"  
    srtfilename = "output\\srtfiles\\"+srtfilename+".srt"                        
    AudioTranscriptor.AudioTranscriptiontoFile(inputpath=output_filename, languatetoconvert= "en",outputpath = srtfilename)
    print("SRT file Generated ")
    video = VideoFileClip(uploaded_file)
    subtitles = pysrt.open(srtfilename)
    output_final = file_name_without_extension+ "_subtitled.mp4"
    output_final = "output\\final\\"+output_final 
    
    print ("Output file name: ",output_final)

    # Create subtitle clips
    subtitle_clips = create_subtitle_clips(subtitles,video.size)

    # Add subtitles to the video
    final_video = CompositeVideoClip([video] + subtitle_clips)

    # Write output video file
    final_video.write_videofile(output_final)

        