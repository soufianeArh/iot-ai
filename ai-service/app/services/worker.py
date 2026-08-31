"""
One inference worker per camera.

The loop is deliberately simple: open the stream, grab a frame every N seconds,
run YOLO on it, write rows and an annotated JPEG. Everything that can fail
(stream drops, decode errors, model errors) is caught so one bad camera cannot
take the service down.

Why sample instead of processing every frame: a 15 fps stream is 15 inferences
per second per camera. On CPU that is impossible and pointless - nothing in a
scene changes meaningfully in 66 ms. Sampling every 2s is ~30x less work and
loses nothing that matters for alerting.
"""
import logging
import os
import threading
import time
from datetime import datetime, timezone

import cv2

from app import db
from app.models import Detection
from app.services import rule_engine
from app.services.detector import DEFAULT_MODEL, get_model

log = logging.getLogger(__name__)

SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "/snapshots")
SAMPLE_INTERVAL = float(os.getenv("SAMPLE_INTERVAL_SECONDS", "3"))
# YOLO resizes internally anyway; saying so explicitly keeps a 1280x1706
# portrait frame from being letterboxed into something much larger.
INFER_SIZE = int(os.getenv("INFER_SIZE", "640"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.4"))
OPEN_TIMEOUT = 20


class InferenceWorker(threading.Thread):
    """Analyses one camera until asked to stop."""

    def __init__(self, app, camera_id: int, rtsp_url: str, model_name: str = None,
                 interval: float = None):
        super().__init__(name=f"worker-cam{camera_id}", daemon=True)
        self.app = app
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        # One or more weight sets, e.g. "default,fire". A model only reports
        # the classes it was trained on, so detecting cars AND fire needs two
        # of them - there is no single set of weights here that does both.
        # Fixed for the life of the task: changing it means stop and start,
        # which keeps stored detections consistent with one class vocabulary.
        self.model_names = [n.strip() for n in (model_name or DEFAULT_MODEL).split(",")
                            if n.strip()]
        # Per task, because cost scales with the number of models. Two models
        # every 6s is the same load as one every 3s, so a camera can buy back
        # what the second model costs without slowing the others down.
        self.interval = float(interval) if interval else SAMPLE_INTERVAL
        # NOT self._stop: threading.Thread already defines _stop() as an
        # internal method, and join() calls it when the thread finishes.
        # Shadowing it with an Event makes join() raise
        # "TypeError: 'Event' object is not callable".
        self._stop_event = threading.Event()
        self.frames_analysed = 0
        self.detections_saved = 0
        self.alerts_raised = 0
        self.last_error = None
        self.started_at = datetime.now(timezone.utc)

    def stop(self):
        self._stop_event.set()

    # ---------------------------------------------------------------- run loop

    def run(self):
        log.info("worker for camera %s starting on %s", self.camera_id, self.rtsp_url)
        while not self._stop_event.is_set():
            capture = self._open_stream()
            if capture is None:
                # stream not up yet (MediaMTX pulls on demand) - back off and retry
                self._stop_event.wait(5)
                continue
            try:
                self._consume(capture)
            finally:
                capture.release()
        log.info("worker for camera %s stopped", self.camera_id)

    def _open_stream(self):
        # Force TCP: RTSP over UDP silently loses packets across Docker's NAT.
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        capture = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if not capture.isOpened():
            self.last_error = "could not open stream"
            capture.release()
            return None
        # Keep the internal buffer tiny so grabbed frames are current, not stale.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.last_error = None
        return capture

    def _consume(self, capture):
        next_run = 0.0
        while not self._stop_event.is_set():
            # grab() decodes nothing - it just advances past frames we skip.
            if not capture.grab():
                self.last_error = "stream ended"
                return
            now = time.monotonic()
            if now < next_run:
                # grab() only advances the decoder; without a small yield this
                # loop spins as fast as frames arrive and burns a whole core.
                time.sleep(0.01)
                continue
            next_run = now + self.interval

            ok, frame = capture.retrieve()
            if not ok:
                continue
            try:
                self._analyse(frame)
            except Exception as exc:                    # never kill the loop
                self.last_error = str(exc)[:200]
                log.exception("camera %s: inference failed", self.camera_id)

    # ---------------------------------------------------------------- analysis

    def _analyse(self, frame):
        # One decode, N models. Each is a separate forward pass - this is
        # genuinely N times the inference cost, not a free lunch.
        hits = []                      # (model, box) across every model
        for name in self.model_names:
            model = get_model(name)
            result = model.predict(frame, conf=MIN_CONFIDENCE,
                                   imgsz=INFER_SIZE, verbose=False)[0]
            if result.boxes is not None and len(result.boxes):
                hits.append((model, result))
        self.frames_analysed += 1

        if not hits:
            return

        snapshot_name = self._save_snapshot([r for _, r in hits])

        rows = []
        for model, result in hits:
            for box in result.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                rows.append(Detection(
                    camera_id=self.camera_id,
                    label=model.names[int(box.cls[0])],
                    confidence=float(box.conf[0]),
                    x1=x1, y1=y1, x2=x2, y2=y2,
                    snapshot=snapshot_name,
                ))

        # Each worker is its own thread, so it needs its own app context and
        # its own session - SQLAlchemy sessions are not thread-safe.
        with self.app.app_context():
            db.session.add_all(rows)
            db.session.commit()

            # Phase 8: decide whether this frame is worth telling anyone about.
            # Runs on the inference thread, so it must stay cheap - one indexed
            # SELECT and, rarely, one INSERT. And it must never be able to kill
            # the loop: a bad rule should cost alerts, not inference.
            try:
                self.alerts_raised += len(
                    rule_engine.evaluate(self.camera_id, rows, snapshot_name))
            except Exception as exc:
                self.last_error = f"rule evaluation failed: {str(exc)[:150]}"
                log.exception("camera %s: rule evaluation failed", self.camera_id)
                db.session.rollback()

        self.detections_saved += len(rows)
        log.info("camera %s: %s detection(s) -> %s",
                 self.camera_id, len(rows), snapshot_name)

    def _save_snapshot(self, results):
        """Write the annotated frame (boxes + labels drawn by Ultralytics).

        Every model draws onto the SAME image, so one snapshot shows the whole
        picture - a truck from COCO and a fire from the fire weights together,
        which is the point of running both.
        """
        try:
            os.makedirs(SNAPSHOT_DIR, exist_ok=True)
            name = f"cam{self.camera_id}_{int(time.time() * 1000)}.jpg"
            canvas = None
            for result in results:
                canvas = result.plot() if canvas is None else result.plot(img=canvas)
            cv2.imwrite(os.path.join(SNAPSHOT_DIR, name), canvas)
            return name
        except Exception as exc:
            log.warning("camera %s: could not write snapshot: %s", self.camera_id, exc)
            return None

    # ---------------------------------------------------------------- reporting

    def status(self):
        return {
            "cameraId": self.camera_id,
            "rtspUrl": self.rtsp_url,
            "model": ",".join(self.model_names),
            "intervalSeconds": self.interval,
            "running": self.is_alive() and not self._stop_event.is_set(),
            "framesAnalysed": self.frames_analysed,
            "detectionsSaved": self.detections_saved,
            "alertsRaised": self.alerts_raised,
            "lastError": self.last_error,
            "startedAt": self.started_at.isoformat(),
        }
