from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from bson import ObjectId
from app.models.materia import PyObjectId  # ok por enquanto

class PdfInDB(BaseModel):
    id: str
    usuario_id: PyObjectId
    aula_id: str
    filename: str
    descricao: Optional[str]
    caminho: str
    transcricao: Optional[str] = None
    audio_path: Optional[str] = None
    data_upload: datetime

    # Pydantic v2: config no nível do modelo
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={ObjectId: str},
    )
