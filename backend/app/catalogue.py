import json
import hashlib
import sys
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api/catalogue", tags=["catalogue"])

GRADES = {
    "neutral": {},
    "exposure": {"exposure": 0.5},
    "contrast": {"contrast": 1.4},
    "saturation": {"saturation": 1.5},
    "monochrome": {"saturation": 0},
    "warmth": {"temperature": 0.22},
    "cooling": {"temperature": -0.22},
    "sepia": {"sepia": 0.85},
    "faded": {"contrast": 0.8, "lift": 0.1, "saturation": 0.75},
    "silver": {"saturation": 0, "contrast": 1.3, "lift": 0.02},
    "copper": {"temperature": 0.3, "saturation": 0.8, "contrast": 1.15},
    "cyan-shadows": {"shadows_r": -0.1, "shadows_b": 0.13, "contrast": 1.1},
    "amber-highlights": {"highlights_r": 0.13, "highlights_b": -0.1},
    "teal-amber": {"shadows_r": -0.12, "shadows_b": 0.1, "highlights_r": 0.12, "highlights_b": -0.08},
    "rose": {"tint": 0.14, "lift": 0.04},
    "forest": {"tint": -0.13, "saturation": 0.8},
    "midnight": {"exposure": -0.7, "temperature": -0.18, "contrast": 1.2},
    "sunrise": {"temperature": 0.25, "tint": 0.06, "exposure": 0.25},
    "bleach": {"saturation": 0.3, "contrast": 1.65},
    "pastel": {"saturation": 0.65, "contrast": 0.8, "lift": 0.08},
    "punch": {"saturation": 1.3, "contrast": 1.4},
    "low-key": {"exposure": -0.4, "contrast": 1.4},
    "high-key": {"exposure": 0.6, "contrast": 0.85},
    "matte": {"lift": 0.12, "contrast": 0.9},
    "emerald": {"tint": -0.16, "temperature": -0.08, "contrast": 1.2},
    "lavender": {"tint": 0.13, "temperature": -0.12, "saturation": 0.75},
    "sand": {"temperature": 0.17, "saturation": 0.65, "lift": 0.03},
    "arctic": {"temperature": -0.3, "exposure": 0.2, "saturation": 0.6},
    "autumn": {"temperature": 0.24, "saturation": 1.2, "contrast": 1.1},
    "noir": {"saturation": 0, "contrast": 1.8, "exposure": -0.3},
    "paper": {"saturation": 0.15, "temperature": 0.1, "contrast": 0.75, "lift": 0.12},
    "split-purple": {"shadows_r": 0.13, "shadows_b": 0.16, "highlights_g": 0.07},
    "split-green": {"shadows_g": 0.12, "highlights_r": 0.12},
    "red-lift": {"shadows_r": 0.15},
    "blue-lift": {"shadows_b": 0.15},
    "green-lift": {"shadows_g": 0.12},
    "highlight-rolloff": {"gamma": 0.8, "contrast": 0.9},
    "shadow-detail": {"gamma": 0.7, "lift": 0.025},
    "vibrance": {"vibrance": 0.6},
    "soft-contrast": {"contrast": 0.82},
    "crisp-mids": {"contrast": 1.25, "gamma": 0.9},
    "lift-blacks": {"shadows_r": 0.2, "shadows_g": 0.2, "shadows_b": 0.2},
    "crush-blacks": {"lift": -0.05, "contrast": 1.1},
    "half-stop-down": {"exposure": -0.5},
    "desaturate": {"saturation": 0.55},
    "brighten-mids": {"gamma": 0.85},
    "cross-process": {"shadows_b": 0.12, "highlights_r": 0.08, "highlights_g": 0.1, "contrast": 1.2, "saturation": 1.15},
    "push-process": {"contrast": 1.35, "saturation": 1.1, "exposure": 0.15, "lift": -0.02},
    "pull-process": {"contrast": 0.8, "saturation": 0.85, "lift": 0.05, "exposure": -0.1},
    "expired-stock": {"temperature": 0.1, "tint": -0.06, "lift": 0.1, "saturation": 0.75, "shadows_g": 0.14, "highlights_r": 0.08, "contrast": 0.85},
    "tintype": {"saturation": 0, "sepia": 0.45, "contrast": 1.35, "exposure": -0.15},
    "cyanotype": {"saturation": 0, "temperature": -0.35, "tint": -0.05, "contrast": 1.1, "lift": 0.03},
    "night-print": {"exposure": -0.35, "contrast": 1.25, "temperature": -0.1, "saturation": 0.8},
    "tungsten": {"temperature": 0.38, "tint": -0.03, "contrast": 1.05},
    "candlelit": {"temperature": 0.3, "exposure": -0.25, "contrast": 1.15, "saturation": 1.1},
    "honey-glow": {"temperature": 0.18, "highlights_r": 0.06, "highlights_g": 0.04, "lift": 0.04},
    "terracotta": {"temperature": 0.3, "tint": 0.14, "saturation": 1.2, "shadows_r": 0.08, "contrast": 1.08},
    "peach-lift": {"temperature": 0.12, "tint": 0.07, "lift": 0.06, "contrast": 0.92},
    "late-sun": {"temperature": 0.36, "exposure": 0.15, "highlights_r": 0.1, "highlights_g": 0.06, "saturation": 1.15, "contrast": 1.15},
    "rust-shadows": {"shadows_r": 0.22, "shadows_g": 0.09, "contrast": 1.12, "temperature": 0.04},
    "overcast": {"temperature": -0.12, "saturation": 0.75, "contrast": 0.88, "lift": 0.03},
    "steel-blue": {"temperature": -0.22, "saturation": 0.7, "contrast": 1.2},
    "moonlit": {"temperature": -0.25, "exposure": -0.45, "saturation": 0.55, "lift": 0.02},
    "mint-air": {"tint": -0.2, "temperature": -0.08, "lift": 0.03, "saturation": 0.9},
    "deep-water": {"temperature": -0.28, "tint": -0.06, "exposure": -0.2, "shadows_b": 0.1},
    "frost-highlights": {"highlights_b": 0.2, "highlights_g": 0.08, "temperature": -0.1, "exposure": 0.12},
    "slate-shade": {"shadows_b": 0.16, "shadows_g": 0.06, "saturation": 0.6, "contrast": 1.12, "lift": 0.04, "temperature": -0.05},
    "red-cyan": {"shadows_r": 0.22, "highlights_g": 0.12, "highlights_b": 0.18},
    "pine-sky": {"shadows_g": 0.2, "shadows_b": 0.04, "highlights_b": 0.2, "highlights_g": 0.04},
    "navy-blush": {"shadows_b": 0.24, "highlights_r": 0.18, "highlights_b": 0.08},
    "violet-gold": {"shadows_r": 0.14, "shadows_b": 0.22, "highlights_r": 0.16, "highlights_g": 0.14},
    "teal-magenta": {"shadows_g": 0.16, "shadows_b": 0.16, "highlights_r": 0.16, "highlights_b": 0.16},
    "cocoa-cream": {"shadows_r": 0.18, "shadows_g": 0.1, "highlights_r": 0.08, "highlights_g": 0.08, "highlights_b": 0.06, "saturation": 0.45, "contrast": 0.95},
    "muted-split": {"saturation": 0.2, "shadows_b": 0.18, "highlights_r": 0.16, "highlights_g": 0.1},
}

