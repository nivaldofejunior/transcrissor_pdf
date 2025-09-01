from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.models.materia import MateriaCreate, MateriaInDB
from app.deps.auth import get_usuario_atual, UsuarioToken  # <<< importa dependência

router = APIRouter()

@router.post("/materias/", response_model=MateriaInDB)
async def criar_materia(
    materia: MateriaCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),   # <<< pega usuário logado
):
    """
    Cria uma nova matéria vinculada ao usuário logado.
    """
    materia_dict = materia.dict()
    materia_dict["usuario_id"] = user.id
    materia_dict["data_criacao"] = datetime.utcnow()

    result = await db.materias.insert_one(materia_dict)
    materia_dict["id"] = str(result.inserted_id)

    return MateriaInDB(**materia_dict)

@router.get("/materias/", response_model=List[MateriaInDB])
async def listar_materias(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: UsuarioToken = Depends(get_usuario_atual),   # <<< pega usuário logado
):
    """
    Lista todas as matérias cadastradas do usuário logado.
    """
    materias: List[MateriaInDB] = []
    cursor = db.aulas.find({"usuario_id": user.id}, {"pdf_path": 0, "audio_path": 0, "audio_gerado": 0}).sort("data_upload", -1)
    async for materia in cursor:
        materia["id"] = str(materia.pop("_id"))
        materias.append(MateriaInDB(**materia))
    return materias
