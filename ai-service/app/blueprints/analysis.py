"""
UI gives cameraID to ai-service
ai service holds no record of camera. so to get stream
step1: check video service (calls GET http://video-service:6000/video/camera/{camera_id}) can raise cameralookup error
the camera url is resolved
step2: then targets MediaMTX directly (stream_url

HTTP routes for ai-service. Thin: parse, delegate, serialise.
"""
import logging

from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models import Detection
from app.services import camera_client, detector, task_manager
from app.services.camera_client import CameraLookupError
from app.services.detector import UnknownModel
from app.services.task_manager import TaskError

log = logging.getLogger(__name__)

analysis_bp = Blueprint("analysis", __name__)

#CameraLookupError raised in camera_client.py
#ai-service tries to check a camera's existence by calling out to video-service
#and it fails (video service unreacheable - reach but no camera record - else)
@analysis_bp.errorhandler(CameraLookupError)
def _handle_lookup(exc):
    return jsonify({"status": 404, "error": "Not Found", "message": str(exc)}), 404


@analysis_bp.errorhandler(TaskError)
def _handle_task(exc):
    return jsonify({"status": 400, "error": "Bad Request", "message": str(exc)}), 400


# ------------------------------------------------------------------ tasks
"""
task: analyse a camera (each task has its own thread- each has its own db session) 
task =  in detection page (ai-servide): 
start stream → loop: wait interval → grab latest frame → run YOLO 
→ save detection(s) → check alert rules (creates an Alert if matched) →  repeat
  No queue. While YOLO is busy on one frame, all frames arriving in the meantime just get thrown away 
  — only the newest one is kept. When YOLO finishes, it grabs whatever's newest at that moment and repeats. 
"""


@analysis_bp.errorhandler(UnknownModel)
def _handle_unknown_model(exc):
    return jsonify({"status": 400, "error": "Bad Request", "message": str(exc)}), 400


@analysis_bp.route("/tasks", methods=["GET"])
#list running only tasks (camera)
def list_tasks():
    #cleans out any workers whose thread has silently died (crashed)
    task_manager.reap()
    return jsonify(task_manager.list_all())


@analysis_bp.route("/tasks/<int:camera_id>", methods=["POST"])
def start_task(camera_id):
    #looks the camera up in video-service (the call that can raise CameraLookupError → 404)
    camera = camera_client.get_camera(camera_id)

    #builds the MediaMTX RTSP URL (rtsp://mediamtx:8554/cam{id}), not the raw camera's own URL
    url = camera_client.stream_url(camera)
    # current_app is a proxy; the worker thread needs the real object.
    app = current_app._get_current_object()


    body = request.get_json(silent=True) or {}
   # get the model name to be linked to YOLO
    model_name = request.args.get("model") or body.get("model")
    #OLO itself has no concept of "interval" at all
    #interval (ai-service's YOLO sampling)
    # only affects how often the analysis worker looks at a frame
    interval = request.args.get("interval", type=float) or body.get("interval")
    # Randomises the wait between frames. Only needed when the source itself
    # loops - see InferenceWorker.jitter.
    jitter = request.args.get("jitter", type=float) or body.get("jitter")
    return jsonify(
        task_manager.start(app, camera_id, url, model_name, interval, jitter)), 202


@analysis_bp.route("/tasks/<int:camera_id>", methods=["DELETE"])
def stop_task(camera_id):
    task_manager.stop(camera_id)
    return "", 204


@analysis_bp.route("/tasks/<int:camera_id>", methods=["GET"])
def task_status(camera_id):
    status = task_manager.status(camera_id)
    if status is None:
        return jsonify({"cameraId": camera_id, "running": False}), 200
    return jsonify(status)


@analysis_bp.route("/models", methods=["GET"])
def list_models():
    """Which weight sets a task can be started with, and - for the ones already
    in memory - what they detect. Deliberately does not load anything: this is
    polled by the UI, and a 10s model load per poll would be absurd."""
    loaded = detector.loaded_classes()
    return jsonify([{"name": n, "loaded": n in loaded, "classes": loaded.get(n, [])}
                    for n in detector.available()])


@analysis_bp.route("/labels", methods=["GET"])
def list_labels():
    """Every class any configured model can detect, for the rule form.

    This DOES load the weights, which is why it is a separate route from
    /models: it is called once when a form opens, not on a poll. The
    alternative - a free-text label box - silently accepts 'vehicle' or 'car'
    and the rule then never fires, with nothing anywhere to explain why.
    """
    out = {}
    for name in detector.available():
        try:
            # class_names(), not get_model().names: only Ultralytics models
            # expose .names. A transformers model keeps its labels in
            # config.id2label, and reaching for .names silently produced an
            # empty class list for the plant model - the dropdown offered
            # nothing and looked like the model had no classes.
            out[name] = sorted(detector.class_names(name).values())
        except Exception as exc:
            log.warning("could not load model %s for labels: %s", name, exc)
            out[name] = []
    return jsonify({"byModel": out,
                    "all": sorted({c for cs in out.values() for c in cs})})


# ------------------------------------------------------------------ detections

@analysis_bp.route("/detections", methods=["GET"])
def list_detections():
    query = Detection.query
    camera_id = request.args.get("cameraId", type=int)
    if camera_id is not None:
        query = query.filter_by(camera_id=camera_id)
    label = request.args.get("label")
    if label:
        query = query.filter_by(label=label)

    limit = min(request.args.get("limit", default=50, type=int), 500)
    rows = query.order_by(Detection.detected_at.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in rows])


@analysis_bp.route("/detections/summary", methods=["GET"])
def summary():
    """How many of each label, per camera - the shape a dashboard wants."""
    rows = (db.session.query(Detection.camera_id, Detection.label,
                             db.func.count(Detection.id))
            .group_by(Detection.camera_id, Detection.label)
            .order_by(db.func.count(Detection.id).desc())
            .all())
    return jsonify([{"cameraId": c, "label": l, "count": n} for c, l, n in rows])
