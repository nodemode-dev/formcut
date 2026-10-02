"""formcut's planar tracker (P0 of DEV_PLAN_planar_tracking.md).

A layer's plane is followed against a reference frame, never chained frame to frame, so it does not drift: per frame
a homography from the reference to that frame, restricted to the motion types chosen (Mocha's five: translation,
scale, rotation, shear, perspective), and a confidence.

Each frame:
1. A prediction from the last two frames' motion.
2. Large motion: a rough robust estimate, ORB features of the reference's tracking matte matched in a window around
   the prediction and fitted in the motion model by MAGSAC (or RANSAC). Small motion: the prediction alone.
3. The refinement: the frame is warped back into the reference by that estimate, so what is left to find is small;
   the reference's points (as many as Min % Pixels Used asks) are followed into it by sub-pixel pyramidal
   Lucas-Kanade, each checked by following it back; points under an exclusion matte (a layer in front, an occluder)
   are dropped; the residual is fitted robustly in the motion model and composed. Twice.
4. A confidence from how many points held and how well they fit.
5. When the plane has turned or grown far from the reference, or confidence falls, the current frame (warped back)
   becomes the reference, its matte the old one carried by the track, so tracking holds across large changes.

The spike that chose this (planning docs, spikes/planar_spike.py): on a plane moving in perspective with noise, blur
and an occluder, chaining features frame to frame drifted to 12.7 px; features against the reference held 1.87 px
mean; ECC refinement diverged under the occluder; this refinement held 0.09 px mean, 0.31 px worst while occluded.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import cv2
import numpy as np

MOTIONS = ("translation", "scale", "rotation", "shear", "perspective")
MATCH_LIGHT = True  # the light matched to the reference before the flow (see _refine)
FAINT_POINTS = 3.0  # a faint surface's points, times the usual: it has less in each
NORMALISE = False  # both pictures in local contrast before the flow, instead of matching the light
SWITCH_TO_CONTRAST = True  # a large change of light read as local contrast instead (see _refine)


@dataclass
class Settings:
    """A track's parameters, named as Mocha names them (its Track tab and Essentials panel)."""

    translation: bool = True
    scale: bool = True
    rotation: bool = True
    shear: bool = False
    perspective: bool = False
    channel: str = "luminance"  # or "auto": the colour channel with the most contrast in the matte; or "max": the
    # brightest of the three (a saturated screen colour under a reflection)
    min_pixels: float | None = None  # percent of the matte's pixels used; None: dynamic, by the matte's size
    smoothing: float = 0.0  # a blur before tracking, against noise
    motion: str = "large"  # "large" (search, then refine), "small" (refine only), "manual" (no tracking)
    search_x: float | None = None  # pixels either way around the prediction; None: automatic
    search_y: float | None = None
    angle: float = 0.0  # degrees of rotation a frame beyond the tracker's own reach (about 10)
    zoom: float = 0.0  # percent of scale a frame beyond its own reach

    def model(self) -> str:
        """The motion model the checked types make. Rotation brings scale with it, as in Mocha; shear brings rotation
        and scale; perspective brings all."""
        if self.perspective:
            return "perspective"
        if self.shear:
            return "affine"
        if self.rotation:
            return "similarity"
        if self.scale:
            return "scale"
        return "translation"


def _h(m: np.ndarray) -> np.ndarray:
    out = np.eye(3)
    out[:2, :] = m
    return out


def fit(model: str, a: np.ndarray, b: np.ndarray, threshold: float = 1.0) -> tuple[np.ndarray | None, np.ndarray]:
    """The transform in the model taking points a to points b, robustly, as a 3x3 matrix; and which points fit."""
    a = np.asarray(a, np.float32).reshape(-1, 2)
    b = np.asarray(b, np.float32).reshape(-1, 2)
    n = len(a)
    none = np.zeros(n, bool)
    if model == "perspective":
        if n < 8:
            return None, none
        method = getattr(cv2, "USAC_MAGSAC", cv2.RANSAC)
        h, inliers = cv2.findHomography(a, b, method, threshold, maxIters=2000, confidence=0.999)
        return (None, none) if h is None else (h / h[2, 2], inliers.ravel().astype(bool))
    if model == "affine":
        if n < 6:
            return None, none
        m, inliers = cv2.estimateAffine2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=threshold, maxIters=2000)
        return (None, none) if m is None else (_h(m), inliers.ravel().astype(bool))
    if model == "similarity":
        if n < 4:
            return None, none
        m, inliers = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=threshold, maxIters=2000)
        return (None, none) if m is None else (_h(m), inliers.ravel().astype(bool))
    # translation, or translation with a uniform scale and no rotation: least squares inside a small RANSAC
    if n < 3:
        return None, none
    rng = np.random.default_rng(1)
    best, best_in = None, none
    for _ in range(200):
        pick = rng.choice(n, 2, replace=False)
        m = _scale_shift(a[pick], b[pick], model)
        if m is None:
            continue
        inliers = np.linalg.norm(_apply(m, a) - b, axis=1) < threshold
        if inliers.sum() > best_in.sum():
            best, best_in = m, inliers
    if best is None or best_in.sum() < 3:
        return None, none
    return _scale_shift(a[best_in], b[best_in], model), best_in


