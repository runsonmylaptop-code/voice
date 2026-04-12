from dotenv import load_dotenv
import os
import requests
import time
import json

load_dotenv()

KEY = os.getenv("KEY")

REGION = os.getenv("REGION")

# SAS URL (Shared Access Signature) to tymczasowy, kryptograficznie podpisany link  do zasobu na Azure Blob Storage z ograniczonym czasem ważności i zakresem uprawnień.
# Azure Speech Service będzie pobierać plik audio bezpośrednio z tego adresu -  nie wysyłamy samego pliku w żądaniu, tylko wskazujemy gdzie go znaleźć.
# Parametry URL: sp=r (tylko odczyt), st/se (czas ważności), sig (podpis cyfrowy).
AUDIO_URL = "https://storageaazr02202686.blob.core.windows.net/voice/ssml_conv.mp3?sp=r&st=2026-04-12T05:43:48Z&se=2026-04-12T13:58:48Z&spr=https&sv=2025-11-05&sr=b&sig=Nt1MoeL2ZOcwErpZyRC%2BTVEWIGpxwHKk4e3pmr1TMkI%3D"

# Buduje URL bazowy do endpointu Batch Transcription API dla konkretnego regionu. Batch Transcription różni się od SDK tym, że działa w pełni asynchronicznie po stronie Azure -
# wysyłamy żądanie, Azure przetwarza plik w tle (nawet godzinami przy długich nagraniach), a my odpytujemy API o status zamiast trzymać otwarte połączenie przez cały czas.
# v3.2 to aktualna wersja API - różne wersje mogą mieć różne pola w odpowiedzi JSON.
BASE_URL = f"https://{REGION}.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions"

# Nagłówki HTTP wymagane przez Azure REST API przy każdym żądaniu. Ocp-Apim-Subscription-Key to niestandardowy nagłówek Azure do autoryzacji kluczem -
# Content-Type: application/json informuje API że żądanie jest zakodowane jako JSON.
HEADERS = {
    "Ocp-Apim-Subscription-Key": KEY,
    "Content-Type": "application/json"
}

# Payload definiuje parametry zadania transkrypcji wysyłanego do Azure. Wszystkie pola są serializowane do JSON przez requests.post(..., json=payload).
# tutaj ładna dokumentacja https://learn.microsoft.com/en-us/azure/ai-services/speech-service/batch-transcription-create?pivots=rest-api
payload = {
    # Lista URL-i do plików audio do transkrypcji - można podać wiele naraz, co pozwala przetworzyć całą serię nagrań w ramach jednego zadania.
    "contentUrls": [AUDIO_URL],
    # Język nagrania - musi dokładnie odpowiadać językowi mówcy
    "locale": "pl-PL",
    # Nazwa zadania widoczna w portalu Azure i w odpowiedziach API - czysto informacyjna, nie wpływa na przetwarzanie, ale może ułatwic identyfikację przy wielu równoległych zadaniach.
    "displayName": "Moja transkrypcja",
    "properties": {
        # Rozróżnianie mówców -  True, każda fraza dostaje przypisany numer mówcy (1, 2, 3...)
        "diarizationEnabled": True,
        # Gdy True, każde słowo w transkrypcji dostaje własny znacznik czasu rozpoczęcia i zakończenia. Przydatne przy tworzeniu napisów lub synchronizacji tekstu z audio, ale zwiększa
        # rozmiar pliku wynikowego - wyłączone gdy potrzebujemy tylko tekstu.
        "wordLevelTimestampsEnabled": False,
        # Steruje sposobem dodawania interpunkcji do transkrypcji:
        # DictatedAndAutomatic - honoruje znaki wypowiedziane słownie ("kropka", "przecinek") i jednocześnie automatycznie wstawia interpunkcję na podstawie kontekstu zdania.
        "punctuationMode": "DictatedAndAutomatic",
        # Steruje filtrowaniem wulgaryzmów w wynikach transkrypcji.
        # None - brak filtrowania, tekst jest przepisywany dosłownie. 
        # Alternatywy: Masked (zastępuje gwiazdkami), Removed (usuwa słowo), Tags (opakowuje tagami XML).
        "profanityFilterMode": "None"
    }
}


# Wysyła żądanie POST tworzące nowe zadanie transkrypcji po stronie Azure.
# requests automatycznie serializuje słownik payload do JSON i ustawia Content-Type.
# Odpowiedź zawiera metadane zadania, w tym jego unikalny URL ("self") do późniejszego odpytywania.
response = requests.post(BASE_URL, headers=HEADERS, json=payload)

# HTTP 201 Created to oczekiwany kod sukcesu przy tworzeniu zasobu przez REST API. Każdy inny kod (np. 401 Unauthorized, 400 Bad Request) oznacza błąd -
# wyświetlamy szczegóły z odpowiedzi, które Azure zwraca w formacie JSON, i kończymy program 
if response.status_code != 201:
    print(f"Błąd: {response.status_code}")
    print(response.json())
    exit(1)

# Pole "self" w odpowiedzi to kanoniczny URL do tego konkretnego zadania transkrypcji. Będziemy go używać zarówno do sprawdzania statusu (GET na job_url)
# jak i do pobierania plików wynikowych (GET na job_url + "/files").
job_url = response.json()["self"]
print(f"Zadanie utworzone: {job_url}")

