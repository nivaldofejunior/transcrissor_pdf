from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.models.materia import MateriaCreate, MateriaInDB

router = APIRouter()

@router.post("/materias/", response_model=MateriaInDB)
async def criar_materia(
    materia: MateriaCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Cria uma nova matéria no sistema com a data de criação atual.
    Retorna os dados completos da matéria criada.
    """
    materia_dict = materia.dict()
    materia_dict["data_criacao"] = datetime.utcnow()

    result = await db.materias.insert_one(materia_dict)
    materia_dict.pop("_id", None)

    return MateriaInDB(id=str(result.inserted_id), **materia_dict)

@router.get("/materias/", response_model=List[MateriaInDB])
async def listar_materias(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Lista todas as matérias cadastradas no sistema.
    Retorna os dados completos de cada matéria.
    """
    materias: List[MateriaInDB] = []
    cursor = db.materias.find()
    async for materia in cursor:
        materia["id"] = str(materia.pop("_id"))
        materias.append(MateriaInDB(**materia))
    return materias
