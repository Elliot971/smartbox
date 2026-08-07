from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.domain import Alert
from app.services.repository import clear_all_alerts, dashboard_summary, latest_alerts, latest_events, latest_slots

router = APIRouter(prefix="/query", tags=["query"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)) -> dict:
    return dashboard_summary(db)


@router.get("/slots")
def get_slots(device_code: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    return latest_slots(db, device_code)


@router.get("/events")
def get_events(limit: int = 30, db: Session = Depends(get_db)) -> list[dict]:
    return latest_events(db, limit)


@router.get("/alerts")
def get_alerts(limit: int = 30, db: Session = Depends(get_db)) -> list[dict]:
    return latest_alerts(db, limit)


@router.delete("/alerts/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(Alert, alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="alert not found")
    db.delete(row)
    db.commit()
    return {"ok": True, "deleted": alert_id}


@router.delete("/alerts")
def delete_all_alerts(db: Session = Depends(get_db)) -> dict:
    count = clear_all_alerts(db)
    return {"ok": True, "deleted": count}