VIDEO_EFFECTS = [
    "gaussian", "box", "directional-blur", "radial-blur", "sharpen", "edge", "emboss",
    "invert", "posterize", "threshold", "solarize", "pixelate", "vignette", "grain",
    "glow", "chromatic", "fisheye", "wave", "mirror", "kaleidoscope", "scanlines",
    "interference", "cartoon", "pencil", "rain", "dust", "camera-shake",
    "tilt-shift", "spin-blur", "lens-blur", "median-soften", "soft-focus", "diagonal-blur", "ghost-trail",
    "halftone", "duotone", "paint-wash", "thermal", "night-vision", "ink-outline", "crosshatch",
    "swirl", "ripple", "pinch", "slice-glitch", "tile-repeat", "polar-wrap", "heat-haze",
    "film-scratches", "light-leak", "aperture-grille", "paper-texture", "snowfall", "bokeh-spots", "chroma-noise",
]

AUDIO_CHAINS = {
    "pitch_up": "aresample=48000,asetrate=60000,aresample=48000,atempo=0.8",
    "pitch_down": "aresample=48000,asetrate=38400,aresample=48000,atempo=1.25",
    "echo": "aecho=0.8:0.7:100|220:0.4|0.2",
    "radio": "highpass=f=400,lowpass=f=2600,acompressor=threshold=0.12:ratio=4",
    "denoise": "afftdn=nf=-25",
    "voice-clean": "highpass=f=90,afftdn=nf=-25,acompressor=threshold=0.12:ratio=3,alimiter",
    "bass": "bass=g=8:f=120",
    "treble": "treble=g=6:f=3500",
    "telephone": "highpass=f=700,lowpass=f=2000",
    "room": "aecho=0.8:0.7:25|47|71:0.25|0.16|0.1",
    "hall": "aecho=0.8:0.7:90|170|290|410:0.4|0.28|0.18|0.1",
    "cathedral": "aecho=0.8:0.7:190|370|590|830:0.5|0.38|0.27|0.17",
    "plate": "aecho=0.8:0.7:41|73|113|167:0.4|0.3|0.2|0.1",
    "robot": "afftfilt=real='hypot(re,im)':imag='0':win_size=512:overlap=0.75",
    "tremolo": "tremolo=f=6:d=0.7",
    "vibrato": "vibrato=f=5:d=0.6",
    "distortion": "asoftclip=type=tanh:threshold=0.35:output=0.8",
    "compress": "acompressor=threshold=0.12:ratio=4:attack=10:release=150",
    "normalize": "loudnorm=I=-16:TP=-1.5:LRA=11",
    "de-ess": "deesser=i=0.5:m=0.5:f=0.5",
    "octave-up": "aresample=48000,asetrate=96000,aresample=48000,atempo=0.5",
    "octave-down": "aresample=48000,asetrate=24000,aresample=48000,atempo=2.0",
    "double-voice": "chorus=0.6:0.9:50|60:0.4|0.32:0.25|0.4:2|2.3",
    "jet-flange": "flanger=delay=2:depth=4:regen=40:speed=0.4",
    "swirl-phase": "aphaser=in_gain=0.6:out_gain=0.8:delay=3:decay=0.5:speed=0.6",
    "bullhorn": "highpass=f=600,lowpass=f=3200,acompressor=threshold=0.08:ratio=6,asoftclip=type=atan:threshold=0.5",
    "two-way-radio": "highpass=f=500,lowpass=f=2800,acrusher=bits=8:mode=log:aa=1,acompressor=threshold=0.1:ratio=5",
    "warm-lows": "lowshelf=g=5:f=180,highshelf=g=-2:f=6000",
    "presence-lift": "equalizer=f=3000:t=q:w=1.2:g=5",
    "mid-scoop": "equalizer=f=800:t=q:w=0.8:g=-7",
    "bit-crush": "volume=0.125,aformat=sample_fmts=u8,aformat=sample_fmts=flt,volume=8",
    "tape-warmth": "asoftclip=type=sin:threshold=0.7,lowpass=f=12000",
    "crisp-detail": "crystalizer=i=2",
    "lofi-band": "highpass=f=150,lowpass=f=3500,acrusher=bits=10:mode=log:aa=1",
    "slapback": "aecho=0.8:0.6:120:0.45",
    "wide-stage": "haas=left_delay=2.05:right_delay=10",
    "stereo-bloom": "stereowiden=delay=20:feedback=0.3:crossfeed=0.3:drymix=0.8",
    "long-tail": "aecho=0.8:0.8:400|800|1200:0.5|0.35|0.2",
    "tunnel": "aecho=0.8:0.85:60|120|180|240:0.6|0.45|0.3|0.2,lowpass=f=5000",
    "small-booth": "aecho=0.8:0.6:8|14|21:0.3|0.2|0.1,lowpass=f=6000",
    "far-away": "highpass=f=200,lowpass=f=2500,aecho=0.8:0.6:180|340:0.35|0.25,volume=0.6",
    "noise-gate": "agate=threshold=0.1:ratio=6:attack=5:release=120:range=0.05",
    "hiss-cut": "lowpass=f=9000,afftdn=nf=-30:nt=w",
    "hum-remover": "bandreject=f=50:width_type=q:w=4,bandreject=f=60:width_type=q:w=4,bandreject=f=100:width_type=q:w=4,bandreject=f=120:width_type=q:w=4",
    "rumble-cut": "highpass=f=80:poles=2",
    "level-rider": "dynaudnorm=f=100:g=5:p=0.9:m=8",
    "peak-limiter": "alimiter=limit=0.8:attack=5:release=50",
    "deep-denoise": "afftdn=nf=-35:nr=20:tn=1",
}

