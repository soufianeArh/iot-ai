"""
equivaelent to controller !!!
"""
import logging

from flask import Blueprint, jsonify, request

from app.services import camera_service, stream_service
from app.services.camera_service import NotFoundError, ValidationError
from app.services.stream_service import StreamError

log = logging.getLogger(__name__)

camera_bp = Blueprint("camera", __name__)


@camera_bp.errorhandler(ValidationError)
def _handle_validation(exc):
    return jsonify({"status": 400, "error": "Bad Request", "message": str(exc)}), 400


@camera_bp.errorhandler(NotFoundError)
def _handle_not_found(exc):
    return jsonify({"status": 404, "error": "Not Found", "message": str(exc)}), 404


@camera_bp.errorhandler(StreamError)
def _handle_stream(exc):
    return jsonify({"status": 502, "error": "Bad Gateway", "message": str(exc)}), 502


@camera_bp.route("", methods=["POST"])
def create():
    camera = camera_service.register_camera(request.get_json(silent=True))
    return jsonify(camera.to_dict()), 201, {"Location": f"/video/camera/{camera.id}"}


@camera_bp.route("", methods=["GET"])
def list_all():
    return jsonify([c.to_dict() for c in camera_service.list_cameras()])


@camera_bp.route("/<int:camera_id>", methods=["GET"])
def get_one(camera_id):
    return jsonify(camera_service.get_camera(camera_id).to_dict())

#noCRUD just test
@camera_bp.route("/<int:camera_id>/probe", methods=["POST"])
def probe(camera_id):
    return jsonify(camera_service.reprobe_camera(camera_id).to_dict())


@camera_bp.route("/<int:camera_id>", methods=["DELETE"])
def delete(camera_id):
    camera_service.delete_camera(camera_id)
    return "", 204


"""
all three are just HTTP calls to MediaMTX's own control API (no rtsp made)
check the status inside mediamtx server / register / and delete 
"""
@camera_bp.route("/<int:camera_id>/stream", methods=["GET"])
def stream_status(camera_id):
    camera_service.get_camera(camera_id)          # 404 if the camera is unknown
    return jsonify(stream_service.path_info(camera_id))


@camera_bp.route("/<int:camera_id>/stream", methods=["POST"])
def stream_register(camera_id):
    camera = camera_service.get_camera(camera_id)
    return jsonify(stream_service.register_path(camera.id, camera.rtsp_url))


@camera_bp.route("/<int:camera_id>/stream", methods=["DELETE"])
def stream_unregister(camera_id):
    camera_service.get_camera(camera_id)
    stream_service.unregister_path(camera_id)
    return "", 204
