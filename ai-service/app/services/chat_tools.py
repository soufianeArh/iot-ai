"""
The tools the chat assistant may call.

This is the part that keeps a chatbot honest. The model does NOT write SQL and
does NOT see the database. It picks one of the functions below and fills in its
arguments; this module runs a parameterised query and hands back JSON.

So the model does the two things it is genuinely good at - deciding which
question to ask, and turning rows into a sentence - and none of the things it is
bad at, like remembering how many alerts there were.

Consequences worth noticing:
  * it cannot read a table that is not exposed here
  * it cannot write, delete or DROP anything
  * it cannot run a query that takes 40 seconds
  * every number in an answer came from Postgres, not from the model

Ownership is respected: detections and alerts are ours and queried directly;
cameras belong to video-service and devices to device-service, so those go over
HTTP exactly as the rest of ai-service does.
"""
import logging
import os
from datetime import timedelta

import requests

from app import db
from app.models import Alert, AlertRule, Detection, utcnow

log = logging.getLogger(__name__)

VIDEO_SERVICE_URL = os.getenv("VIDEO_SERVICE_URL", "http://video-service:6000")
DEVICE_SERVICE_URL = os.getenv("DEVICE_SERVICE_URL", "http://device-service:8080")
HTTP_TIMEOUT = 5

# A hard ceiling on rows returned to the model. Not for the database's sake -
# for the prompt's. Small models drown in long JSON and start inventing.
MAX_ROWS = 25


def _since(minutes: int):
    return utcnow() - timedelta(minutes=max(1, int(minutes)))


def _get(url: str):
    """GET another service, returning a readable error instead of raising."""
    try:
        response = requests.get(url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"error": f"could not reach {url}: {exc}"}


# ------------------------------------------------------------------ detections

def count_detections(label: str = None, camera_id: int = None,
                     since_minutes: int = 1440) -> dict:
    """How many of each label, grouped. The 'how many' question."""
    query = (db.session.query(Detection.camera_id, Detection.label,
                              db.func.count(Detection.id))
             .filter(Detection.detected_at >= _since(since_minutes)))
    if label:
        query = query.filter(Detection.label == label.lower())
    if camera_id is not None:
        query = query.filter(Detection.camera_id == camera_id)

    rows = (query.group_by(Detection.camera_id, Detection.label)
            .order_by(db.func.count(Detection.id).desc()).limit(MAX_ROWS).all())

    return {
        "windowMinutes": since_minutes,
        "total": sum(n for _, _, n in rows),
        "groups": [{"cameraId": c, "label": l, "count": n} for c, l, n in rows],
    }


def recent_detections(label: str = None, camera_id: int = None,
                      limit: int = 10) -> dict:
    """The most recent sightings. The 'when did you last see' question."""
    query = Detection.query
    if label:
        query = query.filter(Detection.label == label.lower())
    if camera_id is not None:
        query = query.filter(Detection.camera_id == camera_id)

    rows = (query.order_by(Detection.detected_at.desc())
            .limit(min(int(limit), MAX_ROWS)).all())
    return {"detections": [
        {"cameraId": r.camera_id, "label": r.label,
         "confidence": round(r.confidence, 2),
         "detectedAt": r.detected_at.isoformat()} for r in rows]}


# ---------------------------------------------------------------------- alerts

def search_alerts(camera_id: int = None, severity: str = None,
                  acknowledged: bool = None, since_minutes: int = None,
                  limit: int = 10) -> dict:
    """Alerts, filtered. acknowledged=false is 'what still needs attention'."""
    query = Alert.query
    if camera_id is not None:
        query = query.filter(Alert.camera_id == camera_id)
    if severity:
        query = query.filter(Alert.severity == severity.upper())
    if acknowledged is not None:
        query = query.filter(Alert.acknowledged.is_(bool(acknowledged)))
    if since_minutes:
        query = query.filter(Alert.raised_at >= _since(since_minutes))

    rows = (query.order_by(Alert.raised_at.desc())
            .limit(min(int(limit), MAX_ROWS)).all())
    return {
        "matched": query.count(),
        "alerts": [{"id": a.id, "rule": a.rule_name, "cameraId": a.camera_id,
                    "severity": a.severity, "what": f"{a.count} x {a.label}",
                    "confidence": round(a.max_confidence, 2),
                    "acknowledged": a.acknowledged,
                    "raisedAt": a.raised_at.isoformat()} for a in rows],
    }


def list_alert_rules() -> dict:
    """The configured rules. Answers 'why did that fire' and 'what am I watching for'."""
    return {"rules": [r.to_dict() for r in AlertRule.query.order_by(AlertRule.id).all()]}


# ------------------------------------------------- cameras and devices (remote)

def list_cameras() -> dict:
    """Cameras with their last probe result. Owned by video-service."""
    cameras = _get(f"{VIDEO_SERVICE_URL}/video/camera")
    if isinstance(cameras, dict):
        return cameras                      # the error dict from _get

    out = []
    for camera in cameras:
        # Live streaming state lives in MediaMTX, not in any table.
        state = _get(f"{VIDEO_SERVICE_URL}/video/camera/{camera['id']}/stream")
        out.append({
            "id": camera["id"], "name": camera["name"],
            "status": camera["status"],           # REACHABLE / UNREACHABLE
            "resolution": (f"{camera['width']}x{camera['height']}"
                           if camera.get("width") else None),
            "fps": camera.get("fps"),
            "lastError": camera.get("lastError"),
            "streaming": bool(state.get("ready")) if isinstance(state, dict) else None,
        })
    return {"cameras": out}


