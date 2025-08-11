from datetime import datetime, timedelta, timezone
from jose import jwt
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"
DEFAULT_ACCESS_MIN = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

def criar_token(dados: dict, *, minutes: int | None = None) -> str:
    """Gera JWT com expiração configurável em minutos (default via env)."""
    mins = minutes if minutes is not None else DEFAULT_ACCESS_MIN
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=mins)
    to_encode = {**dados, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decodificar_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
