"""formcut's own templates, ready to fill with a person's footage and photos.

Each is an ordinary formcut template (templates.py): a project whose media clips
are slots, filled through the same route as a template a person saved. They are
built here rather than stored, so they always match the current document format,
and they cannot be deleted. Their words are placeholders to replace, written for
formcut. Track 0 draws on top, so titles sit on the first track and media below.
Names and slot names carry keys the interface translates (tpl.*).
"""

from __future__ import annotations

import copy
import itertools

_ids = itertools.count(1)


def _id() -> str:
    return f"c{next(_ids)}"


def _text(
    content: str,
    start: float,
    duration: float,
    *,
    size: float = 8,
    color: str = "#ffffff",
    x: float = 0,
    y: float = 0,
    weight: int = 700,
    align: str = "center",
    fade: tuple[float, float] = (0.4, 0.4),
    keys: list | None = None,
    **style,
) -> dict:
    clip = {
        "id": _id(),
        "kind": "text",
        "label": content.splitlines()[0][:40],
        "start": start,
        "duration": duration,
        "textStyle": {"content": content, "size": size, "color": color, "bold": weight >= 600, "weight": weight, "align": align, **style},
        "transform": {"posX": x, "posY": y},
        "fadeIn": fade[0],
        "fadeOut": fade[1],
    }
    if keys:
        clip["keyframes"] = keys
    return clip


def _media(
    slot: str,
    kind: str,
    start: float,
    duration: float,
    *,
    scale: float = 100,
    x: float = 0,
    y: float = 0,
    keys: list | None = None,
    transition: tuple[str, float] | None = None,
    effects: list | None = None,
    fade: tuple[float, float] = (0, 0),
) -> dict:
    clip = {
        "id": _id(),
        "kind": kind,
        "label": slot,
        "start": start,
        "duration": duration,
        "templateSlot": slot,
        "transform": {"scale": scale, "posX": x, "posY": y},
        "fadeIn": fade[0],
        "fadeOut": fade[1],
    }
    if kind != "image":
        clip["sourceIn"] = 0
    if keys:
        clip["keyframes"] = keys
    if transition:
        clip["transitionIn"] = {"type": transition[0], "duration": transition[1]}
    if effects:
        clip["effects"] = [{"id": effect, "amount": 1} for effect in effects]
    return clip


def _left(left: float, width: float) -> dict:
    """A left-aligned text box placed by its left edge, in percent of the width.
    The renderer starts left-aligned text at a 5 percent margin and moves it by
    posX from there (renderer.py, text layout); wrapWidth only sets where lines
    wrap. So a box whose left edge is at `left` has posX = left - 5."""
    return {"align": "left", "wrapWidth": width, "x": left - 5}


def _key(t: float, interp: str = "easeOut", **props) -> dict:
    return {"t": t, "props": props, "interp": interp}


def _project(
    name: str, duration: float, tracks: list[list[dict]], *, width: int = 1920, height: int = 1080, background: str = "#0d0e12"
) -> dict:
    return {
        "title": name,
        "width": width,
        "height": height,
        "fps": 30,
        "duration": duration,
        "activeTimeline": 0,
        "background": background,
        "timelines": [
            {
                "id": "main",
                "name": "Main",
                "tracks": [{"id": f"t{i}", "name": f"Track {i + 1}", "clips": clips} for i, clips in enumerate(tracks)],
            }
        ],
    }


def _slots(*entries: tuple[str, str, str]) -> list[dict]:
    return [
        {"id": slot, "name": name, "nameKey": f"tpl.slot.{key}", "kind": kind}
        for slot, name, key, kind in ((s[0], s[1], s[2], s[3]) for s in entries)
    ]


PLATE = {"plateColor": "#0d0e12", "plateOpacity": 0.78, "platePadding": 18, "plateRadius": 10}


