from fastapi import HTTPException, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

async def assert_do_usuario(db: AsyncIOMotorDatabase, coll: str, _id: ObjectId, usuario_id: ObjectId):
    doc = await db[coll].find_one({"_id": _id, "usuario_id": usuario_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado")
    return doc