TRANSITIONS = ["crossfade", "dip", "wipe-left", "wipe-right", "wipe-up", "wipe-down", "slide-left", "slide-right", "zoom", "iris", "dissolve", "push-up"]

EFFECT_GROUPS = {
    "Blur": ["gaussian", "box", "directional-blur", "radial-blur", "glow", "tilt-shift", "spin-blur", "lens-blur", "median-soften", "soft-focus", "diagonal-blur", "ghost-trail"],
    "Stylize": ["sharpen", "edge", "emboss", "posterize", "threshold", "solarize", "invert", "cartoon", "pencil", "halftone", "duotone", "paint-wash", "thermal", "night-vision", "ink-outline", "crosshatch"],
    "Distort": ["pixelate", "chromatic", "fisheye", "wave", "mirror", "kaleidoscope", "camera-shake", "swirl", "ripple", "pinch", "slice-glitch", "tile-repeat", "polar-wrap", "heat-haze"],
    "Texture": ["vignette", "grain", "scanlines", "interference", "rain", "dust", "film-scratches", "light-leak", "aperture-grille", "paper-texture", "snowfall", "bokeh-spots", "chroma-noise"],
}
FILTER_GROUPS = {
    "Adjust": ["exposure", "contrast", "saturation", "vibrance", "highlight-rolloff", "shadow-detail", "low-key", "high-key", "soft-contrast", "crisp-mids", "lift-blacks", "crush-blacks", "half-stop-down", "desaturate", "brighten-mids"],
    "Film": ["faded", "matte", "pastel", "paper", "bleach", "punch", "silver", "noir", "monochrome", "sepia", "cross-process", "push-process", "pull-process", "expired-stock", "tintype", "cyanotype", "night-print"],
    "Warm": ["warmth", "copper", "amber-highlights", "sunrise", "autumn", "sand", "rose", "red-lift", "tungsten", "candlelit", "honey-glow", "terracotta", "peach-lift", "late-sun", "rust-shadows"],
    "Cool": ["cooling", "cyan-shadows", "midnight", "arctic", "emerald", "forest", "lavender", "blue-lift", "green-lift", "overcast", "steel-blue", "moonlit", "mint-air", "deep-water", "frost-highlights", "slate-shade"],
    "Split": ["teal-amber", "split-purple", "split-green", "red-cyan", "pine-sky", "navy-blush", "violet-gold", "teal-magenta", "cocoa-cream", "muted-split"],
}
AUDIO_GROUPS = {
    "Voice": ["pitch_up", "pitch_down", "robot", "telephone", "radio", "vibrato", "tremolo", "octave-up", "octave-down", "double-voice", "jet-flange", "swirl-phase", "bullhorn", "two-way-radio"],
    "Tone": ["bass", "treble", "distortion", "warm-lows", "presence-lift", "mid-scoop", "bit-crush", "tape-warmth", "crisp-detail", "lofi-band"],
    "Space": ["echo", "room", "hall", "cathedral", "plate", "slapback", "wide-stage", "stereo-bloom", "long-tail", "tunnel", "small-booth", "far-away"],
    "Clean": ["denoise", "voice-clean", "de-ess", "compress", "normalize", "noise-gate", "hiss-cut", "hum-remover", "rumble-cut", "level-rider", "peak-limiter", "deep-denoise"],
}


