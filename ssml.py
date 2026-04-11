from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk

load_dotenv()

key = os.getenv("KEY")
region = os.getenv("REGION")

if not key or not region:
    raise ValueError("Brak key lub region w .env")

speech_config = speechsdk.SpeechConfig(subscription=key, region=region)

# plik wyjściowy
filename_output = "ssml.wav"                        

audio_config = speechsdk.audio.AudioOutputConfig(filename=filename_output)

synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

# Otwiera plik XML z definicją SSML w trybie tylko do odczytu ("r").
# encoding="utf-8" konieczne - SSML często zawiera polskie znaki i tagi Unicode.
# w repozytorium pozostałe pliki ssml
# ssml_large.xml - możliwości dla języka polskiego
# ssml_large_en.xml - możliwości dla języka angielskiego
# ssml_conv.xml - 'rozmowa' dwóch osób
with open("ssml.xml", "r", encoding="utf-8") as file:
     # wczytuje cały plik XML jako jeden string
    ssml = file.read()                                 

# speak_ssml_async() zamiast speak_text_async() - różnica:
#   speak_text_async()  = wysyła czysty tekst, Azure sam dobiera parametry głosu
#   speak_ssml_async()  = wysyła XML z pełną kontrolą nad głosem, tempem, pauzami, emocjami, wymową - wszystko zdefiniowane w pliku SSML
# .get() blokuje do momentu zakończenia syntezy
result = synthesizer.speak_ssml_async(ssml).get()      

if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("Mowa zapisana do pliku")
elif result.reason == speechsdk.ResultReason.Canceled:
    # Szczegóły błędu
    print(f"Błąd: {result.cancellation_details.error_details}")