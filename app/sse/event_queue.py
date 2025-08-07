from asyncio import Queue
import json

event_queue = Queue()

async def publicar_evento_sse(tipo: str, dados: dict):
    await event_queue.put({
        "event": tipo,
        "data": json.dumps(dados)
    })
