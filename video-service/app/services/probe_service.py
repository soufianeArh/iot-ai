"""
RTSP validation via ffprobe.

Everything here is about one lesson: external streams are slow and unreliable,
so every call is bounded by a timeout. A camera that is merely unreachable must
never be able to hang a request thread.
"""
import json
import logging
import os
import shutil
import subprocess

log = logging.getLogger(__name__)

# How long to let ffprobe negotiate RTSP and gather stream metadata.
#
# 12s was too tight and only ever passed by luck: measured on a loaded host the
# original sample stream probed in ~12s and a second, equally valid one took
# 24-50s, so registering a good camera failed intermittently. The cost of a
# larger value is that an unreachable camera holds a request open for longer -
# which is why it stays bounded, and configurable, so a fast host can lower it
# again without a rebuild.
PROBE_TIMEOUT_SECONDS = int(os.getenv("PROBE_TIMEOUT_SECONDS", "45"))


class ProbeError(Exception):
    """Raised when a stream cannot be probed. Message is safe to return to a client."""


def _parse_fps(rate: str):
    """ffprobe reports frame rates as fractions, e.g. '30000/1001'."""
    if not rate or rate == "0/0":
        return None
    try:
        if "/" in rate:
            num, den = rate.split("/", 1)
            den = float(den)
            return round(float(num) / den, 2) if den else None
        return round(float(rate), 2)
    except (ValueError, ZeroDivisionError):
        return None


def probe_stream(rtsp_url: str) -> dict:
    """
    Open the stream, read enough to identify it, then disconnect.

    Returns {'codec', 'width', 'height', 'fps'} or raises ProbeError.
    """
    if not shutil.which("ffprobe"):
        raise ProbeError("ffprobe is not installed in this container")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-rtsp_transport", "tcp",     # UDP silently drops behind NAT/Docker
        "-select_streams", "v:0",     # first video stream only
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate",
        "-of", "json",
        "-timeout", str(PROBE_TIMEOUT_SECONDS * 1_000_000),  # microseconds
        rtsp_url,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,  # hard backstop if ffprobe ignores its own
        )
    except subprocess.TimeoutExpired:
        raise ProbeError(f"stream did not respond within {PROBE_TIMEOUT_SECONDS}s")
    except OSError as exc:
        raise ProbeError(f"could not run ffprobe: {exc}")

    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        raise ProbeError(detail[-1] if detail else "ffprobe failed with no output")

    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError:
        raise ProbeError("ffprobe returned unreadable output")

    if not streams:
        raise ProbeError("no video stream found at this URL")

    stream = streams[0]
    return {
        "codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "fps": _parse_fps(stream.get("avg_frame_rate")),
    }
