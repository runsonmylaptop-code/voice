from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk
import threading

load_dotenv()

key = os.getenv("KEY")
region = os.getenv("REGION")

if not key or not region:
    raise ValueError("Brak key lub region w .env")

speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
speech_config.speech_recognition_language = "pl-PL"

audio_input = "ssml_conv.wav"
audio_config = speechsdk.audio.AudioConfig(filename=audio_input)

output_filename = "transkrypcjaa.txt"

# Otwieramy plik 
# "w" = write, nadpisuje plik jeśli istnieje
file = open(output_filename, "w", encoding="utf-8")

# ConversationTranscriber zamiast SpeechRecognizer - kluczowa różnica:
# ConversationTranscriber rozróżnia mówców i zwraca speaker_id ("Guest-1", "Guest-2")
# SpeechRecognizer transkrybuje mowę ale nie wie kto mówi
transcriber = speechsdk.transcription.ConversationTranscriber(
    speech_config=speech_config,
    audio_config=audio_config
)
# flaga - main wątek czeka aż transkrypcja się skończy
done = threading.Event()                          

def on_transcribed(evt):
    # Odpala się po każdej zakończonej wypowiedzi jednego mówcy.
    # evt.result.speaker_id = automatycznie nadane ID: "Guest-1", "Guest-2" itd.
    # evt.result.text = finalny tekst wypowiedzi tego mówcy
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        # Odkomentuj jeśli chcesz śledzić transkrypcję na konsoli
        # print(f"[{evt.result.speaker_id}] : {evt.result.text}")

        # Zapisuje linię do pliku 
        file.write(f"[{evt.result.speaker_id}] : {evt.result.text}\n")

        # flush() natychmiast zapisuje bufor na dysk 
        file.flush()

def on_stopped(evt):
    # Normalne zakończenie - plik audio dobiegł końca lub wywołano stop_transcribing_async()
    print("Zakończono")
     # odblokuj główny wątek
    done.set()                                   

def on_cancel(evt):
    # Błąd lub EndOfStream (koniec pliku WAV) - tak samo jak w SpeechRecognizer
    print(f"Anulowano: {evt.cancellation_details.reason}")
       # odblokuj główny wątek również przy błędzie
    done.set()                                 

# finalny wynik z speaker_id
transcriber.transcribed.connect(on_transcribed)   
# normalne zakończenie sesji    
transcriber.session_stopped.connect(on_stopped)     
# błąd lub koniec pliku   
transcriber.canceled.connect(on_cancel)                

# start_transcribing_async() uruchamia diaryzację w tle 
transcriber.start_transcribing_async()

# Główny wątek czeka tutaj aż on_stopped lub on_cancel wywoła done.set()
done.wait()

# Zamkamy plik
file.close()

transcriber.stop_transcribing_async().get()