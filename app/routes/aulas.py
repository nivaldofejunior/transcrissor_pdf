from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from typing import Optional, List
from bson import ObjectId
from datetime import datetime
import os
import unicodedata

from app.db.mongo import get_db
from app.models.aula import AulaCreate, AulaInDB
from app.models.pdf import PdfInDB
from app.services.pdf_extractor import extrair_texto_pdf
from app.services.text_cleaner import limpar_transcricao
from app.services.audio_generator import gerar_audio_edge, gerar_audio_google
from app.services.ia_service import melhorar_pontuacao_com_gemini
from app.tasks.audio import gerar_audio_google_task

router = APIRouter()

@router.post("/aulas/", response_model=AulaInDB)
async def criar_aula(aula: AulaCreate, db=Depends(get_db)):
    """
    Cria uma nova aula vinculada a uma matéria existente.
    Retorna os dados completos da aula criada.
    """
    materia = await db.materias.find_one({"_id": ObjectId(aula.materia_id)})
    if not materia:
        raise HTTPException(status_code=404, detail="Matéria não encontrada")

    aula_dict = {
        "titulo": aula.titulo,
        "descricao": aula.descricao,
        "materia_id": aula.materia_id,
        "pdf_path": "",
        "audio_path": None,
        "audio_gerado": False,
        "data_upload": datetime.utcnow()
    }

    result = await db.aulas.insert_one(aula_dict)
    return AulaInDB(id=str(result.inserted_id), **aula_dict)

@router.post("/aulas/{aula_id}/pdfs/", response_model=PdfInDB)
async def upload_pdf(
    aula_id: str,
    file: UploadFile = File(...),
    descricao: Optional[str] = None,
    db=Depends(get_db)
):
    aula = await db.aulas.find_one({"_id": ObjectId(aula_id)})
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    pasta = f"data/aulas/{aula_id}"
    os.makedirs(pasta, exist_ok=True)

    nome_arquivo = unicodedata.normalize("NFKD", file.filename)\
        .encode("ASCII", "ignore").decode("utf-8").replace(" ", "_")
    caminho_pdf = os.path.join(pasta, nome_arquivo)

    with open(caminho_pdf, "wb") as f:
        f.write(await file.read())

    pdf_data = {
        "aula_id": aula_id,
        "filename": nome_arquivo,
        "descricao": descricao,
        "caminho": caminho_pdf,
        "transcricao": None,          # agora vai ser preenchido pela task
        "audio_path": None,           # idem
        "data_upload": datetime.utcnow(),
        "status": "processando"
    }

    result = await db.pdfs.insert_one(pdf_data)
    pdf_id = str(result.inserted_id)

    # 🔥 Dispara processamento completo no Celery
    gerar_audio_google_task.delay(pdf_id)

    pdf_data.pop("_id", None)
    return PdfInDB(id=pdf_id, **pdf_data)

@router.get("/aulas/", response_model=List[AulaInDB])
async def listar_aulas(db=Depends(get_db)):
    """
    Lista todas as aulas cadastradas no sistema.
    Retorna uma lista com os dados completos de cada aula.
    """
    aulas = []
    cursor = db.aulas.find()
    async for aula in cursor:
        aula["id"] = str(aula.pop("_id"))

        # Garante que os campos opcionais estejam presentes no dicionário
        aula.setdefault("descricao", None)
        aula.setdefault("audio_path", None)

        aulas.append(AulaInDB(**aula))
    return aulas

@router.get("/aulas/materia/{materia_id}", response_model=List[AulaInDB])
async def listar_aulas_por_materia(materia_id: str, db=Depends(get_db)):
    """
    Lista todas as aulas vinculadas a uma matéria específica.
    Retorna os dados completos das aulas associadas ao ID da matéria informado.
    """
    aulas = []
    cursor = db.aulas.find({"materia_id": materia_id})
    async for aula in cursor:
        aula["id"] = str(aula.pop("_id"))
        aulas.append(AulaInDB(**aula))
    return aulas

@router.get("/aulas/{aula_id}/pdfs")
async def listar_pdfs_da_aula(aula_id: str, db=Depends(get_db)):
    """
    Lista os PDFs vinculados a uma aula específica.
    Retorna o ID do PDF, transcrição e caminho do áudio (se houver).
    """

    pdfs = []
    cursor = db.pdfs.find({"aula_id": aula_id})  # <-- string mesmo
    async for pdf in cursor:
        pdfs.append({
            "id": str(pdf["_id"]),
            "transcricao": pdf.get("transcricao"),
            "audio": pdf.get("audio_path")
        })
    return pdfs

