import logging
import os
import threading
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime import now_cn
from app.models.domain import (
    Alert,
    CabinetSlot,
    DamageInspection,
    Device,
    LlmAnalysis,
    OperationEvent,
    OperationEventItem,
    Tool,
    User,
)
from app.schemas.device import DeviceEventIn, DeviceSnapshotIn, ToolChangeIn
from app.schemas.inspection import DamageInspectionCreate
from app.services.damage_model import damage_model_service
from app.services.llm import llm_service

logger = logging.getLogger(__name__)


def get_or_create_device(db: Session, device_code: str, firmware_version: str = "") -> Device:
    device = db.scalar(select(Device).where(Device.device_code == device_code))
    if device is None:
        device = Device(device_code=device_code, name=device_code, location="航空维修车间")
        db.add(device)
        db.flush()
    device.online_status = "online"
    device.last_seen_at = now_cn()
    if firmware_version:
        device.firmware_version = firmware_version
    return device


def get_or_create_tool(db: Session, tool_code: str, tool_name: str, tool_class: str = "") -> Tool | None:
    if not tool_code:
        return None
    tool = db.scalar(select(Tool).where(Tool.tool_code == tool_code))
    if tool is None:
        tool = Tool(tool_code=tool_code, tool_name=tool_name or tool_code, tool_class=tool_class)
        db.add(tool)
        db.flush()
    else:
        if tool_name:
            tool.tool_name = tool_name
        if tool_class:
            tool.tool_class = tool_class
    return tool


def get_or_create_user(db: Session, user_code: str, name: str) -> User | None:
    if not user_code and not name:
        return None
    code = user_code or name
    user = db.scalar(select(User).where(User.user_code == code))
    if user is None:
        user = User(user_code=code, name=name or code)
        db.add(user)
        db.flush()
    elif name:
        user.name = name
    return user


