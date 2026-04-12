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

audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

# flaga między wątkami - main wątek czeka, callback go odblokuje
done = threading.Event()                                

def on_recognized(evt):
    # Finalny wynik po zakończeniu wypowiedzi (po ciszy ~1-2s)
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"Rozpoznano: {evt.result.text}")

        # .strip() usuwa białe znaki z początku i końca stringa,
        # .lower() zamienia na małe litery - dzięki temu "Koniec", "KONIEC" też zadziałają
        if "koniec" in evt.result.text.strip().lower():
            print("Usłyszałem 'koniec' - kończę program.")
            # zatrzymuje nasłuchiwanie 
            # wywoła on_stopped, który ustawi done.set()
            recognizer.stop_continuous_recognition_async()
            done.set()                                  
    elif evt.result.reason == speechsdk.ResultReason.NoMatch:
        print("Nie rozpoznano mowy")

def on_recognizing(evt):
    # Wynik częściowy - odpala się wielokrotnie PODCZAS mówienia, tekst się zmienia.
    print(f"Rozpoznaję: {evt.result.text}")

def on_cancel(evt):
    # Błąd połączenia, zły klucz lub koniec pliku WAV
    details = speechsdk.CancellationDetails(evt.result)
    print(f"Anulowano: {details.reason}")
    done.set()

def on_stopped(evt):
    # Normalne zakończenie - wywołane po stop_continuous_recognition()
    print("Zatrzymano nasłuchiwanie")
    done.set()

 # finalny wynik po wypowiedzi
recognizer.recognized.connect(on_recognized)    
 # wynik częściowy podczas mówienia      
recognizer.recognizing.connect(on_recognizing)   
# błąd lub koniec pliku     
recognizer.canceled.connect(on_cancel)         
 # normalne zatrzymanie        
recognizer.session_stopped.connect(on_stopped)        

# Startuje nasłuchiwanie w tle 
recognizer.start_continuous_recognition()

# Blokuje główny wątek aż któryś callback wywoła done.set()
done.wait()

recognizer.stop_continuous_recognition()
