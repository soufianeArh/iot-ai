"""Camera registry logic. Blueprints stay thin and call into here."""
import logging

from app import db
from app.models import Camera, utcnow
from app.services.device_client import device_code_exists
from app.services.probe_service import ProbeError, probe_stream
from app.services import stream_service

log = logging.getLogger(__name__)

ALLOWED_SCHEMES = ("rtsp://", "rtsps://")


class ValidationError(Exception):
    """400-level problem with the caller's input."""


class NotFoundError(Exception):
    """404."""


def _validate_payload(payload: dict, require_url=True):
    if not isinstance(payload, dict):
        raise ValidationError("body must be a JSON object")

    name = (payload.get("name") or "").strip()
    if not name:
        raise ValidationError("name is required")
    if len(name) > 128:
        raise ValidationError("name must be at most 128 characters")

    rtsp_url = (payload.get("rtspUrl") or "").strip()
    if require_url:
        if not rtsp_url:
            raise ValidationError("rtspUrl is required")
        if not rtsp_url.lower().startswith(ALLOWED_SCHEMES):
            raise ValidationError("rtspUrl must start with rtsp:// or rtsps://")

    device_code = (payload.get("deviceCode") or "").strip() or None
    if device_code and not device_code_exists(device_code):
        raise ValidationError(f"unknown deviceCode '{device_code}'")

    return name, rtsp_url, device_code


def _apply_probe(camera: Camera):
    """Probe the stream and record the outcome on the camera. Never raises."""
    try:
        info = probe_stream(camera.rtsp_url)
    except ProbeError as exc:
        camera.status = "UNREACHABLE"
        camera.last_error = str(exc)[:500]
        camera.codec = camera.width = camera.height = camera.fps = None
    else:
        camera.status = "REACHABLE"
        camera.last_error = None
        camera.codec = info["codec"]
        camera.width = info["width"]
        camera.height = info["height"]
        camera.fps = info["fps"]
    camera.last_probed_at = utcnow()
    return camera


def register_camera(payload: dict) -> Camera:
    name, rtsp_url, device_code = _validate_payload(payload)

    if Camera.query.filter_by(rtsp_url=rtsp_url).first():
        raise ValidationError(f"a camera with this rtspUrl is already registered")

    camera = Camera(name=name, rtsp_url=rtsp_url, device_code=device_code, status="UNKNOWN")
    _apply_probe(camera)

    if camera.status == "UNREACHABLE":
        # Reject rather than store a broken camera: the whole point of Phase 5
        # is that a registered camera is a *verified* camera.
        raise ValidationError(f"stream could not be validated: {camera.last_error}")

    db.session.add(camera)
    db.session.commit()
    log.info("registered camera %s (%s %sx%s)", camera.name, camera.codec, camera.width, camera.height)

    # Register the stream with the media server. Best-effort: a media server
    # outage must not lose a camera that was already verified and saved.
    try:
        stream_service.register_path(camera.id, camera.rtsp_url)
    except stream_service.StreamError as exc:
        log.warning("camera %s saved but not registered with the media server: %s", camera.id, exc)

    return camera


def list_cameras():
    return Camera.query.order_by(Camera.id).all()


def get_camera(camera_id: int) -> Camera:
    camera = db.session.get(Camera, camera_id)
    if camera is None:
        raise NotFoundError(f"camera not found: {camera_id}")
    return camera


def reprobe_camera(camera_id: int) -> Camera:
    """Re-check an existing camera. Unlike registration this stores the failure."""
    camera = get_camera(camera_id)
    _apply_probe(camera)
    db.session.commit()
    return camera


def delete_camera(camera_id: int):
    camera = get_camera(camera_id)
    try:
        stream_service.unregister_path(camera_id)
    except stream_service.StreamError as exc:
        log.warning("could not remove path for camera %s: %s", camera_id, exc)
    db.session.delete(camera)
    db.session.commit()


def resync_streams() -> int:
    """
    Re-register every camera's RTSP mapping with the media server.

    MediaMTX keeps API-added paths in memory only - restarting it wipes them all,
    leaving cameras that exist in Postgres but cannot be watched. Postgres is the
    source of truth, so the fix is simply to replay it.

    register_path() is idempotent (it PATCHes a path that already exists), so this
    is safe to run repeatedly and safe to run from more than one worker.
    This does NOT start any streams: paths are sourceOnDemand, so the cameras
    stay disconnected until somebody watches them.

    Returns the number of camera paths restored.
    """
    restored = 0
    for camera in Camera.query.all():
        try:

            stream_service.register_path(camera.id, camera.rtsp_url)
            restored += 1
        except stream_service.StreamError as exc:
            log.warning("could not restore path for camera %s: %s", camera.id, exc)
    if restored:
        log.info("restored %s camera path(s) on the media server", restored)
    return restored