def upsert_snapshot(db: Session, payload: DeviceSnapshotIn) -> dict:
    # snapshot_id 幂等：同一 snapshot_id 重复上传直接返回上次结果
    if payload.snapshot_id:
        existing = db.scalar(
            select(DamageInspection).where(
                DamageInspection.image_url.like(f"%{payload.snapshot_id}%")
            ).order_by(DamageInspection.id.desc())
        )
        if existing:
            logger.info("Snapshot %s already processed, skipping", payload.snapshot_id)
            return {
                "device_id": existing.device_id,
                "device_code": payload.device_code,
                "available": payload.available,
                "total": payload.total,
                "damage_inspection_ids": [],
            }

    device = get_or_create_device(db, payload.device_code, payload.firmware_version)
    device.screwdriver_present = payload.screwdriver_present
    device.vision_complete = payload.vision_complete
    damage_inspection_ids: list[int] = []

    # 视觉检测失败时没有有效照片，跳过损坏检测
    if not payload.vision_complete:
        logger.info("Snapshot vision_complete=False, skipping damage inspection for device %s", payload.device_code)

    logger.info(
        "Received snapshot for device %s: %s",
        payload.device_code,
        payload.model_dump_json(),
    )

    if not payload.vision_complete:
        # 视觉失败，只更新工具状态不做损坏检测
        for item in payload.slots:
            tool = get_or_create_tool(db, item.tool_code, item.tool_name, item.tool_class)
            slot = db.scalar(
                select(CabinetSlot).where(CabinetSlot.device_id == device.id, CabinetSlot.slot_no == item.slot_no)
            )
            if slot is None:
                slot = CabinetSlot(device_id=device.id, slot_no=item.slot_no)
                db.add(slot)
                db.flush()
            previous_status = slot.current_status
            slot.current_status = item.status
            slot.confidence = item.confidence
            slot.updated_at = payload.captured_at.replace(tzinfo=None) if payload.captured_at else now_cn()
            if tool is not None:
                tool.status = item.status
        db.commit()
        available = db.scalar(select(func.count(CabinetSlot.id)).where(
            CabinetSlot.device_id == device.id,
            CabinetSlot.current_status.in_(["present", "available"]),
        )) or 0
        return {
            "device_id": device.id,
            "device_code": device.device_code,
            "available": available,
            "total": len(payload.slots),
            "damage_inspection_ids": [],
        }

    for item in payload.slots:
        tool = get_or_create_tool(db, item.tool_code, item.tool_name, item.tool_class)
        slot = db.scalar(
            select(CabinetSlot).where(CabinetSlot.device_id == device.id, CabinetSlot.slot_no == item.slot_no)
        )
        if slot is None:
            slot = CabinetSlot(device_id=device.id, slot_no=item.slot_no)
            db.add(slot)
            db.flush()

        previous_status = slot.current_status
        slot.tool_id = tool.id if tool else None
        slot.expected_class = item.tool_class or slot.expected_class
        slot.updated_at = payload.timestamp.replace(tzinfo=None) if payload.timestamp else now_cn()

        image_url = item.image_url or item.image_path
        status_changed = item.status != previous_status

        # 照片始终更新（板端拍的是整图包含全部工具）
        if tool is not None and image_url:
            tool.image_url = image_url

        if status_changed:
            # 状态变化的工具：更新状态
            slot.current_status = item.status
            slot.confidence = item.confidence
            if tool is not None:
                tool.status = item.status

            # 只有归还（变为present）时才做损坏检测，借走时不做（空槽没有工具）
            if item.status == "present" and image_url:
                inspection = create_damage_inspection(
                    db,
                    DamageInspectionCreate(
                        device_code=device.device_code,
                        slot_id=slot.id,
                        tool_id=tool.id if tool else None,
                        tool_code=item.tool_code,
                        tool_name=item.tool_name or item.tool_code or f"slot-{item.slot_no}",
                        tool_class=item.tool_class,
                        image_url=image_url,
                        bbox=item.bbox or [],
                    ),
                )
                damage_inspection_ids.append(inspection["id"])
                logger.info(
                    "Created damage inspection %s for device %s slot %s tool %s (returned, full check)",
                    inspection["id"],
                    device.device_code,
                    item.slot_no,
                    item.tool_code,
                )
        elif item.status == "present" and image_url:
            # 在位但状态未变：也创建检测任务，但 analyze 时会比较分数变化决定是否调 kimi-k3
            inspection = create_damage_inspection(
                db,
                DamageInspectionCreate(
                    device_code=device.device_code,
                    slot_id=slot.id,
                    tool_id=tool.id if tool else None,
                    tool_code=item.tool_code,
                    tool_name=item.tool_name or item.tool_code or f"slot-{item.slot_no}",
                    tool_class=item.tool_class,
                    image_url=image_url,
                    bbox=item.bbox or [],
                ),
            )
            damage_inspection_ids.append(inspection["id"])
            logger.info(
                "Created damage inspection %s for device %s slot %s tool %s (present, score check)",
                inspection["id"],
                device.device_code,
                item.slot_no,
                item.tool_code,
            )

    db.commit()
    available = (
        db.scalar(
            select(func.count(CabinetSlot.id)).where(
                CabinetSlot.device_id == device.id,
                CabinetSlot.current_status.in_(["present", "available"]),
            )
        )
        or 0
    )
    return {
        "device_id": device.id,
        "device_code": device.device_code,
        "available": available,
        "total": len(payload.slots),
        "damage_inspection_ids": damage_inspection_ids,
    }


def _add_event_items(db: Session, event: OperationEvent, action: str, items: list[ToolChangeIn]) -> None:
    for item in items:
        db.add(
            OperationEventItem(
                event_id=event.id,
                slot_no=item.slot_no,
                tool_code=item.tool_code,
                tool_name=item.tool_name,
                action=action,
                confidence=item.confidence,
                quantity=getattr(item, "quantity", 1),
            )
        )


def _resolve_screwdriver_mapping(db: Session, device_id: int, action: str, quantity: int) -> list[Tool]:
    """对 screwdriver 类工具，按借还顺序映射到 SD-001/SD-002。

    借出: 先借 SD-001(螺丝刀1)，再借 SD-002(螺丝刀2)
    归还: 先还 SD-001(螺丝刀1)，再还 SD-002(螺丝刀2)
    """
    tools = db.execute(
        select(Tool).where(Tool.tool_class == "screwdriver", Tool.tool_code.like("SD-00%"))
        .order_by(Tool.tool_code)
    ).scalars().all()
    if not tools:
        return []

    if action == "borrowed":
        # 从 present 的开始借
        candidates = [t for t in tools if t.status == "present"]
    else:  # returned
        # 从 borrowed 的开始还
        candidates = [t for t in tools if t.status == "borrowed"]

    return candidates[:quantity]


