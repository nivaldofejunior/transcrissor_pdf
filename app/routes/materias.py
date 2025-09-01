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
    user: UsuarioToken = Depends(get_usuario_atual),
):
    """
    Lista as matérias do usuário logado.
    """
    materias: List[MateriaInDB] = []
    cursor = (
        db.materias
        .find({"usuario_id": user.id})              
        .sort("data_criacao", -1)                    
    )
    async for m in cursor:
        m["id"] = str(m.pop("_id"))
        materias.append(MateriaInDB(**m))
    return materias