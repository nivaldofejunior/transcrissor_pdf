import asyncio
import edge_tts
from google.cloud import texttospeech
import os
from dotenv import load_dotenv
from pathlib import Path
from app.utils.tratar_texto import dividir_texto_em_blocos, limpar_texto_para_tts
from pydub import AudioSegment  # Requer instalação: pip install pydub
from uuid import uuid4

# Carrega o .env do ambiente
env = os.getenv("APP_ENV", "dev")
dotenv_path = Path(f".env.{env}") if Path(f".env.{env}").exists() else Path(".env")
load_dotenv(dotenv_path=dotenv_path)

# Garante que o Google use o caminho correto da chave
google_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not google_credentials or not Path(google_credentials).exists():
    raise FileNotFoundError(f"Arquivo da chave Google não encontrado: {google_credentials}")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials

print("[DEBUG] GOOGLE_APPLICATION_CREDENTIALS:", google_credentials)



# Função com edge-tts (Microsoft)
async def gerar_audio_edge(texto: str, caminho_saida: str, voz: str = "pt-BR-AntonioNeural"):
    texto_limpo = limpar_texto_para_tts(texto)
    blocos = dividir_texto_em_blocos(texto_limpo)

    print(f"[DEBUG] Total de blocos: {len(blocos)}")

    pasta_temp = Path("temp_audios")
    pasta_temp.mkdir(exist_ok=True)

    arquivos_temp = []

    for i, bloco in enumerate(blocos):
        arquivo_temp = pasta_temp / f"{uuid4().hex}.mp3"
        arquivos_temp.append(str(arquivo_temp))

        print(f"[Edge TTS] Gerando bloco {i+1}/{len(blocos)}...")

        try:
            communicate = edge_tts.Communicate(bloco, voice=voz)
            await communicate.save(str(arquivo_temp))
        except Exception as e:
            print(f"[Edge TTS] Erro no bloco {i+1}: {e}")

    # Junta todos os MP3s
    audio_final = AudioSegment.empty()
    for arquivo in arquivos_temp:
        audio_final += AudioSegment.from_file(arquivo, format="mp3")

    audio_final.export(caminho_saida, format="mp3")

    # Limpa arquivos temporários
    for arquivo in arquivos_temp:
        os.remove(arquivo)
    pasta_temp.rmdir()

    print(f"[Edge TTS] Áudio final gerado em {caminho_saida}")


def gerar_audio_google(texto: str, caminho_saida: str, voz: str = "pt-BR-Wavenet-A", pausas: bool = True):

    client = texttospeech.TextToSpeechClient()
    texto_limpo = limpar_texto_para_tts(texto)
    blocos = dividir_texto_em_blocos(texto_limpo)    

    print(f"[DEBUG] Total de blocos: {len(blocos)}")
    for i, b in enumerate(blocos):
        print(f"  Bloco {i+1}: {len(b.encode('utf-8'))} bytes")

    with open(caminho_saida, "wb") as out:
        for i, bloco in enumerate(blocos):
            try:
                if pausas:
                    ssml = "<speak>" + bloco.replace(".", '.<break time="500ms"/>').replace("\n", "<break time=\"700ms\"/>") + "</speak>"
                    input_data = texttospeech.SynthesisInput(ssml=ssml)
                else:
                    input_data = texttospeech.SynthesisInput(text=bloco)

                voice_params = texttospeech.VoiceSelectionParams(
                    language_code="pt-BR",
                    name=voz,
                    ssml_gender=texttospeech.SsmlVoiceGender.MALE
                )

                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=1.0,
                    pitch=0.0
                )

                response = client.synthesize_speech(
                    input=input_data,
                    voice=voice_params,
                    audio_config=audio_config
                )
                out.write(response.audio_content)
                print(f"[Google TTS] Bloco {i+1}/{len(blocos)} gerado com sucesso.")
            except Exception as e:
                print(f"[Google TTS] Erro no bloco {i+1}: {e}")