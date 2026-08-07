import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api import ai, auth, device, inspection, query, stream, tools, upload
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.db.session import Base, engine
from app.models import domain  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()


async def _pending_analysis_worker() -> None:
    """Background worker: periodically scan and analyze pending damage inspections."""
    from app.db.session import SessionLocal
    from app.services.repository import analyze_pending_inspections

    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            count = await asyncio.to_thread(analyze_pending_inspections, db, limit=10)
            if count:
                logger.info("Auto-analyzed %s pending inspection(s)", count)
        except Exception:
            logger.exception("Pending analysis worker error")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        logger.warning("Database is not ready, API starts without table creation: %s", exc)
    worker = asyncio.create_task(_pending_analysis_worker())
    yield
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name, "env": settings.app_env}


@app.get("/")
def root() -> dict:
    return {
        "ok": True,
        "message": "FOD smart toolbox API is running. Open the Web UI at http://127.0.0.1:5173, or API docs at /docs.",
        "docs": "/docs",
        "health": "/health",
        "web_dev_url": "http://127.0.0.1:5173",
    }


# Public endpoints: device uploads use X-Device-Key; health is public.
app.include_router(device.router, prefix="/api")
app.include_router(auth.router, prefix="/api")

# Admin endpoints: require JWT.
admin_dep = [Depends(get_current_user)]
app.include_router(query.router, prefix="/api", dependencies=admin_dep)
app.include_router(ai.router, prefix="/api", dependencies=admin_dep)
app.include_router(inspection.router, prefix="/api", dependencies=admin_dep)
app.include_router(stream.router, prefix="/api", dependencies=admin_dep)
app.include_router(tools.router, prefix="/api", dependencies=admin_dep)
app.include_router(upload.router, prefix="/api", dependencies=admin_dep)
