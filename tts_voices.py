from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk

load_dotenv()

key = os.getenv("KEY")
region = os.getenv("REGION")

if not key or not region:
    raise ValueError("Brak key lub region w .env")

# Lista trzech polskich głosów neuronowych Azure:
VOICES = [
    "pl-PL-ZofiaNeural",
    "pl-PL-AgnieszkaNeural",
    "pl-PL-MarekNeural"
]

speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
# Jeden audio_config dla wszystkich głosów - nie zmienia się między iteracjami
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

for voice in VOICES:
    # nadpisuje głos przed każdą syntezą
    speech_config.speech_synthesis_voice_name = voice      

    # Synthesizer tworzony na nowo w każdej iteracji - konieczne, bo zmieniamy voice w speech_config a to nie wpływa na już utworzony synthesizer.
    # Synthesizer "zapamiętuje" głos z momentu swojego utworzenia.
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    print(f"Głos: {voice}")

    # voice.split('-') rozbija string "pl-PL-ZofiaNeural" na listę ["pl", "PL", "ZofiaNeural"]
    # [2] bierze trzeci element czyli "ZofiaNeural" - sama nazwa głosu bez przedrostka języka
    result = synthesizer.speak_text_async(f"Cześć, nazywam się {voice.split('-')[2].replace("Neural", "")}").get()
