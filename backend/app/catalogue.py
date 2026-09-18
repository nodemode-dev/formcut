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
}

VIDEO_EFFECTS = [
    "gaussian", "box", "directional-blur", "radial-blur", "sharpen", "edge", "emboss",
    "invert", "posterize", "threshold", "solarize", "pixelate", "vignette", "grain",
    "glow", "chromatic", "fisheye", "wave", "mirror", "kaleidoscope", "scanlines",
    "interference", "cartoon", "pencil", "rain", "dust", "camera-shake",
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
}

TRANSITIONS = ["crossfade", "dip", "wipe-left", "wipe-right", "wipe-up", "wipe-down", "slide-left", "slide-right", "zoom", "iris", "dissolve", "push-up"]

EFFECT_GROUPS = {
    "Blur": ["gaussian", "box", "directional-blur", "radial-blur", "glow"],
    "Stylize": ["sharpen", "edge", "emboss", "posterize", "threshold", "solarize", "invert", "cartoon", "pencil"],
    "Distort": ["pixelate", "chromatic", "fisheye", "wave", "mirror", "kaleidoscope", "camera-shake"],
    "Texture": ["vignette", "grain", "scanlines", "interference", "rain", "dust"],
}
FILTER_GROUPS = {
    "Adjust": ["exposure", "contrast", "saturation", "vibrance", "highlight-rolloff", "shadow-detail", "low-key", "high-key"],
    "Film": ["faded", "matte", "pastel", "paper", "bleach", "punch", "silver", "noir", "monochrome", "sepia"],
    "Warm": ["warmth", "copper", "amber-highlights", "sunrise", "autumn", "sand", "rose", "red-lift"],
    "Cool": ["cooling", "cyan-shadows", "midnight", "arctic", "emerald", "forest", "lavender", "blue-lift", "green-lift"],
    "Split": ["teal-amber", "split-purple", "split-green"],
}
AUDIO_GROUPS = {
    "Voice": ["pitch_up", "pitch_down", "robot", "telephone", "radio", "vibrato", "tremolo"],
    "Tone": ["bass", "treble", "distortion"],
    "Space": ["echo", "room", "hall", "cathedral", "plate"],
    "Clean": ["denoise", "voice-clean", "de-ess", "compress", "normalize"],
}


def group_of(key: str, groups: dict) -> str:
    return next((name for name, keys in groups.items() if key in keys), "Other")


NAMES = {
    "gaussian": "Gaussian Blur", "box": "Box Blur", "edge": "Edge Detect", "chromatic": "Chromatic Aberration",
    "grain": "Film Grain", "interference": "Signal Interference", "pencil": "Pencil Sketch", "de-ess": "De-ess",
}


def label(key: str) -> str:
    return NAMES.get(key) or key.replace("-", " ").replace("_", " ").title()


@router.get("")
def catalogue() -> dict:
    parameters = {"gaussian": {"radius": 3}, "box": {"size": 12}, "directional-blur": {"size": 12}, "sharpen": {"radius": 3}, "posterize": {"levels": 5}, "threshold": {"threshold": 0.5}, "solarize": {"threshold": 0.5}, "pixelate": {"size": 12}, "grain": {"strength": 0.07}, "glow": {"radius": 3}, "chromatic": {"size": 12}, "wave": {"size": 12}, "interference": {"size": 12}, "pencil": {"radius": 3}, "camera-shake": {"size": 12}}
    return {
        "video": [{"id": k, "name": label(k), "category": "Color", "group": group_of(k, FILTER_GROUPS), "parameters": GRADES[k]} for k in GRADES]
        + [{"id": k, "name": label(k), "category": "Effects", "group": group_of(k, EFFECT_GROUPS), "parameters": parameters.get(k, {})} for k in VIDEO_EFFECTS],
        "audio": [{"id": k, "name": label(k), "group": group_of(k, AUDIO_GROUPS)} for k in AUDIO_CHAINS],
        "transitions": TRANSITIONS,
        "blendModes": ["Normal", "Multiply", "Screen", "Overlay", "Darken", "Lighten", "Difference", "Add", "Subtract", "Soft Light"],
    }
