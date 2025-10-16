
#import library
import speech_recognition as sr

# Initialize recognizer class (for recognizing the speech)
r = sr.Recognizer()



# Reading Audio file as source
# listening the audio file and store in audio_text variable
def startConvertion(path = "/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/Ahista/audiofiles/ahista_ahista_part4_audio.mp3" ,lang = 'kn-IN'):
    with sr.AudioFile(path) as source:
        print('Fetching File')
        audio_text = r.listen(source)

        print
        # recoginize_() method will throw a request error if the API is unreachable, hence using exception handling
        try:
        
            # using google speech recognition
            print('Converting audio transcripts into text ...')
            text = r.recognize_google(audio_text, language = lang)
            print(text)
    
        except:
            print('Sorry.. run again...')
if __name__ == '__main__':
    # we can add selection langauges in a list and we can show 'n number of language options to the user by using loop
    
    startConvertion() # for time being I am using static file name here, we can take file input from user.
