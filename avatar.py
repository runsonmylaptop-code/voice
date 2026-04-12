# wczytuje zmienne środowiskowe z pliku .env
from dotenv import load_dotenv 
# dostęp do zmiennych systemowych
import os  
# generowanie unikalnych identyfikatorów
import uuid  
# wysyłanie zapytań HTTP do API Azure
import requests  
# funkcja sleep do czekania między zapytaniami
import time 

# ładuje zmienne z pliku .env do środowiska
load_dotenv() 

key = os.getenv("KEY")
region = os.getenv("REGION") 

# sprawdza czy obie zmienne są dostępne
if not key or not region:  
    # przerywa jeśli brakuje konfiguracji
    raise ValueError("Brak key lub region w .env")  

# tworzy unikalną nazwę zadania, np. "avatar-3f2a1b9c"
job_id = f"avatar-{uuid.uuid4()}"  

# tekst który avatar ma wypowiedzieć
tekst = "Pozdrawiam Państwa i dziękuja za zajęcia, do usłyszenia!"  

# URL endpointu API dla konkretnego zadania
BASE_URL = f"https://{region}.api.cognitive.microsoft.com/avatar/batchsyntheses/{job_id}?api-version=2024-08-01"  

HEADERS = {
    # nagłówek autoryzacyjny wymagany przez Azure
    "Ocp-Apim-Subscription-Key": key,  
    # informuje API że wysyłamy dane w formacie JSON
    "Content-Type": "application/json"  
}

payload = {
    # typ wejścia - zwykły tekst (alternatywa: SSML)
    "inputKind": "plainText",  
    "synthesisConfig": {
         # głos do syntezy mowy - polska Zofia
        "voice": "pl-PL-ZofiaNeural" 
    },
    "inputs": [
        # właściwy tekst do wypowiedzenia
        {"content": tekst}  
    ],
    "avatarConfig": {
        # wybrana postać avatara
        "talkingAvatarCharacter": "Lisa", 
        # styl/poza avatara
        "talkingAvatarStyle": "graceful-sitting",  
        # format wyjściowego pliku wideo
        "videoFormat": "mp4",  
        # kodek wideo (szeroka kompatybilność)
        "videoCodec": "h264",  
        # kolor tła w formacie RGBA hex
        "backgroundColor": "#928cceff"  
    }
}

# wysyła żądanie PUT aby utworzyć zadanie syntezy - Azure zwraca 201 jeśli się udało
response = requests.put(BASE_URL, headers=HEADERS, json=payload)  

# jeśli odpowiedź to nie "Created"
if response.status_code != 201:  
    print(f"Błąd: {response.status_code}")
    print(response.json())  # można podejrzeć jak wygląda zwracany json
    exit(1)  # kończy program 

print("Utworzono zadanie ..")

# pętla odpytująca API do czasu zakończenia zadania
while True: 
    # czeka 5 sekund przed kolejnym sprawdzeniem statusu
    time.sleep(5)  
    # odpytuje API o aktualny status zadania
    status_respoone = requests.get(BASE_URL, headers=HEADERS)  
    status_data = status_respoone.json() 
    # wyciąga pole "status" z odpowiedzi
    status = status_data.get("status")  

    print(f"Status {status}")

    # zadanie zakończone sukcesem - wychodzimy z pętli
    if status == "Succeeded":  
        break
    # zadanie nie powiodło się
    elif status == "Failed":  
        print("Nie udało się utworzyć")
        # wyświetla pełną odpowiedź z informacją o błędzie
        print(status_data)  
        exit(1)

# wyciąga URL do gotowego pliku wideo z odpowiedzi
video_url = status_data["outputs"]["result"]  

print(f"Video URL: {video_url}")

# pobiera plik wideo spod wygenerowanego URL
video_respone = requests.get(video_url)  

 # otwiera plik do zapisu w trybie binarnym
with open("avatar.mp4", "wb") as f: 
    # zapisuje pobrany plik wideo na dysk
    f.write(video_respone.content)  