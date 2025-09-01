from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from bson import ObjectId
from app.models.materia import PyObjectId

class AulaCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    materia_id: str

class AulaInDB(BaseModel):
    id: str
    usuario_id: PyObjectId
    titulo: str
    descricao: Optional[str] = None
    materia_id: str
    data_upload: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={ObjectId: str},
    )
