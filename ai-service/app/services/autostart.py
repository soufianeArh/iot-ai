"""
Start the analysis tasks that should always be running, at boot.

The task registry lives in memory, so after every restart nothing analyses
anything until someone POSTs. For a camera that is meant to be permanently on
that is a silent outage - the stack looks healthy and no detections appear.

Configured with one variable:

    AUTOSTART_TASKS=5:default,fire;3:default

Two rules this must obey:

  * It runs in a BACKGROUND THREAD, not at import. Resolving a camera means an
    HTTP call to video-service, which is usually not up yet when ai-service
    starts - blocking here would deadlock the healthcheck.
  * It must NEVER raise into the app. A camera that is unplugged, deleted, or
    misconfigured is a warning in the log, not a container that will not boot.
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
    """Keep trying until the camera resolves or the deadline passes."""
    while time.monotonic() < deadline:
        try:
            camera = camera_client.get_camera(camera_id)
            url = camera_client.stream_url(camera)
            status = task_manager.start(app, camera_id, url, models)
            log.info("autostart: camera %s running on %r", camera_id, status["model"])
            return True
        except Exception as exc:
            # Almost always "video-service not up yet" on the first passes.
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