def create_operation_event(db: Session, payload: DeviceEventIn) -> tuple[OperationEvent, bool]:
    existing = db.scalar(select(OperationEvent).where(OperationEvent.event_id == payload.event_id))
    if existing is not None:
        return existing, False

    device = get_or_create_device(db, payload.device_code)
    user = get_or_create_user(db, payload.operator.user_code, payload.operator.name)

    occurred_at = payload.occurred_at.replace(tzinfo=None) if payload.occurred_at else None
    event = OperationEvent(
        event_id=payload.event_id,
        device_id=device.id,
        operator_id=user.id if user else None,
        event_type=payload.event_type,
        operation_id=payload.operation_id,
        related_event_id=payload.related_event_id,
        result_type=payload.result_type,
        opened_at=payload.opened_at.replace(tzinfo=None) if payload.opened_at else None,
        closed_at=payload.closed_at.replace(tzinfo=None) if payload.closed_at else None,
        occurred_at=occurred_at,
        door_confirmed=payload.door_confirmed,
        reminder_count=payload.reminder_count,
        raw_payload=payload.model_dump(mode="json"),
    )
    db.add(event)
    db.flush()

    et = payload.event_type

    if et == "door_closed":
        # 关门确认：通过 operation_id 找到对应的 door_unconfirmed 告警并关闭
        if payload.operation_id:
            alert = db.scalar(
                select(Alert).where(
                    Alert.device_id == device.id,
                    Alert.alert_type == "door_unconfirmed",
                    Alert.status == "open",
                ).order_by(Alert.created_at.desc())
            )
            if alert:
                alert.status = "closed"
                alert.description += f" | 已确认关门 (event_id={payload.event_id})"
                logger.info("Closed door_unconfirmed alert %s by door_closed event %s", alert.id, payload.event_id)
        # door_closed 不重复统计借还
        db.commit()
        db.refresh(event)
        return event, True

    # operation / door_unconfirmed: 处理借还
    # screwdriver 类型在下面单独处理映射，这里跳过
    non_sd_borrowed = [i for i in payload.borrowed if not (i.tool_class == "screwdriver" and not i.tool_code.startswith("SD-00"))]
    non_sd_returned = [i for i in payload.returned if not (i.tool_class == "screwdriver" and not i.tool_code.startswith("SD-00"))]
    _add_event_items(db, event, "borrowed", non_sd_borrowed)
    _add_event_items(db, event, "returned", non_sd_returned)
    _add_event_items(db, event, "anomaly", payload.anomalies)

    for item in payload.borrowed:
        if item.tool_class == "screwdriver" and not item.tool_code.startswith("SD-00"):
            # 螺丝刀按顺序映射到 SD-001/SD-002
            qty = getattr(item, "quantity", 1)
            sd_tools = _resolve_screwdriver_mapping(db, device.id, "borrowed", qty)
            for i, t in enumerate(sd_tools):
                t.status = "borrowed"
                db.add(OperationEventItem(
                    event_id=event.id, slot_no=item.slot_no,
                    tool_code=t.tool_code, tool_name=t.tool_name,
                    action="borrowed", confidence=item.confidence, quantity=1,
                ))
        else:
            tool = get_or_create_tool(db, item.tool_code, item.tool_name, item.tool_class)
            if tool:
                tool.status = "borrowed"
    for item in payload.returned:
        if item.tool_class == "screwdriver" and not item.tool_code.startswith("SD-00"):
            qty = getattr(item, "quantity", 1)
            sd_tools = _resolve_screwdriver_mapping(db, device.id, "returned", qty)
            for i, t in enumerate(sd_tools):
                t.status = "present"
                db.add(OperationEventItem(
                    event_id=event.id, slot_no=item.slot_no,
                    tool_code=t.tool_code, tool_name=t.tool_name,
                    action="returned", confidence=item.confidence, quantity=1,
                ))
        else:
            tool = get_or_create_tool(db, item.tool_code, item.tool_name, item.tool_class)
            if tool:
                tool.status = "present"

    if et == "door_unconfirmed":
        # 三次提醒后仍未关门 → 告警
        db.add(
            Alert(
                device_id=device.id,
                operation_event_id=event.id,
                alert_type="door_unconfirmed",
                severity="high",
                title="门未关确认告警",
                description=f"设备 {device.device_code} 三次提醒后仍未关门确认。operation_id={payload.operation_id}",
            )
        )
    elif payload.anomalies or "anomaly" in payload.result_type:
        db.add(
            Alert(
                device_id=device.id,
                operation_event_id=event.id,
                alert_type="operation_anomaly",
                severity="high" if payload.anomalies else "medium",
                title="工具箱操作异常",
                description=f"事件 {payload.event_id} 产生 {len(payload.anomalies)} 个异常项",
            )
        )

    db.commit()
    db.refresh(event)
    return event, True


