# app/tasks/audio.py
from app.tasks.celery_app import celery_app
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

import os
import asyncio
import requests

from app.services.pdf_extractor import extrair_texto_pdf
from app.services.text_cleaner import limpar_transcricao
from app.services.ia_service import melhorar_pontuacao_com_gemini
from app.services.audio_generator import gerar_audio_google

MONGO_URI = os.getenv("MONGO_URI")
# no .env: BACKEND_URL=http://api:8001/api   (sem aspas!)
BACKEND_URL = os.getenv("BACKEND_URL", "http://api:8001/api")


@celery_app.task(name="app.tasks.audio.gerar_audio_google_task")
def gerar_audio_google_task(pdf_id: str):
    """
    Pipeline completo no worker:
      - carrega registro do PDF
      - extrai texto do PDF
      - limpa + melhora pontuação com IA (fallback em caso de erro)
      - gera áudio (Google TTS)
      - atualiza Mongo (transcrição / audio_path)
      - notifica FastAPI via POST /api/eventos/pdf-audio (SSE no backend)
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = AsyncIOMotorClient(MONGO_URI)
    db = client["projeto_t_db"]

    try:
        # 1) Carregar registro do PDF
        pdf = loop.run_until_complete(db.pdfs.find_one({"_id": ObjectId(pdf_id)}))
        if not pdf:
            print(f"[Celery] PDF {pdf_id} não encontrado.")
            _post_evento(status="erro", pdf_id=pdf_id, erro="PDF não encontrado no banco.")
            return

        caminho_pdf = pdf.get("caminho")
        if not caminho_pdf or not os.path.exists(caminho_pdf):
            _post_evento(status="erro", pdf_id=pdf_id, erro="Caminho do PDF ausente ou inexistente.")
            return

        # 2) Extrair + limpar + IA (pontuação)
        try:
            transcricao_crua = extrair_texto_pdf(caminho_pdf)
            transcricao_limpa = limpar_transcricao(transcricao_crua)

            try:
                transcricao_melhorada = melhorar_pontuacao_com_gemini(transcricao_limpa)
            except Exception as e_ia:
                print(f"[WARN] Falha na IA de pontuação: {e_ia}")
                transcricao_melhorada = transcricao_limpa

            loop.run_until_complete(db.pdfs.update_one(
                {"_id": ObjectId(pdf_id)},
                {"$set": {"transcricao": transcricao_melhorada}}
            ))
        except Exception as e_tx:
            _post_evento(status="erro", pdf_id=pdf_id, erro=f"Falha ao processar texto: {e_tx}")
            return

        # 3) Gerar TTS (Google)
        pasta = os.path.dirname(caminho_pdf)
        nome_base = os.path.splitext(pdf["filename"])[0]
        caminho_audio = os.path.join(pasta, f"{nome_base}_google.mp3")

        try:
            gerar_audio_google(transcricao_melhorada, caminho_audio)
        except Exception as e_tts:
            _post_evento(status="erro", pdf_id=pdf_id, erro=f"Falha ao gerar áudio: {e_tts}")
            return

        loop.run_until_complete(db.pdfs.update_one(
            {"_id": ObjectId(pdf_id)},
            {"$set": {"audio_path": caminho_audio}}
        ))

        # 4) Sucesso → POST evento (FastAPI atualiza status + emite SSE)
        _post_evento(status="concluido", pdf_id=pdf_id)

        print(f"[Celery] Pipeline concluído para PDF {pdf_id}")

    except Exception as e:
        # fallback geral
        try:
            _post_evento(status="erro", pdf_id=pdf_id, erro=str(e))
        except Exception as post_err:
            print(f"[Celery] Falha ao notificar erro: {post_err}")
        raise
    finally:
        client.close()


def _post_evento(*, status: str, pdf_id: str, erro: str | None = None) -> None:
    """
    Notifica o backend FastAPI (container api) para:
      - atualizar status no Mongo
      - publicar evento SSE para o frontend
    """
    base = BACKEND_URL.rstrip("/")  # evita "//"
    url = f"{base}/eventos/pdf-audio"
    payload = {"pdf_id": pdf_id, "status": status, "erro": erro}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
