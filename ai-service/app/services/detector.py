"""
The YOLO model wrapper.

Loading the weights takes seconds and ~50 MB of RAM, so it is done once and
shared by every worker thread. Ultralytics releases the GIL during inference,
so threads genuinely run in parallel here.
"""
import logging
import os
import threading

log = logging.getLogger(__name__)

MODEL_PATH = os.getenv("YOLO_MODEL", "/app/yolov8n.pt")

# PyTorch uses EVERY core for inference by default. On a laptop already running
# ffmpeg encode + decode + a media server, that starves everything else - health
# checks time out and the whole stack goes unhealthy. Two threads is plenty for
# yolov8n and leaves the machine usable.
TORCH_THREADS = int(os.getenv("TORCH_THREADS", "2"))

_model = None
_lock = threading.Lock()


def get_model():
    """Load the model on first use, then reuse it."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:                      # re-check inside the lock
                import torch
                torch.set_num_threads(TORCH_THREADS)

                from ultralytics import YOLO
                log.info("loading YOLO model from %s (torch threads=%s)",
                         MODEL_PATH, TORCH_THREADS)
                _model = YOLO(MODEL_PATH)
                log.info("model loaded, %s classes", len(_model.names))
    return _model


def class_names():
    return get_model().names
