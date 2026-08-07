from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.events import event_broker

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/events")
async def stream_events() -> StreamingResponse:
    return StreamingResponse(event_broker.subscribe(), media_type="text/event-stream")

