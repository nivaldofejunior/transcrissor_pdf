# app/db/mongo.py
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# Carrega .env (prioriza .env.<APP_ENV> se existir)
env = os.getenv("APP_ENV", "dev")
dotenv_path = Path(f".env.{env}") if Path(f".env.{env}").exists() else Path(".env")
load_dotenv(dotenv_path=dotenv_path)

# Variáveis de conexão
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASS = os.getenv("MONGO_PASS")
# ⚠️ Em Docker, use o nome do serviço do compose ("mongodb"); localmente, pode ser "localhost"
MONGO_HOST = os.getenv("MONGO_HOST", "mongodb")
DB_NAME = os.getenv("DB_NAME", "projeto_t_db")

# Monta a URI com/sem auth
if MONGO_USER and MONGO_PASS:
    MONGO_URI = (
        f"mongodb://{quote_plus(MONGO_USER)}:{quote_plus(MONGO_PASS)}"
        f"@{MONGO_HOST}:27017/{DB_NAME}?authSource={DB_NAME}"
    )
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:27017/{DB_NAME}"

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None

def get_client() -> AsyncIOMotorClient:
    """Retorna um cliente singleton."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client

def get_db() -> AsyncIOMotorDatabase:
    """Retorna a instância do banco (p/ Depends e uso direto)."""
    global _db
    if _db is None:
        _db = get_client()[DB_NAME]
    return _db
