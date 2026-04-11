from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk
import threading
import time

load_dotenv()

key = os.getenv("KEY")
region = os.getenv("REGION")

if not key or not region:
    raise ValueError("Brak key lub region w .env")

speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
speech_config.speech_recognition_language = "pl-PL"

# plik z nagraniem do transkrypcji - wygenerowany wcześniej przez tts_ssml.py
audio_input = "ssml1.wav"                           

audio_config = speechsdk.audio.AudioConfig(filename=audio_input)

recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

# flaga synchronizująca wątki - główny wątek czeka aż SDK skończy
done = threading.Event()                                

def on_recognized(evt):
    # Wywołany po każdej zakończonej wypowiedzi (po wykryciu ciszy).
    # evt.result.text zawiera finalny, stabilny tekst - nie zmienia się już po tym evencie.
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"Rozpoznano: {evt.result.text}")
    elif evt.result.reason == speechsdk.ResultReason.NoMatch:
        # Azure słyszał dźwięk ale nie potrafił dopasować go do słów -
        # może to być cisza, szum, muzyka lub mowa w innym języku niż pl-PL
        print("Nie rozpoznano mowy")

def on_recognizing(evt):
    # Wywołany wielokrotnie PODCZAS mówienia - efekt częściowy, tekst się zmienia.
    # przydatny do pokazywania "napisów na żywo"
    print(f"Rozpoznaję: {evt.result.text}")

def on_cancel(evt):
    # Wywołany przy błędzie LUB przy końcu pliku WAV (EndOfStream).
    # CancellationDetails zawiera szczegóły 
    details = speechsdk.CancellationDetails(evt.result)
    print(f"Anulowano: {details.reason}")
    # odblokuj główny wątek - koniec pracy
    done.set()                                          

def on_stopped(evt):
    # Wywołany gdy sesja zakończyła się normalnie -
    # np. po wywołaniu stop_continuous_recognition()
    print("Zatrzymano nasłuchiwanie")
    # krótkie opóźnienie - daje SDK czas na dokończenie ostatniego callbacku przed zamknięciem
    time.sleep(0.5)  
    # odblokuj główny wątek                                  
    done.set()                                         

# Podłączenie callbacków do eventów - Azure wywoła te funkcje automatycznie
recognizer.recognized.connect(on_recognized)
recognizer.recognizing.connect(on_recognizing)        
recognizer.canceled.connect(on_cancel)
recognizer.session_stopped.connect(on_stopped)

# Uruchamia transkrypcję w tle - wraca natychmiast, nie blokuje.
# SDK tworzy własny wątek i wywołuje callbacki z tego wątku.
recognizer.start_continuous_recognition()

# Blokuje główny wątek aż done.set() zostanie wywołane w którymś callbacku.
# Bez tego program zakończyłby się natychmiast po start_continuous_recognition()
done.wait()

recognizer.stop_continuous_recognition_async()