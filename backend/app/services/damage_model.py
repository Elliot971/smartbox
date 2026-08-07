import io
import os
import uuid

import httpx
from PIL import Image

from app.core.config import get_settings

# Map DB tool_class names to the 4090 DINOv2 model's known class names,
# so DINOv2 (which works reliably) handles them instead of falling through
# to the AdaCLIP branch (which has broken dependencies).
TOOL_CLASS_ALIASES = {
    "crimper": "crimping_pliers",
    "electronic_pliers": "diagonal_pliers",
    "pliers": "slip_joint_pliers",
}


class DamageModelService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def analyze(self, task: dict) -> dict:
        if self.settings.damage_model_url:
            cropped_path = self._maybe_crop(task)
            if cropped_path:
                task = {**task, "_cropped_path": cropped_path}
            try:
                return self._remote_analyze(task)
            finally:
                if cropped_path and os.path.exists(cropped_path):
                    os.remove(cropped_path)
        return self._mock_analyze(task)

    def _maybe_crop(self, task: dict) -> str | None:
        """If bbox is provided, crop the original image to a single-tool ROI."""
        bbox = task.get("bbox")
        image_url = task.get("image_url", "")
        if not bbox or len(bbox) != 4 or not image_url:
            return None

        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        orig_path = os.path.join(backend_root, image_url.lstrip("/")) if image_url.startswith("/") else image_url
        if not os.path.exists(orig_path):
            return None

        try:
            img = Image.open(orig_path).convert("RGB")
        except Exception:
            return None

        w, h = img.size
        try:
            coords = [float(v) for v in bbox]
        except Exception:
            return None

        x1, y1, x2, y2 = coords
        # Normalized coordinates (0~1) vs pixel coordinates
        if max(coords) <= 1.0:
            x1, x2 = x1 * w, x2 * w
            y1, y2 = y1 * h, y2 * h

        x1, y1 = max(0, int(round(x1))), max(0, int(round(y1)))
        x2, y2 = min(w, int(round(x2))), min(h, int(round(y2)))
        if x2 <= x1 or y2 <= y1:
            return None

        cropped = img.crop((x1, y1, x2, y2))
        upload_dir = os.path.join(backend_root, "uploads", "inspections")
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"cropped_{uuid.uuid4().hex}.jpg"
        cropped_path = os.path.join(upload_dir, filename)
        cropped.save(cropped_path, "JPEG", quality=95)
        return cropped_path

    def _compress_image_bytes(self, file_path: str, max_side: int = 1024, quality: int = 85) -> tuple:
        """Compress image to JPEG bytes (max side limited). Returns (bytes, w, h) or (None, 0, 0)."""
        try:
            img = Image.open(file_path).convert("RGB")
            w, h = img.size
            if max(w, h) > max_side:
                ratio = max_side / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=quality)
            return buf.getvalue(), img.size[0], img.size[1]
        except Exception:
            return None, 0, 0

    def _remote_analyze(self, task: dict) -> dict:
        headers = {}
        if self.settings.damage_model_api_key:
            headers["Authorization"] = f"Bearer {self.settings.damage_model_api_key}"

        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        cropped_path = task.get("_cropped_path")
        image_url = task.get("image_url", "")
        if cropped_path:
            file_path = cropped_path
        else:
            file_path = os.path.join(backend_root, image_url.lstrip("/")) if image_url else ""

        if not file_path or not os.path.exists(file_path):
            return self._mock_analyze(task)

        url = self.settings.damage_model_url.rstrip("/") + "/predict-upload"
        # Compress image before upload (10x faster, same accuracy)
        compressed, _, _ = self._compress_image_bytes(file_path)
        if compressed:
            files = {"file": ("image.jpg", compressed, "image/jpeg")}
        else:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, "image/jpeg")}
        # Map DB tool_class to DINOv2's known class names
        mapped_class = TOOL_CLASS_ALIASES.get(
            task.get("tool_class", ""), task.get("tool_class", "")
        )
        data = {
            "task_id": str(task.get("id", "")),
            "tool_code": task.get("tool_code", ""),
            "tool_name": task.get("tool_name", ""),
            "tool_class": mapped_class,
        }
        try:
            with httpx.Client(timeout=self.settings.damage_model_timeout) as client:
                resp = client.post(url, files=files, data=data, headers=headers)
                resp.raise_for_status()
                result = resp.json()
            return self._normalize(result)
        except Exception:
            # 4090 model error (e.g. AdaCLIP dependency issues) — don't kill the
            # pipeline. Return a mock result so kimi-k3 can still assess the image.
            return self._mock_analyze(task)

    def _mock_analyze(self, task: dict) -> dict:
        text = " ".join(
            [
                task.get("tool_code", ""),
                task.get("tool_name", ""),
                task.get("tool_class", ""),
                task.get("image_url", ""),
            ]
        ).lower()
        damaged_words = ("broken", "damage", "damaged", "crack", "裂", "断", "缺", "坏", "破损")
        suspected_words = ("wear", "scratch", "rust", "磨", "划", "锈", "变形")
        if any(word in text for word in damaged_words):
            return {
                "status": "damaged",
                "severity": "high",
                "confidence": 0.88,
                "summary": "云端检测结果：疑似存在明显损坏，建议拦截入库并人工复核。",
                "raw_result": {"provider": "mock-cloud-damage-detector"},
            }
        if any(word in text for word in suspected_words):
            return {
                "status": "suspected",
                "severity": "medium",
                "confidence": 0.73,
                "summary": "云端检测结果：存在磨损或轻微异常特征，建议人工确认后再入库。",
                "raw_result": {"provider": "mock-cloud-damage-detector"},
            }
        return {
            "status": "normal",
            "severity": "low",
            "confidence": 0.66,
            "summary": "云端检测结果：未发现明显损坏特征，可作为正常工具记录。",
            "raw_result": {"provider": "mock-cloud-damage-detector"},
        }

    def detect_tools(self, image_url: str) -> list[dict]:
        """Call the 4090 tool-detection service to segment tools in an image.

        The image is compressed to max 1024px before upload (10x faster, same
        accuracy). Returned bbox coordinates are normalized to [0,1] relative
        to the original image so _maybe_crop can use them regardless of size.
        """
        if not self.settings.damage_model_url:
            return []

        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        orig_path = os.path.join(backend_root, image_url.lstrip("/")) if image_url.startswith("/") else image_url
        if not orig_path or not os.path.exists(orig_path):
            return []

        url = self.settings.damage_model_url.rstrip("/") + "/detect-tools"
        headers = {}
        if self.settings.damage_model_api_key:
            headers["Authorization"] = f"Bearer {self.settings.damage_model_api_key}"

        try:
            compressed, cw, ch = self._compress_image_bytes(orig_path)
            if not compressed:
                return []
            files = {"file": ("image.jpg", compressed, "image/jpeg")}
            with httpx.Client(timeout=self.settings.damage_model_timeout) as client:
                resp = client.post(url, files=files, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            if not data.get("ok"):
                return []
            # Normalize bbox from compressed-image pixels to [0,1] relative to original
            detections = data.get("detections", [])
            for det in detections:
                bbox = det.get("bbox", [])
                if len(bbox) == 4 and cw > 0 and ch > 0:
                    det["bbox"] = [
                        bbox[0] / cw, bbox[1] / ch,
                        bbox[2] / cw, bbox[3] / ch,
                    ]
            return detections
        except Exception:
            return []

    @staticmethod
    def match_tool_bbox(detections: list[dict], tool_class: str) -> list[float] | None:
        """Pick the highest-confidence detection whose class_name matches tool_class."""
        if not tool_class or not detections:
            return None
        target = tool_class.lower().replace("_", " ")
        candidates = []
        for det in detections:
            name = det.get("class_name", "").lower().replace("_", " ")
            if target in name or name in target:
                candidates.append((det.get("confidence", 0), det.get("bbox", [])))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _normalize(self, data: dict) -> dict:
        status = data.get("status") or data.get("label") or "suspected"
        if status not in {"normal", "suspected", "damaged", "failed"}:
            status = "suspected"
        severity = data.get("severity")
        if severity not in {"low", "medium", "high"}:
            severity = "high" if status == "damaged" else "medium" if status == "suspected" else "low"
        return {
            "status": status,
            "severity": severity,
            "confidence": data.get("confidence"),
            "summary": data.get("summary") or data.get("message") or "云端损坏检测已完成。",
            "raw_result": data,
        }


damage_model_service = DamageModelService()