def group_of(key: str, groups: dict) -> str:
    return next((name for name, keys in groups.items() if key in keys), "Other")


# One spec per parameter key the pixel pipeline reads. A catalogue entry's
# declarations derive from its defaults: the key names the spec, the entry's
# own value is the default. The renderer clamps incoming values to these.
PARAM_SPECS = {
    "exposure": {"min": -2.0, "max": 2.0, "step": 0.01, "unit": "stops", "group": "tone"},
    "contrast": {"min": 0.2, "max": 3.0, "step": 0.01, "unit": "x", "group": "tone"},
    "gamma": {"min": 0.2, "max": 3.0, "step": 0.01, "unit": "", "group": "tone"},
    "lift": {"min": -0.25, "max": 0.25, "step": 0.005, "unit": "", "group": "tone"},
    "saturation": {"min": 0.0, "max": 3.0, "step": 0.01, "unit": "x", "group": "color"},
    "vibrance": {"min": -1.0, "max": 1.0, "step": 0.01, "unit": "", "group": "color"},
    "temperature": {"min": -0.5, "max": 0.5, "step": 0.005, "unit": "", "group": "color"},
    "tint": {"min": -0.5, "max": 0.5, "step": 0.005, "unit": "", "group": "color"},
    "sepia": {"min": 0.0, "max": 1.0, "step": 0.01, "unit": "", "group": "color"},
    "shadows_r": {"min": -0.3, "max": 0.3, "step": 0.005, "unit": "", "group": "wheels"},
    "shadows_g": {"min": -0.3, "max": 0.3, "step": 0.005, "unit": "", "group": "wheels"},
    "shadows_b": {"min": -0.3, "max": 0.3, "step": 0.005, "unit": "", "group": "wheels"},
    "highlights_r": {"min": -0.3, "max": 0.3, "step": 0.005, "unit": "", "group": "wheels"},
    "highlights_g": {"min": -0.3, "max": 0.3, "step": 0.005, "unit": "", "group": "wheels"},
    "highlights_b": {"min": -0.3, "max": 0.3, "step": 0.005, "unit": "", "group": "wheels"},
    "radius": {"min": 1.0, "max": 24.0, "step": 1.0, "unit": "px", "group": "shape"},
    "size": {"min": 2.0, "max": 64.0, "step": 1.0, "unit": "px", "group": "shape"},
    "levels": {"min": 2.0, "max": 16.0, "step": 1.0, "unit": "", "group": "shape"},
    "threshold": {"min": 0.0, "max": 1.0, "step": 0.01, "unit": "", "group": "shape"},
    "strength": {"min": 0.0, "max": 1.0, "step": 0.01, "unit": "", "group": "shape"},
}


