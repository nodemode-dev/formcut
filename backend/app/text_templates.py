"""Animated titles: text styles with motion, added at the playhead from the Text tab.

The built-in title styles (presets.TITLE_STYLES) restyle a title that exists;
these are finished designs: one or more lines, each with its style, place,
keyframes and fades, timed from the moment they are added. The interface adds
them on a new track at the top, so they draw above the footage (track 0 draws
on top). Thumbnails are drawn through the renderer at each design's telling
moment (effect_previews.py). Words are placeholders, written for formcut.
Left-aligned text starts at a 5 percent margin and moves by posX from there.
"""

from __future__ import annotations

WHITE, INK, SUN, CORAL, RED = "#ffffff", "#0d0e12", "#ffc83d", "#ff5a5f", "#e5282e"


def _line(
    content: str,
    offset: float,
    duration: float,
    *,
    size: float = 9,
    color: str = WHITE,
    weight: int = 800,
    x: float = 0,
    y: float = 0,
    fade: tuple[float, float] = (0.25, 0.3),
    keys: list | None = None,
    rotation: float = 0,
    **style,
) -> dict:
    clip = {
        "offset": offset,
        "duration": duration,
        "kind": "text",
        "label": content.splitlines()[0][:40],
        "textStyle": {
            "content": content,
            "size": size,
            "color": color,
            "bold": weight >= 600,
            "weight": weight,
            "align": style.pop("align", "center"),
            **style,
        },
        "transform": {"posX": x, "posY": y, "rotation": rotation},
        "fadeIn": fade[0],
        "fadeOut": fade[1],
    }
    if keys:
        clip["keyframes"] = keys
    return clip


def _k(t: float, interp: str = "easeOut", **props) -> dict:
    return {"t": t, "props": props, "interp": interp}


PLATE = {"plateColor": INK, "plateOpacity": 0.8, "platePadding": 18, "plateRadius": 10}