def _scale_shift(a: np.ndarray, b: np.ndarray, model: str) -> np.ndarray | None:
    if model == "translation":
        d = np.median(b - a, axis=0)
        return np.array([[1, 0, d[0]], [0, 1, d[1]], [0, 0, 1]], float)
    ca, cb = a.mean(0), b.mean(0)
    spread = ((a - ca) ** 2).sum()
    if spread < 1e-9:
        return None
    s = float(((a - ca) * (b - cb)).sum() / spread)
    t = cb - s * ca
    return np.array([[s, 0, t[0]], [0, s, t[1]], [0, 0, 1]], float)


def _apply(h: np.ndarray, pts: np.ndarray) -> np.ndarray:
    return cv2.perspectiveTransform(np.asarray(pts, np.float64).reshape(-1, 1, 2), h).reshape(-1, 2)


def _faint(gray: np.ndarray, matte: np.ndarray) -> bool:
    """A surface with little texture: its mean gradient under 25 levels a pixel."""
    inside = matte > 0
    if not inside.any():
        return False
    grad = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    return float(grad[inside].mean()) <= 25


def _local_contrast(gray: np.ndarray, sigma: float = 6.0) -> np.ndarray:
    """Each pixel as its difference from the local mean over the local spread: indifferent to gain and offset, even
    varying across the surface, and to the contrast a blur takes away."""
    g = gray.astype(np.float32)
    mean = cv2.GaussianBlur(g, (0, 0), sigma)
    d = g - mean
    spread = np.sqrt(cv2.GaussianBlur(d * d, (0, 0), sigma) + 16.0)
    return np.clip(128 + 48 * d / spread, 0, 255).astype(np.uint8)


def _light(ref: np.ndarray, seen: np.ndarray) -> tuple[float, float] | None:
    """Gain and offset taking the reference's pixel values to the frame's (seen = gain * ref + offset); None where the
    light has not clearly changed (gain within 3 percent, offset within 2 levels) or the fit is not to be believed.

    The pairs an occluder or a misplacement spoils are found by a robust line (least squares within 2.5 median
    deviations, three rounds); the gain itself is then the ratio of the two sides' spreads (interquartile ranges) over
    the pairs kept, not the line's slope: both sides carry the same noise, which flattens a least-squares slope (on a
    faint surface it read gains of 0.47 to 0.92 where the light had not changed) but cancels in a ratio of spreads.
    Where the reference's own spread is too narrow to measure a gain (under 20 levels), the offset alone is fitted."""
    if len(ref) > 6000:
        pick = np.random.default_rng(0).choice(len(ref), 6000, replace=False)
        ref, seen = ref[pick], seen[pick]
    gain, offset = 1.0, float(np.median(seen - ref))
    keep = np.ones(len(ref), bool)
    for _ in range(3):
        residual = seen - (gain * ref + offset)
        spread = float(np.median(np.abs(residual - np.median(residual)))) * 1.4826 + 0.5
        keep = np.abs(residual) < 2.5 * spread
        if keep.sum() < 100:
            return None
        a = np.vstack([ref[keep], np.ones(keep.sum())]).T
        (gain, offset), *_ = np.linalg.lstsq(a, seen[keep], rcond=None)
        gain, offset = float(gain), float(offset)
    r, q = ref[keep], seen[keep]
    r_low, r_mid, r_high = np.percentile(r, (25, 50, 75))
    q_low, q_mid, q_high = np.percentile(q, (25, 50, 75))
    gain = float((q_high - q_low) / (r_high - r_low)) if r_high - r_low >= 20 else 1.0
    if not 0.4 < gain < 2.5:
        return None
    offset = float(q_mid - gain * r_mid)
    if abs(gain - 1) < 0.03 and abs(q_mid - r_mid) < 2:
        return None
    return gain, offset


