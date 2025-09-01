from motor.motor_asyncio import AsyncIOMotorDatabase

async def ensure_indexes(db: AsyncIOMotorDatabase):
    await db.materias.create_index([("usuario_id", 1), ("titulo", 1)])
    await db.aulas.create_index([("usuario_id", 1), ("materia_id", 1)])
    await db.pdfs.create_index([("usuario_id", 1), ("aula_id", 1)])
