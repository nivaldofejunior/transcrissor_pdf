# app/routes/auth_routes.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId

from app.models.usuario import UsuarioCreate, UsuarioLogin
from app.auth.hash_handler import gerar_hash, verificar_hash
from app.auth.jwt_handler import criar_token, decodificar_token  # garanta que exista
from app.db.mongo import get_db

router = APIRouter()

security = HTTPBearer()  # Bearer <token>

@router.post("/register")
async def registrar_usuario(
    usuario: UsuarioCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    existe = await db.usuarios.find_one({"email": usuario.email})
    if existe:
        raise HTTPException(status_code=400, detail="Email já registrado")

    usuario_dict = usuario.dict()
    usuario_dict["senha_hash"] = gerar_hash(usuario.senha)
    usuario_dict.pop("senha")
    usuario_dict["criado_em"] = datetime.utcnow()

    result = await db.usuarios.insert_one(usuario_dict)
    return {"id": str(result.inserted_id), "nome": usuario.nome, "email": usuario.email}

@router.post("/login")
async def login_usuario(
    usuario: UsuarioLogin,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    db_usuario = await db.usuarios.find_one({"email": usuario.email})
    if not db_usuario or not verificar_hash(usuario.senha, db_usuario["senha_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = criar_token({"sub": str(db_usuario["_id"])})
    return {"access_token": token, "token_type": "bearer"}

# --------- Proteção com JWT ---------

async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        payload = decodificar_token(cred.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido")
        user = await db.usuarios.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

@router.get("/me")
async def me(usuario = Depends(get_current_user)):
    return {
        "id": str(usuario["_id"]),
        "nome": usuario["nome"],
        "email": usuario["email"],
        "criado_em": usuario["criado_em"],
    }

# índice único de email (chame no startup)
async def ensure_indexes():
    db = get_db()
    await db.usuarios.create_index("email", unique=True)
