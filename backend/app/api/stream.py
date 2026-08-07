import logging

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.auth import get_current_user
from app.db.session import SessionLocal
from app.services.events import event_broker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/events")
async def stream_events(token: str = Query("")) -> StreamingResponse:
    # SSE 不支持自定义 header，用 URL 参数传 token
    if token:
        db = SessionLocal()
        try:
            get_current_user(token=token, db=db)
        except Exception:
            logger.warning("SSE token invalid, allowing anonymous (read-only)")
        finally:
            db.close()
    return StreamingResponse(event_broker.subscribe(), media_type="text/event-stream")