def dashboard_summary(db: Session) -> dict:
    today_start = datetime.combine(now_cn().date(), datetime.min.time())
    devices_total = db.scalar(select(func.count(Device.id))) or 0
    online_devices = db.scalar(select(func.count(Device.id)).where(Device.online_status == "online")) or 0
    tools_total = db.scalar(select(func.count(Tool.id))) or 0
    tools_available = db.scalar(select(func.count(Tool.id)).where(Tool.status.in_(["present", "available"]))) or 0
    open_alerts = db.scalar(select(func.count(Alert.id)).where(Alert.status == "open")) or 0
    today_events = db.scalar(select(func.count(OperationEvent.id)).where(OperationEvent.synced_at >= today_start)) or 0
    return {
        "devices_total": devices_total,
        "online_devices": online_devices,
        "tools_total": tools_total,
        "tools_available": tools_available,
        "open_alerts": open_alerts,
        "today_events": today_events,
    }


def latest_slots(db: Session, device_code: str | None = None) -> list[dict]:
    query = select(CabinetSlot, Device, Tool).join(Device, CabinetSlot.device_id == Device.id).join(
        Tool, CabinetSlot.tool_id == Tool.id, isouter=True
    )
    if device_code:
        query = query.where(Device.device_code == device_code)
    query = query.order_by(Device.device_code, CabinetSlot.slot_no)
    rows = db.execute(query).all()
    return [
        {
            "device_code": device.device_code,
            "slot_no": slot.slot_no,
            "tool_code": tool.tool_code if tool else "",
            "tool_name": tool.tool_name if tool else "",
            "tool_class": tool.tool_class if tool else slot.expected_class,
            "status": slot.current_status,
            "confidence": slot.confidence,
            "updated_at": slot.updated_at.isoformat() if slot.updated_at else None,
        }
        for slot, device, tool in rows
    ]


def latest_events(db: Session, limit: int = 30) -> list[dict]:
    rows = db.execute(
        select(OperationEvent, Device, User)
        .join(Device, OperationEvent.device_id == Device.id)
        .join(User, OperationEvent.operator_id == User.id, isouter=True)
        .order_by(OperationEvent.synced_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": event.id,
            "event_id": event.event_id,
            "device_code": device.device_code,
            "operator_name": user.name if user else "",
            "event_type": event.event_type,
            "operation_id": event.operation_id,
            "result_type": event.result_type,
            "door_confirmed": event.door_confirmed,
            "reminder_count": event.reminder_count,
            "opened_at": event.opened_at.isoformat() if event.opened_at else None,
            "closed_at": event.closed_at.isoformat() if event.closed_at else None,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "synced_at": event.synced_at.isoformat(),
        }
        for event, device, user in rows
    ]


def latest_alerts(db: Session, limit: int = 30) -> list[dict]:
    rows = db.execute(
        select(Alert, Device).join(Device, Alert.device_id == Device.id).order_by(Alert.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": alert.id,
            "device_code": device.device_code,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "description": alert.description,
            "status": alert.status,
            "created_at": alert.created_at.isoformat(),
        }
        for alert, device in rows
    ]


