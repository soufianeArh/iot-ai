"""
Standing-water coverage: what fraction of a frame is under water.

NOT a model. There are no weights, nothing is trained, and nothing is
downloaded - this is arithmetic on pixels, a millisecond per frame.

It exists because flood is the wrong shape for a detector. YOLO finds
*things*: countable objects with a boundary you can draw a box around. Water
across a field is *stuff* - no instances, no natural box, and "how many
floods" is not a question. So the output here is one number per frame, a
coverage fraction, and the matching alert rule is a threshold rather than a
count.

WHAT ACTUALLY SEPARATES WATER FROM SOIL

Not colour. The flood photos from this site are muddy brown, very close to
the wet soil beside them. The reliable signal is TEXTURE: a water surface is
smooth, while soil, stubble and canopy are full of high-frequency detail.
So the primary test is local variance, and colour is only used to rule things
out afterwards.

THE THREE THINGS THAT FOOL IT, AND WHAT IS DONE ABOUT THEM

  sky        smooth, bright, low saturation - indistinguishable from water on
             texture alone. Removed by finding smooth regions that touch the
             top edge and are brighter than the scene median.
  vegetation smooth in places when out of focus. Removed by hue: a strongly
             green pixel is not water.
  shadow     smooth and dark. Removed by a floor on brightness.

It is a heuristic and it says so. It will disagree with a person at the
margins; it is meant to answer "is a large part of this field under water"
rather than to trace a shoreline.
"""
import logging
import os

import cv2
import numpy as np

log = logging.getLogger(__name__)

ENABLED = os.getenv("WATER_INDEX_ENABLED", "true").lower() in ("1", "true", "yes")

# Analysis runs on a downscaled copy: coverage is a ratio, so resolution buys
# nothing, and the box filters below are the expensive part.
WORK_WIDTH = 480

# Local standard deviation under which a pixel counts as "smooth". Tuned on
# the sample frames: muddy water sits near 2-5, bare soil and canopy well above.
SMOOTH_MAX = float(os.getenv("WATER_SMOOTH_MAX", "6.0"))

WINDOW = 9          # neighbourhood for the variance estimate
MIN_VALUE = 45      # below this it is shadow, not water
GREEN_LO, GREEN_HI = 35, 85     # OpenCV hue degrees/2 - vegetation
GREEN_SAT = 60      # a green pixel only counts as vegetation if saturated


def _local_sigma(gray: np.ndarray) -> np.ndarray:
    """Standard deviation in a WINDOW-sized neighbourhood, per pixel.

    E[x^2] - E[x]^2 via two box blurs: far cheaper than a sliding window, and
    the whole reason this can run on every frame without being noticed.
    """
    f = gray.astype(np.float32)
    mean = cv2.blur(f, (WINDOW, WINDOW))
    mean_sq = cv2.blur(f * f, (WINDOW, WINDOW))
    return np.sqrt(np.maximum(mean_sq - mean * mean, 0))


def _sky_mask(smooth: np.ndarray, value: np.ndarray) -> np.ndarray:
    """Smooth regions connected to the top edge and brighter than the scene.

    A cloudy sky is smooth, bright and desaturated - every test that finds
    water finds it too. What sky is not, is *surrounded by field*: it touches
    the top of the frame. So the removal is by connectivity, not by colour.
    """
    bright = value > max(np.median(value) + 10, 90)
    candidate = (smooth & bright).astype(np.uint8)
    if not candidate.any():
        return np.zeros_like(candidate, dtype=bool)

    count, labels = cv2.connectedComponents(candidate, connectivity=8)
    touching = np.unique(labels[0, :])          # component ids on the top row
    sky = np.isin(labels, touching[touching > 0])

    # A component has to be substantial to be sky; a bright smooth puddle can
    # graze the top edge of a low-angle shot.
    if sky.sum() < 0.02 * sky.size:
        return np.zeros_like(sky)
    return sky


def analyse(frame: np.ndarray) -> dict:
    """Coverage in 0..1 plus the intermediate fractions, for tuning."""
    h, w = frame.shape[:2]
    if w > WORK_WIDTH:
        scale = WORK_WIDTH / w
        frame = cv2.resize(frame, (WORK_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hue, sat, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    smooth = _local_sigma(gray) < SMOOTH_MAX
    vegetation = (hue >= GREEN_LO) & (hue <= GREEN_HI) & (sat > GREEN_SAT)
    dark = value < MIN_VALUE
    sky = _sky_mask(smooth, value)

    water = smooth & ~vegetation & ~dark & ~sky

    # Opening then closing: drop isolated smooth specks, then fill the pinholes
    # left by crop poking through shallow water. Without this a flooded field
    # reads as thousands of fragments rather than one sheet.
    k = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(water.astype(np.uint8), cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

    return {
        "coverage": float(mask.mean()),
        "smoothFraction": float(smooth.mean()),
        "skyFraction": float(sky.mean()),
        "vegetationFraction": float(vegetation.mean()),
    }


def coverage(frame: np.ndarray) -> float:
    """Just the number. Never raises - a failed measurement must not stop
    inference, so it reports 0 and logs instead."""
    try:
        return analyse(frame)["coverage"]
    except Exception as exc:
        log.warning("water index failed: %s", exc)
        return 0.0
