# biblioteka do ładowania zmiennych z pliku .env
from dotenv import load_dotenv              

# dostęp do zmiennych środowiskowych systemu
import os                                              

# SDK Azure do syntezy i rozpoznawania mowy
import azure.cognitiveservices.speech as speechsdk      

 # wczytuje plik .env z katalogu projektu - bez tego os.getenv zwróci None
load_dotenv()                                          

# pobiera klucz API Azure z pliku .env
key    = os.getenv("KEY")         

# pobiera region Azure
region = os.getenv("REGION")                            

# sprawdza czy oba klucze zostały poprawnie wczytane
if not key or not region:                               
# rzuca wyjątek jeśli któregoś brakuje    
    raise ValueError("Brak key lub region w .env")     

# tworzy główną konfigurację połączenia z usługą Azure Speech
speech_config = speechsdk.SpeechConfig(subscription=key, region=region)    
# ustawia głos
speech_config.speech_synthesis_voice_name = "pl-PL-ZofiaNeural"            

# Zmienia format wyjściowy z domyślnego WAV na MP3 16kHz 128kbps.
# speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3)

# nazwa pliku do którego zostanie zapisana wygenerowana mowa
filename_output = "tts.wav"                           

# AudioOutputConfig z filename= zapisuje audio do pliku zamiast odtwarzać przez głośniki.
# AudioOutputConfig(use_default_speaker=True) - odtwarza przez głośnik
audio_config = speechsdk.audio.AudioOutputConfig(filename=filename_output)

# SpeechSynthesizer łączy konfigurację połączenia (klucz, region, głos)
# z konfiguracją wyjścia (gdzie ma trafić audio - plik lub głośnik)
synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

 # tekst który zostanie zamieniony na mowę
text_to_speech = "Dzień dobry. Dzisiaj jest sobota"    

# speak_text_async() wysyła tekst do Azure i rozpoczyna syntezę asynchronicznie (nie blokuje).
# .get() czeka na zakończenie i zwraca wynik - bez .get() program mógłby zakończyć się przed zapisem pliku.
result = synthesizer.speak_text_async(text_to_speech).get()

# synteza zakończyła się sukcesem i plik został zapisany
if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:     
    print("Mowa zapisana do pliku")
 # coś się wywaliło - zły klucz, zły region itp.    
elif result.reason == speechsdk.ResultReason.Canceled:
# wypisuje szczegółowy komunikat błędu zwrócony przez Azure                          
    print(f"Błąd: {result.cancellation_details.error_details}")           