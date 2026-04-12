from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk
import threading
from openai import AzureOpenAI

load_dotenv()

key = os.getenv("KEY")
region = os.getenv("REGION")
open_ai_key = os.getenv("OPENAI_KEY")

# tworzy klienta Azure OpenAI - odpowiada za komunikację z modelem GPT
# api_version - wersja API OpenAI której będziemy używać
# azure_endpoint - adres zasobu Azure OpenAI (unikalny dla każdego zasobu)
# api_key - klucz uwierzytelniający do Azure OpenAI
client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint="https://speechazr0202686.cognitiveservices.azure.com/",
    api_key=open_ai_key,
)

# --- KONFIGURACJA STT (Speech-to-Text) ---

# tworzy konfigurację połączenia z Azure Speech Service
speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
# ustawia język rozpoznawania mowy na polski
speech_config.speech_recognition_language = "pl-PL"

# konfiguruje źródło dźwięku - domyślny mikrofon systemu operacyjnego
audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
# tworzy obiekt rozpoznający mowę łącząc konfigurację API ze źródłem dźwięku
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

# --- KONFIGURACJA TTS (Text-to-Speech) ---

# tworzy osobną konfigurację dla syntezy mowy 
tts_config = speechsdk.SpeechConfig(subscription=key, region=region)
# ustawia głos syntezatora - Agnieszka, polski głos żeński
tts_config.speech_synthesis_voice_name = "pl-pl-AgnieszkaNeural"

# konfiguruje wyjście dźwięku - domyślne głośniki
audio_output = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
# tworzy syntezator mowy łącząc konfigurację API z wyjściem dźwięku
synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config, audio_config=audio_output)


def ask_gpt(text_from_user):
    print("Wysyłka do chata")

    # chat.completions.create - wysyła konwersację do modelu GPT i czeka na odpowiedź
    response = client.chat.completions.create(
        messages=[
            {
                # rola "system" definiuje osobowość i zachowanie asystenta
                # ta wiadomość nie pochodzi od użytkownika - ustawia kontekst dla modelu
                "role": "system",
                "content": "Jesteś asystentem 5 letniego dziecka, odpowiadaj krótko i prostym językiem",
            },
            {
                # rola "user" - wiadomość od użytkownika, na którą model ma odpowiedzieć
                "role": "user",
                "content": text_from_user,
            }
        ],
        # max_tokens - maksymalna długość odpowiedzi (1 token ≈ 0.75 słowa)
        max_tokens=50,
        # temperature - losowość odpowiedzi: 0.0 = deterministyczna, 1.0 = bardzo kreatywna
        temperature=0.7,
        # nazwa wdrożonego modelu w zasobie Azure OpenAI
        model="gpt-4.1-mini-2"
    )

    # wyciąga tekst odpowiedzi 
    answer = response.choices[0].message.content
    print(answer)
    return answer


def say(text_from_chat):
    print("Odczytanie tekstu")

    # speak_text_async() wysyła tekst do Azure TTS i odtwarza go przez głośniki
    # .get() blokuje wątek do czasu zakończenia odtwarzania
    result = synthesizer.speak_text_async(text_from_chat).get()

    # sprawdza czy synteza nie została przerwana błędem
    if result.reason == speechsdk.ResultReason.Canceled:
        print(f"Błąd TTS: {result.cancellation_details.error_details}")


# Event z modułu threading - blokuje główny wątek do czasu zakończenia rozmowy
done = threading.Event()


def on_recognized(evt):
    # sprawdza czy Azure faktycznie rozpoznało mowę (a nie np. ciszę)
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        # usuwa białe znaki z początku i końca rozpoznanego tekstu
        query = evt.result.text.strip()

        # ignoruje puste wyniki (np. rozpoznano ciszę lub szum)
        if not query:
            return

        print(f"[User] {query}")

        # słowo-klucz kończące rozmowę - użytkownik mówi "koniec"
        if "koniec" in evt.result.text.strip().lower():
            # odblokowuje główny wątek - program zakończy działanie
            done.set()
            return

        try:
            # wysyła pytanie do GPT i odbiera odpowiedź tekstową
            answer = ask_gpt(query)
            # odczytuje odpowiedź GPT na głos przez głośniki
            say(answer)
        except Exception as exp:
            print(f"Błąd: {exp}")

    elif evt.result.reason == speechsdk.ResultReason.NoMatch:
        # NoMatch oznacza że Azure odebrało dźwięk ale nie rozpoznało w nim mowy
        # pass - celowo ignorujemy (np. szum tła, westchnienie)
        pass


def on_canceled(evt):
    # pobiera szczegóły anulowania - powód i opis błędu
    deatils = speechsdk.CancellationDetails(evt.result)
    # CancellationReason.Error oznacza faktyczny błąd (np. zły klucz, brak sieci)
    # EndOfStream to normalny koniec pliku audio - nie jest błędem
    if deatils.reason == speechsdk.CancellationReason.Error:
        print(f"Błąd: {speechsdk.CancellationDetails(evt.result).error_details}")
    # odblokowuje główny wątek niezależnie od powodu anulowania
    done.set()


def on_stopped(evt):
    # wywoływane gdy sesja rozpoznawania dobiegnie naturalnego końca
    # odblokowuje główny wątek
    done.set()


# podpina funkcje obsługi zdarzeń do rozpoznawacza
recognizer.recognized.connect(on_recognized)
recognizer.canceled.connect(on_canceled)
recognizer.session_stopped.connect(on_stopped)

# asystent odzywa się pierwszy zapraszając do rozmowy
say("Jak mogę pomóc?\n")

# uruchamia ciągłe rozpoznawanie mowy w wątku w tle
recognizer.start_continuous_recognition_async()


done.wait()

recognizer.stop_continuous_recognition_async()