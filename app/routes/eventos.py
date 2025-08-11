from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.sse.event_queue import publicar_evento_sse
from app.db.mongo import get_db

router = APIRouter()

class EventoPdfAudioIn(BaseModel):
    pdf_id: str
    status: str  # ex.: "processando" | "concluido" | "erro"
    erro: str | None = None

@router.post("/eventos/pdf-audio")
async def receber_evento_pdf_audio(
    payload: EventoPdfAudioIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    # valida/casta o id
    try:
        oid = ObjectId(payload.pdf_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pdf_id inválido (esperado ObjectId de 24 caracteres hex)."
        )

    try:
        # Atualiza o status no Mongo
        await db.pdfs.update_one(
            {"_id": oid},
            {"$set": {"status": payload.status}}
        )

        # Publica via SSE
        await publicar_evento_sse(
            f"pdf_audio_{payload.status}",
            {"pdf_id": payload.pdf_id, "status": payload.status, "erro": payload.erro}
        )

        return {"mensagem": "Evento registrado com sucesso"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao registrar evento: {e}"
        )
