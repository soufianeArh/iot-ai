"""
HTTP client for device-service.

_validate_payload() calls device_code_exists() from here to
  check a deviceCode against device-service, since cameras (video-service) and devices (device-service) live in completely different
  services/databases with no shared DB access.
"""
import logging
import os

import requests

log = logging.getLogger(__name__)

DEVICE_SERVICE_URL = os.getenv("DEVICE_SERVICE_URL", "http://device-service:8080")
TIMEOUT_SECONDS = 5


def device_code_exists(device_code: str) -> bool:
    """
    True if device-service knows this code.

    Fails OPEN: if device-service is unreachable we allow the write rather than
    block camera registration on an unrelated outage. The alternative (fail
    closed) is defensible too - it is a genuine availability/consistency call.
    """
    if not device_code:
        return True

    try:
        response = requests.get(f"{DEVICE_SERVICE_URL}/api/devices", timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return any(d.get("deviceCode") == device_code for d in response.json())
    except requests.RequestException as exc:
        log.warning("device-service unreachable (%s); accepting deviceCode '%s' unchecked",
                    exc, device_code)
        return True
