from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DamageInspectionCreate(BaseModel):
    device_code: str = "FOD-TOOLBOX-001"
    slot_id: int | None = None
    tool_id: int | None = None
    tool_code: str = ""
    tool_name: str
    tool_class: str = ""
    image_url: str = ""
    bbox: list[float] = Field(default_factory=list)


class DamageInspectionOut(BaseModel):
    id: int
    device_code: str
    slot_id: int | None = None
    tool_id: int | None = None
    tool_code: str
    tool_name: str
    tool_class: str
    image_url: str
    heatmap_url: str = ""
    status: str
    severity: str
    confidence: float | None = None
    summary: str
    raw_result: dict[str, Any] = Field(default_factory=dict)
    bbox: list[float] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DamageInspectionAnalyzeResponse(BaseModel):
    ok: bool = True
    task: DamageInspectionOut


class ToolDamageSummary(BaseModel):
    tool_id: int
    tool_code: str
    tool_name: str
    image_url: str
    heatmap_url: str = ""
    latest_status: str = "pending"
    latest_severity: str = "low"
    latest_summary: str = ""
    task_count: int = 0
