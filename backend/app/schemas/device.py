from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OperatorIn(BaseModel):
    user_code: str = ""
    name: str = ""
    auth_type: str = "face"


class SlotSnapshotIn(BaseModel):
    slot_no: int
    tool_code: str = ""
    tool_name: str = ""
    tool_class: str = ""
    status: str
    confidence: float | None = None
    image_url: str = ""
    image_path: str = ""
    # 可选：该槽位/工具在整图中的归一化或像素坐标 [x1, y1, x2, y2]，供云端损坏检测模型做区域裁剪或 ROI 分析
    bbox: list[float] = Field(default_factory=list)


class DeviceSnapshotIn(BaseModel):
    device_code: str
    snapshot_id: str = ""
    captured_at: datetime | None = None
    timestamp: datetime | None = None
    firmware_version: str = ""
    total: int = 0
    available: int = 0
    screwdriver_present: int = 0
    vision_complete: bool = False
    slots: list[SlotSnapshotIn] = Field(default_factory=list)


class ToolChangeIn(BaseModel):
    slot_no: int | None = None
    tool_code: str = ""
    tool_name: str = ""
    tool_class: str = ""
    confidence: float | None = None
    quantity: int = 1


class DeviceEventIn(BaseModel):
    event_id: str
    device_code: str
    operator: OperatorIn = Field(default_factory=OperatorIn)
    event_type: str = "operation"
    operation_id: str = ""
    related_event_id: str = ""
    result_type: str = ""
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    occurred_at: datetime | None = None
    door_confirmed: bool = False
    reminder_count: int = 0
    borrowed: list[ToolChangeIn] = Field(default_factory=list)
    returned: list[ToolChangeIn] = Field(default_factory=list)
    anomalies: list[ToolChangeIn] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ApiResult(BaseModel):
    ok: bool = True
    message: str = "ok"
    data: dict[str, Any] = Field(default_factory=dict)

