from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk
import threading

# Wczytuje zmienne środowiskowe z pliku .env znajdującego się w katalogu roboczym. Dzięki temu klucz API i region nie są zapisane na stałe w kodzie,
# co jest dobrą praktyką bezpieczeństwa - plik .env powinien być w .gitignore.
load_dotenv()

# Pobiera klucz subskrypcji ze zmiennych środowiskowych. Bez tego klucza żadne zapytanie do API nie zostanie autoryzowane.
key = os.getenv("KEY")

# Pobiera nazwę regionu w którym jest wdrożona usługa Speech. Region musi zgadzać się z tym, gdzie utworzono zasób w portalu Azure
region = os.getenv("REGION")

# Tworzy obiekt konfiguracji dla usługi tłumaczenia mowy (Speech Translation). W odróżnieniu od zwykłego SpeechConfig (który tylko rozpoznaje mowę),
# SpeechTranslationConfig obsługuje równoczesne rozpoznawanie i tłumaczenie. Przekazujemy klucz i region, by SDK wiedział, z którym zasobem Azure się połączyć.
translation_config = speechsdk.translation.SpeechTranslationConfig(
    subscription=key,
    region=region
)

# Ustawia język wejściowy rozpoznawania mowy na polski ("pl-PL"). SDK będzie interpretował dźwięk z mikrofonu jako mowę polską i na tej
# podstawie będzie tworzył transkrypcję przed tłumaczeniem.
translation_config.speech_recognition_language = "pl-PL"

# Dodaje angielski jako jeden z języków docelowych tłumaczenia. Można dodać wiele języków - usługa przetłumaczy każdą wypowiedź
# na wszystkie zadeklarowane języki jednocześnie, w jednym zapytaniu.
translation_config.add_target_language("en")

# Dodaje niemiecki jako drugi język docelowy tłumaczenia. Wyniki dla obu języków będą dostępne w słowniku evt.result.translations.
translation_config.add_target_language("de")

# Tworzy konfigurację źródła dźwięku wskazującą na domyślny mikrofon systemowy. use_default_microphone=True Alternatywnie można podać ścieżkę do pliku audio zamiast mikrofonu.
audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

# Tworzy główny obiekt rozpoznawania i tłumaczenia mowy (TranslationRecognizer). Łączy w sobie konfigurację tłumaczenia (języki, klucz, region)
# z konfiguracją audio (skąd pochodzi dźwięk). To ten obiekt zarządza całym cyklem życia sesji: start, nasłuchiwanie, stop.
recognizer = speechsdk.translation.TranslationRecognizer(
    translation_config=translation_config,
    audio_config=audio_config
)

# Tworzy obiekt synchronizacji wątków (Event) ze standardowej biblioteki threading. done.wait() w dalszej części kodu zablokuje główny wątek programu do momentu,
# aż któryś z callbacków wywoła done.set() - sygnalizując zakończenie pracy. Bez tego główny wątek zakończyłby się natychmiast, zanim SDK zdąży cokolwiek rozpoznać.
done = threading.Event()

def on_recognized(evt):
    # Sprawdza, czy wynik rozpoznawania jest pełnym, przetłumaczonym zdaniem. 
    # ResultReason.TranslatedSpeech oznacza, że SDK zakończył rozpoznawanie jednej wypowiedzi (po ciszy) i ma gotowy wynik wraz z tłumaczeniami. 
    # Inne możliwe wartości to np. NoMatch (nie rozpoznano) lub RecognizedSpeech (rozpoznano, ale nie przetłumaczono - nie powinno tu wystąpić).
    if evt.result.reason == speechsdk.ResultReason.TranslatedSpeech:
        # Sprawdza, czy użytkownik wypowiedział słowo "koniec" (po normalizacji do małych liter i usunięciu białych znaków z brzegów).
        # To jest umowne słowo-klucz kończące program
        if "koniec" in evt.result.text.strip().lower():
            print("Usłyszałem 'koniec' - kończę program.")
            # Asynchronicznie zatrzymuje ciągłe rozpoznawanie mowy. Metoda _async oznacza, że nie blokuje bieżącego wątku (callbacku).
            # Po zakończeniu zatrzymywania SDK wywoła zdarzenie session_stopped, które jest podpięte do on_stopped - ten z kolei wywoła done.set().
            recognizer.stop_continuous_recognition_async()
            # Ustawia flagę done jako "gotowe", co odblokuje done.wait() w głównym wątku i pozwoli programowi przejść do końca.
            # done.set() jest wywoływane tutaj dodatkowo (poza on_stopped), by mieć pewność, że program zakończy się nawet jeśli session_stopped
            # z jakiegoś powodu nie zostanie wywołane.
            done.set()
        else:                                      
            # Wypisuje oryginalną transkrypcję rozpoznanej polskiej wypowiedzi. evt.result.text zawiera tekst w języku źródłowym (pl-PL).
            print(f"PL (oryginał): {evt.result.text}")
            # Pobiera tłumaczenie na angielski ze słownika translations.
            # Klucz to kod języka bez regionu (samo "en", nie "en-US").
            # Jeśli z jakiegoś powodu tłumaczenie nie istnieje, zwraca pusty string.
            print(f"EN: {evt.result.translations.get('en', '')}")
            # Pobiera tłumaczenie na niemiecki - analogicznie jak angielski powyżej.
            print(f"DE: {evt.result.translations.get('de', '')}")
            print("---")

