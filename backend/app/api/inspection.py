from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.models.domain import DamageInspection, Tool
from app.schemas.inspection import (
    DamageInspectionAnalyzeResponse,
    DamageInspectionCreate,
    DamageInspectionOut,
    ToolDamageSummary,
)
from app.services.repository import analyze_damage_inspection, create_damage_inspection, latest_damage_inspections


def _analyze_task_bg(task_id: int) -> None:
    db = SessionLocal()
    try:
        analyze_damage_inspection(db, task_id)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Background analysis failed for task %s", task_id)
    finally:
        db.close()

router = APIRouter(prefix="/inspection", tags=["inspection"])


@router.get("/tasks", response_model=list[DamageInspectionOut])
def get_tasks(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    return latest_damage_inspections(db, limit)


@router.post("/tasks", response_model=DamageInspectionOut)
def create_task(
    payload: DamageInspectionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    task = create_damage_inspection(db, payload)
    background_tasks.add_task(_analyze_task_bg, task["id"])
    return task


@router.post("/tasks/{task_id}/analyze", response_model=DamageInspectionAnalyzeResponse)
def analyze_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = analyze_damage_inspection(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="inspection task not found")
    return {"ok": True, "task": task}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(DamageInspection, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="inspection task not found")
    db.delete(row)
    db.commit()
    return {"ok": True, "deleted": task_id}


@router.delete("/tool-summary/{tool_code}")
def delete_tool_inspections(tool_code: str, db: Session = Depends(get_db)) -> dict:
    """删除指定工具的所有损坏检测记录"""
    rows = db.execute(
        select(DamageInspection).where(DamageInspection.tool_code == tool_code)
    ).scalars().all()
    count = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return {"ok": True, "deleted": count}


@router.get("/tool-summary", response_model=list[ToolDamageSummary])
def tool_damage_summary(db: Session = Depends(get_db)) -> list[dict]:
    """返回每个有图片的工具的最新损坏检测结果"""
    tools = db.execute(select(Tool).where(Tool.image_url != "").order_by(Tool.id)).scalars().all()
    result = []
    for tool in tools:
        latest = db.scalar(
            select(DamageInspection)
            .where(DamageInspection.tool_code == tool.tool_code)
            .order_by(desc(DamageInspection.id))
        )
        count = db.scalar(select(DamageInspection).where(DamageInspection.tool_code == tool.tool_code)) or 0
        result.append({
            "tool_id": tool.id,
            "tool_code": tool.tool_code,
            "tool_name": tool.tool_name,
            "image_url": tool.image_url,
            "latest_status": latest.status if latest else "pending",
            "latest_severity": latest.severity if latest else "low",
            "latest_summary": latest.summary if latest else "尚未检测",
            "task_count": count if isinstance(count, int) else 0,
        })
    return result


@router.post("/upload-and-analyze")
async def upload_and_analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tool_code: str = Form(""),
    tool_name: str = Form("上传检测"),
    tool_class: str = Form(""),
    db: Session = Depends(get_db),
) -> dict:
    """上传照片，立即返回任务ID，后台异步分析"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")

    import os, uuid

    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "inspections")
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    image_url = f"/uploads/inspections/{filename}"

    task = create_damage_inspection(db, DamageInspectionCreate(
        device_code="FOD-TOOLBOX-001",
        tool_code=tool_code,
        tool_name=tool_name,
        tool_class=tool_class,
        image_url=image_url,
    ))
    # 后台异步分析，不阻塞响应
    background_tasks.add_task(_analyze_task_bg, task["id"])
    return {"ok": True, "task_id": task["id"], "message": "已创建检测任务，后台分析中"}