def declare(defaults: dict) -> list[dict]:
    """The parameter declarations for one catalogue entry, from its defaults."""
    out = []
    for key, value in defaults.items():
        spec = PARAM_SPECS[key]
        out.append({"key": key, "labelKey": f"param.{key}", "min": spec["min"], "max": spec["max"],
                    "default": value, "step": spec["step"], "unit": spec["unit"], "group": spec["group"]})
    return out


def clamp_params(params: dict) -> dict:
    """Incoming parameter values held to their declared ranges; unknown keys dropped."""
    out = {}
    for key, value in (params or {}).items():
        spec = PARAM_SPECS.get(key)
        if spec is None or not isinstance(value, (int, float)):
            continue
        out[key] = min(spec["max"], max(spec["min"], float(value)))
    return out


NAMES = {
    "gaussian": "Gaussian Blur", "box": "Box Blur", "edge": "Edge Detect", "chromatic": "Chromatic Aberration",
    "grain": "Film Grain", "interference": "Signal Interference", "pencil": "Pencil Sketch", "de-ess": "De-ess",
    "silver": "Halide Mono", "copper": "Burnished", "rose": "Blush Lift", "forest": "Moss Tint",
    "midnight": "Nightfall", "sunrise": "First Light", "bleach": "Skip Bleach", "pastel": "Chalk Soft",
    "punch": "Hard Snap", "emerald": "Jade Contrast", "lavender": "Lilac Haze", "sand": "Dune Wash",
    "arctic": "Glacier Bright", "autumn": "Harvest", "noir": "Ink Shadow", "paper": "Newsprint",
}


