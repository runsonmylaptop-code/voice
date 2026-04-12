# Zadanie
# W katalogu voices/ znajdują się pliki audio w różnych językach. Napisz program, który automatycznie przetworzy każdy z nich i wygeneruje dwa pliki wyjściowe.
# 1. Plik tekstowy pl_nazwa_pliku.txt zawierający:
# - oryginalną transkrypcję wypowiedzi (w języku źródłowym)
# - polskie tłumaczenie tej wypowiedzi
# 2. Plik audio pl_nazwa_pliku.wav zawierający:
# - polskie tłumaczenie odczytane syntetycznym głosem po polsku


from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk
import threading

# wczytuje zmienne środowiskowe z pliku .env
load_dotenv()

# pobiera klucz API i region z zmiennych środowiskowych
key = os.getenv("KEY")
region = os.getenv("REGION")

# folder z plikami audio do przetworzenia
INPUT_FOLDER = "voices"

# przerywa program jeśli brakuje wymaganych danych konfiguracyjnych
if not key or not region:
    raise ValueError("Brak key lub region w .env")

# konfiguracja syntezy mowy - używa polskiego głosu Marek
speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
speech_config.speech_synthesis_voice_name = "pl-PL-MarekNeural"

# konfiguracja tłumaczenia mowy - docelowy język to polski
translation_config = speechsdk.translation.SpeechTranslationConfig(subscription=key, region=region)
translation_config.add_target_language("pl")

# automatyczne wykrywanie języka spośród czterech obsługiwanych
auto_detect_source = speechsdk.AutoDetectSourceLanguageConfig(languages=["en-GB", "fr-FR", "es-ES", "tr-TR"])


# zbiera wszystkie pliki .wav z folderu wejściowego
wav_files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith(".wav")]

# informuje jeśli folder jest pusty
if not wav_files:
    print(f"Nie ma plików")

def translate(wav_filename):

    # buduje pełną ścieżkę do pliku wejściowego
    wav_path = os.path.join(INPUT_FOLDER, wav_filename)

    # konfiguruje wejście audio z pliku
    audio_config = speechsdk.audio.AudioConfig(filename=wav_path)

  
    # tworzy obiekt rozpoznający mowę z tłumaczeniem i auto-detekcją języka
    recognizer = speechsdk.translation.TranslationRecognizer(translation_config=translation_config, audio_config=audio_config, auto_detect_source_language_config=auto_detect_source)

    # Event z modułu threading - blokuje główny wątek do czasu zakończenia sesji
    done = threading.Event()

    # listy zbierające kolejne fragmenty tłumaczenia i oryginału
    full_trans = []
    full_org = []

    def on_recognized(evt):
        # sprawdza czy fragment został poprawnie przetłumaczony
        if evt.result.reason == speechsdk.ResultReason.TranslatedSpeech:
            # pobiera polskie tłumaczenie i oryginalny tekst fragmentu
            trans = evt.result.translations.get("pl", "")
            org = evt.result.text

            full_trans.append(trans)
            full_org.append(org)

    def on_canceled(evt):
        # pobiera szczegóły anulowania
        deatils = speechsdk.CancellationDetails(evt.result)
        # wyświetla błąd jeśli przyczyną było coś innego niż koniec pliku
        if deatils.reason == speechsdk.CancellationReason.Error:
            print(f"Anulowano: {speechsdk.CancellationDetails(evt.result).error_details}")
        # odblokowuje główny wątek - program może się zakończyć
        done.set()

    def on_stopped(evt):
        # wywoływane gdy sesja rozpoznawania dobiegnie naturalnego końca 
        # odblokowuje główny wątek
        done.set()

    # podpina on_recognized pod zdarzenie finalnych wyników - odpala się po zakończeniu zdania
    recognizer.recognized.connect(on_recognized)
    # podpina on_canceled - odpala się przy błędzie lub końcu sesji
    recognizer.canceled.connect(on_canceled)
    # podpina on_stopped - odpala się gdy sesja zostanie zakończona
    recognizer.session_stopped.connect(on_stopped)

    # uruchamia ciągłe rozpoznawanie mowy w wątku w tle - nie blokuje głównego wątku
    recognizer.start_continuous_recognition()
    # blokuje wątek główny do czasu zakończenia przetwarzania
    done.wait()
    # zatrzymuje rozpoznawanie po zakończeniu pliku
    recognizer.stop_continuous_recognition_async()

    # łączy wszystkie fragmenty w jeden ciągły tekst
    trans_text = "\n".join(full_trans)
    org_text = "\n".join(full_org)

    # wyciąga nazwę pliku bez rozszerzenia
    file_name = os.path.splitext(wav_filename)[0]

    # buduje nazwy plików wyjściowych z prefiksem "pl_"
    txt_output = f"pl_{file_name}.txt"
    audio_output = f"pl_{file_name}.wav"

    # zapisuje oryginalny tekst i tłumaczenie do pliku tekstowego
    with open(os.path.join(INPUT_FOLDER, txt_output), "w", encoding="utf-8") as file:
        file.write(org_text)
        file.write("\n")
        file.write(trans_text)

    # konfiguruje wyjście audio - zapis do pliku .wav
    audio_config = speechsdk.audio.AudioConfig(filename=os.path.join(INPUT_FOLDER, audio_output))

    # tworzy syntezator mowy zapisujący wynik do pliku
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    # zleca syntezę przetłumaczonego tekstu i czeka na wynik
    tts_result = synthesizer.speak_text_async(trans_text).get()

    # wyświetla błąd jeśli synteza nie powiodła się
    if tts_result.reason == speechsdk.ResultReason.Canceled:
        print(f"Błąd: {tts_result.cancellation_details.error_details}")


# przetwarza kolejno każdy plik .wav z folderu
for wav_file in wav_files:
    translate(wav_file)