def on_canceled(evt):
    # Pobiera szczegóły anulowania z obiektu wyniku zdarzenia. 
    # CancellationDetails zawiera powód anulowania oraz szczegóły błędu, jeśli anulowanie nastąpiło z powodu wyjątku lub problemu z siecią/API.
    details = speechsdk.CancellationDetails(evt.result)
    # Sprawdza, czy przyczyną anulowania był błąd (np. nieprawidłowy klucz, brak połączenia z internetem, przekroczony limit API).
    # Inne możliwe wartości CancellationReason to np. EndOfStream (plik audio dobiegł końca) - te nie są błędami i nie wymagają logowania.
    if details.reason == speechsdk.CancellationReason.Error:
        # Wypisuje szczegółowy opis błędu zwrócony przez serwis Azure. 
        # error_details może zawierać m.in. kod HTTP, opis problemu z autoryzacją lub informację o niedostępności usługi - przydatne przy debugowaniu.
        print(f"Błąd: {details.error_details}")
    # Niezależnie od rodzaju anulowania (błąd czy normalne zakończenie strumienia) sygnalizuje głównemu wątkowi, że praca SDK dobiegła końca i można zamknąć program.
    done.set()

def on_stopped(evt):
    # Callback wywoływany przez SDK po zakończeniu sesji rozpoznawania, tj. po tym jak stop_continuous_recognition_async() w pełni się wykona
    # i sesja zostanie formalnie zamknięta po stronie serwisu Azure. Sygnalizuje głównemu wątkowi (done.wait()), że można bezpiecznie zakończyć program.
    done.set()

# Rejestruje callback on_recognized jako obserwator zdarzenia "recognized". Zdarzenie to jest emitowane przez SDK za każdym razem, gdy zostanie
# rozpoznana i przetłumaczona kompletna wypowiedź (po wykryciu ciszy/pauzy).
recognizer.recognized.connect(on_recognized)

# Rejestruje callback on_canceled jako obserwator zdarzenia "canceled". Zdarzenie to jest emitowane gdy sesja zostanie przerwana z powodu błędu
# lub gdy źródło audio dobiegnie końca (np. koniec pliku).
recognizer.canceled.connect(on_canceled)

# Rejestruje callback on_stopped jako obserwator zdarzenia "session_stopped". Zdarzenie to jest emitowane gdy sesja rozpoznawania zostanie poprawnie zakończona
# po wywołaniu stop_continuous_recognition_async().
recognizer.session_stopped.connect(on_stopped)

print("Mów do mikrofonu... ('koniec' żeby skończyć)")

# Uruchamia tryb ciągłego rozpoznawania mowy w tle (w osobnym wątku SDK). W odróżnieniu od recognize_once_async() (który rozpoznaje jedną wypowiedź i kończy),
# start_continuous_recognition() nie blokuje i nie kończy się samoczynnie - SDK będzie nasłuchiwał i emitował zdarzenia "recognized" dopóki
# nie zostanie jawnie zatrzymany przez stop_continuous_recognition_async().
recognizer.start_continuous_recognition()

# Blokuje główny wątek programu do momentu ustawienia flagi done przez jeden z callbacków. Jest to niezbędne, bo start_continuous_recognition() działa asynchronicznie -
# bez tego blokowania główny wątek dobiegłby do końca pliku i program zamknąłby się natychmiast, zanim SDK zdążyłoby cokolwiek rozpoznać.
# done.set() zostanie wywołane przez on_recognized (słowo "koniec"), on_canceled (błąd lub koniec strumienia) lub on_stopped (czyste zamknięcie sesji).

done.wait()

# Zatrzymuje sesję rozpoznawania po tym, jak done.wait() się odblokuje. Jest to wywołanie "zabezpieczające" - jeśli done.set() zostało ustawione
# przez on_canceled lub on_stopped, sesja mogła już być zatrzymana, ale kolejne wywołanie stop jest bezpieczne i nie spowoduje błędu.
recognizer.stop_continuous_recognition_async()