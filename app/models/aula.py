from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AulaCreate(BaseModel):
    titulo: str
    descricao: Optional[str]
    materia_id: str  # ID da matéria

class AulaInDB(BaseModel):
    id: str
    titulo: str
    descricao: Optional[str]
    materia_id: str
    pdf_path: str
    audio_path: Optional[str]
    audio_gerado: bool = False
    data_upload: datetime