def _cinematic_intro() -> dict:
    title = _text(
        "YOUR TITLE",
        0.8,
        6.2,
        size=12,
        weight=800,
        letterSpacing=24,
        fade=(1.0, 0.8),
        keys=[_key(0, "easeOut", scale=92, opacity=0), _key(1.4, "easeOut", scale=100, opacity=100)],
    )
    sub = _text("A film by your name", 2.0, 5.0, size=4.0, weight=500, y=14, letterSpacing=8, color="#e8e2d4", fade=(0.8, 0.8))
    video = _media(
        "video", "video", 0, 8, keys=[_key(0, "linear", scale=100), _key(8, "linear", scale=110)], effects=["teal-amber"], fade=(0.6, 1.0)
    )
    return {"project": _project("Cinematic intro", 8, [[title, sub], [video]]), "slots": _slots(("video", "Video", "video", "video"))}


def _lower_third() -> dict:
    box = _left(6, 44)
    slide = [_key(0, "easeOut", posX=box["x"] - 40), _key(0.6, "easeOut", posX=box["x"])]
    name = _text("Your Name", 0.8, 4.6, size=5.2, weight=800, y=30, fade=(0.3, 0.4), keys=slide, **PLATE, **box)
    role = _text("What you do", 1.1, 4.3, size=3.0, weight=500, y=38, color="#ffc83d", fade=(0.3, 0.4), keys=slide, **box)
    video = _media("video", "video", 0, 6)
    return {"project": _project("Lower third", 6, [[name, role], [video]]), "slots": _slots(("video", "Video", "video", "video"))}


def _photo_slideshow() -> dict:
    photos = []
    for i in range(5):
        start = i * 3.0
        drift = 4 if i % 2 == 0 else -4
        photos.append(
            _media(
                f"photo{i + 1}",
                "image",
                start,
                3.6 if i < 4 else 3.0,
                keys=[_key(0, "linear", scale=104, posX=-drift), _key(3.6, "linear", scale=114, posX=drift)],
                transition=("crossfade", 0.6) if i else None,
                fade=(0.5 if i == 0 else 0, 0.8 if i == 4 else 0),
            )
        )
    title = _text("Our summer", 0.5, 3.0, size=9, weight=800, fade=(0.6, 0.6), shadowColor="#000000", shadowBlur=18, shadowY=4)
    slots = _slots(*[(f"photo{i + 1}", f"Photo {i + 1}", f"photo{i + 1}", "image") for i in range(5)])
    return {"project": _project("Photo slideshow", 15, [[title], photos]), "slots": slots}


def _quote_card() -> dict:
    mark = _text("\u201c", 0.3, 5.4, size=22, color="#ffc83d", y=-24, weight=800, fade=(0.5, 0.5))
    quote = _text(
        "Write the words you want\npeople to remember here.",
        0.6,
        5.0,
        size=6.4,
        weight=600,
        lineHeight=1.2,
        wrapWidth=72,
        fade=(0.8, 0.6),
        keys=[_key(0, "easeOut", posY=4, opacity=0), _key(0.9, "easeOut", posY=0, opacity=100)],
    )
    author = _text("Name of the speaker", 1.6, 4.0, size=3.0, weight=500, y=20, color="#b8b8c2", letterSpacing=4, fade=(0.6, 0.6))
    return {"project": _project("Quote card", 6, [[mark, quote, author]], background="#15161b"), "slots": []}


def _countdown() -> dict:
    numbers = [
        _text(
            str(5 - i),
            float(i),
            1.0,
            size=34,
            weight=900,
            fade=(0.05, 0.25),
            color=("#ffc83d" if i == 4 else "#ffffff"),
            keys=[_key(0, "overshoot", scale=55), _key(0.35, "easeOut", scale=100)],
        )
        for i in range(5)
    ]
    return {"project": _project("Countdown", 5, [numbers], background="#101116"), "slots": []}


def _split_screen() -> dict:
    left = _media("left", "video", 0, 8, scale=49, x=-25)
    right = _media("right", "video", 0, 8, scale=49, x=25)
    labels = [
        _text("Left", 0.4, 7.2, size=3.2, weight=700, x=-25, y=-33, fade=(0.4, 0.4), **PLATE),
        _text("Right", 0.4, 7.2, size=3.2, weight=700, x=25, y=-33, fade=(0.4, 0.4), **PLATE),
    ]
    slots = _slots(("left", "Left", "left", "video"), ("right", "Right", "right", "video"))
    return {"project": _project("Split screen", 8, [labels, [left, right]], background="#0b0c10"), "slots": slots}