def corners_of(h: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """The surface's corners (in the reference) carried to a frame."""
    return _apply(h, corners)


def _sound(h: np.ndarray | None, box: tuple[int, int, int, int]) -> bool:
    """Whether an estimate can be believed at all: finite, the plane's box still a convex quadrilateral the same way
    round (not folded or mirrored), between a twentieth and twenty times its area. A plane lost (footage that is not
    planar, a surface gone from view) gives estimates that fail this; they are not used."""
    if h is None or not np.all(np.isfinite(h)) or abs(h[2, 2]) < 1e-12:
        return False
    x0, y0, x1, y1 = box
    quad = _apply(h, np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float))
    if not np.all(np.isfinite(quad)):
        return False
    edges = np.roll(quad, -1, axis=0) - quad
    turns = edges[:, 0] * np.roll(edges, -1, axis=0)[:, 1] - edges[:, 1] * np.roll(edges, -1, axis=0)[:, 0]
    if not np.all(turns > 0):  # every corner turning the way the box's own do: convex, not folded or mirrored
        return False
    area = 0.5 * abs(np.dot(quad[:, 0], np.roll(quad[:, 1], 1)) - np.dot(quad[:, 1], np.roll(quad[:, 0], 1)))
    return 0.05 < area / max(1.0, float((x1 - x0) * (y1 - y0))) < 20


def _plane_scale(h: np.ndarray, box: tuple[int, int, int, int]) -> float:
    """How much the plane has grown or shrunk since its reference: the area of its reference box carried by the
    homography over the box's own area. (Read from the homography's linear part at the image origin until P0's last
    pass, which under perspective is not the plane's scale: it set off seven needless refreshes on one benchmark shot,
    each keeping the error of its moment.)"""
    x0, y0, x1, y1 = box
    quad = _apply(h, np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float))
    area = 0.5 * abs(np.dot(quad[:, 0], np.roll(quad[:, 1], 1)) - np.dot(quad[:, 1], np.roll(quad[:, 0], 1)))
    return math.sqrt(area / max(1.0, float((x1 - x0) * (y1 - y0))))


class _Reference:
    """A reference frame: its picture, its tracking matte, its points to follow, its features to match."""

    def __init__(self, gray: np.ndarray, matte: np.ndarray, settings: Settings, orb):
        self.gray = gray
        self.matte = matte
        area = int((matte > 0).sum())
        share = settings.min_pixels if settings.min_pixels is not None else max(1.0, min(30.0, 60000.0 / max(1, area) * 3))
        count = int(np.clip(area * share / 100.0 / 4.0, 300, 2000))  # a point for every few pixels of the share asked
        count = int(count * FAINT_POINTS) if _faint(gray, matte) else count
        found = cv2.goodFeaturesToTrack(gray, count, 0.004, 5, mask=matte)
        if found is None or len(found) < count // 2:
            # a surface with little texture: a lower bar finds the detail it has
            found = cv2.goodFeaturesToTrack(gray, count, 0.0005, 4, mask=matte)
        self.points = np.zeros((0, 1, 2), np.float32) if found is None else found.astype(np.float32)
        # the flow's window: wider where the texture is faint, so each point sees enough of it
        gx, gy = cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)
        strength = float(np.mean(np.hypot(gx, gy)[matte > 0])) if (matte > 0).any() else 0.0
        self.keys, self.descriptors = orb.detectAndCompute(gray, matte)
        ys, xs = np.nonzero(matte)
        self.box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else (0, 0, gray.shape[1], gray.shape[0])
        # windows sized to the tracked area, not fixed in pixels: the same surface at 1080p is three times the pixels it
        # is at 360p, and a fixed window sees a third of it (at 1080p a faint surface held 0.78 px with 21 and 31)
        short = max(16, min(self.box[2] - self.box[0], self.box[3] - self.box[1]))
        window = int(np.clip(short / (12 if strength > 25 else 8), 21, 61)) | 1
        self.window = window
        self.levels = 3 if short > 360 else 2
        self.sigma = float(np.clip(short / 30, 4, 16))  # the local contrast's neighbourhood


