from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk
import threading

# wczytuje zmienne z pliku .env do środowiska systemowego
load_dotenv()

# pobiera klucz API do Azure Speech ze zmiennych środowiskowych
key = os.getenv("KEY")
# pobiera region usługi Azure (np. "swedencentral", "westeurope")
region = os.getenv("REGION")

# SpeechTranslationConfig zamiast zwykłego SpeechConfig - umożliwia tłumaczenie mowy
translation_config = speechsdk.translation.SpeechTranslationConfig(
    subscription=key,
    region=region
)

# ustawia język wejściowy - w tym języku użytkownik będzie mówić do mikrofonu
translation_config.speech_recognition_language = "pl-PL"
# dodaje angielski jako język docelowy tłumaczenia
translation_config.add_target_language("en")

# konfiguruje źródło dźwięku - domyślny mikrofon systemu operacyjnego
audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

# TranslationRecognizer łączy konfigurację tłumaczenia ze źródłem dźwięku
recognizer = speechsdk.translation.TranslationRecognizer(
    translation_config=translation_config,
    audio_config=audio_config
)

# Event z modułu threading - blokuje główny wątek do czasu zakończenia sesji
done = threading.Event()


def on_recognizing(evt):
    # Callback wywoływany wielokrotnie w trakcie trwania wypowiedzi - wyniki są częściowe i niestabilne, tzn. tekst może się zmieniać wraz z każdą nową sylabą.
    # Służy do podglądu "na żywo" tego co mówi użytkownik, zanim SDK wyda finalny werdykt. NIE należy tu podejmować żadnych decyzji logicznych (np. wykrywania słowa "koniec"),
    # bo tekst w tym momencie jest niepewny i może być jeszcze wielokrotnie poprawiony.
    text = evt.result.text

    # Pobiera częściowe tłumaczenie na angielski ze słownika translations. Może być puste lub niekompletne - SDK tłumaczy na bieżąco, ale nie gwarantuje
    # pełnego tłumaczenia aż do momentu finalizacji wypowiedzi w on_recognized.
    translation = evt.result.translations.get("en", "")

    # \r cofa kursor na początek bieżącej linii bez przechodzenia niżej, dzięki czemu każda aktualizacja nadpisuje poprzednią zamiast drukować nową linię.
    # :<80 wyrównuje tekst do lewej i dopełnia spacjami do 80 znaków - jest to kluczowe, bo gdy nowy tekst jest krótszy od poprzedniego, bez dopełnienia pozostałyby
    # "śmieci" (ogon starych znaków) na końcu linii i linia wyglądałaby na uszkodzoną. 
    # end="" wyłącza domyślny znak nowej linii dodawany przez print() - bez tego \r nie miałoby sensu, bo kursor i tak przeskakiwałby do następnej linii. 
    # flush=True wymusza natychmiastowe opróżnienie bufora wyjściowego i wysłanie tekstu na terminal - bez tego Python może przetrzymywać znaki w buforze i wyświetlić je z opóźnieniem lub zbiorczo, co psuje efekt aktualizacji w czasie rzeczywistym.
    print(f"\rPL: {text:<80} EN: {translation:<80}", end="", flush=True)

def on_recognized(evt):
    # Callback wywoływany jednokrotnie po zakończeniu wypowiedzi (po wykryciu pauzy/ciszy). W tym momencie SDK uznał rozpoznawanie za kompletne - wynik jest finalny i stabilny.
    # To tutaj, a nie w on_recognizing, należy umieszczać całą logikę biznesową* ale to zależy od przypadku użycia :)
    if evt.result.reason == speechsdk.ResultReason.TranslatedSpeech:

        if "koniec" in evt.result.text.strip().lower():
            print("Usłyszałem 'koniec' - kończę program.")
            # Asynchronicznie zatrzymuje ciągłe rozpoznawanie mowy. Metoda _async oznacza, że nie blokuje bieżącego wątku (callbacku).
            # Po zakończeniu zatrzymywania SDK wywoła zdarzenie session_stopped, które jest podpięte do on_stopped - ten z kolei wywoła done.set().
            recognizer.stop_continuous_recognition_async()
        else:
            # Pobiera finalny, pewny tekst rozpoznanej wypowiedzi w języku źródłowym (pl-PL). W przeciwieństwie do evt.result.text z on_recognizing, ten tekst już się nie zmieni.
            text = evt.result.text

            # Pobiera finalne tłumaczenie na angielski - kompletne i gotowe do wyświetlenia. Użycie .get() z wartością domyślną "" chroni przed KeyError gdy SDK
            # z jakiegoś powodu nie zwróciło tłumaczenia dla danego języka.
            translation = evt.result.translations.get("en", "")

            # \r na początku nadpisuje ostatnią linię z częściowym podglądem (z on_recognizing), zastępując ją finalnym wynikiem opatrzonym symbolem -> sygnalizującym pewność wyniku.
            # Brak end="" oznacza, że print() doda domyślny znak nowej linii (\n) na końcu, dzięki czemu kolejna rozpoznana wypowiedź zacznie się od świeżej linii,
            # a finalny wynik zostaje "zamrożony" w historii terminala - nie będzie nadpisany.
            print(f"\r-> PL: {text:<80} EN: {translation:<80}")


def on_canceled(evt):
    # pobiera szczegóły anulowania - powód i opis błędu
    details = speechsdk.CancellationDetails(evt.result)
    # CancellationReason.Error oznacza faktyczny błąd (np. zły klucz, brak sieci) EndOfStream to normalny koniec sesji - nie jest błędem
    if details.reason == speechsdk.CancellationReason.Error:
        # \n przed błędem żeby nie nadpisać poprzedniej linii z tekstem
        print(f"\nBłąd: {details.error_details}")
    # odblokowuje główny wątek - program może się zakończyć
    done.set()

def on_stopped(evt):
    # wywoływane gdy sesja rozpoznawania dobiegnie naturalnego końca
    # odblokowuje główny wątek
    done.set()

# podpina on_recognizing pod zdarzenie częściowych wyników - odpala się w trakcie mówienia
recognizer.recognizing.connect(on_recognizing)
# podpina on_recognized pod zdarzenie finalnych wyników - odpala się po zakończeniu zdania
recognizer.recognized.connect(on_recognized)
# podpina on_canceled - odpala się przy błędzie lub końcu sesji
recognizer.canceled.connect(on_canceled)
# podpina on_stopped - odpala się gdy sesja zostanie zakończona
recognizer.session_stopped.connect(on_stopped)

print("Mów do mikrofonu... ('koniec' aby zkończyć")

# uruchamia ciągłe rozpoznawanie mowy w wątku w tle - nie blokuje głównego wątku
recognizer.start_continuous_recognition()

# blokuje wątek główny do czasu zakończenia przetwarzania
done.wait()

recognizer.stop_continuous_recognition_async()
