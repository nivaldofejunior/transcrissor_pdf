from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime

from app.db.mongo import db
from app.models.materia import MateriaCreate, MateriaInDB
from typing import List


router = APIRouter()

@router.post("/materias/", response_model=MateriaInDB)
async def criar_materia(materia: MateriaCreate):
    """
    Cria uma nova matéria no sistema com a data de criação atual.
    Retorna os dados completos da matéria criada.
    """
    materia_dict = materia.dict()
    materia_dict["data_criacao"] = datetime.utcnow()

    result = await db.materias.insert_one(materia_dict)
    materia_dict.pop("_id", None)  # <-- EVITA O ERRO DE VALIDAÇÃO

    return MateriaInDB(id=str(result.inserted_id), **materia_dict)

@router.get("/materias/", response_model=list[MateriaInDB])
async def listar_materias():
    """
    Lista todas as matérias cadastradas no sistema.
    Retorna os dados completos de cada matéria.
    """
    materias = []
    cursor = db.materias.find()
    async for materia in cursor:
        materia["id"] = str(materia.pop("_id"))
        materias.append(MateriaInDB(**materia))
    return materias
