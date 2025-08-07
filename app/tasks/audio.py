from app.tasks.celery_app import celery_app
from app.services.audio_generator import gerar_audio_google
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import asyncio
import requests

MONGO_URI = os.getenv("MONGO_URI")
BACKEND_URL = os.getenv("BACKEND_URL", "http://api:8001")

@celery_app.task(name="app.tasks.audio.gerar_audio_google_task")
def gerar_audio_google_task(pdf_id: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = AsyncIOMotorClient(MONGO_URI)
    db = client["projeto_t_db"]

    try:
        # 1. Buscar o PDF
        pdf = loop.run_until_complete(db.pdfs.find_one({"_id": ObjectId(pdf_id)}))
        if not pdf or not pdf.get("transcricao"):
            print(f"[Celery] PDF {pdf_id} não encontrado ou sem transcrição.")
            return

        # 2. Gerar áudio
        pasta = os.path.dirname(pdf["caminho"])
        nome_arquivo_base = os.path.splitext(pdf["filename"])[0]
        caminho_audio = os.path.join(pasta, f"{nome_arquivo_base}_google.mp3")

        gerar_audio_google(pdf["transcricao"], caminho_audio)

        # 3. Atualizar caminho do áudio no banco
        loop.run_until_complete(db.pdfs.update_one(
            {"_id": ObjectId(pdf_id)},
            {"$set": {"audio_path": caminho_audio}}
        ))

        # 4. Enviar POST para o backend informando que concluiu
        requests.post(
            f"{BACKEND_URL}/eventos/pdf-audio",
            json={"pdf_id": pdf_id, "status": "concluido"},
            timeout=10
        )

        print(f"[Celery] Áudio gerado com sucesso para PDF {pdf_id}")

    except Exception as e:
        # Enviar erro ao backend
        try:
            requests.post(
                f"{BACKEND_URL}/eventos/pdf-audio",
                json={"pdf_id": pdf_id, "status": "erro", "erro": str(e)},
                timeout=10
            )
        except Exception as post_err:
            print(f"[Celery] Falha ao notificar erro: {post_err}")

        print(f"[Celery] Erro ao gerar áudio para PDF {pdf_id}: {e}")
        raise e

    finally:
        client.close()