def list_devices() -> dict:
    """Devices plus their latest reported values. Owned by device-service."""
    devices = _get(f"{DEVICE_SERVICE_URL}/api/devices")
    if isinstance(devices, dict):
        return devices

    out = []
    for device in devices:
        properties = _get(f"{DEVICE_SERVICE_URL}/api/devices/{device['id']}/properties")
        latest = ({p["key"]: p["value"] for p in properties}
                  if isinstance(properties, list) else {})
        out.append({
            "deviceCode": device["deviceCode"], "name": device["name"],
            "status": device["status"],           # ONLINE / OFFLINE, set over MQTT
            "latestValues": latest,
        })
    return {"devices": out}


# -------------------------------------------------------------------- overview

def overview() -> dict:
    """
    Everything that might need attention, in one call.

    Exists because "anything I should look at?" is the question people actually
    ask, and answering it otherwise costs the model four round trips - which on
    a small local model is where it starts losing the thread.
    """
    from app.services import task_manager

    open_alerts = Alert.query.filter_by(acknowledged=False).count()
    recent = search_alerts(since_minutes=60, limit=5)

    cameras = list_cameras().get("cameras", [])
    devices = list_devices().get("devices", [])

    return {
        "openAlerts": open_alerts,
        "alertsLastHour": recent.get("matched", 0),
        "mostRecentAlerts": recent.get("alerts", [])[:3],
        "camerasUnreachable": [c["name"] for c in cameras
                               if c.get("status") != "REACHABLE"],
        "devicesOffline": [d["name"] for d in devices
                           if d.get("status") != "ONLINE"],
        "analysisRunningOnCameras": [t["cameraId"] for t in task_manager.list_all()
                                     if t.get("running")],
        "detectionsLastHour": count_detections(since_minutes=60).get("total", 0),
    }


# ------------------------------------------------------------------- registry
#
# JSON Schema per tool, in the OpenAI function-calling format that Ollama,
# Groq and OpenAI all accept. The `description` fields are prompt engineering:
# they are the only thing telling the model when each tool applies, so they say
# WHEN to use it, not just what it does.

REGISTRY = {
    "overview": overview,
    "count_detections": count_detections,
    "recent_detections": recent_detections,
    "search_alerts": search_alerts,
    "list_alert_rules": list_alert_rules,
    "list_cameras": list_cameras,
    "list_devices": list_devices,
}

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "overview",
            "description": ("System status in one call: open alerts, unreachable "
                            "cameras, offline devices, recent activity. Use this "
                            "for broad questions like 'is everything ok', "
                            "'anything I should look at', 'what is the status'."),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_detections",
            "description": ("Count objects seen by the cameras, grouped by camera "
                            "and label. Use for 'how many people did camera 3 see', "
                            "'what has been detected today', 'which camera is busiest'."),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string",
                              "description": "object class, e.g. person, bus, car, truck"},
                    "camera_id": {"type": "integer", "description": "restrict to one camera"},
                    "since_minutes": {"type": "integer",
                                      "description": "look-back window; 60 = last hour, 1440 = last day"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recent_detections",
            "description": ("The most recent sightings with timestamps. Use for "
                            "'when did you last see a bus', 'what was detected "
                            "most recently'."),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "object class, e.g. person"},
                    "camera_id": {"type": "integer"},
                    "limit": {"type": "integer", "description": "how many rows, max 25"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_alerts",
            "description": ("Alerts raised by the rules. Use for 'any alerts', "
                            "'what needs attention' (acknowledged=false), "
                            "'what fired in the last hour' (since_minutes=60)."),
            "parameters": {
                "type": "object",
                "properties": {
                    "camera_id": {"type": "integer"},
                    "severity": {"type": "string", "enum": ["INFO", "WARNING", "CRITICAL"]},
                    "acknowledged": {"type": "boolean",
                                     "description": "false = still open / unhandled"},
                    "since_minutes": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_alert_rules",
            "description": ("The alert rules that are configured, with their "
                            "thresholds and cooldowns. Use to explain WHY an "
                            "alert fired, or what the system is watching for."),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_cameras",
            "description": ("Cameras, their reachability, resolution and whether "
                            "they are streaming right now. Use for 'which cameras "
                            "are offline', 'is camera 3 working'."),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": ("IoT devices (sensors), their ONLINE/OFFLINE state and "
                            "their latest reported values such as temperature and "
                            "humidity. Use for 'what is the temperature', "
                            "'which devices are offline'."),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run(name: str, arguments: dict):
    """Dispatch one tool call. Never raises - the model gets the error as data."""
    function = REGISTRY.get(name)
    if function is None:
        return {"error": f"no such tool: {name}"}
    try:
        log.info("tool call: %s(%s)", name, arguments)
        return function(**(arguments or {}))
    except TypeError as exc:
        # Small models routinely invent arguments. Telling the model what it did
        # wrong lets it retry, which is far better than a 500 to the user.
        return {"error": f"bad arguments for {name}: {exc}"}
    except Exception as exc:
        log.exception("tool %s failed", name)
        return {"error": f"{name} failed: {str(exc)[:200]}"}
