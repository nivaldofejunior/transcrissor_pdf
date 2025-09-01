# app/deps/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from app.auth.jwt_handler import decodificar_token  # tua função

security = HTTPBearer(auto_error=False)

class UsuarioToken:
    def __init__(self, id: ObjectId, username: str | None = None, email: str | None = None):
        self.id = id
        self.username = username
        self.email = email

async def get_usuario_atual(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UsuarioToken:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente")

    token = credentials.credentials  # só o JWT, sem "Bearer "
    try:
        payload = decodificar_token(token)
        user_id_str = payload.get("sub") or payload.get("user_id") or payload.get("_id")
        if not user_id_str:
            raise ValueError("user id não encontrado no token")
        return UsuarioToken(
            id=ObjectId(user_id_str),
            username=payload.get("name") or payload.get("username"),
            email=payload.get("email"),
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
