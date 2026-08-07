from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_device_key(x_device_key: str | None = Header(default=None)) -> None:
    """Validate device uploads when DEVICE_API_KEY is configured.

    The key is optional in development so the local demo can run quickly. Set
    DEVICE_API_KEY in production and send it from ESP32-P4 as X-Device-Key.
    """
    expected = get_settings().device_api_key
    if not expected:
        return
    if x_device_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid device key",
        )
