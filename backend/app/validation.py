import math

from .catalogue import AUDIO_CHAINS, GRADES, TRANSITIONS, VIDEO_EFFECTS


def number(value, name, low=-100000, high=100000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Invalid " + name)


def project_values(project):
    fill = project.get("background")
    if fill is None:
        return
    if isinstance(fill, str):
        if len(fill) > 32:
            raise ValueError("Invalid background")
        return
    if not isinstance(fill, dict) or fill.get("type") not in ("colour", "gradient", "image", "blur"):
        raise ValueError("Invalid background")
    if fill.get("amount") is not None:
        number(fill["amount"], "background amount", 1, 200)


def clip_values(clip):
    for name, low, high in [
        ("sourceIn", 0, 86400),
        ("speed", 0.05, 100),
        ("volume", 0, 4),
        ("pan", -1, 1),
        ("fadeIn", 0, 86400),
        ("fadeOut", 0, 86400),
    ]:
        if clip.get(name) is not None:
            number(clip[name], name, low, high)
    for edge in ("left", "top", "right", "bottom"):
        value = (clip.get("crop") or {}).get(edge)
        if value is not None:
            number(value, "crop " + edge, 0, 0.45)
    mask = clip.get("mask") or {}
    if mask:
        from .renderer import MASK_SHAPES

        shape = mask.get("shape")
        if shape not in set(MASK_SHAPES) | {"linear", "path"}:
            raise ValueError("Unknown mask shape")
        if shape == "path":
            points = mask.get("points") or []
            if not isinstance(points, list) or not 2 <= len(points) <= 400:
                raise ValueError("A drawn mask needs between two and four hundred points")
            for point in points:
                for field, low, high in [("x", -2, 3), ("y", -2, 3), ("inX", -3, 3), ("inY", -3, 3), ("outX", -3, 3), ("outY", -3, 3)]:
                    if point.get(field) is not None:
                        number(point[field], "path " + field, low, high)
        if mask.get("angle") is not None:
            number(mask["angle"], "mask angle", -360, 360)
    for entry in clip.get("keyframes") or []:
        handles = entry.get("handles")
        if handles is not None:
            if not isinstance(handles, list) or len(handles) != 4:
                raise ValueError("An easing curve needs four handle values")
            for value in handles:
                number(value, "easing handle", -5, 5)
    if clip.get("smoothSlow") is not None and not isinstance(clip["smoothSlow"], bool):
        raise ValueError("Invalid smoothSlow")
    steady = clip.get("stabilise") or {}
    if steady:
        for name, low, high in [("smoothing", 0, 1), ("crop", 0, 0.3)]:
            if steady.get(name) is not None:
                number(steady[name], "stabilise " + name, low, high)
    panel = clip.get("colour") or {}
    if panel:
        for name, low, high in [
            ("temperature", 2000, 11000),
            ("tint", -100, 100),
            ("saturation", -100, 100),
            ("exposure", -5, 5),
            ("brightness", -100, 100),
            ("contrast", -100, 100),
            ("highlights", -100, 100),
            ("shadows", -100, 100),
            ("whites", -100, 100),
            ("blacks", -100, 100),
            ("sharpen", 0, 100),
            ("fade", 0, 100),
            ("vignette", -100, 100),
        ]:
            if panel.get(name) is not None:
                number(panel[name], "colour " + name, low, high)
    style = clip.get("textStyle") or {}
    for name, low, high in [
        ("weight", 100, 900),
        ("outlineWidth", 0, 50),
        ("shadowBlur", 0, 100),
        ("shadowX", -200, 200),
        ("shadowY", -200, 200),
        ("plateOpacity", 0, 1),
        ("platePadding", 0, 200),
        ("plateRadius", 0, 200),
        ("lineHeight", 0.5, 4),
        ("letterSpacing", -50, 200),
        ("wrapWidth", 5, 100),
        ("textOpacity", 0, 1),
    ]:
        if style.get(name) is not None:
            number(style[name], "title " + name, low, high)
    for point in clip.get("speedCurve") or []:
        number(point["t"], "curve time", 0, 86400)
        number(point["speed"], "curve speed", 0.05, 100)
    transform = clip.get("transform") or {}
    for prop in ("posX", "posY", "scale", "rotation", "opacity", "width", "height"):
        if prop in transform:
            number(transform[prop], prop)
    frames = clip.get("keyframes") or []
    if len(frames) > 20000:
        raise ValueError("Too many keyframes")
    for frame in frames:
        number(frame["t"], "keyframe time", -86400, 86400)
        from .timing import EASINGS

        if frame.get("interp", "linear") not in set(EASINGS) | {"hold", "bezier"}:
            raise ValueError("Unknown interpolation")
        for key, value in frame.get("props", {}).items():
            if key not in ("posX", "posY", "scale", "rotation", "opacity"):
                raise ValueError("Unknown animated property")
            number(value, key)
    from .effect_packages import entries as package_entries

    video_packages = {e["id"] for e in package_entries("video")}
    audio_packages = {e["id"] for e in package_entries("audio")}
    for field, allowed in [
        ("effects", set(GRADES) | set(VIDEO_EFFECTS) | video_packages),
        ("audioEffects", set(AUDIO_CHAINS) | audio_packages),
    ]:
        entries = clip.get(field) or []
        if len(entries) > 32:
            raise ValueError("Too many processors")
        for entry in entries:
            if entry.get("id") not in allowed:
                raise ValueError("Unknown processor")
            number(entry.get("amount", 1), "processor amount", 0, 1)
            for key, value in (entry.get("params") or {}).items():
                number(value, key, -100, 100)
            keys = entry.get("keys") or {}
            if not isinstance(keys, dict) or len(keys) > 16:
                raise ValueError("Invalid parameter keys")
            for name, points in keys.items():
                if not isinstance(points, list) or len(points) > 200:
                    raise ValueError("Invalid parameter keys")
                for point in points:
                    number(point.get("t"), name + " key time", 0, 86400)
                    number(point.get("value"), name + " key value", -100, 100)
    for point in clip.get("volumeKeys") or []:
        number(point.get("t"), "volume key time", 0, 86400)
        number(point.get("value"), "volume key value", 0, 4)
    animations = clip.get("animations") or {}
    if animations:
        for slot in ("in", "out"):
            entry = animations.get(slot)
            if entry is not None:
                number(entry.get("seconds", 1), slot + " animation seconds", 0.05, 86400)
    transition = clip.get("transitionIn")
    if transition:
        if transition.get("type") not in TRANSITIONS:
            raise ValueError("Unknown transition")
        number(transition.get("duration", 0.5), "transition duration", 0.01, 86400)
    cutout = clip.get("cutout")
    if cutout:
        if cutout.get("model") not in ("object-cutout", "person-cutout", "sharp-cutout", "video-matting", "click-select"):
            raise ValueError("Unknown cutout model")
        number(cutout.get("threshold", 0.5), "cutout threshold", 0, 1)
        number(cutout.get("feather", 0.1), "cutout feather", 0.005, 0.5)
        chosen = cutout.get("point")
        if chosen is not None:
            if not isinstance(chosen, dict):
                raise ValueError("Cutout point must be an object")
            number(chosen.get("x", 0.5), "cutout point x", 0, 1)
            number(chosen.get("y", 0.5), "cutout point y", 0, 1)
        points = cutout.get("points") or []
        if not isinstance(points, list) or len(points) > 16:
            raise ValueError("Cutout points must be a list of at most 16")
        for entry in points:
            if not isinstance(entry, dict):
                raise ValueError("Cutout point must be an object")
            number(entry.get("x", 0.5), "cutout point x", 0, 1)
            number(entry.get("y", 0.5), "cutout point y", 0, 1)
        box = cutout.get("box")
        if box is not None:
            if not isinstance(box, dict):
                raise ValueError("Cutout box must be an object")
            for side in ("x0", "y0", "x1", "y1"):
                number(box.get(side), "cutout box " + side, 0, 1)
            if not (box["x0"] < box["x1"] and box["y0"] < box["y1"]):
                raise ValueError("Cutout box must have a size")
        for stroke in cutout.get("strokes", []):
            if stroke.get("mode") not in ("keep", "erase"):
                raise ValueError("Invalid brush mode")
            number(stroke.get("radius", 0.02), "brush radius", 0.001, 1)
            for point in stroke.get("points", []):
                if len(point) != 2:
                    raise ValueError("Invalid brush point")
                for coordinate in point:
                    number(coordinate, "brush coordinate", -10, 10)
