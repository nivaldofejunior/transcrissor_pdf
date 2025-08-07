from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.sse.event_queue import event_queue

router = APIRouter()

@router.get("/sse/pdf-status")
async def sse_pdf_status():
    async def event_generator():
        while True:
            evento = await event_queue.get()
            yield f"event: {evento['event']}\ndata: {evento['data']}\n\n"

    return EventSourceResponse(event_generator())