def _before_after() -> dict:
    before = _media("before", "image", 0, 3.4)
    after = _media("after", "image", 3.0, 3.0, transition=("wipe-right", 1.0))
    corner = _left(5, 30)
    labels = [
        _text("BEFORE", 0.3, 2.8, size=3.4, weight=800, y=-38, letterSpacing=6, fade=(0.3, 0.3), **PLATE, **corner),
        _text("AFTER", 4.0, 1.8, size=3.4, weight=800, y=-38, letterSpacing=6, color="#ffc83d", fade=(0.3, 0.3), **PLATE, **corner),
    ]
    slots = _slots(("before", "Before", "before", "image"), ("after", "After", "after", "image"))
    return {"project": _project("Before and after", 6, [labels, [before, after]]), "slots": slots}


def _product_showcase() -> dict:
    photo = _media(
        "product",
        "image",
        0,
        8,
        scale=56,
        x=-25,
        keys=[_key(0, "overshoot", scale=36, opacity=0), _key(0.7, "easeOut", scale=56, opacity=100)],
    )
    column = _left(58, 38)
    features = [
        _text(
            line,
            1.4 + i * 0.7,
            6.6 - i * 0.7,
            size=3.8,
            weight=600,
            y=-8 + i * 9,
            fade=(0.3, 0.5),
            **column,
            keys=[_key(0, "easeOut", posX=column["x"] + 8, opacity=0), _key(0.5, "easeOut", posX=column["x"], opacity=100)],
        )
        for i, line in enumerate(("First thing it does well", "Second reason to want it", "One more good detail"))
    ]
    name = _text("Product name", 0.6, 7.4, size=6.6, weight=800, y=-24, fade=(0.4, 0.5), **column)
    price = _text(
        "$00",
        3.6,
        4.4,
        size=6.0,
        weight=900,
        x=24,
        y=28,
        fade=(0.2, 0.5),
        plateColor="#ff5a5f",
        plateOpacity=1,
        platePadding=22,
        plateRadius=40,
        keys=[_key(0, "overshoot", scale=60), _key(0.4, "easeOut", scale=100)],
    )
    return {
        "project": _project("Product showcase", 8, [[name, *features, price], [photo]], background="#101218"),
        "slots": _slots(("product", "Product photo", "product", "image")),
    }


def _vertical_short() -> dict:
    video = _media("video", "video", 0, 10, scale=320)
    headline = _text("Say what this is about", 0.3, 9.4, size=4.4, weight=800, y=-34, wrapWidth=80, fade=(0.3, 0.3), **PLATE)
    follow = _text(
        "Follow for more",
        7.4,
        2.6,
        size=3.6,
        weight=700,
        y=36,
        color="#0d0e12",
        fade=(0.3, 0.3),
        plateColor="#ffc83d",
        plateOpacity=1,
        platePadding=20,
        plateRadius=30,
        keys=[_key(0, "overshoot", scale=70), _key(0.4, "easeOut", scale=100)],
    )
    return {
        "project": _project("Vertical short", 10, [[headline, follow], [video]], width=1080, height=1920),
        "slots": _slots(("video", "Video", "video", "video")),
    }


def _travel_opener() -> dict:
    clips = [
        _media(
            f"clip{i + 1}",
            "video",
            i * 2.6,
            3.0 if i < 2 else 2.8,
            transition=(("slide-left", 0.4) if i == 1 else ("zoom", 0.4)) if i else None,
            fade=(0.4 if i == 0 else 0, 0.8 if i == 2 else 0),
        )
        for i in range(3)
    ]
    place = _text(
        "PLACE NAME",
        1.0,
        6.2,
        size=11,
        weight=900,
        letterSpacing=30,
        fade=(0.6, 0.8),
        shadowColor="#000000",
        shadowBlur=24,
        keys=[_key(0, "easeOut", scale=108, opacity=0), _key(1.0, "easeOut", scale=100, opacity=100)],
    )
    day = _text("Day one", 2.0, 5.0, size=3.4, weight=500, y=12, letterSpacing=10, color="#ffe9b8", fade=(0.6, 0.8))
    slots = _slots(*[(f"clip{i + 1}", f"Clip {i + 1}", f"clip{i + 1}", "video") for i in range(3)])
    return {"project": _project("Travel opener", 8, [[place, day], clips]), "slots": slots}


