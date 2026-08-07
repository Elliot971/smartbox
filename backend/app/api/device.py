import logging
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.security import verify_device_key
from app.db.session import SessionLocal, get_db
from app.schemas.device import ApiResult, DeviceEventIn, DeviceSnapshotIn
from app.services.events import event_broker
from app.services.repository import analyze_damage_inspection, create_operation_event, upsert_snapshot

DEVICE_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "device_images")
os.makedirs(DEVICE_UPLOAD_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/device", tags=["device"], dependencies=[Depends(verify_device_key)])


def _analyze_snapshot_inspection(inspection_id: int) -> None:
    """Background task: run damage analysis for a board-uploaded snapshot inspection."""
    db = SessionLocal()
    try:
        analyze_damage_inspection(db, inspection_id)
        logger.info("Damage analysis completed for snapshot inspection %s", inspection_id)
    except Exception:
        logger.exception("Damage analysis failed for snapshot inspection %s", inspection_id)
    finally:
        db.close()


@router.post("/snapshot", response_model=ApiResult)
async def upload_snapshot(
    payload: DeviceSnapshotIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ApiResult:
    data = upsert_snapshot(db, payload)
    for inspection_id in data.get("damage_inspection_ids", []):
        background_tasks.add_task(_analyze_snapshot_inspection, inspection_id)
    await event_broker.publish("snapshot.updated", data)
    return ApiResult(data=data)


@router.post("/events", response_model=ApiResult)
async def upload_event(payload: DeviceEventIn, db: Session = Depends(get_db)) -> ApiResult:
    event, created = create_operation_event(db, payload)
    data = {"id": event.id, "event_id": event.event_id, "created": created}
    await event_broker.publish("event.created", data)
    return ApiResult(data=data)


@router.post("/upload-image", response_model=ApiResult)
async def upload_device_image(file: UploadFile = File(...)) -> ApiResult:
    """ESP32-P4 上传单张图片，返回可供 snapshot / event 引用的 image_url。

    该端点使用 X-Device-Key 鉴权（与 /device/* 一致），不需要登录 JWT。
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        return ApiResult(ok=False, message="file must be an image", data={})

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(DEVICE_UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())

    image_url = f"/uploads/device_images/{filename}"
    return ApiResult(data={"image_url": image_url, "filename": filename})
