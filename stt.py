from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk

load_dotenv()

key = os.getenv("KEY")
region = os.getenv("REGION")

if not key or not region:
    raise ValueError("Brak key lub region w .env")

speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
# język rozpoznawania - musi zgadzać się z językiem w nagraniu w przeciwnym razie wyjdą głupoty
speech_config.speech_recognition_language = "pl-PL" 

# plik WAV do transkrypcji 
audio_input = "zofia.wav"                               

audio_config = speechsdk.AudioConfig(filename=audio_input)

recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

# recognize_once() - synchroniczna (blokująca) wersja rozpoznawania.
# Słucha do pierwszej ciszy (~1-2s) i zwraca jeden wynik.
# Dobre dla: krótkich komend, pojedynczych zdań, plików < 15s.
# Złe dla: długich nagrań z pauzami - przetnie wypowiedź w połowie.
result = recognizer.recognize_once()

if result.reason == speechsdk.ResultReason.RecognizedSpeech:
    print("Rozpoznany tekst: ")
    # finalny rozpoznany tekst jako string
    print(result.text)                 

    # result.duration zwraca czas trwania wypowiedzi w jednostkach 100-nanosekundowych.
    # Żeby dostać sekundy: result.duration / 10_000_000
    print(result.duration / 10_000_000)

    # result.offset - moment w pliku audio w którym ZACZĘŁA SIĘ wypowiedź.
    # Zwracany w jednostkach 100-nanosekundowych 
    print(result.offset/ 10_000_000)
else:
    print(f"Błąd: {result.reason}")