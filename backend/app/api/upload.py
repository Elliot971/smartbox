import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.query import UploadResponse

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "inspections")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/image", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)) -> UploadResponse:
    print(f"[upload] received file: {file.filename}, content_type: {file.content_type}, size: {file.size if hasattr(file, 'size') else 'unknown'}")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    import uuid

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    try:
        with open(filepath, "wb") as f:
            f.write(file.file.read())
        print(f"[upload] saved to {filepath}")
        return UploadResponse(url=f"/uploads/inspections/{filename}", filename=filename)
    except Exception as e:
        print(f"[upload] error saving file: {e}")
        raise HTTPException(status_code=500, detail=f"save file failed: {e}")
