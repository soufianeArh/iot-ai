"""
Generic audit hook: after every mutating request, ship one row to
auth-service's /internal/audit. Reads are never recorded. Python port of the
Java services' AuditFilter + AuditRules, keep the three in step.

Best effort and off the request path, on a small thread pool, so a logging
failure never affects the response the user gets.
"""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

import jwt
import requests
from flask import request

log = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-before-anything-real-CHANGE-ME")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "").rstrip("/")

_READ_METHODS = {"GET", "HEAD", "OPTIONS"}
_STACK_PREFIXES = {"api", "ai", "video", "auth", "internal"}
_RESOURCE = {
    "devices": "device", "zones": "zone", "users": "user",
    "rules": "rule", "alerts": "alert", "tasks": "task",
    "camera": "camera", "me": "profile",
}
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="audit")


def _should_audit(method: str, path: str) -> bool:
    if method in _READ_METHODS:
        return False
    if path.startswith("/actuator") or path.endswith("/health") or path == "/error":
        return False
    # not real state changes: starting/stopping a stream, testing a camera
    if path.endswith("/stream") or path.endswith("/probe"):
        return False
    if path == "/ai/chat" or path in ("/api/auth/login", "/api/auth/logout"):
        return False
    return method in ("POST", "PUT", "PATCH", "DELETE")


def _action(method: str, path: str) -> str:
    if path.endswith("/ack"):
        return "ACK"
    return {"POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}.get(method, method)


def _outcome(status: int) -> str:
    if 200 <= status < 300:
        return "SUCCESS"
    if status in (401, 403):
        return "DENIED"
    if 400 <= status < 500:
        return "REJECTED"
    if status >= 500:
        return "ERROR"
    return "SUCCESS"


def _segments(path: str) -> list[str]:
    return [s for s in path.split("/") if s and s not in _STACK_PREFIXES]


def _resource(path: str) -> str | None:
    seg = _segments(path)
    return _RESOURCE.get(seg[0], seg[0]) if seg else None


def _resource_id(path: str) -> str | None:
    seg = _segments(path)
    return seg[1] if len(seg) >= 2 and seg[1].isdigit() else None


def _service_token() -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": "audit", "role": "SERVICE", "iat": now, "exp": now + 300},
        JWT_SECRET, algorithm="HS512",
    )


def _actor() -> tuple[str | None, str | None]:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, None
    try:
        claims = jwt.decode(header[len("Bearer "):], JWT_SECRET, algorithms=["HS512"])
    except jwt.PyJWTError:
        return None, None
    return claims.get("sub"), claims.get("role")


def _client_ip() -> str | None:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr


def _post(row: dict) -> None:
    # Runs on the thread pool: must not touch `request`.
    try:
        requests.post(
            f"{AUTH_SERVICE_URL}/internal/audit",
            json=row,
            headers={"Authorization": f"Bearer {_service_token()}"},
            timeout=5,
        )
    except requests.RequestException as exc:
        log.debug("audit row dropped: %s", exc)


def install(app, service_name: str) -> None:
    if not AUTH_SERVICE_URL:
        log.warning("audit reporting disabled: AUTH_SERVICE_URL not set")
        return

    @app.after_request
    def _audit(response):
        try:
            method, path = request.method, request.path
            if _should_audit(method, path):
                actor, role = _actor()
                # A SERVICE token is the stack talking to itself, not a person.
                if role != "SERVICE":
                    _pool.submit(_post, {
                        "actor": actor, "actorRole": role, "service": service_name,
                        "method": method, "action": _action(method, path),
                        "resource": _resource(path), "resourceId": _resource_id(path),
                        "path": path, "status": response.status_code,
                        "outcome": _outcome(response.status_code), "ip": _client_ip(),
                    })
        except Exception as exc:  # never break the response
            log.debug("audit skipped: %s", exc)
        return response
