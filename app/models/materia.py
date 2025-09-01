from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Any
from bson import ObjectId
from pydantic_core import core_schema, PydanticCustomError

_HEX24 = "^[a-fA-F0-9]{24}$"

def _to_object_id(v: Any) -> ObjectId:
    if isinstance(v, ObjectId):
        return v
    try:
        return ObjectId(str(v))
    except Exception:
        raise PydanticCustomError("objectid", "Valor não é um ObjectId válido")

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        # Diz ao Pydantic: no JSON é string 24-hex; em Python valida/retorna ObjectId
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(pattern=_HEX24),
            python_schema=core_schema.no_info_plain_validator_function(_to_object_id),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema_, handler):
        # Gera o schema padrão e acrescenta exemplo
        schema = handler(core_schema_)
        # (já será "type: string" com pattern, por causa do json_schema acima)
        schema.setdefault("examples", ["64f0a1b2c3d4e5f60718293a"])
        return schema
        
class MateriaCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None

class MateriaInDB(BaseModel):
    id: str
    usuario_id: PyObjectId
    nome: str
    descricao: Optional[str] = None
    data_criacao: datetime

    model_config = ConfigDict(populate_by_name=True, json_encoders={ObjectId: str})