def _breaking_news() -> dict:
    video = _media("video", "video", 0, 8)
    tag = _text(
        "BREAKING",
        0.4,
        7.6,
        size=3.2,
        weight=900,
        y=26,
        letterSpacing=4,
        fade=(0.2, 0.3),
        **_left(4, 30),
        plateColor="#e5282e",
        plateOpacity=1,
        platePadding=14,
        plateRadius=4,
    )
    head = _left(4, 70)
    headline = _text(
        "Write the headline here",
        0.6,
        7.4,
        size=4.6,
        weight=800,
        y=34,
        color="#111111",
        fade=(0.2, 0.3),
        **head,
        plateColor="#ffffff",
        plateOpacity=1,
        platePadding=16,
        plateRadius=4,
        keys=[_key(0, "easeOut", posX=head["x"] - 30), _key(0.5, "easeOut", posX=head["x"])],
    )
    ticker = _text(
        "More news runs along the bottom of the screen \u2022 Add your own lines here \u2022 formcut",
        0.0,
        8.0,
        size=3.0,
        weight=600,
        y=44,
        fade=(0.2, 0.2),
        plateColor="#0d0e12",
        plateOpacity=0.9,
        platePadding=10,
        plateRadius=0,
        keys=[_key(0, "linear", posX=70), _key(8, "linear", posX=-70)],
    )
    return {
        "project": _project("Breaking news", 8, [[tag, headline, ticker], [video]]),
        "slots": _slots(("video", "Video", "video", "video")),
    }


def _end_screen() -> dict:
    thanks = _text("Thanks for watching", 0.4, 9.2, size=6.6, weight=800, y=-30, fade=(0.5, 0.6))
    watch = _text("Watch next", 1.0, 8.6, size=3.2, weight=600, y=-18, color="#ffc83d", letterSpacing=6, fade=(0.5, 0.6))
    tiles = [
        _media(
            f"next{i + 1}",
            "video",
            0.6 + i * 0.3,
            9.4 - i * 0.3,
            scale=38,
            x=(-24 if i == 0 else 24),
            y=10,
            fade=(0.5, 0.6),
            keys=[_key(0, "overshoot", scale=24), _key(0.6, "easeOut", scale=38)],
        )
        for i in range(2)
    ]
    slots = _slots(("next1", "Next video 1", "next1", "video"), ("next2", "Next video 2", "next2", "video"))
    return {"project": _project("End screen", 10, [[thanks, watch], tiles], background="#0f1015"), "slots": slots}


BUILDERS = {
    "libcinematicintro": ("Cinematic intro", _cinematic_intro),
    "liblowerthird": ("Lower third", _lower_third),
    "libphotoslideshow": ("Photo slideshow", _photo_slideshow),
    "libquotecard": ("Quote card", _quote_card),
    "libcountdown": ("Countdown", _countdown),
    "libsplitscreen": ("Split screen", _split_screen),
    "libbeforeafter": ("Before and after", _before_after),
    "libproductshowcase": ("Product showcase", _product_showcase),
    "libverticalshort": ("Vertical short", _vertical_short),
    "libtravelopener": ("Travel opener", _travel_opener),
    "libbreakingnews": ("Breaking news", _breaking_news),
    "libendscreen": ("End screen", _end_screen),
}


def template(template_id: str) -> dict | None:
    """A fresh copy of a built-in template, or None if there is no such template."""
    found = BUILDERS.get(template_id)
    if not found:
        return None
    name, build = found
    item = build()
    return {
        "formcut_template": 1,
        "id": template_id,
        "name": name,
        "nameKey": f"tpl.{template_id}",
        "bundled": True,
        "assets": [],
        **copy.deepcopy(item),
    }


def listing() -> list[dict]:
    return [
        {k: item[k] for k in ("id", "name", "nameKey", "slots", "bundled")} for item in (template(template_id) for template_id in BUILDERS)
    ]
