from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk
import threading
import pyaudio

load_dotenv()

key = os.getenv("KEY")

region = os.getenv("REGION")

# SpeechTranslationConfig zamiast zwykłego SpeechConfig - umożliwia tłumaczenie mowy
translation_config = speechsdk.translation.SpeechTranslationConfig(
    subscription=key,
    region=region
)

# ustawia język wejściowy - w tym języku użytkownik będzie mówić do mikrofonu
translation_config.speech_recognition_language = "pl-PL"

# Dodaje angielski jako język docelowy tłumaczenia.  Kod języka docelowego to samo ISO 639-1 ("en"), bez regionu - w odróżnieniu
# od języka wejściowego który wymaga pełnego kodu ("pl-PL").  Można dodać wiele języków jednocześnie, ale voice_name poniżej zadziała
# tylko dla jednego - Azure wygeneruje audio tylko dla tego jednego głosu.
translation_config.add_target_language("en")

# KLUCZOWA LINIA - właśnie ona włącza syntezę mowy (TTS) na wyjściu. 
# Bez tej linii SDK zwraca wyłącznie tekst w evt.result.translations,
# a zdarzenie "synthesizing" nigdy nie zostanie wywołane.
# Z tą linią po każdej rozpoznanej frazie Azure automatycznie:
# 1) tłumaczy tekst na angielski
# 2) przekazuje tłumaczenie do silnika TTS
# 3) strumieniuje wygenerowane audio z powrotem przez zdarzenie "synthesizing"
# Nazwa głosu musi być zgodna z językiem docelowym - głos angielski dla "en".
translation_config.voice_name = "en-US-JennyNeural"

# konfiguruje źródło dźwięku - domyślny mikrofon systemu operacyjnego
audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

# Tworzy główny obiekt rozpoznawania i tłumaczenia mowy.
# TranslationRecognizer łączy konfigurację tłumaczenia (języki, klucz, region, głos TTS)
# z konfiguracją audio (skąd pochodzi dźwięk wejściowy).
# To ten obiekt zarządza całym cyklem życia sesji: nawiązanie połączenia WebSocket
# z Azure, ciągłe strumieniowanie audio, odbieranie wyników i zamknięcie sesji.
recognizer = speechsdk.translation.TranslationRecognizer(
    translation_config=translation_config,
    audio_config=audio_config
)

# Inicjalizuje bibliotekę PyAudio raz dla całej sesji - jest to kosztowna operacja
# która inicjalizuje sterownik PortAudio i skanuje dostępne urządzenia audio.
# Gdybyśmy tworzyli nową instancję PyAudio przy każdej frazie (w callbacku),
# ryzykowalibyśmy opóźnienia, artefakty dźwiękowe i potencjalne wycieki zasobów.
pa = pyaudio.PyAudio()

# Otwiera strumień wyjściowy audio z parametrami ściśle zgodnymi z formatem
# zwracanym przez Azure Speech SDK:
#
# format=pyaudio.paInt16 - 16-bitowe próbki PCM.
#   Azure zawsze zwraca audio w tym formacie - inne formaty (float32, int32)
#   spowodowałyby zniekształcony dźwięk lub ciszę.
#
# channels=1 - mono. Azure Speech TTS zwraca jeden kanał audio.
#   Ustawienie channels=2 (stereo) przy danych mono powoduje że PyAudio
#   interpretuje co drugą próbkę jako prawy kanał - dźwięk byłby 2x przyspieszony
#   i zniekształcony.
#
# rate=16000 - częstotliwość próbkowania 16 000 Hz (16 kHz).
#   Jest to standardowa częstotliwość dla usług rozpoznawania mowy 
#
# output=True - strumień jest wyjściowy (odtwarzanie), nie wejściowy (nagrywanie).
#   Gdybyśmy ustawili input=True przez pomyłkę, PyAudio próbowałby czytać z karty
#   dźwiękowej zamiast do niej pisać.
stream = pa.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    output=True
)

# Tworzy obiekt synchronizacji wątków ze standardowej biblioteki threading.
# done.wait() w dalszej części kodu zablokuje główny wątek programu do momentu,
# aż któryś z callbacków wywoła done.set() - sygnalizując zakończenie pracy.
# Bez tego główny wątek zakończyłby się natychmiast po start_continuous_recognition(),
# zanim SDK zdążyłoby cokolwiek rozpoznać lub odtworzyć.
done = threading.Event()

