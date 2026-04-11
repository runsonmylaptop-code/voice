from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk

load_dotenv()

key = os.getenv("KEY")
region = os.getenv("REGION")

if not key or not region:
    raise ValueError("Brak key lub region w .env")

speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
speech_config.speech_synthesis_voice_name = "pl-PL-ZofiaNeural"

# use_default_speaker=True - audio trafia bezpośrednio do głośnika zamiast do pliku
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

# Synthesizer tworzony RAZ przed pętlą - to ważne, bo tworzenie go w każdej iteracji
# oznaczałoby nowe połączenie z Azure przy każdym wpisie (wolniej i drożej)
synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

# nieskończona pętla - działa aż użytkownik wpisze "koniec"
while True:                                          
# czeka na wpisanie tekstu przez użytkownika i blokuje wątek                           
    text = input("Wpisz tekst lub 'koniec': ")                
# .lower() zamieniamy tekst na male znaki żeby "Koniec", "KONIEC" też dział                
    if text.lower() == 'koniec': 
    # wychodzi z pętli while i kończy program
        break                                                               
    # speak_text_async() wysyła tekst do Azure asynchronicznie.
    # .get() blokuje pętlę aż Azure skończy mówić - dzięki temukolejny input() pojawia się dopiero po zakończeniu odtwarzania
    result = synthesizer.speak_text_async(text).get()