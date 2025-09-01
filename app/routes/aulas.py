from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from typing import Optional, List
from bson import ObjectId
from datetime import datetime
from pathlib import Path
import unicodedata

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.models.aula import AulaCreate, AulaInDB
from app.models.pdf import PdfInDB
from app.deps.auth import get_usuario_atual, UsuarioToken

from app.core.paths import pdf_path, audio_path  # data/pdfs/<usuario>/<aula>/<pdf>.pdf
from app.tasks.audio import gerar_audio_google_task

router = APIRouter()

# =====================================================================================
# AULAS
# =====================================================================================

@router.post("/aulas/", response_model=AulaInDB)
async def criar_aula(
    aula: AulaCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Cria uma nova aula vinculada a uma matéria existente do usuário logado.
    """
    # Garante que a matéria existe e pertence ao usuário
    materia = await db.materias.find_one({"_id": ObjectId(aula.materia_id), "usuario_id": user.id})
    if not materia:
        raise HTTPException(status_code=404, detail="Matéria não encontrada")

    aula_dict = {
        "titulo": aula.titulo,
        "descricao": aula.descricao,
        "materia_id": aula.materia_id,
        "usuario_id": user.id,
        "data_upload": datetime.utcnow(),
    }

    result = await db.aulas.insert_one(aula_dict)
    return AulaInDB(id=str(result.inserted_id), **aula_dict)

@router.get("/aulas/", response_model=List[AulaInDB])
async def listar_aulas(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Lista as aulas do usuário logado.
    """
    aulas: List[AulaInDB] = []
    cursor = db.aulas.find({"usuario_id": user.id}).sort("data_upload", -1)
    async for aula in cursor:
        aula["id"] = str(aula.pop("_id"))
        aula.setdefault("descricao", None)
        aula.setdefault("audio_path", None)
        aulas.append(AulaInDB(**aula))
    return aulas


@router.get("/aulas/materia/{materia_id}", response_model=List[AulaInDB])
async def listar_aulas_por_materia(
    materia_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Lista as aulas da matéria informada (apenas do usuário logado).
    """
    # Garante que a matéria pertence ao usuário
    materia = await db.materias.find_one({"_id": ObjectId(materia_id), "usuario_id": user.id})
    if not materia:
        raise HTTPException(status_code=404, detail="Matéria não encontrada")

    aulas: List[AulaInDB] = []
    cursor = db.aulas.find({"usuario_id": user.id, "materia_id": materia_id}).sort("data_upload", -1)
    async for aula in cursor:
        aula["id"] = str(aula.pop("_id"))
        aulas.append(AulaInDB(**aula))
    return aulas

# =====================================================================================
# PDFs DA AULA
# =====================================================================================

@router.post("/aulas/{aula_id}/pdfs/", response_model=PdfInDB)
async def upload_pdf(
    aula_id: str,
    file: UploadFile = File(...),
    descricao: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Faz upload de um PDF para uma aula do usuário e dispara task de processamento.
    """
    # Aula precisa ser do usuário
    aula = await db.aulas.find_one({"_id": ObjectId(aula_id), "usuario_id": user.id})
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    # Normaliza o nome do arquivo (ASCII-safe)
    nome_arquivo = (
        unicodedata.normalize("NFKD", file.filename)
        .encode("ASCII", "ignore").decode("utf-8")
        .replace(" ", "_")
    )

    # Cria doc no Mongo primeiro para ter o pdf_id
    pdf_data = {
        "usuario_id": user.id,
        "aula_id": aula_id,               # segue teu padrão (string)
        "filename": nome_arquivo,
        "descricao": descricao,
        "caminho": "",                    # preenchido após salvar
        "transcricao": None,
        "audio_path": None,
        "data_upload": datetime.utcnow(),
        "status": "processando",
    }
    result = await db.pdfs.insert_one(pdf_data)
    pdf_id = str(result.inserted_id)

    # Salva o arquivo no layout por usuário
    destino = pdf_path(str(user.id), aula_id, pdf_id)  # data/pdfs/<user>/<aula>/<pdf>.pdf
    destino.parent.mkdir(parents=True, exist_ok=True)
    contents = await file.read()
    destino.write_bytes(contents)

    # Atualiza caminho no Mongo
    await db.pdfs.update_one({"_id": result.inserted_id}, {"$set": {"caminho": str(destino)}})
    pdf_saved = await db.pdfs.find_one({"_id": result.inserted_id})

    # Dispara processamento completo no Celery (como no teu código)
    gerar_audio_google_task.delay(pdf_id)

    pdf_saved["id"] = str(pdf_saved.pop("_id"))
    return PdfInDB(**pdf_saved)

@router.get("/aulas/{aula_id}/pdfs", response_model=List[PdfInDB])
async def listar_pdfs_da_aula(
    aula_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Lista os PDFs de uma aula específica do usuário.
    """
    aula = await db.aulas.find_one({"_id": ObjectId(aula_id), "usuario_id": user.id})
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    pdfs: List[PdfInDB] = []
    cursor = db.pdfs.find({"usuario_id": user.id, "aula_id": aula_id}).sort("data_upload", -1)
    async for pdf in cursor:
        pdf["id"] = str(pdf.pop("_id"))
        pdfs.append(PdfInDB(**pdf))
    return pdfs

# =====================================================================================
# ÁUDIO
# =====================================================================================

@router.post("/pdfs/{pdf_id}/gerar-audio", response_model=PdfInDB)
async def gerar_audio_pdf(
    pdf_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    (Manual) Gera áudio com Edge TTS a partir da transcrição de um PDF do usuário.
    """
    pdf = await db.pdfs.find_one({"_id": ObjectId(pdf_id), "usuario_id": user.id})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF não encontrado")

    if not pdf.get("transcricao"):
        raise HTTPException(status_code=400, detail="Este PDF ainda não possui transcrição.")

    # Caminho padronizado para o áudio
    aula_id = pdf["aula_id"]
    dest_audio = audio_path(str(user.id), aula_id, pdf_id, ext="mp3")
    dest_audio.parent.mkdir(parents=True, exist_ok=True)

    # Lazy import para evitar ciclos
    from app.services.audio_generator import gerar_audio_edge

    try:
        await gerar_audio_edge(pdf["transcricao"], str(dest_audio))
        await db.pdfs.update_one(
            {"_id": ObjectId(pdf_id)},
            {"$set": {"audio_path": str(dest_audio)}}
        )
        pdf["audio_path"] = str(dest_audio)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar áudio: {e}")

    pdf["id"] = str(pdf["_id"])
    return PdfInDB(**pdf)


@router.post("/pdfs/{pdf_id}/gerar-audio-google")
async def gerar_audio_pdf_google(
    pdf_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    # Verifica posse antes de enfileirar
    pdf = await db.pdfs.find_one({"_id": ObjectId(pdf_id), "usuario_id": user.id})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF não encontrado")
    gerar_audio_google_task.delay(pdf_id)
    return {"mensagem": "Tarefa de geração de áudio iniciada com sucesso"}


@router.get("/pdfs/{pdf_id}/audio", response_class=FileResponse)
async def baixar_audio_pdf(
    pdf_id: str,
    download: bool = False,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Toca ou baixa o áudio do PDF do usuário (conforme `download`).
    """
    pdf = await db.pdfs.find_one({"_id": ObjectId(pdf_id), "usuario_id": user.id})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF não encontrado")

    # Recalcula o caminho padronizado; se o doc tiver um caminho antigo, usamos ele como fallback
    aula_id = pdf["aula_id"]
    padrao = audio_path(str(user.id), aula_id, pdf_id, ext="mp3")
    caminho = Path(pdf.get("audio_path") or padrao)

    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Áudio ainda não foi gerado para este PDF.")

    filename = caminho.name
    safe_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'

    return FileResponse(
        path=str(caminho),
        filename=safe_name,
        media_type="audio/mpeg",
        headers=headers
    )

# =====================================================================================
# EXCLUSÕES (com verificação de posse)
# =====================================================================================

@router.delete("/pdfs/{pdf_id}")
async def excluir_pdf(
    pdf_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Exclui um PDF do usuário.
    """
    pdf = await db.pdfs.find_one({"_id": ObjectId(pdf_id), "usuario_id": user.id})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF não encontrado")

    aula_id = pdf["aula_id"]
    caminho_pdf = Path(pdf.get("caminho") or pdf_path(str(user.id), aula_id, pdf_id))
    caminho_audio = Path(pdf.get("audio_path") or audio_path(str(user.id), aula_id, pdf_id, ext="mp3"))

    # Best-effort removal
    for p in (caminho_pdf, caminho_audio):
        try:
            if p.exists():
                p.unlink(missing_ok=True)
        except Exception:
            pass

    await db.pdfs.delete_one({"_id": ObjectId(pdf_id)})
    return {"mensagem": "PDF excluído com sucesso"}


@router.delete("/aulas/{aula_id}")
async def excluir_aula(
    aula_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Exclui uma aula do usuário e todos os seus PDFs.
    """
    aula = await db.aulas.find_one({"_id": ObjectId(aula_id), "usuario_id": user.id})
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    # Exclui PDFs da aula (e arquivos físicos de forma best-effort)
    cursor = db.pdfs.find({"usuario_id": user.id, "aula_id": aula_id})
    async for pdf in cursor:
        try:
            aid = pdf["aula_id"]
            p_pdf = Path(pdf.get("caminho") or pdf_path(str(user.id), aid, str(pdf["_id"])))
            p_audio = Path(pdf.get("audio_path") or audio_path(str(user.id), aid, str(pdf["_id"]), ext="mp3"))
            if p_pdf.exists():
                p_pdf.unlink(missing_ok=True)
            if p_audio.exists():
                p_audio.unlink(missing_ok=True)
        except Exception:
            pass

    await db.pdfs.delete_many({"usuario_id": user.id, "aula_id": aula_id})
    resultado = await db.aulas.delete_one({"_id": ObjectId(aula_id), "usuario_id": user.id})

    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    return {"mensagem": "Aula e seus PDFs excluídos com sucesso"}


@router.delete("/materias/{materia_id}")
async def excluir_materia(
    materia_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Exclui uma matéria do usuário, suas aulas e PDFs.
    """
    materia = await db.materias.find_one({"_id": ObjectId(materia_id), "usuario_id": user.id})
    if not materia:
        raise HTTPException(status_code=404, detail="Matéria não encontrada")

    # Aulas da matéria (do usuário)
    aulas = await db.aulas.find({"usuario_id": user.id, "materia_id": materia_id}).to_list(length=None)
    aula_ids = [str(a["_id"]) for a in aulas]

    if aula_ids:
        # PDFs das aulas da matéria
        cursor = db.pdfs.find({"usuario_id": user.id, "aula_id": {"$in": aula_ids}})
        async for pdf in cursor:
            try:
                aid = pdf["aula_id"]
                p_pdf = Path(pdf.get("caminho") or pdf_path(str(user.id), aid, str(pdf["_id"])))
                p_audio = Path(pdf.get("audio_path") or audio_path(str(user.id), aid, str(pdf["_id"]), ext="mp3"))
                if p_pdf.exists():
                    p_pdf.unlink(missing_ok=True)
                if p_audio.exists():
                    p_audio.unlink(missing_ok=True)
            except Exception:
                pass
        await db.pdfs.delete_many({"usuario_id": user.id, "aula_id": {"$in": aula_ids}})

    await db.aulas.delete_many({"usuario_id": user.id, "materia_id": materia_id})
    await db.materias.delete_one({"_id": ObjectId(materia_id), "usuario_id": user.id})

    return {"mensagem": "Matéria, aulas e PDFs relacionados excluídos com sucesso"}
