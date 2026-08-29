"""
Streaming control plane.

Browsers cannot play RTSP - no browser ever has. A media server sits in the
middle: it pulls RTSP from the camera and republishes it as something a browser
understands (HLS over HTTP, or WebRTC).

This module does NOT touch video. It only tells MediaMTX which cameras to pull,
by calling its config API. The video itself flows camera -> MediaMTX -> browser
and never passes through Python.

    register camera   ->  POST /v3/config/paths/add/cam1  {"source": "rtsp://..."}
    browser plays     ->  GET  /hls/cam1/index.m3u8       (proxied by nginx)

EasyAIoT does the same job differently: VIDEO/app/services/pusher_service.py
spawns an ffmpeg process per camera that pulls RTSP and pushes RTMP into SRS.
That gives per-stream control at the cost of managing N ffmpeg processes.
MediaMTX pulls natively, so there are no child processes to supervise.
"""
import logging
import os

import requests

log = logging.getLogger(__name__)

MEDIA_API = os.getenv("MEDIA_SERVER_API", "http://mediamtx:9997")
TIMEOUT = 5


class StreamError(Exception):
    """Media server refused or is unreachable."""


def path_name(camera_id: int) -> str:
    """MediaMTX calls a stream a 'path'. One per camera, derived from its id."""
    return f"cam{camera_id}"


def _api(method: str, endpoint: str, **kwargs):
    url = f"{MEDIA_API}{endpoint}"
    try:
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise StreamError(f"media server unreachable: {exc}")
    return response


def start_stream(camera_id: int, rtsp_url: str) -> dict:
    """
    Tell MediaMTX to serve this camera.

    sourceOnDemand=True is the important flag: MediaMTX only opens the RTSP
    connection when a viewer actually asks for the stream, and closes it 10s
    after the last viewer leaves. Without it, every registered camera would be
    pulled 24/7 whether anyone is watching or not.
    """
    name = path_name(camera_id)
    payload = {
        "source": rtsp_url,
        "sourceOnDemand": True,
        "sourceOnDemandCloseAfter": "10s",
    }

    response = _api("POST", f"/v3/config/paths/add/{name}", json=payload)
    if response.status_code == 400 and "already exists" in response.text.lower():
        # idempotent: re-issuing start on a running stream should not fail
        _api("PATCH", f"/v3/config/paths/patch/{name}", json=payload)
    elif not response.ok:
        raise StreamError(f"media server rejected the stream: {response.text[:200]}")

    log.info("stream '%s' registered -> %s", name, rtsp_url)
    return stream_info(camera_id)


def stop_stream(camera_id: int):
    name = path_name(camera_id)
    response = _api("DELETE", f"/v3/config/paths/delete/{name}")
    if not response.ok and response.status_code != 404:
        raise StreamError(f"could not stop stream: {response.text[:200]}")
    log.info("stream '%s' removed", name)


def stream_info(camera_id: int) -> dict:
    """
    Playback URLs plus live state.

    URLs are relative on purpose: nginx proxies /hls/ and /whep/ on the same
    origin as the page, so the browser needs no hostname and no CORS.
    """
    name = path_name(camera_id)
    response = _api("GET", f"/v3/paths/get/{name}")

    configured = response.ok
    ready = bool(response.json().get("ready")) if configured else False

    return {
        "path": name,
        "configured": configured,
        "ready": ready,          # True only while a viewer is connected (on-demand)
        "hlsUrl": f"/hls/{name}/index.m3u8",
        "webrtcUrl": f"/whep/{name}/whep",
    }
