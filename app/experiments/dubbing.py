import os
import shutil
import subprocess
from elevenlabs.client import ElevenLabs
from elevenlabs import Voice, VoiceSettings
from google.cloud import speech, translate_v2 as translate, texttospeech
from pydub import AudioSegment
from moviepy import VideoFileClip, AudioFileClip
from spleeter.separator import Separator

# --- Configuration ---
# Google Cloud
SOURCE_LANGUAGE_CODE = "en-US"
TARGET_LANGUAGE_CODE = "es-ES"
TARGET_LANGUAGE_TRANSLATE = "es"

# ElevenLabs (Replace with your API Key)
ELEVENLABS_API_KEY = ""
if ELEVENLABS_API_KEY == "YOUR_ELEVENLABS_API_KEY":
    raise ValueError("Please replace 'YOUR_ELEVENLABS_API_KEY' with your actual ElevenLabs API key.")
client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# File Paths
SPLEETER_MODEL = 'spleeter:2stems'
WAV2LIP_PATH = "Wav2Lip" # Path to the cloned Wav2Lip directory

# --- Main Professional Dubbing Function ---

def dub_movie_professional(video_path, output_path):
    print("--- Starting Professional-Grade Movie Dubbing ---")
    
    temp_dir = "temp_professional_dubbing"
    if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try:
        # 1. Extract and Separate Audio
        print("\n[Step 1/5] Extracting and Separating Audio...")
        original_audio_path = os.path.join(temp_dir, "original_audio.wav")
        video_clip = VideoFileClip(video_path)
        video_clip.audio.write_audiofile(original_audio_path, codec='pcm_s16le')
        vocals_path, background_path = separate_audio_components(original_audio_path, temp_dir)
        print("  > Audio separation complete.")

        # 2. Transcribe and Diarize (using our previous function)
        print("\n[Step 2/5] Transcribing and Identifying Speakers...")
        # Note: We're reusing the Google-based diarization function. It's good enough for this.
        # from advanced_dubber import transcribe_with_diarization # Assuming you have the previous script
        diarized_segments = transcribe_with_diarization(vocals_path, SOURCE_LANGUAGE_CODE)
        if not diarized_segments:
            print("  > No speech detected. Aborting.")
            return
        print(f"  > Transcription complete. Found {len(diarized_segments)} speech segments.")

        # 3. Clone Voices, Translate, and Synthesize with Emotion
        print("\n[Step 3/5] Cloning Voices, Translating, and Synthesizing...")
        original_vocal_audio = AudioSegment.from_wav(vocals_path)
        dubbed_vocal_track = AudioSegment.silent(duration=len(original_vocal_audio))
        cloned_voices = {}

        for i, segment in enumerate(diarized_segments):
            speaker_tag = segment['speaker']
            print(f"\n--- Processing Segment {i+1}/{len(diarized_segments)} (Speaker {speaker_tag}) ---")

            # A. Clone voice if we haven't seen this speaker before
            if speaker_tag not in cloned_voices:
                print(f"  > New speaker detected (Tag {speaker_tag}). Cloning voice...")
                start_ms = int(segment['start'] * 1000)
                end_ms = int(segment['end'] * 1000)
                # Take a sample of the speaker's voice for cloning
                voice_sample_audio = original_vocal_audio[start_ms:end_ms]
                sample_path = os.path.join(temp_dir, f"speaker_{speaker_tag}_sample.wav")
                voice_sample_audio.export(sample_path, format="wav")
                
                cloned_voices[speaker_tag] = client.voices.add(
                    name=f"ClonedSpeaker_{speaker_tag}",
                    description=f"Auto-cloned voice for speaker {speaker_tag}",
                    files=[sample_path],
                )
                print(f"  > Voice cloned successfully. Voice ID: {cloned_voices[speaker_tag].voice_id}")

            # B. Translate text
            translated_text = translate_text(segment['text'], TARGET_LANGUAGE_TRANSLATE, SOURCE_LANGUAGE_CODE.split('-')[0])
            print(f"  > Translated: {translated_text}")

            # C. Synthesize with the cloned voice
            voice_to_use = cloned_voices[speaker_tag]
            audio_response = client.generate(
                text=translated_text,
                voice=Voice(
                    voice_id=voice_to_use.voice_id,
                    settings=VoiceSettings(stability=0.5, similarity_boost=0.75, style=0.1, use_speaker_boost=True)
                ),
                model="eleven_multilingual_v2"
            )
            
            dubbed_segment_path = os.path.join(temp_dir, f"dubbed_segment_{i}.mp3")
            with open(dubbed_segment_path, "wb") as f:
                f.write(audio_response)

            # D. Adjust timing and overlay
            dubbed_segment_audio = AudioSegment.from_mp3(dubbed_segment_path)
            original_duration = (segment['end'] - segment['start']) * 1000
            adjusted_audio = adjust_audio_speed(dubbed_segment_audio, original_duration)
            dubbed_vocal_track = dubbed_vocal_track.overlay(adjusted_audio, position=segment['start'] * 1000)
        
        # 4. Create Final Pre-Lip-Sync Video
        print("\n[Step 4/5] Merging final audio to create pre-sync video...")
        dubbed_vocals_path = os.path.join(temp_dir, "final_dubbed_vocals.wav")
        dubbed_vocal_track.export(dubbed_vocals_path, format="wav")

        background_audio = AudioSegment.from_wav(background_path)
        final_audio = background_audio.overlay(dubbed_vocal_track)
        
        final_audio_path = os.path.join(temp_dir, "final_dubbed_audio.wav") # Use WAV for Wav2Lip
        final_audio.export(final_audio_path, format="wav")

        pre_sync_video_path = os.path.join(temp_dir, "video_presync.mp4")
        final_audio_clip = AudioFileClip(final_audio_path)
        video_clip.set_audio(final_audio_clip).write_videofile(pre_sync_video_path, codec="libx264", audio_codec="aac")
        print(f"  > Pre-sync video created at: {pre_sync_video_path}")

        # 5. Execute Wav2Lip for Final Lip-Sync
        print("\n[Step 5/5] Executing Wav2Lip for final lip-sync (this will take a long time)...")
        run_wav2lip(pre_sync_video_path, final_audio_path, output_path)
        
        print(f"\n--- SUCCESS! Professionally dubbed and lip-synced movie saved to {output_path} ---")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up cloned voices from ElevenLabs account to avoid clutter
        if 'cloned_voices' in locals():
            for speaker_tag, voice in cloned_voices.items():
                print(f"Cleaning up cloned voice for speaker {speaker_tag}...")
                client.voices.delete(voice.voice_id)
        # shutil.rmtree(temp_dir) # Uncomment for auto-cleanup