def clear_all_alerts(db: Session) -> int:
    """Delete all alert records and return the number of deleted rows."""
    count = db.scalar(select(func.count(Alert.id))) or 0
    db.execute(Alert.__table__.delete())
    db.commit()
    return count


def _inspection_to_dict(row: DamageInspection, device: Device) -> dict:
    return {
        "id": row.id,
        "device_code": device.device_code,
        "slot_id": row.slot_id,
        "tool_id": row.tool_id,
        "tool_code": row.tool_code,
        "tool_name": row.tool_name,
        "tool_class": row.tool_class,
        "image_url": row.image_url,
        "status": row.status,
        "severity": row.severity,
        "confidence": row.confidence,
        "summary": row.summary,
        "raw_result": row.raw_result or {},
        "bbox": row.bbox or [],
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def latest_damage_inspections(db: Session, limit: int = 50) -> list[dict]:
    rows = db.execute(
        select(DamageInspection, Device)
        .join(Device, DamageInspection.device_id == Device.id)
        .order_by(DamageInspection.updated_at.desc(), DamageInspection.id.desc())
        .limit(limit)
    ).all()
    return [_inspection_to_dict(row, device) for row, device in rows]


def create_damage_inspection(db: Session, payload: DamageInspectionCreate) -> dict:
    device = get_or_create_device(db, payload.device_code)
    tool = get_or_create_tool(db, payload.tool_code, payload.tool_name, payload.tool_class)
    row = DamageInspection(
        device_id=device.id,
        slot_id=payload.slot_id,
        tool_id=tool.id if tool else payload.tool_id,
        tool_code=tool.tool_code if tool else payload.tool_code,
        tool_name=tool.tool_name if tool else payload.tool_name,
        tool_class=tool.tool_class if tool else payload.tool_class,
        image_url=payload.image_url,
        bbox=payload.bbox or [],
        summary="等待云端损坏检测模型分析",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _inspection_to_dict(row, device)


def analyze_damage_inspection(db: Session, task_id: int) -> dict | None:
    row = db.get(DamageInspection, task_id)
    if row is None:
        return None

    # Prevent concurrent analysis of the same task.
    if row.status == "analyzing":
        return _inspection_to_dict(row, db.get(Device, row.device_id))
    row.status = "analyzing"
    db.commit()

    device = db.get(Device, row.device_id)
    task = _inspection_to_dict(row, device)

    # If the board did not send a bbox, try tool-detection models to segment it.
    # Works for both board snapshots and uploaded photos (tool_class may be empty).
    # Run YOLO and kimi-k3 in parallel: YOLO is fast (~3s), kimi-k3 is slower (~15s)
    # but more accurate. If YOLO matches, use it; otherwise fall back to kimi-k3.
    if not task.get("bbox") and row.image_url and row.tool_class:
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        full_img_path = os.path.join(backend_root, row.image_url.lstrip("/"))

        # Start kimi-k3 in background (non-blocking)
        kimi_result = [None]
        kimi_thread = None
        if os.path.isfile(full_img_path) and llm_service.settings.llm_vision_model:
            def _run_kimi():
                kimi_result[0] = llm_service.locate_tool_vision(
                    full_img_path, row.tool_name or row.tool_code, row.tool_class
                )
            kimi_thread = threading.Thread(target=_run_kimi, daemon=True)
            kimi_thread.start()

        # Run YOLO (fast, ~3s) while kimi-k3 runs in parallel
        detections = damage_model_service.detect_tools(row.image_url)
        bbox = damage_model_service.match_tool_bbox(detections, row.tool_class or row.tool_name)

        # If YOLO didn't match, wait for kimi-k3 result
        if not bbox and kimi_thread:
            kimi_thread.join(timeout=60)
            bbox = kimi_result[0]

        if bbox:
            row.bbox = bbox
            task["bbox"] = bbox
            row.raw_result = {"detected_bbox": bbox, "detections": detections}
            db.commit()

    # Crop to the single-tool ROI (provided by board or detected above).
    cropped_path = damage_model_service._maybe_crop(task)
    if cropped_path:
        # Replace image_url with the cropped file so both damage model and LLM see one tool.
        task = {**task, "image_url": cropped_path}
        task.pop("bbox", None)

    result = damage_model_service.analyze(task)

    # 获取异常分数
    new_score = result.get("raw_result", {}).get("anomaly_score", 0.5)

    # 查找该槽位上次的异常分数
    slot = db.get(CabinetSlot, row.slot_id) if row.slot_id else None
    old_score = slot.last_anomaly_score if slot else None

    # 分数变化检测：如果上次有分数且变化不大，跳过 kimi-k3 报告（省钱省时间）
    SCORE_CHANGE_THRESHOLD = 0.1
    if old_score is not None and abs(new_score - old_score) < SCORE_CHANGE_THRESHOLD:
        logger.info(
            "分数变化不足 (slot %s: %.3f -> %.3f, delta=%.3f < %.1f), 跳过 kimi-k3 报告",
            row.slot_id, old_score, new_score, abs(new_score - old_score), SCORE_CHANGE_THRESHOLD,
        )
        # 更新分数但不触发 kimi-k3
        if slot:
            slot.last_anomaly_score = new_score
        row.status = result["status"]
        row.severity = result["severity"]
        row.confidence = result["confidence"]
        row.summary = result["summary"]
        row.raw_result = result["raw_result"]
        row.updated_at = now_cn()
        if cropped_path and os.path.exists(cropped_path):
            os.remove(cropped_path)
        # 分数变化不大不创建告警
        db.commit()
        return _inspection_to_dict(row, device)

    # 分数变化大或首次检测，触发 kimi-k3 完整报告
    logger.info(
        "分数变化显著 (slot %s: %s -> %.3f), 触发 kimi-k3 报告",
        row.slot_id, f"{old_score:.3f}" if old_score is not None else "首次", new_score,
    )
    # 更新槽位的上次分数
    if slot:
        slot.last_anomaly_score = new_score

    # Generate LLM natural language report, preferring the cropped ROI if available.
    llm_image_path = cropped_path if cropped_path else ""
    if not llm_image_path and row.image_url:
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        llm_image_path = os.path.join(backend_root, row.image_url.lstrip("/"))
    try:
        llm_summary = llm_service.generate_damage_report_sync(
            tool_name=row.tool_name or row.tool_code,
            tool_class=row.tool_class,
            status=result["status"],
            anomaly_score=result.get("raw_result", {}).get("anomaly_score", 0.5),
            model_used=result.get("raw_result", {}).get("model_used", "unknown"),
            severity=result["severity"],
            confidence=result.get("confidence", 0.5),
            image_path=llm_image_path,
        )
    except Exception:
        llm_summary = result["summary"]

    # 如果 kimi-k3 报告表明图中没有工具（空槽/空白背景/模糊），删除此检测记录，不入库不显示
    no_tool_indicators = ["未见工具", "未见可辨识", "空白泡棉", "白色背景", "画面模糊",
                          "未发现工具", "无可辨识", "空槽", "未见工具本体", "仅空白",
                          "仅白色", "未见任何工具", "无法辨识", "无工具"]
    if llm_summary and any(ind in llm_summary for ind in no_tool_indicators):
        logger.info("kimi-k3 报告图中无工具，删除检测记录 %s: %s", task_id, llm_summary[:60])
        # 无工具时不更新 last_anomaly_score（保持上次的分数，避免空槽高分影响下次比较）
        if slot:
            slot.last_anomaly_score = old_score  # 保持原值不变
        if cropped_path and os.path.exists(cropped_path):
            os.remove(cropped_path)
        db.delete(row)
        db.commit()
        return None

    # kimi-k3 视觉判定可覆盖 4090 异常检测的 status
    # 只有 kimi-k3 明确判定为低风险，且报告中没有描述任何损坏特征时，才降为 normal
    final_status = result["status"]
    final_severity = result["severity"]
    if llm_summary:
        # 损坏特征词：如果报告里出现这些词，不能降级
        damage_indicators = ["锈", "磨损", "崩缺", "裂纹", "变形", "弯曲", "断裂", "破损", "开裂",
                             "松动", "剥落", "老化", "划痕", "缺口", "损坏", "失效", "腐蚀",
                             "发黑", "锈蚀", "锈斑", "刃口", "打滑", "间隙过大"]
        # 低风险判定词
        low_indicators = ["低风险", "可正常使用"]
        # 高风险判定词
        high_indicators = ["高风险", "立即停用", "报废更换", "断裂风险"]

        has_damage = any(ind in llm_summary for ind in damage_indicators)
        has_low = any(ind in llm_summary for ind in low_indicators)
        has_high = any(ind in llm_summary for ind in high_indicators)

        if has_high:
            # kimi-k3 判定高风险，升级为 damaged
            final_status = "damaged"
            final_severity = "high"
            logger.info("kimi-k3 视觉判定升级: %s/%s -> damaged/high (报告含高风险描述)", result["status"], result["severity"])
        elif has_low and not has_damage:
            # kimi-k3 判定低风险，且报告无任何损坏描述，才降级
            final_status = "normal"
            final_severity = "low"
            logger.info("kimi-k3 视觉判定覆盖: %s/%s -> normal/low (工具外观完好)", result["status"], result["severity"])
        # else: 保持 4090 的判定

    row.status = final_status
    row.severity = final_severity
    row.confidence = result["confidence"]
    row.summary = llm_summary
    row.raw_result = result["raw_result"]
    row.updated_at = now_cn()

    if cropped_path and os.path.exists(cropped_path):
        os.remove(cropped_path)

    if row.status in {"damaged", "suspected"}:
        # 查找最近的操作事件，关联操作人实现追溯
        recent_event = db.scalar(
            select(OperationEvent)
            .where(OperationEvent.device_id == row.device_id)
            .order_by(OperationEvent.synced_at.desc())
            .limit(1)
        )
        operator_info = ""
        if recent_event and recent_event.operator_id:
            operator = db.get(User, recent_event.operator_id)
            if operator:
                operator_info = f" 最近操作人：{operator.name}"
        score_info = ""
        if slot:  # 自动检测（板端快照触发）
            if old_score is not None:
                score_info = f" 分数变化：{old_score:.2f}→{new_score:.2f}"
            else:
                score_info = f" 分数变化：首次检测 {new_score:.2f}"
        else:  # 上传检测
            score_info = f" 分数：{new_score:.2f}"

        db.add(
            Alert(
                device_id=row.device_id,
                alert_type="tool_damage",
                severity=row.severity,
                title=f"工具损坏检测：{row.tool_name or row.tool_code}",
                description=row.summary + score_info + operator_info,
            )
        )

    db.commit()
    return _inspection_to_dict(row, device)


def analyze_pending_inspections(db: Session, limit: int = 10) -> int:
    """Analyze any inspections still in 'pending' status. Used by the background worker.

    Also recovers tasks stuck in 'analyzing' for more than 10 minutes (e.g. after a crash
    or container restart) by resetting them to 'pending'.
    """
    # Recover stuck 'analyzing' tasks (>10 min) so they get retried.
    cutoff = now_cn() - timedelta(minutes=10)
    stuck = (
        db.execute(
            select(DamageInspection)
            .where(DamageInspection.status == "analyzing")
            .where(DamageInspection.updated_at < cutoff)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    for row in stuck:
        row.status = "pending"
        logger.warning("Recovered stuck analyzing inspection %s (updated_at=%s)", row.id, row.updated_at)
    if stuck:
        db.commit()

    rows = (
        db.execute(
            select(DamageInspection)
            .where(DamageInspection.status == "pending")
            .order_by(DamageInspection.created_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    analyzed = 0
    for row in rows:
        try:
            analyze_damage_inspection(db, row.id)
            analyzed += 1
        except Exception:
            logger.exception("Auto-analysis failed for inspection %s", row.id)
    return analyzed


def save_llm_analysis(
    db: Session, target_type: str, target_id: int, provider: str, prompt: str, raw_response: str, risk_level: str
) -> LlmAnalysis:
    row = LlmAnalysis(
        target_type=target_type,
        target_id=target_id,
        model_provider=provider,
        prompt=prompt,
        response=raw_response,
        risk_level=risk_level,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
