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

#camrea metdata (no stream,)
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
    media_rtsp = os.getenv("MEDIA_RTSP_BASE", "rtsp://mediamtx:8554")
    return f"{media_rtsp}/cam{camera['id']}"
