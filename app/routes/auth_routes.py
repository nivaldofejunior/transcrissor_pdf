# app/routes/auth_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from pymongo.errors import OperationFailure
import os, secrets

from app.models.usuario import (
    UsuarioCreate, UsuarioLogin, UsuarioInDB,
    cpf_valido, limpar_cpf
)
from app.auth.hash_handler import gerar_hash, verificar_hash
from app.auth.jwt_handler import criar_token, decodificar_token
from app.db.mongo import get_db

router = APIRouter()
security = HTTPBearer()  # Bearer <token>

# -------- Config (via .env se quiser) --------
ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "15"))
REFRESH_TTL_DAYS = int(os.getenv("REFRESH_TTL_DAYS", "7"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"  # true em produção (https)
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()         # lax|strict|none
COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "rtid")
COOKIE_PATH = "/api/auth"

def _now():
    return datetime.now(timezone.utc)

def _new_refresh_id():
    return secrets.token_urlsafe(32)

# ---------- Cadastro ----------
@router.post("/register", response_model=UsuarioInDB, status_code=status.HTTP_201_CREATED)
async def registrar_usuario(
    usuario: UsuarioCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    email = usuario.email.lower().strip()
    cpf_num = limpar_cpf(usuario.cpf)

    existente = await db.usuarios.find_one({"$or": [{"email": email}, {"cpf": cpf_num}]})
    if existente:
        dup_email = existente.get("email") == email
        dup_cpf = existente.get("cpf") == cpf_num
        if dup_email and dup_cpf:
            raise HTTPException(status_code=409, detail="E-mail e CPF já cadastrados")
        if dup_email:
            raise HTTPException(status_code=409, detail="E-mail já cadastrado")
        raise HTTPException(status_code=409, detail="CPF já cadastrado")

    doc = {
        "nome": usuario.nome,
        "email": email,
        "cpf": cpf_num,
        "senha_hash": gerar_hash(usuario.senha),
        "roles": [],
        "criado_em": _now(),
    }

    res = await db.usuarios.insert_one(doc)

    return UsuarioInDB(
        id=str(res.inserted_id),
        nome=doc["nome"],
        email=doc["email"],
        cpf=doc["cpf"],
        criado_em=doc["criado_em"],
        roles=doc["roles"],
    )

# ---------- Login (e-mail OU CPF) ----------
@router.post("/login")
async def login_usuario(
    body: UsuarioLogin,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    ident = body.identificador
    if "@" in ident:
        user = await db.usuarios.find_one({"email": ident})
    else:
        if not cpf_valido(ident):
            raise HTTPException(status_code=400, detail="CPF inválido")
        user = await db.usuarios.find_one({"cpf": ident})

    if not user or not verificar_hash(body.senha, user["senha_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    # Access token (curto)
    token = criar_token({
        "sub": str(user["_id"]),
        "email": user["email"],
        "cpf": user["cpf"],
        "name": user.get("nome", ""),
        "roles": user.get("roles", []),
    }, minutes=ACCESS_TTL_MIN)

    # Refresh token (longo) – salvo no Mongo + cookie httpOnly
    refresh_id = _new_refresh_id()
    expires_at = _now() + timedelta(days=REFRESH_TTL_DAYS)
    await db.refresh_tokens.insert_one({
        "user_id": str(user["_id"]),
        "refresh_id": refresh_id,
        "expires_at": expires_at,
        "revoked": False,
        "created_at": _now(),
    })

    response.set_cookie(
        key=COOKIE_NAME,
        value=refresh_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,  # "lax" geralmente é ok
        max_age=REFRESH_TTL_DAYS * 24 * 3600,
        path=COOKIE_PATH,
    )

    return {"access_token": token, "token_type": "bearer", "expires_in": ACCESS_TTL_MIN * 60}

# ---------- Refresh (rotaciona) ----------
@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    rtid = request.cookies.get(COOKIE_NAME)
    if not rtid:
        raise HTTPException(status_code=401, detail="Sem refresh token")

    doc = await db.refresh_tokens.find_one({"refresh_id": rtid})
    if not doc or doc.get("revoked"):
        raise HTTPException(status_code=401, detail="Refresh inválido")

    if doc["expires_at"] < _now():
        raise HTTPException(status_code=401, detail="Refresh expirado")

    user = await db.usuarios.find_one({"_id": ObjectId(doc["user_id"])})
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    # Rotação: revoga o atual e cria um novo
    await db.refresh_tokens.update_one({"_id": doc["_id"]}, {"$set": {"revoked": True, "revoked_at": _now()}})
    new_id = _new_refresh_id()
    new_exp = _now() + timedelta(days=REFRESH_TTL_DAYS)
    await db.refresh_tokens.insert_one({
        "user_id": str(user["_id"]),
        "refresh_id": new_id,
        "expires_at": new_exp,
        "revoked": False,
        "created_at": _now(),
        "rotated_from": doc["refresh_id"],
    })

    response.set_cookie(
        key=COOKIE_NAME,
        value=new_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TTL_DAYS * 24 * 3600,
        path=COOKIE_PATH,
    )

    # Novo access
    access = criar_token({
        "sub": str(user["_id"]),
        "email": user["email"],
        "cpf": user["cpf"],
        "name": user.get("nome", ""),
        "roles": user.get("roles", []),
    }, minutes=ACCESS_TTL_MIN)

    return {"access_token": access, "token_type": "bearer", "expires_in": ACCESS_TTL_MIN * 60}

# ---------- Logout ----------
@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    rtid = request.cookies.get(COOKIE_NAME)
    if rtid:
        await db.refresh_tokens.update_many({"refresh_id": rtid}, {"$set": {"revoked": True, "revoked_at": _now()}})
        response.delete_cookie(key=COOKIE_NAME, path=COOKIE_PATH)
    return {"ok": True}

# ---------- Proteção com JWT ----------
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
        "cpf": usuario["cpf"],
        "criado_em": usuario["criado_em"],
        "roles": usuario.get("roles", []),
    }


def _needs_recreate(curr: dict, opts: dict) -> bool:
    """Compara opções importantes. Se divergir, devemos recriar o índice."""
    # ATENÇÃO: TTL não pode ser alterado; se mudou, recria.
    checks = ("unique", "expireAfterSeconds", "partialFilterExpression")
    for k in checks:
        if k in opts or k in curr:
            if curr.get(k) != opts.get(k):
                return True
    return False

async def _upsert_index(coll, keys, *, name: str | None = None, **opts):
    """
    Cria índice se não existir. Se existir com opções diferentes (ou com nome diferente),
    dropa o antigo e recria com as opções/nome desejados.
    """
    info = await coll.index_information()  # dict[name] -> { 'key': [('field', 1)], ... }
    # 1) Se já existe com o nome desejado
    if name and name in info:
        curr = info[name]
        if curr.get("key") == keys and not _needs_recreate(curr, opts):
            return  # ok, nada a fazer
        await coll.drop_index(name)

    # 2) Procura índice com mesmas chaves (mesmo que o nome seja diferente)
    to_drop = None
    for iname, curr in info.items():
        if curr.get("key") == keys:
            to_drop = iname
            break
    if to_drop:
        await coll.drop_index(to_drop)

    # 3) Cria com o nome/opções desejados
    await coll.create_index(keys, name=name, **opts)

# ---------- Índices (chamar no startup) ----------
async def ensure_indexes(db):
    # Usuarios: email único, cpf único
    await _upsert_index(db.usuarios, [("email", 1)], name="uniq_email", unique=True)
    await _upsert_index(db.usuarios, [("cpf", 1)],   name="uniq_cpf",   unique=True)

    # Refresh tokens
    await _upsert_index(db.refresh_tokens, [("refresh_id", 1)], name="uniq_refresh_id", unique=True)
    await _upsert_index(db.refresh_tokens, [("user_id", 1)],    name="idx_refresh_user")
    # TTL: apaga docs quando expires_at < now (expireAfterSeconds=0)
    await _upsert_index(db.refresh_tokens, [("expires_at", 1)], name="ttl_refresh", expireAfterSeconds=0)