def on_recognized(evt):
    # Callback wywoływany jednokrotnie po zakończeniu każdej wypowiedzi
    # (po wykryciu pauzy lub ciszy). Wynik jest w tym momencie finalny i stabilny.
    # Równolegle z wywołaniem tego callbacku Azure rozpoczyna już syntezę TTS
    # dla przetłumaczonego tekstu - zdarzenia "synthesizing" zaczną napływać
    # niemal natychmiast po tym callbacku
    if evt.result.reason == speechsdk.ResultReason.TranslatedSpeech:

        # Sprawdza czy użytkownik wymówił słowo "koniec" jako komendę zatrzymania.
        # strip() usuwa białe znaki z brzegów (np. spację przed słowem),
        # lower() normalizuje do małych liter, by "Koniec", "KONIEC" też działały.
        # Sprawdzamy "in" zamiast == bo SDK może dołączyć interpunkcję: "koniec."
        if "koniec" in evt.result.text.strip().lower():
            print("\nUsłyszałem 'koniec' - kończę program.")
            # Asynchronicznie zatrzymuje ciągłe rozpoznawanie mowy. Metoda _async oznacza, że nie blokuje bieżącego wątku (callbacku).
            # Po zakończeniu zatrzymywania SDK wywoła zdarzenie session_stopped, które jest podpięte do on_stopped - ten z kolei wywoła done.set().
            recognizer.stop_continuous_recognition_async()
            # Sygnalizuje głównemu wątkowi że może zakończyć program.
            # done.set() jest wywoływane tu dodatkowo (poza on_stopped),
            # by mieć pewność że program zakończy się nawet jeśli session_stopped
            # z jakiegoś powodu nie zostanie wywołane przez SDK.
            done.set()
        else:
            print(f"PL: {evt.result.text}")
            # Pobiera finalne tłumaczenie na angielski. Klucz to samo "en" bez regionu,
            # zgodnie z tym jak języki docelowe są deklarowane w add_target_language().
            # .get() z domyślną wartością "" chroni przed KeyError jeśli Azure
            # z jakiegoś powodu nie zwróciło tłumaczenia (np. przy bardzo krótkich frazach).
            print(f"  EN: {evt.result.translations.get('en', '')}")

def on_synthesizing(evt):
    # Callback wywoływany wielokrotnie dla każdej rozpoznanej frazy - raz na każdy fragment audio generowany przez silnik TTS Azure.
    # Fragmenty audio przychodzą strumieniowo zanim cała fraza zostanie w pełni zsyntetyzowana,
    # co minimalizuje opóźnienie między końcem mówienia a początkiem odtwarzania.
    # Kolejność zdarzeń dla jednej frazy:
    #   on_recognized → on_synthesizing (1) → on_synthesizing (2) → ... → SynthesizingAudioCompleted
    #
    # SynthesizingAudio oznacza że ten konkretny fragment audio jest gotowy do odtworzenia.
    if evt.result.reason == speechsdk.ResultReason.SynthesizingAudio:
        # evt.result.audio to obiekt bytes zawierający surowe próbki PCM tego fragmentu audio.
        # Rozmiar fragmentu audio jest zmienny i zależy od wewnętrznej logiki Azure TTS -
        # zazwyczaj kilka do kilkudziesięciu kilobajtów na fragment.
        #
        # stream.write() zapisuje bajty bezpośrednio do bufora wyjściowego karty dźwiękowej.
        # Jest to operacja blokująca tylko gdy bufor jest pełny (co przy normalnym tempie mowy praktycznie nie występuje) - w typowym przypadku wraca natychmiast.
        # Dzięki temu odtwarzanie jest płynne i zsynchronizowane z tempem napływania danych, bez konieczności ręcznego buforowania czy zarządzania wątkami odtwarzania.
        #
        # UWAGA: stream.write() nie jest thread-safe w PyAudio. Ponieważ callbacks SDK są wywoływane z wewnętrznego wątku SDK, a główny wątek tylko czeka na done.wait(),
        # w praktyce tylko jeden wątek pisze do strumienia i nie ma konfliktu.
        # Gdyby callbacki były wywoływane z wielu wątków jednocześnie, należałoby użyć threading.Lock() do ochrony dostępu do stream.write().
        stream.write(evt.result.audio)

