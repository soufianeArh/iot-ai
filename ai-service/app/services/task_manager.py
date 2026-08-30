"""
Keeps track of which cameras are being analysed.

This is the same spawn-and-supervise problem EasyAIoT solves in
VIDEO/app/services/algorithm_task_launcher_service.py - they spawn a process per
task, this spawns a thread. The registry lives in memory, so like MediaMTX's
paths it is lost on restart and must be rebuilt from the database.
"""
import logging
import threading

import requests

from app.services.worker import InferenceWorker

log = logging.getLogger(__name__)

_workers = {}                 # camera_id -> InferenceWorker
_lock = threading.Lock()


class TaskError(Exception):
    """Something stopped a task from starting or stopping."""


def start(app, camera_id: int, rtsp_url: str) -> dict:
    with _lock:
        existing = _workers.get(camera_id)
        if existing and existing.is_alive():
            return existing.status()               # idempotent

        worker = InferenceWorker(app, camera_id, rtsp_url)
        worker.start()
        _workers[camera_id] = worker
        log.info("started analysis for camera %s", camera_id)
        return worker.status()


def stop(camera_id: int):
    with _lock:
        worker = _workers.pop(camera_id, None)
    if worker is None:
        raise TaskError(f"no analysis running for camera {camera_id}")
    worker.stop()
    worker.join(timeout=10)                        # let the loop exit cleanly
    log.info("stopped analysis for camera %s", camera_id)


def status(camera_id: int):
    worker = _workers.get(camera_id)
    return worker.status() if worker else None


def list_all():
    with _lock:
        return [w.status() for w in _workers.values()]


def reap():
    """Drop workers whose thread has died, so a restart can recreate them."""
    with _lock:
        dead = [cid for cid, w in _workers.items() if not w.is_alive()]
        for cid in dead:
            log.warning("worker for camera %s died, removing from registry", cid)
            _workers.pop(cid, None)
    return dead
