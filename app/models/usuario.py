from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UsuarioBase(BaseModel):
    nome: str
    email: EmailStr

class UsuarioCreate(UsuarioBase):
    senha: str

class UsuarioInDB(UsuarioBase):
    id: str
    criado_em: datetime

class UsuarioLogin(BaseModel):
    email: EmailStr
    senha: str
