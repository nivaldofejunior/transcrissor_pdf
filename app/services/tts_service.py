import fitz  # PyMuPDF
from gtts import gTTS
import os
from uuid import uuid4

AUDIO_DIR = "data/audios"
os.makedirs(AUDIO_DIR, exist_ok=True)

def extrair_texto_pdf(caminho_pdf: str) -> str:
    texto = ""
    with fitz.open(caminho_pdf) as doc:
        for pagina in doc:
            texto += pagina.get_text()
    return texto.strip()

def gerar_audio(texto: str, nome_base: str) -> str:
    caminho_audio = os.path.join(AUDIO_DIR, f"{nome_base}.mp3")
    tts = gTTS(text=texto, lang='pt')
    tts.save(caminho_audio)
    return caminho_audio
