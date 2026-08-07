from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime import now_cn
from app.db.session import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    location: Mapped[str] = mapped_column(String(128), default="")
    online_status: Mapped[str] = mapped_column(String(24), default="offline")
    firmware_version: Mapped[str] = mapped_column(String(64), default="")
    screwdriver_present: Mapped[int] = mapped_column(Integer, default=0)
    vision_complete: Mapped[bool] = mapped_column(default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)

    slots: Mapped[list["CabinetSlot"]] = relationship(back_populates="device")


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tool_name: Mapped[str] = mapped_column(String(128))
    tool_class: Mapped[str] = mapped_column(String(64), default="")
    spec: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="present")
    image_url: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)


class CabinetSlot(Base):
    __tablename__ = "cabinet_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    slot_no: Mapped[int] = mapped_column(Integer)
    tool_id: Mapped[int | None] = mapped_column(ForeignKey("tools.id"), nullable=True)
    expected_class: Mapped[str] = mapped_column(String(64), default="")
    current_status: Mapped[str] = mapped_column(String(32), default="empty")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)

    device: Mapped[Device] = relationship(back_populates="slots")
    tool: Mapped[Tool | None] = relationship()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(64), default="operator")
    nfc_uid: Mapped[str] = mapped_column(String(64), default="")


class OperationEvent(Base):
    __tablename__ = "operation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), default="operation")
    operation_id: Mapped[str] = mapped_column(String(96), default="", index=True)
    related_event_id: Mapped[str] = mapped_column(String(96), default="")
    result_type: Mapped[str] = mapped_column(String(32), default="")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    door_confirmed: Mapped[bool] = mapped_column(default=False)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)

    device: Mapped[Device] = relationship()
    operator: Mapped[User | None] = relationship()
    items: Mapped[list["OperationEventItem"]] = relationship(cascade="all, delete-orphan")


class OperationEventItem(Base):
    __tablename__ = "operation_event_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("operation_events.id"), index=True)
    slot_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_code: Mapped[str] = mapped_column(String(64), default="")
    tool_name: Mapped[str] = mapped_column(String(128), default="")
    action: Mapped[str] = mapped_column(String(32))
    before_status: Mapped[str] = mapped_column(String(32), default="")
    after_status: Mapped[str] = mapped_column(String(32), default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    operation_event_id: Mapped[int | None] = mapped_column(ForeignKey("operation_events.id"), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(24), default="medium")
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)


class DamageInspection(Base):
    __tablename__ = "damage_inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("cabinet_slots.id"), nullable=True, index=True)
    tool_id: Mapped[int | None] = mapped_column(ForeignKey("tools.id"), nullable=True, index=True)
    tool_code: Mapped[str] = mapped_column(String(64), default="", index=True)
    tool_name: Mapped[str] = mapped_column(String(128), default="")
    tool_class: Mapped[str] = mapped_column(String(64), default="")
    image_url: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    severity: Mapped[str] = mapped_column(String(24), default="low")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_result: Mapped[dict] = mapped_column(JSON, default=dict)
    bbox: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)

    device: Mapped[Device] = relationship()


class LlmAnalysis(Base):
    __tablename__ = "llm_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[int] = mapped_column(Integer)
    model_provider: Mapped[str] = mapped_column(String(64), default="mock")
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(24), default="low")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)