@router.post("/pdfs/{pdf_id}/gerar-audio", response_model=PdfInDB)
async def gerar_audio_pdf(pdf_id: str, db=Depends(get_db)):
    """
    Gera manualmente um arquivo de áudio a partir da transcrição de um PDF específico,
    utilizando o mecanismo de texto para fala Edge.
    Atualiza o caminho do áudio no banco e retorna os dados do PDF.
    """
    pdf = await db.pdfs.find_one({"_id": ObjectId(pdf_id)})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF não encontrado")

    if not pdf.get("transcricao"):
        raise HTTPException(status_code=400, detail="Este PDF ainda não possui transcrição.")

    pasta = os.path.dirname(pdf["caminho"])
    nome_arquivo_base = os.path.splitext(pdf["filename"])[0]
    caminho_audio = os.path.join(pasta, f"{nome_arquivo_base}.mp3")

    try:
        await gerar_audio_edge(pdf["transcricao"], caminho_audio)
        await db.pdfs.update_one(
            {"_id": ObjectId(pdf_id)},
            {"$set": {"audio_path": caminho_audio}}
        )
        pdf["audio_path"] = caminho_audio
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar áudio: {e}")

    pdf["id"] = str(pdf["_id"])
    return PdfInDB(**pdf)

@router.post("/pdfs/{pdf_id}/gerar-audio-google")
async def gerar_audio_pdf_google(pdf_id: str, db=Depends(get_db)):
    gerar_audio_google_task.delay(pdf_id)
    return {"mensagem": "Tarefa de geração de áudio iniciada com sucesso"}

@router.get("/pdfs/{pdf_id}/audio", response_class=FileResponse)
async def baixar_audio_pdf(pdf_id: str, download: bool = False, db=Depends(get_db)):
    """
    Toca ou baixa o áudio do PDF, dependendo do parâmetro `download`.
    - `?download=true` → força o download
    - Sem parâmetro → toca direto no navegador
    """
    pdf = await db.pdfs.find_one({"_id": ObjectId(pdf_id)})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF não encontrado")

    audio_path = pdf.get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Áudio ainda não foi gerado para este PDF.")

    filename = os.path.basename(audio_path)
    safe_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'

    return FileResponse(
        path=audio_path,
        filename=safe_name,
        media_type="audio/mpeg",
        headers=headers
    )

    """
    Faz o download do arquivo de áudio gerado a partir da transcrição de um PDF específico.
    Garante que o nome do arquivo esteja em formato seguro para o cabeçalho HTTP.
    """
    pdf = await db.pdfs.find_one({"_id": ObjectId(pdf_id)})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF não encontrado")

    audio_path = pdf.get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Áudio ainda não foi gerado para este PDF.")

    # Garante nome compatível com encoding do header
    original_name = os.path.basename(audio_path)
    safe_name = unicodedata.normalize("NFKD", original_name).encode("ascii", "ignore").decode("ascii")

    return FileResponse(
        path=audio_path,
        filename=safe_name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'}
    )

@router.delete("/pdfs/{pdf_id}")
async def excluir_pdf(pdf_id: str, db=Depends(get_db)):
    """
    Exclui um PDF específico pelo ID.
    Retorna uma mensagem de confirmação se a exclusão for bem-sucedida.
    """
    resultado = await db.pdfs.delete_one({"_id": ObjectId(pdf_id)})

    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="PDF não encontrado")

    return {"mensagem": "PDF excluído com sucesso"}

@router.delete("/aulas/{aula_id}")
async def excluir_aula(aula_id: str, db=Depends(get_db)):
    """
    Exclui uma aula específica pelo ID e remove todos os PDFs vinculados a ela.
    Retorna uma mensagem de confirmação se a exclusão for bem-sucedida.
    """

    # Exclui os PDFs relacionados à aula
    await db.pdfs.delete_many({"aula_id": aula_id})

    # Exclui a aula em si
    resultado = await db.aulas.delete_one({"_id": ObjectId(aula_id)})

    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    return {"mensagem": "Aula e seus PDFs excluídos com sucesso"}


@router.delete("/materias/{materia_id}")
async def excluir_materia(materia_id: str, db=Depends(get_db)):
    """
    Exclui uma matéria específica pelo ID, junto com todas as aulas e PDFs vinculados a ela.
    Retorna uma mensagem de confirmação se a exclusão for bem-sucedida.
    """

    # Exclui aulas da matéria
    aulas = await db.aulas.find({"materia_id": materia_id}).to_list(length=None)
    aula_ids = [str(aula["_id"]) for aula in aulas]

    # Exclui os PDFs relacionados às aulas da matéria
    if aula_ids:
        await db.pdfs.delete_many({"aula_id": {"$in": aula_ids}})

    # Exclui as aulas da matéria
    await db.aulas.delete_many({"materia_id": materia_id})

    # Exclui a própria matéria
    resultado = await db.materias.delete_one({"_id": ObjectId(materia_id)})

    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Matéria não encontrada")

    return {"mensagem": "Matéria, aulas e PDFs relacionados excluídos com sucesso"}