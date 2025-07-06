import motor.motor_asyncio
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

usuario = quote_plus(os.getenv("MONGO_USER"))
senha = quote_plus(os.getenv("MONGO_PASS"))
host = os.getenv("MONGO_HOST", "localhost")
db_name = os.getenv("DB_NAME")

MONGO_URI = f"mongodb://{usuario}:{senha}@{host}:27017/{db_name}?authSource={db_name}"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[db_name]

async def get_db():
    return db