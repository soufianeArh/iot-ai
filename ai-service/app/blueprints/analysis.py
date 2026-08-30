"""HTTP routes for ai-service. Thin: parse, delegate, serialise."""
import logging

from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models import Detection
from app.services import camera_client, task_manager
from app.services.camera_client import CameraLookupError
from app.services.task_manager import TaskError

log = logging.getLogger(__name__)

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.errorhandler(CameraLookupError)
def _handle_lookup(exc):
    return jsonify({"status": 404, "error": "Not Found", "message": str(exc)}), 404


@analysis_bp.errorhandler(TaskError)
def _handle_task(exc):
    return jsonify({"status": 400, "error": "Bad Request", "message": str(exc)}), 400


# ------------------------------------------------------------------ tasks

@analysis_bp.route("/tasks", methods=["GET"])
def list_tasks():
    task_manager.reap()
    return jsonify(task_manager.list_all())


@analysis_bp.route("/tasks/<int:camera_id>", methods=["POST"])
def start_task(camera_id):
    camera = camera_client.get_camera(camera_id)
    url = camera_client.stream_url(camera)
    # current_app is a proxy; the worker thread needs the real object.
    app = current_app._get_current_object()
    return jsonify(task_manager.start(app, camera_id, url)), 202


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