# --- Helper Functions (Re-used and New) ---
def transcribe_with_diarization(audio_path, language_code):
    """Transcribes audio and identifies speakers."""
    client = speech.SpeechClient()
    with open(audio_path, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    # Get audio properties for accurate config
    audio_segment = AudioSegment.from_wav(audio_path)
    
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=audio_segment.frame_rate,
        language_code=language_code,
        enable_speaker_diarization=True,
        diarization_speaker_count=len(SPEAKER_VOICES) -1 # Let Google know how many speakers to look for
    )

    print("  > Sending audio to Google for transcription (this may take a while)...")
    operation = client.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=900) # Timeout in seconds

    # Process diarization results
    result = response.results[-1] # The last result has the full transcript
    words_info = result.alternatives[0].words
    
    segments = []
    current_segment = None

    for word_info in words_info:
        speaker_tag = word_info.speaker_tag
        if current_segment is None or current_segment['speaker'] != speaker_tag:
            # End previous segment
            if current_segment:
                current_segment['end'] = word_info.start_time.total_seconds()
                segments.append(current_segment)
            # Start new segment
            current_segment = {
                'speaker': speaker_tag,
                'start': word_info.start_time.total_seconds(),
                'text': word_info.word
            }
        else:
            current_segment['text'] += " " + word_info.word
    
    # Add the last segment
    if current_segment:
        current_segment['end'] = words_info[-1].end_time.total_seconds()
        segments.append(current_segment)
        
    return segments

def separate_audio_components(audio_path, output_dir):
    separator = Separator(SPLEETER_MODEL)
    separator.separate_to_file(audio_path, output_dir, codec='wav')
    input_filename = os.path.splitext(os.path.basename(audio_path))[0]
    spleeter_output_dir = os.path.join(output_dir, input_filename)
    return os.path.join(spleeter_output_dir, "vocals.wav"), os.path.join(spleeter_output_dir, "accompaniment.wav")

def translate_text(text, target, source):
    client = translate.Client()
    return client.translate(text, target_language=target, source_language=source)["translatedText"]

def adjust_audio_speed(audio_segment, target_duration_ms):
    ratio = len(audio_segment) / target_duration_ms
    return audio_segment.speedup(playback_speed=ratio) if ratio > 0 else audio_segment

def run_wav2lip(video_path, audio_path, output_path):
    """Executes the Wav2Lip inference script using a subprocess."""
    checkpoint = os.path.join(WAV2LIP_PATH, 'checkpoints', 'wav2lip_gan.pth')
    
    # Ensure paths are absolute for the subprocess
    video_path_abs = os.path.abspath(video_path)
    audio_path_abs = os.path.abspath(audio_path)
    output_path_abs = os.path.abspath(output_path)
    
    # Command to run. Adjust padding if faces are cut off.
    command = [
        'python', 'inference.py',
        '--checkpoint_path', checkpoint,
        '--face', video_path_abs,
        '--audio', audio_path_abs,
        '--outfile', output_path_abs,
        # '--pads', '0', '20', '0', '0' # Example padding: top, bottom, left, right
    ]
    
    print(f"  > Running command: {' '.join(command)}")
    # We run this from within the Wav2Lip directory
    subprocess.run(command, cwd=WAV2LIP_PATH, check=True)

# --- Execution Block ---

if __name__ == "__main__":
    # Import the diarization function from our previous script
    # This assumes 'advanced_dubber.py' is in the same directory.
    # try:
    #     from advanced_dubber import transcribe_with_diarization
    # except ImportError:
    #     print("\nERROR: Could not import 'transcribe_with_diarization'.")
    #     print("Please ensure the 'advanced_dubber.py' script from the previous step is in the same directory.\n")
    #     exit()

    input_video = "input.mp4"
    output_video = "dubbed_professional_output.mp4"

    if not os.path.exists(input_video):
        print(f"Error: Input video '{input_video}' not found.")
    elif not os.path.exists(WAV2LIP_PATH):
        print(f"Error: Wav2Lip directory not found at '{WAV2LIP_PATH}'.")
    else:
        dub_movie_professional(input_video, output_video)