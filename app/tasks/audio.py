# app/tasks/audio.py
from app.tasks.celery_app import celery_app

import os
from pathlib import Path
from typing import Optional
import requests
from bson import ObjectId
from pymongo import MongoClient

from app.core.paths import audio_path
from app.services.pdf_extractor import extrair_texto_pdf
from app.services.text_cleaner import limpar_transcricao
from app.services.ia_service import melhorar_pontuacao_com_gemini
from app.services.audio_generator import gerar_audio_google  # síncrona

# ---- ENV ----
# Usa a mesma MONGO_URI que a API (vinda do .env). Não force outro DB aqui.
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI", "mongodb://mongodb:27017/projeto_t_db")
DB_NAME = os.getenv("DB_NAME", "projeto_t_db")

BACKEND_URL = (os.getenv("BACKEND_URL", "http://api:8001/api") or "").rstrip("/")
DATA_DIR = os.getenv("DATA_DIR", "data")

def _log(msg: str):
    print(f"[task.audio] {msg}", flush=True)

def _get_db():
    client = MongoClient(MONGO_URI)
    db = client.get_default_database()  # vai funcionar porque tua URI inclui /projeto_t_db
    return client, db

def _post_evento(*, status: str, pdf_id: str, erro: Optional[str] = None) -> None:
    if not BACKEND_URL:
        _log("BACKEND_URL vazio; pulando POST de evento")
        return
    try:
        url = f"{BACKEND_URL}/eventos/pdf-audio"
        r = requests.post(url, json={"pdf_id": pdf_id, "status": status, "erro": erro}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        _log(f"Falha ao notificar backend: {e}")

@celery_app.task(name="app.tasks.audio.gerar_audio_google_task")
def gerar_audio_google_task(pdf_id: str):
    client, db = _get_db()
    _log(f"INICIO pdf_id={pdf_id} DATA_DIR={DATA_DIR} MONGO_URI={MONGO_URI} DB={db.name}")

    try:
        doc = db.pdfs.find_one({"_id": ObjectId(pdf_id)})
        if not doc:
            _log(f"PDF {pdf_id} não encontrado no Mongo")
            _post_evento(status="erro", pdf_id=pdf_id, erro="PDF não encontrado")
            return

        user_id = str(doc.get("usuario_id") or "")
        aula_id = doc.get("aula_id")
        caminho_pdf = doc.get("caminho")

        if not user_id or not aula_id or not caminho_pdf:
            _log(f"Documento incompleto: usuario_id={user_id} aula_id={aula_id} caminho={caminho_pdf}")
            db.pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": {"status": "erro"}})
            _post_evento(status="erro", pdf_id=pdf_id, erro="Documento incompleto (usuario_id/aula_id/caminho)")
            return

        pdf_path_fs = Path(caminho_pdf)
        if not pdf_path_fs.exists():
            _log(f"PDF não existe no worker: {pdf_path_fs}")
            db.pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": {"status": "erro"}})
            _post_evento(status="erro", pdf_id=pdf_id, erro="Arquivo PDF inexistente no worker")
            return

        db.pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": {"status": "processando"}})

        texto = doc.get("transcricao")
        if not texto:
            _log("Extraindo texto do PDF...")
            try:
                texto_cru = extrair_texto_pdf(str(pdf_path_fs))
            except Exception as e:
                _log(f"Falha ao extrair texto: {e}")
                db.pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": {"status": "erro"}})
                _post_evento(status="erro", pdf_id=pdf_id, erro=f"Falha ao extrair texto: {e}")
                return

            if not texto_cru or not texto_cru.strip():
                _log("Texto extraído vazio")
                db.pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": {"status": "erro"}})
                _post_evento(status="erro", pdf_id=pdf_id, erro="Texto vazio após extração")
                return

            _log("Limpando transcrição...")
            texto_limpo = limpar_transcricao(texto_cru) or texto_cru

            try:
                _log("Melhorando pontuação com IA...")
                texto = melhorar_pontuacao_com_gemini(texto_limpo) or texto_limpo
            except Exception as e:
                _log(f"Falha na IA de pontuação (seguindo com texto limpo): {e}")
                texto = texto_limpo

            db.pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": {"transcricao": texto}})
        else:
            _log("Transcrição já existe. Pulando extração.")

        dest_audio = audio_path(user_id, aula_id, pdf_id, ext="mp3")
        dest_audio.parent.mkdir(parents=True, exist_ok=True)
        _log(f"Gerando áudio em: {dest_audio}")
        try:
            gerar_audio_google(texto, str(dest_audio))
        except Exception as e:
            _log(f"Falha ao gerar áudio: {e}")
            db.pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": {"status": "erro"}})
            _post_evento(status="erro", pdf_id=pdf_id, erro=f"Falha ao gerar áudio: {e}")
            return

        db.pdfs.update_one(
            {"_id": ObjectId(pdf_id)},
            {"$set": {"audio_path": str(dest_audio), "status": "concluido"}}
        )
        _post_evento(status="concluido", pdf_id=pdf_id)
        _log("SUCESSO: áudio gerado e documento atualizado")

    except Exception as e:
        _log(f"ERRO geral na task: {e}")
        try:
            db.pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": {"status": "erro"}})
        except Exception:
            pass
        _post_evento(status="erro", pdf_id=pdf_id, erro=str(e))
    finally:
        client.close()
