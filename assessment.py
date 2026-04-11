from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk
import json

load_dotenv()

key = os.getenv("KEY")
region = os.getenv("REGION")

if not key or not region:
    raise ValueError("Brak key lub region w .env")

# SpeechConfig to główny obiekt konfiguracyjny SDK - przechowuje dane uwierzytelniające
# subscription = klucz API, region = lokalizacja serwera Azure 
speech_config = speechsdk.SpeechConfig(subscription=key, region=region)

# ustawia język w którym Azure będzie próbować rozpoznać mowę
# format: kod_języka-KOD_KRAJU, np. en-US, en-GB, pl-PL, de-DE
speech_config.speech_recognition_language = "en-US"

# AudioConfig określa źródło dźwięku
# use_default_microphone=True - używa mikrofonu 
audio_config = speechsdk.AudioConfig(use_default_microphone=True)

# tekst referencyjny - to co użytkownik powinien powiedzieć
# Azure porówna wymowę użytkownika słowo po słowie z tym tekstem
text = "AI learns from data, so it gets better over time"

# PronunciationAssessmentConfig konfiguruje szczegółowość i sposób oceny wymowy
config = speechsdk.PronunciationAssessmentConfig(
    # reference_text - wzorzec do porównania, musi być w tym samym języku co speech_recognition_language
    reference_text=text,
    # HundredMark - ocena w skali 0–100 (alternatywa: FivePoint - skala 1–5)
    grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
    # granularity określa najdrobniejszy poziom oceny:
    # - Word: ocena tylko na poziomie słów
    # - Phoneme: ocena każdego pojedynczego dźwięku (fonem to najmniejsza jednostka dźwiękowa języka)
    granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
    # enable_miscue=True wykrywa słowa pominięte, dodane lub zamienione względem tekstu wzorcowego
    # np. jeśli wzorzec ma "so" a użytkownik powiedział "and" - zostanie oznaczone jako błąd
    enable_miscue=True
)

# IPA (International Phonetic Alphabet) - międzynarodowy alfabet fonetyczny
# pozwala na zapis wymowy niezależny od ortografii, np. "thought" = /θɔːt/
# alternatywa: "SAPI" - uproszczony alfabet Microsoftu, mniej precyzyjny
config.phoneme_alphabet = "IPA"

# włącza ocenę prozodii - analizuje elementy mowy powyżej poziomu pojedynczych dźwięków: 
# - rytm (czy akcenty padają na właściwe sylaby)
# - intonacja (czy zdania kończą się odpowiednim tonem)
# - tempo (czy mowa nie jest za szybka/wolna)
# - pauzy (czy przerwy są naturalne)
# tylko dla en-US
config.enable_prosody_assessment()

# SpeechRecognizer łączy konfigurację API (speech_config) ze źródłem dźwięku (audio_config)
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

# serializuje konfigurację oceny wymowy do formatu JSON i dołącza ją do recognizera
# musi być wywołane przed rozpoczęciem rozpoznawania
config.apply_to(recognizer)

# recognize_once_async() nasłuchuje aż do pierwszej pauzy lub końca wypowiedzi
# .get() blokuje wątek i czeka na wynik - działa synchronicznie
result = recognizer.recognize_once_async().get()

# ResultReason.RecognizedSpeech - mowa została wykryta i pomyślnie przetworzona
if result.reason == speechsdk.ResultReason.RecognizedSpeech:
    print(f"Rozpoznano: {result.text}\n")

    # PronunciationAssessmentResult wrapper do JSONa, wyciągnie ustrukturyzowane dane
    result_pars = speechsdk.PronunciationAssessmentResult(result)

    # accuracy_score - jak dokładnie wymówiono poszczególne dźwięki (0–100)
    # niska wartość = dźwięki brzmią obco lub są zastępowane innymi
    print(f"accuracy_score: {result_pars.accuracy_score}")

    # fluency_score - płynność mowy (0–100)
    # uwzględnia długość i naturalność pauz między słowami
    print(f"fluency_score: {result_pars.fluency_score}")

    # pronunciation_score - ogólna ocena wymowy (0–100)
    # ważona suma accuracy, fluency i completeness
    print(f"pronunciation_score: {result_pars.pronunciation_score}")

    # completeness_score - procent słów z tekstu wzorcowego które zostały wypowiedziane (0–100)
    # pominięcie słów obniża tę wartość
    print(f"completeness_score: {result_pars.completeness_score}")

    print("\n Wynik słów")

    # result_pars.words to lista obiektów Word - po jednym dla każdego słowa z tekstu wzorcowego
    for word in result_pars.words:
        # error_type może przyjąć wartości:
        # - None / "" - słowo wymówione poprawnie
        # - "Mispronunciation" - słowo wymówione niepoprawnie
        # - "Omission" - słowo pominięte
        # - "Insertion" - słowo dodane, którego nie ma w wzorcu
        error = word.error_type if word.error_type else "OK"

        # word.word - samo słowo jako tekst
        # word.accuracy_score - dokładność wymowy tego konkretnego słowa (0–100)
        print(f"[{word.word}] accuracy: {word.accuracy_score} błąd: {error}")

        # word.phonemes dostępne tylko gdy granularity=Phoneme
        if word.phonemes:
            # p.phoneme - symbol IPA danego fonemu, np. "θ", "æ", "ɪ"
            # p.accuracy_score - jak dokładnie ten konkretny dźwięk został wymówiony (0–100)
            phonemes = " ".join(f"{p.phoneme} ({p.accuracy_score})" for p in word.phonemes)
            print(f"Fonemy: {phonemes}")

    print("\n Surowy JSON")

    # zawiera wszystkie dane łącznie z tymi których SDK nie udostępnia przez właściwości
    raw_json = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)

    if raw_json:
        # json.loads() zamienia string JSON na słownik Pythona
        parsed_json = json.loads(raw_json)
        # indent=2 - wcięcia dla czytelności, ensure_ascii=False - poprawny zapis znaków spoza ASCII (np. symboli IPA)
        print(json.dumps(parsed_json, indent=2, ensure_ascii=False))

# NoMatch - Azure odebrało dźwięk ale nie rozpoznało w nim mowy
# może wystąpić przy szumie tła, zbyt cichej mowie lub złym języku rozpoznawania
elif result.reason == speechsdk.ResultReason.NoMatch:
    print("Nie rozpoznano mowy")

# Canceled - połączenie zostało przerwane, najczęściej z powodu błędu sieci lub złego klucza API
elif result.reason == speechsdk.ResultReason.Canceled:
    # CancellationDetails zawiera reason (powód) i error_details (szczegółowy komunikat błędu)
    print(f"Błąd: {speechsdk.CancellationDetails(result=result).reason} { {speechsdk.CancellationDetails(result=result).error_details}}")