def label(key: str) -> str:
    return NAMES.get(key) or key.replace("-", " ").replace("_", " ").title()


def _preview_version() -> str:
    try:
        source = b"".join(Path(__file__).with_name(name).read_bytes() for name in ("catalogue.py", "effect_previews.py", "pixel_effects.py", "renderer.py"))
    except OSError:
        source = str(Path(sys.executable).stat().st_mtime_ns).encode()
    return hashlib.sha1(source).hexdigest()[:12]


PREVIEW_VERSION = _preview_version()


EFFECT_DEFAULTS = {"gaussian": {"radius": 3}, "box": {"size": 12}, "directional-blur": {"size": 12}, "sharpen": {"radius": 3}, "posterize": {"levels": 5}, "threshold": {"threshold": 0.5}, "solarize": {"threshold": 0.5}, "pixelate": {"size": 12}, "grain": {"strength": 0.07}, "glow": {"radius": 3}, "chromatic": {"size": 12}, "wave": {"size": 12}, "interference": {"size": 12}, "pencil": {"radius": 3}, "camera-shake": {"size": 12}, "tilt-shift": {"radius": 3}, "lens-blur": {"radius": 3}, "median-soften": {"radius": 3}, "soft-focus": {"radius": 3}, "diagonal-blur": {"size": 12}, "ghost-trail": {"size": 12}, "halftone": {"size": 12}, "crosshatch": {"size": 12}, "ripple": {"size": 12}, "slice-glitch": {"size": 12}, "heat-haze": {"size": 12}, "chroma-noise": {"strength": 0.15}}


def package_entries(kind: str) -> list[dict]:
    from .effect_packages import entries
    return [{"id": e["id"], "name": e["name"], "category": e.get("category", "Packages"),
             "group": "Packages", "parameters": e["parameters"], "declarations": e["declarations"]}
            for e in entries(kind)]


@router.get("")
def catalogue() -> dict:
    return {
        "video": [{"id": k, "name": label(k), "category": "Color", "group": group_of(k, FILTER_GROUPS), "parameters": GRADES[k], "declarations": declare(GRADES[k])} for k in GRADES]
        + [{"id": k, "name": label(k), "category": "Effects", "group": group_of(k, EFFECT_GROUPS), "parameters": EFFECT_DEFAULTS.get(k, {}), "declarations": declare(EFFECT_DEFAULTS.get(k, {}))} for k in VIDEO_EFFECTS],
        "audio": [{"id": k, "name": label(k), "group": group_of(k, AUDIO_GROUPS)} for k in AUDIO_CHAINS],
        "transitions": TRANSITIONS,
        "blendModes": ["Normal", "Multiply", "Screen", "Overlay", "Darken", "Lighten", "Difference", "Add", "Subtract", "Soft Light"],
        "previewVersion": PREVIEW_VERSION,
    }