print("Czekam na wynik...")

# Pętla pollingu - odpytuje Azure co określony czas aż zadanie zmieni status na końcowy. Batch Transcription jest asynchroniczne, więc nie ma innego sposobu niż aktywne odpytywanie;
while True:
    # Czeka 3 sekundy przed kolejnym sprawdzeniem statusu.
    # Przy długich nagraniach (>10 min) można bezpiecznie zwiększyć do 60-120 sekund.
    time.sleep(3)

    # Wysyła GET na URL zadania aby pobrać jego aktualne metadane i status.
    status_response = requests.get(job_url, headers=HEADERS)
    # Parsuje odpowiedź JSON na słownik Pythona do dalszego przetwarzania.
    status_data = status_response.json()
    # Wyciąga pole "status" określające etap przetwarzania zadania. Możliwe wartości: NotStarted (w kolejce), Running (w trakcie), Succeeded, Failed.
    status = status_data.get("status")

    print(f"Status: {status}")

    # Succeeded oznacza że Azure zakończył transkrypcję i pliki wynikowe są gotowe do pobrania.
    # Wychodzimy z pętli i przechodzimy do pobierania wyników.
    if status == "Succeeded":
        break
    # Failed oznacza że Azure napotkał błąd podczas przetwarzania -  może to być uszkodzony plik audio, nieobsługiwany kodek lub błąd po stronie usługi.
    # Szczegóły błędu są w status_data i mogą zawierać kod błędu oraz opis przyczyny.
    elif status == "Failed":
        print("Błąd przetwarzania:")
        print(status_data)
        exit(1)

# Buduje URL do listy plików wynikowych zadania przez dodanie segmentu "/files" do bazowego URL zadania - jest to konwencja REST API Azure Speech.
files_url = job_url + "/files"


# Pobiera listę wszystkich plików wygenerowanych przez zakończone zadanie.
files_response = requests.get(files_url, headers=HEADERS)
print(f"files_response: {files_response}")
# "values" to lista obiektów JSON opisujących poszczególne pliki wynikowe zadania.
files = files_response.json()["values"]
print(f"files: {files}")
# Szuka wśród plików wynikowych tego z właściwą transkrypcją (kind == "Transcription").
# Azure generuje kilka plików na zadanie: właściwą transkrypcję oraz TranscriptionReport
# (raport z metadanymi, statystykami i ewentualnymi błędami dla każdego pliku audio).
transcript_url = None
for f in files:
    if f["kind"] == "Transcription":
        # contentUrl to bezpośredni, tymczasowy link do pobrania pliku JSON z wynikami,
        # hostowany na Azure Blob Storage - nie wymaga nagłówków autoryzacyjnych do pobrania.
        transcript_url = f["links"]["contentUrl"]
        break

# Pobiera plik JSON z wynikami transkrypcji bezpośrednio z Azure Storage
transcript_response = requests.get(transcript_url)
# Parsuje pobrany JSON na słownik Pythona zawierający pełne wyniki transkrypcji.
transcript_data = transcript_response.json()

# Zapisuje kompletny surowy JSON z wszystkimi danymi zwróconymi przez Azure - zawiera m.in. znaczniki czasu, współczynniki pewności (confidence scores),
# alternatywne transkrypcje (nBest) i metadane kanałów audio. Przydatne jako archiwum lub do późniejszego przetworzenia
# bez ponownego wysyłania żądania do API (co kosztuje czas i pieniądze).
with open("transkrypcja_raw.json", "w", encoding="utf-8") as f:
    # indent=2 tworzy czytelne wcięcia w pliku JSON  
    # ensure_ascii=False pozwala zapisywać polskie znaki (ą, ę, ó...) 
    json.dump(transcript_data, f, indent=2, ensure_ascii=False)

# Tworzy uproszczony, czytelny plik tekstowy z transkrypcją - jeden wiersz na rozpoznaną frazę w formacie "Speaker N: tekst".
with open("transkrypcja.txt", "w", encoding="utf-8") as f:
    # recognizedPhrases to lista wszystkich rozpoznanych fragmentów wypowiedzi. Każdy element odpowiada jednej frazie oddzielonej pauzą w nagraniu.
    for phrase in transcript_data["recognizedPhrases"]:
        # Numer Speakers przypisany przez mechanizm diarization (1, 2, 3...). Jeśli diarizationEnabled=False lub SDK nie rozpoznał mówcy, zwraca "?".
        speaker = phrase.get("speaker", "?")
        # nBest to lista alternatywnych transkrypcji posortowana malejąco według pewności. Indeks [0] to zawsze najlepsza (najbardziej prawdopodobna) propozycja.
        # Pole "display" zawiera tekst z interpunkcją i właściwą kapitalizacją,  w odróżnieniu od "lexical" (surowe słowa) i "itn" (po normalizacji liczb itp.).
        text = phrase["nBest"][0]["display"]
        f.write(f"Mówca {speaker}: {text}\n")

print("Gotowe! Sprawdź transkrypcja.txt")