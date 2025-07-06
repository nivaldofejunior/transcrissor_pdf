# app/models/materia.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class MateriaCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None

class MateriaInDB(BaseModel):
    id: str  # <-- sem alias
    nome: str
    descricao: Optional[str] = None
    data_criacao: datetime
