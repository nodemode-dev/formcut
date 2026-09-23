#!/usr/bin/env python3
"""Write formcut's library of looks: backend/app/effect_library/[id]/manifest.json.

    python setup/effect_library.py           # write the library
    python setup/effect_library.py --check   # exit 1 if it is out of date

Each look is a stack package: one of twenty colour grades, then one of nine
finishes made of formcut's own texture effects, 180 in all. They render through
the same effects as everything else, so preview and export agree on any machine.
Names are composed from translated parts, so every look is named in all twelve
languages. The manifests are generated, never edited by hand.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "backend" / "app" / "effect_library"
LANGUAGES = ("de", "es", "fr", "it", "ja", "ko", "pt-BR", "ru", "tr", "zh-Hans", "zh-Hant")
NAMES = json.loads((Path(__file__).with_name("effect_library_names.json")).read_text(encoding="utf-8"))

# English name and the grade; the translations are in effect_library_names.json.
GRADES = [
    ("Golden Hour", {"temperature": 0.35, "saturation": 1.15, "contrast": 1.05, "highlights_r": 0.04}),
    ("Blue Hour", {"temperature": -0.3, "tint": 0.05, "saturation": 0.9, "exposure": -0.1, "shadows_b": 0.06}),
    ("Faded Film", {"contrast": 0.82, "lift": 0.06, "saturation": 0.8, "highlights_r": 0.03}),
    (
        "Teal and Orange",
        {"shadows_b": 0.08, "shadows_g": 0.03, "highlights_r": 0.08, "highlights_g": 0.02, "saturation": 1.1, "contrast": 1.1},
    ),
    ("Bleach Bypass", {"saturation": 0.45, "contrast": 1.35, "gamma": 1.05}),
    ("Noir", {"saturation": 0.0, "contrast": 1.4, "gamma": 1.1}),
    ("Silver Mono", {"saturation": 0.0, "contrast": 1.1, "lift": 0.03, "highlights_b": 0.02}),
    ("Sepia Print", {"sepia": 0.85, "contrast": 1.05, "lift": 0.03}),
    ("Pastel", {"saturation": 0.75, "lift": 0.08, "contrast": 0.85, "exposure": 0.15, "tint": 0.04}),
    ("Vivid Pop", {"saturation": 1.45, "vibrance": 0.3, "contrast": 1.12}),
    ("Cross Process", {"shadows_b": 0.1, "highlights_g": 0.06, "highlights_r": 0.05, "contrast": 1.2, "saturation": 1.2}),
    ("Moody Green", {"tint": -0.12, "saturation": 0.85, "contrast": 1.1, "exposure": -0.15, "shadows_g": 0.04}),
    ("Arctic", {"temperature": -0.45, "saturation": 0.8, "exposure": 0.1, "highlights_b": 0.05}),
    ("Desert", {"temperature": 0.45, "saturation": 0.9, "contrast": 1.05, "lift": 0.03, "highlights_r": 0.05}),
    ("Rose Tint", {"tint": 0.18, "highlights_r": 0.05, "saturation": 1.05}),
    ("Night City", {"temperature": -0.2, "contrast": 1.25, "exposure": -0.3, "shadows_b": 0.08, "highlights_r": 0.04, "saturation": 1.2}),
    ("Matte", {"lift": 0.1, "contrast": 0.9, "saturation": 0.9}),
    ("Punchy Contrast", {"contrast": 1.4, "saturation": 1.1, "gamma": 0.95}),
    ("Autumn", {"temperature": 0.25, "tint": 0.05, "saturation": 1.2, "highlights_r": 0.06, "shadows_r": 0.03}),
    ("Mint", {"tint": -0.1, "temperature": -0.1, "lift": 0.05, "saturation": 0.9, "highlights_g": 0.04}),
]

# The finishes after the grade: formcut's own texture effects at a chosen strength.
FINISHES = [
    (None, []),
    ("Grain", [("grain", 0.4)]),
    ("Vignette", [("vignette", 0.8)]),
    ("Light Leak", [("light-leak", 0.6)]),
    ("Dust and Scratches", [("dust", 0.6), ("film-scratches", 0.5)]),
    ("Soft Glow", [("soft-focus", 0.5), ("glow", 0.4)]),
    ("Halftone Print", [("halftone", 0.35)]),
    ("Retro Screen", [("scanlines", 0.6), ("chroma-noise", 0.4)]),
    ("Paper Texture", [("paper-texture", 0.7)]),
]


def _slug(name: str) -> str:
    return name.lower().replace(" and ", "-").replace(" ", "-")


def manifests() -> dict[str, dict]:
    looks = {}
    for grade_name, grade in GRADES:
        grade_names = NAMES[grade_name]
        for finish_name, steps in FINISHES:
            finish_names = NAMES[finish_name] if finish_name else {}
            look_id = _slug(grade_name) + (f"-{_slug(finish_name)}" if finish_name else "")
            looks[look_id] = {
                "id": look_id,
                "name": grade_name + (f" · {finish_name}" if finish_name else ""),
                "kind": "video",
                "category": grade_name,
                "names": {code: grade_names[code] + (f" · {finish_names[code]}" if finish_name else "") for code in LANGUAGES},
                "stack": [{"grade": grade}] + [{"effect": effect, "amount": amount} for effect, amount in steps],
            }
    return looks


def _text(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    looks = manifests()
    existing = {p.name for p in LIBRARY.iterdir() if p.is_dir()} if LIBRARY.is_dir() else set()
    stale = [
        look_id
        for look_id, manifest in looks.items()
        if not (LIBRARY / look_id / "manifest.json").is_file()
        or (LIBRARY / look_id / "manifest.json").read_text(encoding="utf-8") != _text(manifest)
    ]
    extra = sorted(existing - set(looks))
    if "--check" in sys.argv[1:]:
        if stale or extra:
            print(f"the library is out of date ({len(stale)} changed, {len(extra)} extra): run python setup/effect_library.py")
            return 1
        print(f"the library is current: {len(looks)} looks")
        return 0
    for folder in extra:
        shutil.rmtree(LIBRARY / folder)
    for look_id in stale:
        (LIBRARY / look_id).mkdir(parents=True, exist_ok=True)
        (LIBRARY / look_id / "manifest.json").write_text(_text(looks[look_id]), encoding="utf-8")
    print(f"wrote {len(stale)} of {len(looks)} looks, removed {len(extra)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
