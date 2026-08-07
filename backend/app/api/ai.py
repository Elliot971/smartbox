from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
import json

from app.core.config import get_settings
from app.db.session import get_db
from app.models.domain import Alert, OperationEvent
from app.schemas.query import LlmAnalyzeRequest, LlmAnalyzeResponse, LlmChatRequest, LlmChatResponse
from app.services.llm import llm_service
from app.services.repository import save_llm_analysis

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=LlmChatResponse)
async def chat(req: LlmChatRequest) -> LlmChatResponse:
    result = await llm_service.chat(req.message, req.context or None, req.model)
    return LlmChatResponse(**result)


@router.post("/chat/stream")
async def chat_stream(req: LlmChatRequest):
    """流式对话接口（SSE），前端可逐 token 显示回复。"""
    async def generate():
        async for chunk in llm_service.chat_stream(req.message, req.context or None, req.model):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/analyze", response_model=LlmAnalyzeResponse)
async def analyze(req: LlmAnalyzeRequest, db: Session = Depends(get_db)) -> LlmAnalyzeResponse:
    if req.target_type == "alert":
        row = db.scalar(select(Alert).where(Alert.id == req.target_id))
    elif req.target_type == "event":
        row = db.scalar(select(OperationEvent).where(OperationEvent.id == req.target_id))
    else:
        raise HTTPException(status_code=400, detail="target_type must be alert or event")

    if row is None:
        raise HTTPException(status_code=404, detail="target not found")

    context = {
        col.name: (getattr(row, col.name).isoformat() if hasattr(getattr(row, col.name), "isoformat") else getattr(row, col.name))
        for col in row.__table__.columns
    }
    result = await llm_service.analyze(context, req.question)
    parsed = result["parsed"]
    settings = get_settings()
    save_llm_analysis(
        db,
        req.target_type,
        req.target_id,
        settings.llm_provider,
        result["prompt"],
        result["raw"],
        parsed["risk_level"],
    )
    return LlmAnalyzeResponse(
        risk_level=parsed["risk_level"],
        summary=parsed["summary"],
        suggested_action=parsed["suggested_action"],
        raw_response=result["raw"],
    )