class PlanarTracker:
    """Follows one layer's plane from its reference frame through the frames it is given, in either direction."""

    def __init__(self, reference_frame: np.ndarray, matte: np.ndarray, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.model = self.settings.model()
        self.channel = self._pick_channel(reference_frame, matte)
        self.orb = cv2.ORB_create(2500, scaleFactor=1.2, nlevels=8, edgeThreshold=15, patchSize=21)
        gray = self._gray(reference_frame)
        self.size = (gray.shape[1], gray.shape[0])
        self.ref = _Reference(gray, (matte > 0).astype(np.uint8) * 255, self.settings, self.orb)
        self.ref_to_origin = np.eye(3)  # the current reference's place in the first reference's frame
        self.history: list[np.ndarray] = [np.eye(3)]  # the last homographies, origin to frame, for the prediction
        self.refreshes = 0

    # the picture the tracker reads: one channel, blurred as asked
    def _pick_channel(self, frame: np.ndarray, matte: np.ndarray) -> int | None:
        if self.settings.channel != "auto" or frame.ndim == 2:
            return None
        inside = matte > 0
        spreads = [float(frame[:, :, c][inside].std()) if inside.any() else 0.0 for c in range(3)]
        return int(np.argmax(spreads))

    def _gray(self, frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 3 and self.settings.channel == "max":
            # the brightest of the three channels (HSV value): a saturated screen colour stays at the top however much
            # white a reflection adds, where its luminance rises with it. On the owner's upright phone, whose reflection
            # crosses its screen, this took its sides from 0.72 to 0.39 px RMS (worst 6.1 to 2.8 px); the other two
            # shots held or improved (gradient magnitude was tried as well, and did not)
            gray = frame.max(axis=2)
        elif frame.ndim == 3:
            gray = frame[:, :, self.channel] if self.channel is not None else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        gray = np.ascontiguousarray(gray, dtype=np.uint8)
        if self.settings.smoothing > 0:
            gray = cv2.GaussianBlur(gray, (0, 0), float(self.settings.smoothing))
        return gray

    def _prediction(self) -> np.ndarray:
        """Origin to the next frame: the last motion again (constant velocity in the plane's own terms)."""
        if len(self.history) < 2:
            return self.history[-1]
        last, before = self.history[-1], self.history[-2]
        try:
            step = last @ np.linalg.inv(before)
        except np.linalg.LinAlgError:
            return last
        guess = step @ last
        return guess / guess[2, 2]

    def _rough(self, gray: np.ndarray, guess: np.ndarray) -> np.ndarray:
        """Large motion: the reference's features matched in a window around where the prediction puts the plane."""
        ref = self.ref
        if ref.descriptors is None or len(ref.keys) < 8:
            return guess
        x0, y0, x1, y1 = ref.box
        box = _apply(guess, np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float))
        span = max(float(np.ptp(box[:, 0])), float(np.ptp(box[:, 1])), 16.0)
        mx = self.settings.search_x if self.settings.search_x is not None else 0.35 * span + 24
        my = self.settings.search_y if self.settings.search_y is not None else 0.35 * span + 24
        grow = 1 + self.settings.zoom / 100.0
        turn = span * math.sin(math.radians(min(90.0, self.settings.angle))) / 2  # a fast spin sweeps the box's corners
        mx, my = mx * grow + turn, my * grow + turn
        window = np.zeros(gray.shape, np.uint8)
        margin = np.array([mx, my])
        lo = np.maximum(box.min(0) - margin, 0).astype(int)
        hi = np.minimum(box.max(0) + margin, (gray.shape[1] - 1, gray.shape[0] - 1)).astype(int)
        if (hi <= lo).any():
            return guess
        window[lo[1] : hi[1] + 1, lo[0] : hi[0] + 1] = 255
        keys, descriptors = self.orb.detectAndCompute(gray, window)
        if descriptors is None or len(keys) < 8:
            return guess
        pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(ref.descriptors, descriptors, k=2)
        good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.8 * p[1].distance]
        if len(good) < 8:
            return guess
        a = np.float32([ref.keys[m.queryIdx].pt for m in good])
        b = np.float32([keys[m.trainIdx].pt for m in good])
        found, inliers = fit(self.model, a, b, threshold=2.5)
        if found is None or inliers.sum() < 8 or not _sound(found, ref.box):
            return guess
        return found

    def _refine(self, gray: np.ndarray, start: np.ndarray, exclude: np.ndarray | None) -> tuple[np.ndarray, float]:
        """The frame warped back into the reference by start; the reference's points followed into it; the residual
        fitted and composed. Returns reference to frame, and the share of points that held."""
        ref = self.ref
        pts = ref.points
        if len(pts) < 8:
            return start, 0.0
        if exclude is not None:
            # points that the estimate puts under an exclusion (a layer in front, an occluder) are not followed
            at = _apply(start, pts.reshape(-1, 2)).round().astype(int)
            inside = (at[:, 0] >= 0) & (at[:, 1] >= 0) & (at[:, 0] < gray.shape[1]) & (at[:, 1] < gray.shape[0])
            blocked = np.zeros(len(pts), bool)
            blocked[inside] = exclude[at[inside, 1], at[inside, 0]] > 0
            pts = pts[~blocked]
            if len(pts) < 8:
                return start, 0.0
        x0, y0, x1, y1 = ref.box
        pad = 24
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
        x1, y1 = min(self.size[0], x1 + pad), min(self.size[1], y1 + pad)
        shift = np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]], float)
        crop_ref = ref.gray[y0:y1, x0:x1]
        inside = ref.matte[y0:y1, x0:x1] > 0
        # the reference's smooth pixels: where a pixel's misplacement by a fraction changes its value least, so pairs of
        # them across the warp say what the light did, not what the motion did
        grad = cv2.magnitude(cv2.Sobel(crop_ref, cv2.CV_32F, 1, 0), cv2.Sobel(crop_ref, cv2.CV_32F, 0, 1))
        smooth = inside & (grad <= np.percentile(grad[inside], 40)) if inside.any() else inside
        local = pts - np.float32([x0, y0])
        win = (ref.window, ref.window)
        crop_lcn = _local_contrast(crop_ref, ref.sigma) if NORMALISE else None
        h = start.copy()
        held = 0.0
        for _ in range(2):
            # the frame, in the reference's coordinates, over the reference's box only
            back = cv2.warpPerspective(
                gray, h @ shift, (x1 - x0, y1 - y0), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
            )
            # the light matched to the reference's inside the tracked area (gain and offset), so a change of light is
            # not read as motion: the flow assumes the brightness holds
            # (a robust fit of gain and offset to pairs of smooth pixels, an occluder's pairs rejected as outliers and
            # excluded pixels left out; applied only where the light has clearly changed)
            usable = smooth
            if exclude is not None:
                hidden = cv2.warpPerspective(exclude, h @ shift, (x1 - x0, y1 - y0), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_NEAREST)
                usable = smooth & (hidden == 0)
            normalise = NORMALISE
            if MATCH_LIGHT and not normalise and usable.sum() > 200:
                # the light read from low-passed copies of both: a motion blur takes fine contrast from the frame but
                # not from the reference, which a fit on the full detail would read as a change of gain
                soft = max(1.5, ref.sigma / 4)
                light = _light(
                    cv2.GaussianBlur(crop_ref, (0, 0), soft)[usable].astype(np.float32),
                    cv2.GaussianBlur(back, (0, 0), soft)[usable].astype(np.float32),
                )
                if light is not None:
                    gain, offset = light
                    if SWITCH_TO_CONTRAST and (abs(gain - 1) > 0.1 or abs(offset + (gain - 1) * 128) > 10):
                        # a large change of light (and the contrast a blur takes with it): local contrast instead,
                        # which no single gain and offset describe as well (on the benchmark, 0.14 px against 0.31)
                        normalise = True
                    else:
                        back = np.clip((back.astype(np.float32) - offset) / gain, 0, 255).astype(np.uint8)
            if normalise:
                crop_lcn = crop_lcn if crop_lcn is not None else _local_contrast(crop_ref, ref.sigma)
            a_img, b_img = (crop_lcn, _local_contrast(back, ref.sigma)) if normalise else (crop_ref, back)
            moved, ok1, _ = cv2.calcOpticalFlowPyrLK(
                a_img,
                b_img,
                local,
                None,
                winSize=win,
                maxLevel=ref.levels,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
            )
            if moved is None:
                break
            returned, ok2, _ = cv2.calcOpticalFlowPyrLK(b_img, a_img, moved, None, winSize=win, maxLevel=ref.levels)
            ok = (ok1.ravel() == 1) & (ok2.ravel() == 1) & (np.linalg.norm((returned - local).reshape(-1, 2), axis=1) < 0.5)
            if ok.sum() < 8:
                break
            residual, inliers = fit(self.model, local[ok].reshape(-1, 2), moved[ok].reshape(-1, 2), threshold=1.0)
            if residual is None:
                break
            # residual maps reference-box points to the back-warped picture's points; back(x) = frame(h shift x)
            composed = h @ shift @ residual @ np.linalg.inv(shift)
            composed = composed / composed[2, 2]
            if not _sound(composed, ref.box):
                break
            h = composed
            held = float(inliers.sum()) / max(1, len(local))
        return h, held

    def step(self, frame: np.ndarray, exclude: np.ndarray | None = None) -> tuple[np.ndarray, float]:
        """A step that cannot be made (the numbers of a lost plane failing somewhere) gives the prediction with no
        confidence rather than an error: in the owner's first run of the workspace a lost plane stopped the whole job
        with "Singular matrix"."""
        try:
            return self._step(frame, exclude)
        except (np.linalg.LinAlgError, cv2.error, ValueError, FloatingPointError, ZeroDivisionError):
            guess = self.history[-1]
            self.history = [*self.history, guess][-3:]
            return guess, 0.0

    def _step(self, frame: np.ndarray, exclude: np.ndarray | None = None) -> tuple[np.ndarray, float]:
        """The next frame (in the direction being tracked): its homography from the first reference, and the confidence
        (0 to 1). exclude, where given, is a matte in the frame's own coordinates of what must not be tracked."""
        gray = self._gray(frame)
        guess = self._prediction()
        if self.settings.motion == "manual":
            self.history.append(guess)
            return guess, 0.0
        # the current reference's coordinates: origin to frame = (reference to frame) @ (origin to reference)
        to_ref = np.linalg.inv(self.ref_to_origin)
        local_guess = guess @ self.ref_to_origin
        rough = self._rough(gray, local_guess) if self.settings.motion == "large" else local_guess
        local, held = self._refine(gray, rough, exclude)
        if self.settings.motion == "large" and rough is not local_guess:
            # the rough match and the prediction disagree by more than a pixel at the plane's corners: refine from both
            # and keep the one more of the points agree with (a faint surface's rough match can mislead the refinement)
            x0, y0, x1, y1 = self.ref.box
            box = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)
            if held < 0.2 or np.linalg.norm(_apply(rough, box) - _apply(local_guess, box), axis=1).max() > 1.0:
                again, again_held = self._refine(gray, local_guess, exclude)
                if again_held > held + 0.02:
                    local, held = again, again_held
        result = local @ to_ref
        result = result / result[2, 2]
        self.history = [*self.history, result][-3:]
        # A new reference only when the plane has shrunk or grown past three times its reference: the warp back
        # absorbs turns, tilts and smaller zooms, and every refresh keeps the error of its moment (on the benchmark,
        # refreshing at 1.5x or 30 degrees drifted a faint surface from 0.42 to 1.26 px; without, it held 0.45 px)
        scale = _plane_scale(local, self.ref.box)
        if held > 0.8 and exclude is None and abs(math.log(max(1e-6, scale))) > math.log(3.0):
            # (never while points are failing or something is excluded: a reference taken then keeps the occluder)
            self._refresh(gray, local)
        return result, float(np.clip(held, 0.0, 1.0))

    def _refresh(self, gray: np.ndarray, local: np.ndarray) -> None:
        """The current frame becomes the reference: its matte the old one carried by the track."""
        matte = cv2.warpPerspective(self.ref.matte, local, self.size, flags=cv2.INTER_NEAREST)
        if (matte > 0).sum() < 400:
            return
        self.ref_to_origin = self.ref_to_origin @ np.linalg.inv(local)
        self.ref_to_origin /= self.ref_to_origin[2, 2]
        self.ref = _Reference(gray, matte, self.settings, self.orb)
        self.refreshes += 1


def track(
    read: Callable[[int], np.ndarray],
    start: int,
    stop: int,
    matte: np.ndarray,
    settings: Settings | None = None,
    exclude: Callable[[int], np.ndarray | None] | None = None,
    on_frame: Callable[[int, np.ndarray, float], None] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict[int, tuple[np.ndarray, float]]:
    """A layer tracked from frame start (its reference, the matte drawn there) to frame stop, forwards or backwards
    (stop before start): {frame: (homography from start, confidence)}."""
    tracker = PlanarTracker(read(start), matte, settings)
    out = {start: (np.eye(3), 1.0)}
    step = 1 if stop >= start else -1
    for index in range(start + step, stop + step, step):
        if cancelled():
            break
        h, confidence = tracker.step(read(index), exclude(index) if exclude else None)
        out[index] = (h, confidence)
        if on_frame is not None:
            on_frame(index, h, confidence)
    return out
