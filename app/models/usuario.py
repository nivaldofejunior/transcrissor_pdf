from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
import re

def limpar_cpf(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")

def cpf_valido(cpf: str) -> bool:
    cpf = limpar_cpf(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10) % 11
    if d1 == 10: d1 = 0
    if d1 != int(cpf[9]): return False
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10) % 11
    if d2 == 10: d2 = 0
    return d2 == int(cpf[10])

class UsuarioBase(BaseModel):
    nome: str = Field(..., min_length=2)
    email: EmailStr
    cpf: str

    @validator("email")
    def lower_email(cls, v): return v.lower().strip()

    @validator("cpf")
    def valida_cpf(cls, v):
        num = limpar_cpf(v)
        if not cpf_valido(num):
            raise ValueError("CPF inválido")
        return num

class UsuarioCreate(UsuarioBase):
    senha: str = Field(..., min_length=6)

class UsuarioInDB(UsuarioBase):
    id: str
    criado_em: datetime
    roles: list[str] = []

class UsuarioLogin(BaseModel):
    identificador: str  # email ou cpf
    senha: str

    @validator("identificador")
    def normaliza_identificador(cls, v):
        v = v.strip()
        return v.lower() if "@" in v else limpar_cpf(v)
