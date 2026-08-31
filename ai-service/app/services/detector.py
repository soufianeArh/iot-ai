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

# Extra models, as "name=path,name=path". The COCO model has no fire or flood
# class, so a camera watching a field needs different weights - but a camera
# watching a gate still needs person and bus. One global model cannot serve
# both, so models are named and chosen per task.
EXTRA_MODELS = os.getenv("YOLO_EXTRA_MODELS", "")

DEFAULT_MODEL = "default"

# PyTorch uses EVERY core for inference by default. On a laptop already running
# ffmpeg encode + decode + a media server, that starves everything else - health
# checks time out and the whole stack goes unhealthy. Two threads is plenty for
# yolov8n and leaves the machine usable.
TORCH_THREADS = int(os.getenv("TORCH_THREADS", "2"))

_models = {}                    # name -> loaded YOLO
_lock = threading.Lock()


class UnknownModel(Exception):
    """Asked for a model that was never configured. Message is client-safe."""


def _paths():
    """name -> weights path, from the two environment variables."""
    paths = {DEFAULT_MODEL: MODEL_PATH}
    for pair in EXTRA_MODELS.split(","):
        pair = pair.strip()
        if not pair:
            continue
        name, _, path = pair.partition("=")
        if name.strip() and path.strip():
            paths[name.strip()] = path.strip()
    return paths


def available():
    """What can be asked for, without loading anything. Weights are big and
    each one costs RAM, so listing must stay free."""
    return sorted(_paths())


def get_model(name: str = None):
    """Load a model on first use, then reuse it. Each name is loaded once."""
    name = name or DEFAULT_MODEL
    model = _models.get(name)
    if model is not None:
        return model

    with _lock:
        if name in _models:                         # re-check inside the lock
            return _models[name]

        paths = _paths()
        if name not in paths:
            raise UnknownModel(
                f"unknown model {name!r}; available: {', '.join(sorted(paths))}")

        import torch
        torch.set_num_threads(TORCH_THREADS)

        from ultralytics import YOLO
        log.info("loading YOLO model %r from %s (torch threads=%s)",
                 name, paths[name], TORCH_THREADS)
        model = YOLO(paths[name])

        # Warm up INSIDE the lock. Ultralytics fuses conv+batchnorm lazily, on
        # the first predict. Two workers starting at once both enter that
        # fusion and one sees a half-rewritten module:
        #     'Conv' object has no attribute 'bn'
        # A throwaway inference here forces it to completion while we still
        # hold the lock, so every caller afterwards gets a finished model.
        import numpy as np
        model.predict(np.zeros((64, 64, 3), dtype=np.uint8), verbose=False)

        log.info("model %r loaded, classes: %s", name, model.names)
        _models[name] = model
        return model


def class_names(name: str = None):
    return get_model(name).names


def loaded_classes() -> dict:
    """Classes of the models already in memory, without loading any.

    Deliberately does not call get_model(): reporting what the system CAN
    detect must never cost a 10s model load, and a model that no task has
    used yet has nothing to report anyway.
    """
    return {name: sorted(model.names.values()) for name, model in _models.items()}