# K7: declared strength parameters, templated into the chain inside the engine.
# Clients send an id and numbers; filter text never crosses the boundary.
AUDIO_PARAMS: dict[str, dict] = {
    "denoise": {"strength": {"min": 0, "max": 100, "default": 50, "unit": "%"}},
    "deep-denoise": {"strength": {"min": 0, "max": 100, "default": 60, "unit": "%"}},
    "hiss-cut": {"strength": {"min": 0, "max": 100, "default": 50, "unit": "%"}},
    "voice-clean": {"strength": {"min": 0, "max": 100, "default": 50, "unit": "%"}},
    "compress": {"strength": {"min": 0, "max": 100, "default": 50, "unit": "%"}},
    "bass": {"strength": {"min": -100, "max": 100, "default": 50, "unit": "%"}},
    "treble": {"strength": {"min": -100, "max": 100, "default": 50, "unit": "%"}},
}

# Chains that take their strength by template rather than by wet/dry alone.
AUDIO_TEMPLATES: dict[str, str] = {
    "denoise": "afftdn=nf={nf:.1f}",
    "deep-denoise": "afftdn=nf={nf:.1f}:nr={nr:.0f}:tn=1",
    "hiss-cut": "lowpass=f={cut:.0f},afftdn=nf={nf:.1f}:nt=w",
    "voice-clean": "highpass=f=90,afftdn=nf={nf:.1f},acompressor=threshold=0.12:ratio={ratio:.1f},alimiter",
    "compress": "acompressor=threshold={threshold:.3f}:ratio={ratio:.1f}",
    "bass": "bass=g={gain:.1f}",
    "treble": "treble=g={gain:.1f}",
}


def audio_chain(effect_id: str, params: dict | None) -> str:
    from .effect_packages import chain_for
    packaged = chain_for(effect_id, params)
    if packaged:
        return packaged
    """The filter text for an effect, with any declared strength applied."""
    template = AUDIO_TEMPLATES.get(effect_id)
    if not template:
        return AUDIO_CHAINS[effect_id]
    declared = AUDIO_PARAMS.get(effect_id, {})
    raw = (params or {}).get("strength", declared.get("strength", {}).get("default", 50))
    try:
        strength = float(raw)
    except (TypeError, ValueError):
        strength = float(declared.get("strength", {}).get("default", 50))
    span = declared.get("strength", {})
    strength = max(float(span.get("min", 0)), min(float(span.get("max", 100)), strength))
    unit = strength / 100.0
    return template.format(
        # afftdn's nf is the assumed noise floor in dB, bounded to -80..-20:
        # a HIGHER (less negative) value treats more of the signal as noise, so
        # strength must climb towards -20, not away from it.
        nf=-75.0 + 52.0 * abs(unit),
        nr=6.0 + 24.0 * abs(unit),
        cut=14000.0 - 8000.0 * abs(unit),
        ratio=1.5 + 6.5 * abs(unit),
        threshold=max(0.02, 0.35 - 0.33 * abs(unit)),
        gain=12.0 * unit,
    )


def imported_looks() -> list[dict]:
    """K2: every imported .cube, offered as a library look under Filters."""
    from .assets import ROOT
    out = []
    if ROOT.is_dir():
        for record in sorted(ROOT.glob("*.json")):
            try:
                item = json.loads(record.read_text())
            except ValueError:
                continue
            if item.get("kind") == "lut":
                out.append({"id": item["id"], "name": item.get("name", "Look"), "group": "Imported"})
    return out


# Parameters measured in pixels must follow the resolution actually decoded, or
# a preview (which decodes small) blurs harder than the export of the same clip.
PIXEL_PARAMS = {name for name, spec in PARAM_SPECS.items() if spec.get("unit") == "px"}


def scale_pixel_params(params: dict, scale: float) -> dict:
    """Scale pixel-measured parameters by a decode ratio, keeping declared floors."""
    if not params or abs(scale - 1.0) < 1e-6:
        return params
    out = dict(params)
    for name in PIXEL_PARAMS & set(out):
        spec = PARAM_SPECS[name]
        out[name] = max(float(spec["min"]), float(out[name]) * scale)
    return out