TEXT_TEMPLATES: list[dict] = [
    {
        "id": "pop",
        "name": "Pop in",
        "hero": 1.0,
        "clips": [_line("POP IN", 0, 3.5, size=11, weight=900, keys=[_k(0, "overshoot", scale=40), _k(0.45, "easeOut", scale=100)])],
    },
    {
        "id": "rise",
        "name": "Rise up",
        "hero": 1.0,
        "clips": [_line("Rise up", 0, 3.5, size=10, keys=[_k(0, "easeOut", posY=10, opacity=0), _k(0.6, "easeOut", posY=0, opacity=100)])],
    },
    {
        "id": "zoom-out",
        "name": "Zoom out",
        "hero": 1.2,
        "clips": [
            _line(
                "ZOOM OUT",
                0,
                3.5,
                size=10,
                weight=900,
                letterSpacing=6,
                keys=[_k(0, "easeOut", scale=170, opacity=0), _k(0.7, "easeOut", scale=100, opacity=100)],
            )
        ],
    },
    {
        "id": "drop",
        "name": "Drop in",
        "hero": 1.0,
        "clips": [_line("Drop in", 0, 3.5, size=10, keys=[_k(0, "overshoot", posY=-45), _k(0.6, "easeOut", posY=0)])],
    },
    {
        "id": "spin",
        "name": "Spin in",
        "hero": 1.2,
        "clips": [
            _line(
                "Spin in",
                0,
                3.5,
                size=10,
                keys=[_k(0, "easeOut", rotation=-120, scale=30, opacity=0), _k(0.7, "overshoot", rotation=0, scale=100, opacity=100)],
            )
        ],
    },
    {
        "id": "lower-third",
        "name": "Lower third",
        "hero": 1.5,
        "clips": [
            _line(
                "Your Name",
                0,
                4.0,
                size=5.2,
                align="left",
                wrapWidth=44,
                x=1,
                y=30,
                **PLATE,
                keys=[_k(0, "easeOut", posX=-39), _k(0.6, "easeOut", posX=1)],
            ),
            _line(
                "What you do",
                0.3,
                3.7,
                size=3.0,
                weight=500,
                color=SUN,
                align="left",
                wrapWidth=44,
                x=1,
                y=38,
                keys=[_k(0, "easeOut", posX=-39), _k(0.6, "easeOut", posX=1)],
            ),
        ],
    },
    {
        "id": "subtitle-bar",
        "name": "Subtitle bar",
        "hero": 1.0,
        "clips": [_line("A line of subtitle text", 0, 3.5, size=4.2, weight=600, y=38, wrapWidth=80, **PLATE)],
    },
    {
        "id": "kicker-headline",
        "name": "Kicker and headline",
        "hero": 1.4,
        "clips": [
            _line(
                "SMALL KICKER",
                0,
                3.6,
                size=3.2,
                weight=700,
                color=SUN,
                y=-9,
                letterSpacing=8,
                keys=[_k(0, "easeOut", posY=-3, opacity=0), _k(0.5, "easeOut", posY=-9, opacity=100)],
            ),
            _line(
                "The big headline",
                0.25,
                3.35,
                size=9.5,
                weight=900,
                y=3,
                keys=[_k(0, "easeOut", posY=10, opacity=0), _k(0.6, "easeOut", posY=3, opacity=100)],
            ),
        ],
    },
    {
        "id": "neon",
        "name": "Neon flicker",
        "hero": 1.5,
        "clips": [
            _line(
                "NEON",
                0,
                3.5,
                size=14,
                weight=800,
                color="#b9fbff",
                shadowColor="#00e5ff",
                shadowBlur=30,
                fade=(0, 0.3),
                keys=[
                    _k(0, "linear", opacity=0),
                    _k(0.1, "linear", opacity=100),
                    _k(0.2, "linear", opacity=25),
                    _k(0.3, "linear", opacity=100),
                    _k(0.45, "linear", opacity=40),
                    _k(0.55, "linear", opacity=100),
                ],
            )
        ],
    },
    {
        "id": "stamp",
        "name": "Stamp",
        "hero": 1.0,
        "clips": [
            _line(
                "APPROVED",
                0,
                3.0,
                size=8,
                weight=900,
                letterSpacing=6,
                rotation=-8,
                fade=(0, 0.3),
                plateColor=RED,
                plateOpacity=1,
                platePadding=20,
                plateRadius=8,
                keys=[_k(0, "easeIn", scale=260, opacity=0), _k(0.22, "overshoot", scale=100, opacity=100)],
            )
        ],
    },
    {
        "id": "call-to-action",
        "name": "Call to action",
        "hero": 0.9,
        "clips": [
            _line(
                "Subscribe",
                0,
                3.0,
                size=6,
                weight=800,
                plateColor=RED,
                plateOpacity=1,
                platePadding=22,
                plateRadius=40,
                keys=[
                    _k(0, "overshoot", scale=50),
                    _k(0.4, "easeInOut", scale=100),
                    _k(0.9, "easeInOut", scale=108),
                    _k(1.4, "easeInOut", scale=100),
                    _k(1.9, "easeInOut", scale=108),
                    _k(2.4, "easeInOut", scale=100),
                ],
            )
        ],
    },
    {
        "id": "quote",
        "name": "Quote",
        "hero": 2.0,
        "clips": [
            _line(
                "\u201cWords worth\nremembering.\u201d",
                0,
                4.0,
                size=7,
                weight=600,
                italic=True,
                lineHeight=1.15,
                wrapWidth=70,
                y=-4,
                fade=(0.8, 0.5),
            ),
            _line("Name of the speaker", 0.8, 3.2, size=3.0, weight=500, color="#b8b8c2", y=15, letterSpacing=4, fade=(0.6, 0.5)),
        ],
    },
    {
        "id": "cinematic",
        "name": "Cinematic",
        "hero": 2.0,
        "clips": [
            _line(
                "CINEMATIC",
                0,
                4.0,
                size=9,
                weight=300,
                letterSpacing=34,
                fade=(1.0, 0.8),
                keys=[_k(0, "linear", scale=100), _k(4.0, "linear", scale=104)],
            )
        ],
    },
    {
        "id": "new-label",
        "name": "New label",
        "hero": 1.0,
        "clips": [
            _line(
                "NEW",
                0,
                3.0,
                size=7,
                weight=900,
                color=INK,
                rotation=-6,
                outlineWidth=0,
                plateColor=SUN,
                plateOpacity=1,
                platePadding=18,
                plateRadius=10,
                keys=[_k(0, "overshoot", scale=40), _k(0.4, "easeOut", scale=100)],
            )
        ],
    },
    {
        "id": "three-words",
        "name": "Three words",
        "hero": 1.6,
        "clips": [
            _line(
                word,
                0.35 * i,
                3.5 - 0.35 * i,
                size=9,
                weight=900,
                y=-12 + 12 * i,
                color=(SUN if i == 2 else WHITE),
                keys=[_k(0, "easeOut", posX=10, opacity=0), _k(0.4, "easeOut", posX=0, opacity=100)],
            )
            for i, word in enumerate(("Plan.", "Shoot.", "Share."))
        ],
    },
    {
        "id": "caption-box",
        "name": "Caption box",
        "hero": 1.0,
        "clips": [
            _line(
                "Caption text goes here",
                0,
                3.5,
                size=4.4,
                weight=700,
                color="#111111",
                y=36,
                wrapWidth=80,
                outlineWidth=0,
                plateColor=WHITE,
                plateOpacity=1,
                platePadding=18,
                plateRadius=14,
                keys=[_k(0, "easeOut", posY=40, opacity=0), _k(0.4, "easeOut", posY=36, opacity=100)],
            )
        ],
    },
]

IDS = {entry["id"] for entry in TEXT_TEMPLATES}


def _slug(template_id: str) -> str:
    return template_id.replace("-", "")


def listing() -> list[dict]:
    """Each design, with the length it runs for and its clips timed from where it is added."""
    return [
        {
            "id": entry["id"],
            "name": entry["name"],
            "nameKey": f"tt.{_slug(entry['id'])}",
            "duration": max(c["offset"] + c["duration"] for c in entry["clips"]),
            "clips": entry["clips"],
        }
        for entry in TEXT_TEMPLATES
    ]


def project(template_id: str, width: int, height: int) -> dict:
    """A small project holding the design from time 0, for its thumbnail and its tests."""
    entry = next(e for e in TEXT_TEMPLATES if e["id"] == template_id)
    clips = [
        {**{k: v for k, v in clip.items() if k != "offset"}, "id": f"tt{i}", "start": clip["offset"]}
        for i, clip in enumerate(entry["clips"])
    ]
    duration = max(c["start"] + c["duration"] for c in clips)
    return {
        "title": "p",
        "width": width,
        "height": height,
        "fps": 30,
        "duration": duration,
        "activeTimeline": 0,
        "background": "#1c1d24",
        "timelines": [{"id": "p", "name": "p", "tracks": [{"id": "t", "name": "T", "clips": clips}]}],
    }


def hero(template_id: str) -> float:
    return next(e["hero"] for e in TEXT_TEMPLATES if e["id"] == template_id)
