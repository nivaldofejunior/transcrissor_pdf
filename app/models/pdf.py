from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class PdfInDB(BaseModel):
    id: str
    aula_id: str
    filename: str
    descricao: Optional[str]
    caminho: str
    transcricao: Optional[str] = None
    audio_path: Optional[str] = None
    data_upload: datetime

    class Config:
        model_config = ConfigDict(populate_by_name=True)