from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from bson import ObjectId
from app.sse.event_queue import publicar_evento_sse
from app.db.mongo import get_db

router = APIRouter()

@router.post("/eventos/pdf-audio")
async def receber_evento_pdf_audio(request: Request):
    """
    Recebe eventos das tasks de geração de áudio.
    Atualiza o status no MongoDB e envia via SSE.
    """
    body = await request.json()
    pdf_id = body.get("pdf_id")
    status = body.get("status")
    erro = body.get("erro")

    if not pdf_id or not status:
        return JSONResponse(status_code=400, content={"erro": "pdf_id e status são obrigatórios"})

    db = await get_db()

    # Atualiza o status do PDF
    await db.pdfs.update_one(
        {"_id": ObjectId(pdf_id)},
        {"$set": {"status": status}}
    )

    # Publica via SSE
    await publicar_evento_sse(
        f"pdf_audio_{status}",
        {"pdf_id": pdf_id, "status": status, "erro": erro}
    )

    return {"mensagem": "Evento registrado com sucesso"}
