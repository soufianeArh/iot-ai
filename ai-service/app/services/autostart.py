"""
Start the analysis tasks that should always be running, at boot.
"""
import logging
import os
import threading
import time

from app.services import camera_client, task_manager

log = logging.getLogger(__name__)

SPEC = os.getenv("AUTOSTART_TASKS", "")

# video-service has its own start_period; give it room without hanging forever.
MAX_WAIT_SECONDS = int(os.getenv("AUTOSTART_MAX_WAIT", "180"))
RETRY_SECONDS = 5


def _parse(spec: str):
    """"5:default,fire;3:default" -> [(5, "default,fire"), (3, "default")]"""
    entries = []
    for chunk in spec.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        camera, _, models = chunk.partition(":")
        try:
            entries.append((int(camera.strip()), models.strip() or None))
        except ValueError:
            log.warning("autostart: ignoring malformed entry %r", chunk)
    return entries


def _start_one(app, camera_id, models, deadline):
    """
    it tries to start analysis for one camera, and if it fails (because video-service isn't up yet),
    it just waits a bit and tries again up to a max time limit
    If it still hasn't worked by then, it gives up and logs "start it yourself"
    """
    while time.monotonic() < deadline:
        try:
            camera = camera_client.get_camera(camera_id)
            url = camera_client.stream_url(camera)
            status = task_manager.start(app, camera_id, url, models)
            log.info("autostart: camera %s running on %r", camera_id, status["model"])
            return True
        except Exception as exc:
            # Almost always "video-service not up yet" on the first passes
            log.debug("autostart: camera %s not ready (%s)", camera_id, exc)
            time.sleep(RETRY_SECONDS)

    log.warning("autostart: gave up on camera %s after %ss - start it by hand "
                "with POST /ai/tasks/%s", camera_id, MAX_WAIT_SECONDS, camera_id)
    return False


def run(app):
    """Called once from run.py. Returns immediately; work happens off-thread."""
    entries = _parse(SPEC)
    if not entries:
        return

    def worker():
        deadline = time.monotonic() + MAX_WAIT_SECONDS
        log.info("autostart: %s task(s) queued from AUTOSTART_TASKS", len(entries))
        for camera_id, models in entries:
            try:
                _start_one(app, camera_id, models, deadline)
            except Exception:                        # belt and braces
                log.exception("autostart: camera %s failed unexpectedly", camera_id)

    threading.Thread(target=worker, name="autostart", daemon=True).start()
