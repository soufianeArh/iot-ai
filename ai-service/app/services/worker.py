"""
One inference worker per camera.
"""
import logging
import os
import random
import threading
import time
from datetime import datetime, timezone

import cv2

from app import db
from app.models import Detection
from app.services import rule_engine
from app.services import detector
from app.services.detector import DEFAULT_MODEL

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
                 interval: float = None, jitter: float = None):
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

        # Fraction by which each wait is randomised, 0 = off (the default, so
        # existing cameras are unchanged). Set it when the SOURCE loops:
        # three models take ~10.5s per frame and a 21s sample loop meant every
        # sample landed on the same two images while the other five were never
        # analysed - it looked exactly like a model that could only see cows.
        # A real camera is never periodic, so this is only needed for the fake
        # ones. Opt in per task: ?jitter=0.35
        self.jitter = max(0.0, min(0.9, float(jitter))) if jitter else 0.0
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
        """
        Analyse the NEWEST frame every interval, not the next one in the queue.

        A reader thread does nothing but decode and keep the latest frame; this
        loop takes whatever is current when it wakes.

        That separation is the whole point. Reading inline, the decoder only
        advances while this loop is in it - and inference takes ~10s while RTSP
        delivers at source rate, so it fell steadily behind and analysed older
        and older frames. With stills lasting 5s, consecutive samples landed
        inside the SAME still and came back byte-identical: it looked like a
        camera that could only see one thing, when it was really a reader that
        could not keep up.

        Dropping frames is correct here. This is live monitoring - what matters
        is what the camera sees NOW, not every frame in order.
        """
        latest = {"frame": None}
        lock = threading.Lock()
        reader_failed = threading.Event()

        def reader():
            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    reader_failed.set()
                    return
                with lock:
                    latest["frame"] = frame

        thread = threading.Thread(target=reader, name=f"reader-cam{self.camera_id}",
                                  daemon=True)
        thread.start()

        try:
            while not self._stop_event.is_set():
                if reader_failed.is_set():
                    self.last_error = "stream ended"
                    return

                self._stop_event.wait(self.interval * (
                    random.uniform(1 - self.jitter, 1 + self.jitter)
                    if self.jitter else 1.0))
                if self._stop_event.is_set():
                    return

                with lock:
                    frame = latest["frame"]
                    latest["frame"] = None       # never analyse the same one twice
                if frame is None:
                    continue

                try:
                    self._analyse(frame)
                except Exception as exc:                # never kill the loop
                    self.last_error = str(exc)[:200]
                    log.exception("camera %s: inference failed", self.camera_id)
        finally:
            self._stop_event.set() if reader_failed.is_set() else None
            thread.join(timeout=2)

    # ---------------------------------------------------------------- analysis

    def _analyse(self, frame):
        # One decode, N models. Each is a separate forward pass - this is
        # genuinely N times the inference cost, not a free lunch.
        #
        # detector.detect() returns the same shape whatever library ran, so a
        # transformers plant-disease model and an Ultralytics fire model are
        # merged here without the worker knowing the difference. Each model
        # applies its OWN confidence floor: one global value discarded a real
        # tomato blight at 0.569 while COCO needed 0.65 to stay quiet.
        found = []
        for name in self.model_names:
            found.extend(detector.detect(name, frame))
        self.frames_analysed += 1

        if not found:
            return

        snapshot_name = self._save_snapshot(frame, found)

        rows = [Detection(
            camera_id=self.camera_id,
            label=hit["label"],
            confidence=hit["confidence"],
            x1=hit["box"][0], y1=hit["box"][1],
            x2=hit["box"][2], y2=hit["box"][3],
            snapshot=snapshot_name,
        ) for hit in found]

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

    def _save_snapshot(self, frame, hits):
        """Draw every model's boxes onto ONE image and write it.

        Annotating here rather than using Ultralytics' own plot() is what lets
        results from different libraries share a snapshot: a truck from COCO
        and a leaf disease from a transformers model land on the same picture.
        """
        try:
            os.makedirs(SNAPSHOT_DIR, exist_ok=True)
            name = f"cam{self.camera_id}_{int(time.time() * 1000)}.jpg"
            canvas = frame.copy()
            for hit in hits:
                x1, y1, x2, y2 = hit["box"]
                cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 200, 255), 2)
                caption = f"{hit['label']} {hit['confidence']:.2f}"
                # Filled strip behind the text: a label drawn straight onto a
                # bright field is unreadable in exactly the frames that matter.
                (tw, th), _ = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(canvas, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, y1),
                              (0, 200, 255), -1)
                cv2.putText(canvas, caption, (x1 + 2, max(10, y1 - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
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
            "jitter": self.jitter,
            "running": self.is_alive() and not self._stop_event.is_set(),
            "framesAnalysed": self.frames_analysed,
            "detectionsSaved": self.detections_saved,
            "alertsRaised": self.alerts_raised,
            "lastError": self.last_error,
            "startedAt": self.started_at.isoformat(),
        }
