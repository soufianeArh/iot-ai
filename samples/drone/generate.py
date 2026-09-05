"""
Synthetic drone-style aerial frames: a crop fire and a field flooding.
Procedural, no source images and no network.

Two things do most of the work for realism: fbm() layers fractal noise so
detail exists at every scale instead of one smooth blur, and warp() pushes
pixels around with another noise field so smoke curls and burn scars come
out ragged instead of a perfect oval.

All colours are BGR, since that's what OpenCV writes.
"""
import numpy as np
import cv2

H, W = 720, 1280
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)


# ---------------------------------------------------------------- noise ----

def fbm(rng, sigma, octaves=5, gain=0.5):
    """Fractal noise: coarse shape plus progressively finer detail."""
    out = np.zeros((H, W), np.float32)
    amp, s = 1.0, sigma
    for _ in range(octaves):
        n = cv2.GaussianBlur(rng.random((H, W)).astype(np.float32), (0, 0), s)
        n = (n - n.mean()) / (n.std() + 1e-6)
        out += n * amp
        amp *= gain
        s = max(s * 0.45, 0.8)
    return (out - out.min()) / (np.ptp(out) + 1e-6)


def warp(img, rng, amp, sigma):
    """Displace every pixel by a smooth random vector field."""
    dx = (fbm(rng, sigma, 3) - 0.5) * 2 * amp
    dy = (fbm(rng, sigma, 3) - 0.5) * 2 * amp
    return cv2.remap(img, (XX + dx).astype(np.float32), (YY + dy).astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def blob(rng, cx, cy, rx, ry, soft=0.30, rough=28.0):
    """An irregular filled region: a radial falloff, then warped."""
    r = np.sqrt(((XX - cx) / rx) ** 2 + ((YY - cy) / ry) ** 2)
    return np.clip(warp(np.clip((1.0 - r) / soft, 0, 1), rng, rough, 26), 0, 1)


def over(base, colour, alpha):
    """Composite a flat colour over the image with a float mask."""
    a = np.clip(alpha, 0, 1)[..., None]
    return base * (1 - a) + np.asarray(colour, np.float32) * a


# ---------------------------------------------------------------- field ----

def field(rng, crop, soil, angle, period):
    """Crop rows seen from directly above, with tramlines and patchy vigour."""
    t = np.deg2rad(angle)
    u = XX * np.cos(t) + YY * np.sin(t)
    v = -XX * np.sin(t) + YY * np.cos(t)

    # Drill rows. The wander keeps them off a perfect grid.
    wander = (fbm(rng, 55, 3) - 0.5) * period * 0.7
    rows = 0.5 + 0.5 * np.sin((u + wander) * (2 * np.pi / period))
    rows = rows ** 0.8

    # Patchy growth: thin here, vigorous there.
    vigour = np.clip(0.35 + 1.15 * fbm(rng, 110, 4), 0, 1.35)
    # Compressed toward the middle: full-swing rows read as corduroy from
    # this height, where a real crop canopy has already partly closed over.
    m = np.clip(0.28 + 0.62 * rows * vigour, 0, 1)

    img = over(np.broadcast_to(np.asarray(soil, np.float32), (H, W, 3)).copy(),
               crop, m)

    # Tramlines: the wheel tracks of the sprayer, every N rows.
    tram = np.abs(np.sin(u * np.pi / (period * 12)))
    tram = np.clip((0.06 - tram) / 0.06, 0, 1) * 0.55
    img = over(img, np.asarray(soil, np.float32) * 0.92, tram)

    # A faint headland where the machinery turns.
    head = np.clip((26 - np.abs(v - v.min() - 40)) / 26, 0, 1) * 0.35
    img = over(img, np.asarray(soil, np.float32) * 1.05, head)

    # Plant-scale texture.
    grain = fbm(rng, 1.6, 3)[..., None]
    return img * (0.86 + 0.28 * grain)


def add_track(img, rng, angle, offset, width):
    """A dirt access track, giving the eye something to judge scale by."""
    t = np.deg2rad(angle)
    d = np.abs(XX * np.sin(t) - YY * np.cos(t) + offset + (fbm(rng, 60, 2) - .5) * 18)
    m = cv2.GaussianBlur(np.clip((width - d) / 7.0, 0, 1), (0, 0), 2)
    dirt = np.asarray([88, 118, 152], np.float32) * (0.8 + 0.4 * fbm(rng, 2.5, 3)[..., None])
    return img * (1 - m[..., None]) + dirt * m[..., None]


def add_treeline(img, rng, y0, thickness):
    """Scrub along a field boundary: lumpy, with shadow on one side."""
    edge = y0 + (fbm(rng, 45, 4) - 0.5) * 70
    lump = thickness * (0.55 + 0.9 * fbm(rng, 18, 3))
    m = cv2.GaussianBlur(np.clip((lump - np.abs(YY - edge)) / 9.0, 0, 1), (0, 0), 2)

    # Canopy, then the shadow it throws downslope.
    canopy = np.asarray([34, 58, 40], np.float32) * (0.45 + 1.1 * fbm(rng, 4, 4)[..., None])
    img = img * (1 - m[..., None]) + canopy * m[..., None]
    shade = np.clip(np.roll(m, 14, axis=0) - m, 0, 1) * 0.45
    return img * (1 - shade[..., None] * 0.55)


def camera(img, rng, blur=0.7, noise=2.6):
    """Vignette, slight defocus, sensor noise: the tells of a real frame."""
    r = np.sqrt(((XX - W / 2) / (W / 2)) ** 2 + ((YY - H / 2) / (H / 2)) ** 2)
    img = img * (1.0 - 0.22 * np.clip(r - 0.45, 0, 2) ** 2)[..., None]
    img = cv2.GaussianBlur(img, (0, 0), blur)
    img = img + rng.normal(0, noise, img.shape).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


# ------------------------------------------------------------ scene: fire --

def fire_scene(seed, cx, cy, size, wind, angle, crop, soil):
    rng = np.random.default_rng(seed)
    img = field(rng, crop, soil, angle, 22)
    img = add_track(img, rng, angle + 90, -210, 11)
    img = add_treeline(img, rng, 78, 30)

    wx, wy = wind

    # The burn scar. Elongated along the wind, because that is the direction
    # the fire has travelled from.
    scar = blob(rng, cx - wx * size * 0.5, cy - wy * size * 0.5,
                size * 1.9, size * 1.25, 0.42, rough=34)

    # Char is not uniform: unburnt clumps survive inside it.
    patchy = np.clip(fbm(rng, 9, 5) * 1.5 - 0.25, 0, 1)
    img = over(img, [26, 26, 28], scar * (0.55 + 0.45 * patchy))
    img = over(img, [58, 62, 68], scar * patchy * 0.35)      # grey ash

    # The active flame front: a broken crescent at the leading edge only.
    lead = blob(rng, cx + wx * size * 0.30, cy + wy * size * 0.30,
                size * 1.55, size * 1.0, 0.42, rough=34)
    front = np.clip(lead - cv2.GaussianBlur(lead, (0, 0), 11) * 1.06, 0, 1)
    front = cv2.GaussianBlur(front, (0, 0), 2) * 6.0

    # Break it into separate burning cells, since a continuous ring reads as a donut.
    cells = np.clip(fbm(rng, 6, 5) * 2.2 - 0.55, 0, 1)
    front = np.clip(front * cells, 0, 1)

    img = over(img, [22, 58, 168], np.clip(front * 1.5, 0, 1))     # deep red
    img = over(img, [40, 126, 232], np.clip(front * 1.15 - 0.18, 0, 1))
    img = over(img, [130, 208, 250], np.clip(front * 1.0 - 0.55, 0, 1))  # core

    # Embers scattered ahead of the front.
    spark = (rng.random((H, W)) < 0.00035).astype(np.float32)
    spark *= np.clip(blob(rng, cx + wx * size, cy + wy * size, size * 1.4, size, 0.9), 0, 1)
    img = over(img, [70, 170, 245], cv2.GaussianBlur(spark, (0, 0), 1.1) * 3.0)

    # Firelight spilling onto the crop nearby.
    bloom = cv2.GaussianBlur(front, (0, 0), 30)[..., None]
    img = img + np.asarray([6, 34, 70], np.float32) * bloom * 2.2

    # Smoke. An elongated wedge along the wind, warped hard so it curls, then
    # cut by fine noise so the edges are ragged instead of airbrushed.
    px, py = cx + wx * size * 1.1, cy + wy * size * 1.1
    for i, (spread, dens, tone) in enumerate([
            (1.0, 0.75, [64, 66, 72]),      # dark, close to the flame
            (1.9, 0.50, [122, 126, 132]),
            (3.1, 0.34, [178, 182, 188]),
            (4.6, 0.20, [212, 216, 220])]):  # thin and pale, well downwind
        d = size * spread
        plume = blob(rng, px + wx * d, py + wy * d,
                     size * (0.7 + spread * 0.85), size * (0.5 + spread * 0.6),
                     0.95, rough=30 + spread * 26)
        plume = warp(plume, rng, 34 + spread * 18, 34)
        plume = plume * np.clip(fbm(rng, 14 - i * 2, 5) * 1.9 - 0.35, 0, 1.15)
        img = over(img, tone, plume * dens)

    return camera(img, rng)


# ----------------------------------------------------------- scene: flood --

def flood_scene(seed, angle, canal_offset, crop, soil):
    rng = np.random.default_rng(seed)
    img = field(rng, crop, soil, angle, 20)
    img = add_treeline(img, rng, H - 58, 26)

    # The irrigation canal that has burst, running across the frame.
    t = np.deg2rad(angle + 90)
    d = XX * np.sin(t) - YY * np.cos(t) + canal_offset + (fbm(rng, 70, 2) - .5) * 26
    canal = np.clip((7.0 - np.abs(d)) / 4.0, 0, 1)
    bank = np.clip(np.clip((19.0 - np.abs(d)) / 7.0, 0, 1) - canal, 0, 1)

    # Water spreading downhill from the breach: overlapping lobes, each one
    # following the low ground, not a single tidy pool.
    sheet = np.zeros((H, W), np.float32)
    for i in range(8):
        f = i / 7.0
        sheet = np.maximum(sheet, blob(
            rng,
            W * 0.26 + f * W * 0.50 + rng.normal(0, 34),
            H * 0.34 + f * H * 0.34 + rng.normal(0, 28),
            210 - f * 92, 140 - f * 58, 0.7, rough=40))
    sheet = sheet * np.clip((d + 5) / 13.0, 0, 1)     # downhill side only
    sheet = np.clip(np.maximum(sheet, canal), 0, 1)
    sheet = warp(sheet, rng, 22, 30)

    # Water has a shoreline, not a gradient. Without this hard threshold the
    # edge fades out over 50 px and the whole thing reads as ground mist.
    sheet = cv2.GaussianBlur(np.clip((sheet - 0.42) * 7.0, 0, 1), (0, 0), 1.6)

    depth = cv2.GaussianBlur(sheet, (0, 0), 26) * sheet

    # Silty water: pale grey-brown in the shallows, dark green-brown in the
    # pools. Rows still show through where it is thin, which is why the
    # alpha is tied to depth rather than being flat.
    water = (np.asarray([78, 100, 122], np.float32) * (1 - depth[..., None])
             + np.asarray([104, 100, 86], np.float32) * depth[..., None])
    # Semi-transparent at the margins: the rows have to show through the
    # shallows, or it looks like grey paint rather than water.
    a = np.clip(sheet * (0.42 + 0.55 * depth), 0, 1)[..., None]
    img = img * (1 - a) + water * a

    # Sky reflected off the surface, the giveaway that it is water and not
    # bare mud. Has to be broad and gentle, since high-frequency speckle
    # here reads as frost instead.
    sheen = np.clip(fbm(rng, 46, 2) * 1.5 - 0.62, 0, 1) * sheet * depth
    img = img + np.asarray([206, 196, 178], np.float32) * \
        cv2.GaussianBlur(sheen, (0, 0), 12)[..., None] * 0.40

    # Crop tips still breaking the surface in the shallows.
    tips = (rng.random((H, W)) < 0.0009).astype(np.float32) \
        * np.clip(sheet - depth * 1.2, 0, 1)
    img = over(img, [58, 92, 78], cv2.GaussianBlur(tips, (0, 0), 1.0) * 1.6)

    # Saturated dark soil in the ring the water has soaked but not covered.
    halo = np.clip(cv2.GaussianBlur(sheet, (0, 0), 18) - sheet, 0, 1)
    img = over(img, [48, 60, 76], halo * 0.5)

    img = over(img, [92, 116, 144], bank * 0.6)       # dry canal bank
    return camera(img, rng)


CROP_GREEN, SOIL_BROWN = [62, 118, 66], [74, 106, 142]
CROP_DRY, SOIL_RED = [78, 152, 150], [66, 96, 138]

IMAGES = [
    ("drone-crop-fire-01.jpg",
     lambda: fire_scene(7, 560, 430, 62, (0.82, -0.57), 18, CROP_GREEN, SOIL_BROWN)),
    ("drone-crop-fire-02.jpg",
     lambda: fire_scene(23, 780, 300, 46, (-0.60, 0.80), -12, CROP_DRY, SOIL_RED)),
    ("drone-field-flood-01.jpg",
     lambda: flood_scene(11, 8, -140, CROP_GREEN, SOIL_BROWN)),
    ("drone-field-flood-02.jpg",
     lambda: flood_scene(29, -22, 150, CROP_DRY, SOIL_RED)),
]

for name, make in IMAGES:
    cv2.imwrite("/out/" + name, make(), [cv2.IMWRITE_JPEG_QUALITY, 90])
    print("wrote", name)
