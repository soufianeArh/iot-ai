"""
The detector registry.

Holds every model a task can be started with, loads each one once, and hands
back detections in ONE shape regardless of what produced them:

    [{"label": str, "confidence": float, "box": (x1, y1, x2, y2)}, ...]

Two families live here behind that interface:

  yolo  Ultralytics weights (COCO, fire). Fast, box detectors.
  hf    transformers detection models (plant disease). Slower, but they are
        where the specialised agricultural models actually exist - nobody
        publishes usable Ultralytics weights for leaf disease.

Keeping the difference inside this module is deliberate: the worker asks for
detections and does not care which library produced them, so adding a third
family later touches this file and nothing else.
"""
import logging
import os
import threading

log = logging.getLogger(__name__)

MODEL_PATH = os.getenv("YOLO_MODEL", "/app/yolov8n.pt")

# Extra Ultralytics weights, as "name=path,name=path". The COCO model has no
# fire class, so a field camera needs different weights - but a gate camera
# still needs person and bus. One global model cannot serve both, so models are
# named and chosen per task.
EXTRA_MODELS = os.getenv("YOLO_EXTRA_MODELS", "")

# transformers detection models, same syntax, pointing at a directory holding
# config.json + preprocessor_config.json + model.safetensors.
HF_MODELS = os.getenv("HF_MODELS", "")

# Per-model confidence floors, as "name=0.4,name=0.8".
#
# A single global threshold is wrong once models differ. Measured here: the
# plant model scores a genuine tomato blight at 0.569, which the global 0.65
# would discard entirely - the detection would simply never appear and the
# model would look broken. Meanwhile COCO wants 0.65 to stay quiet.
MODEL_CONFIDENCE = os.getenv("MODEL_CONFIDENCE", "")
DEFAULT_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.4"))

DEFAULT_MODEL = "default"
INFER_SIZE = int(os.getenv("INFER_SIZE", "640"))

# PyTorch uses EVERY core for inference by default. On a laptop already running
# ffmpeg encode + decode + a media server, that starves everything else - health
# checks time out and the whole stack goes unhealthy. Two threads is plenty for
# yolov8n and leaves the machine usable.
TORCH_THREADS = int(os.getenv("TORCH_THREADS", "2"))

_models = {}                    # name -> (kind, loaded thing)
_lock = threading.Lock()


class UnknownModel(Exception):
    #Raised when someone asks for a model name that isn't configured


def _pairs(spec: str) -> dict:
    out = {}
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, value = chunk.partition("=")
        if name.strip() and value.strip():
            out[name.strip()] = value.strip()
    return out


def _registry() -> dict:
    """name -> (kind, path)."""
    #builds the full list of available models
    reg = {DEFAULT_MODEL: ("yolo", MODEL_PATH)}
    for name, path in _pairs(EXTRA_MODELS).items():
        reg[name] = ("yolo", path)
    for name, path in _pairs(HF_MODELS).items():
        reg[name] = ("hf", path)
    return reg


def available():
    """just lists model names, without loading any of them into memory"""
    return sorted(_registry())


def confidence_for(name: str) -> float:
    try:
        return float(_pairs(MODEL_CONFIDENCE).get(name, DEFAULT_CONFIDENCE))
    except ValueError:
        return DEFAULT_CONFIDENCE


def _load(name: str):
    """
    Loads a model into memory the first time it's asked for,
    then caches it in _models so it's never reloaded again.
    """
    entry = _models.get(name)
    if entry is not None:
        return entry

    with _lock:
        if name in _models:                         # re-check inside the lock
            return _models[name]

        reg = _registry()
        if name not in reg:
            raise UnknownModel(
                f"unknown model {name!r}; available: {', '.join(sorted(reg))}")

        kind, path = reg[name]

        import numpy as np
        import torch
        torch.set_num_threads(TORCH_THREADS)

        if kind == "yolo":
            from ultralytics import YOLO
            log.info("loading YOLO model %r from %s", name, path)
            model = YOLO(path)

            # Warm up INSIDE the lock. Ultralytics fuses conv+batchnorm lazily,
            # on the first predict. Two workers starting at once both enter that
            # fusion and one sees a half-rewritten module:
            #     'Conv' object has no attribute 'bn'
            # A throwaway inference forces it to completion while we still hold
            # the lock, so every caller afterwards gets a finished model.
            model.predict(np.zeros((64, 64, 3), dtype=np.uint8), verbose=False)
            loaded = ("yolo", model)
        else:
            from transformers import AutoImageProcessor, AutoModelForObjectDetection
            log.info("loading transformers model %r from %s", name, path)
            processor = AutoImageProcessor.from_pretrained(path)
            hf = AutoModelForObjectDetection.from_pretrained(path)
            hf.eval()
            loaded = ("hf", (processor, hf))

        _models[name] = loaded
        log.info("model %r loaded, %s classes", name, len(_names(loaded)))
        return loaded


def _names(entry) -> dict:
    #returns a model's class names dict
    kind, model = entry
    return model.names if kind == "yolo" else model[1].config.id2label


def get_model(name: str = None):
    """
    returns the raw underlying model object,
    for callers that need direct access (rare — detect() is preferred)
    """
    return _load(name or DEFAULT_MODEL)[1]


def detect(name: str, frame, conf: float = None) -> list:
    """
    Run one model over one BGR frame. Uniform output for every family.
    Loads the model (if not already loaded), runs inference on one frame,
    and normalizes the output to the same shape ({label, confidence, box})
    regardless of whether it was a YOLO model or a transformers model   underneath
    """
    name = name or DEFAULT_MODEL
    kind, model = _load(name)
    threshold = conf if conf is not None else confidence_for(name)

    if kind == "yolo":
        result = model.predict(frame, conf=threshold, imgsz=INFER_SIZE, verbose=False)[0]
        hits = []
        for box in (result.boxes or []):
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            hits.append({"label": model.names[int(box.cls[0])],
                         "confidence": float(box.conf[0]),
                         "box": (x1, y1, x2, y2)})
        return hits

    import torch
    from PIL import Image
    processor, hf = model
    # transformers wants RGB; OpenCV frames are BGR.
    image = Image.fromarray(frame[:, :, ::-1])
    with torch.no_grad():
        outputs = hf(**processor(images=image, return_tensors="pt"))

    sizes = torch.tensor([image.size[::-1]])
    result = processor.post_process_object_detection(
        outputs, threshold=threshold, target_sizes=sizes)[0]

    hits = []
    for score, label, box in zip(result["scores"], result["labels"], result["boxes"]):
        x1, y1, x2, y2 = (int(v) for v in box.tolist())
        hits.append({"label": hf.config.id2label[int(label)],
                     "confidence": float(score),
                     "box": (x1, y1, x2, y2)})
    return hits


def class_names(name: str = None):
    #public wrapper around _names(), for a specific model
    return _names(_load(name or DEFAULT_MODEL))


def loaded_classes() -> dict:
    """
    reports classes only for models already loaded in memory
    deliberately does NOT trigger a load, so just checking
    "what can this system currently detect" never costs the RAM/time of loading a model nobody's using yet
    """
    return {name: sorted(_names(entry).values()) for name, entry in _models.items()}
