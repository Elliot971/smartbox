from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.datetime import now_cn


class DashboardSummary(BaseModel):
    devices_total: int
    online_devices: int
    tools_total: int
    tools_available: int
    open_alerts: int
    today_events: int


class LlmAnalyzeRequest(BaseModel):
    target_type: str = "alert"
    target_id: int
    question: str = ""


class LlmAnalyzeResponse(BaseModel):
    risk_level: str
    summary: str
    suggested_action: str
    raw_response: str


class LlmChatRequest(BaseModel):
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    model: str = ""


class LlmChatResponse(BaseModel):
    answer: str
    model: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)


class StreamEvent(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_cn)


class ToolIn(BaseModel):
    tool_code: str
    tool_name: str
    tool_class: str = ""
    spec: str = ""
    status: str = "present"
    image_url: str = ""


class ToolOut(BaseModel):
    id: int
    tool_code: str
    tool_name: str
    tool_class: str
    spec: str
    status: str
    image_url: str
    created_at: datetime


class UploadResponse(BaseModel):
    url: str
    filename: str = ""

