"""
Looks cameras up in video-service.

ai-service holds no camera table of its own - video-service owns that. Asking
over HTTP keeps one owner per piece of data, at the cost of a network call.
"""
import logging
import os

import requests

log = logging.getLogger(__name__)

VIDEO_SERVICE_URL = os.getenv("VIDEO_SERVICE_URL", "http://video-service:6000")
TIMEOUT = 5


class CameraLookupError(Exception):
    pass


def get_camera(camera_id: int) -> dict:
    try:
        response = requests.get(f"{VIDEO_SERVICE_URL}/video/camera/{camera_id}", timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise CameraLookupError(f"video-service unreachable: {exc}")

    if response.status_code == 404:
        raise CameraLookupError(f"camera not found: {camera_id}")
    if not response.ok:
        raise CameraLookupError(f"video-service returned {response.status_code}")
    return response.json()


def stream_url(camera: dict) -> str:
    """
    Read frames from the MEDIA SERVER, not from the camera directly.

    Cameras usually allow only a handful of simultaneous RTSP connections, and
    the browser is already using one. Pulling from MediaMTX means the camera
    still sees a single connection no matter how many workers and viewers there
    are - that is the whole point of having a media server.
    """
    media_rtsp = os.getenv("MEDIA_RTSP_BASE", "rtsp://mediamtx:8554")
    return f"{media_rtsp}/cam{camera['id']}"