def on_canceled(evt):
    # pobiera szczegóły anulowania - powód i opis błędu
    details = speechsdk.CancellationDetails(evt.result)
    # CancellationReason.Error oznacza nieoczekiwane przerwanie - może to być nieprawidłowy klucz API, brak połączenia z internetem, przekroczony limit
    # lub błąd po stronie serwisu Azure.
    # Inne wartości CancellationReason (np. EndOfStream) to normalne zakończenie - nie wymagają logowania błędu.
    if details.reason == speechsdk.CancellationReason.Error:
        # error_details zawiera szczegółowy opis od Azure 
        print(f"Błąd: {details.error_details}")
    # Niezależnie od rodzaju anulowania sygnalizujemy głównemu wątkowi koniec pracy.
    done.set()

def on_stopped(evt):
    # wywoływane gdy sesja rozpoznawania dobiegnie naturalnego końca
    # odblokowuje główny wątek
    done.set()

# Rejestruje callback on_recognized jako obserwator zdarzenia "recognized".
# SDK wywoła tę funkcję za każdym razem gdy rozpozna i przetłumaczy kompletną wypowiedź.
recognizer.recognized.connect(on_recognized)

# Rejestruje callback on_synthesizing jako obserwator zdarzenia "synthesizing".
# To zdarzenie jest dostępne TYLKO gdy ustawiono voice_name w konfiguracji -
# bez voice_name zdarzenie to nigdy nie zostanie wywołane, nawet jeśli je podepniemy.
# SDK wywoła tę funkcję wielokrotnie dla każdej frazy, raz na każdy chunk audio z TTS.
recognizer.synthesizing.connect(on_synthesizing)

# Rejestruje callback on_canceled jako obserwator zdarzenia "canceled".
# Wywołane przy błędach połączenia, autoryzacji lub końcu strumienia audio.
recognizer.canceled.connect(on_canceled)

# Rejestruje callback on_stopped jako obserwator zdarzenia "session_stopped".
# Wywołane po poprawnym zamknięciu sesji przez stop_continuous_recognition_async().
recognizer.session_stopped.connect(on_stopped)

print("Mów po polsku - usłyszysz tłumaczenie po angielsku...")

# uruchamia ciągłe rozpoznawanie mowy w wątku w tle - nie blokuje głównego wątku
recognizer.start_continuous_recognition()

# Blokuje główny wątek aż do momentu gdy któryś callback wywoła done.set().
#   - on_recognized (gdy usłyszano "koniec")
#   - on_canceled (błąd lub koniec pliku audio)
#   - on_stopped (czyste zamknięcie sesji)
done.wait()

# Asynchronicznie zatrzymuje sesję - "zabezpieczające" wywołanie po odlokowaniu done.wait().
# Jeśli done zostało ustawione przez on_stopped lub on_canceled, sesja mogła być już
# zatrzymana, ale kolejne wywołanie stop jest bezpieczne i nie powoduje błędu.
# Jeśli done zostało ustawione przez on_recognized ("koniec"), stop_continuous_recognition_async()
# zostało już wywołane wewnątrz callbacku - to wywołanie jest wtedy nadmiarowe ale nieszkodliwe.
recognizer.stop_continuous_recognition_async()

# Zatrzymuje strumień audio przed jego zamknięciem.
# stop_stream() sygnalizuje PyAudio że nie będzie więcej danych - pozwala na dokończenie odtwarzania buforowanych danych zanim strumień zostanie fizycznie zamknięty.
# Pominięcie tego kroku może skutkować urwaniem ostatniego zdania w połowie słowa.
stream.stop_stream()

# Zwalnia zasoby systemowe zajęte przez strumień audio.
# Bez tego wywołania strumień pozostałby otwarty co mogłoby uniemożliwić innym programom dostęp do karty dźwiękowej.
stream.close()

# Zwalnia zasoby biblioteki PortAudio (sterownik audio na poziomie systemu).
# Powinno być wywołane jako ostatnie, po zamknięciu wszystkich strumieni.
# pa.terminate() bez wcześniejszego stream.close() może powodować błędy 
pa.terminate()