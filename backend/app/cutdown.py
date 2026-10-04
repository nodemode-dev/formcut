"""The cutdown planner: scripts of a target length cut from a master's mix, with their exact source segments.

From the owner's Posh cutdowns, whose hand-made solver found the delivered four :15 and three :30 scripts. A script is
units (source ranges holding whole sentences) in source order: each join an out-point and an in-point a whole number
of bars apart, both outside speech, the pause it leaves between the voices natural (0.2 to 1.3 s, plus any music
bridge the join passes through, such as an end-card wipe); the last unit the closing call to action, ending on the
music's button; the length exact. Editorial proxies a planner can apply: every unit holds a whole sentence; the first
opens the film or opens on a sentence that does not lean on what came before; scripts that say the same thing count
once. What a person still judges (is this a story, does the picture fit) the cutdown skill says.
"""

import itertools

# an opener whose first word is one of these leans on what came before it
LEANING = {"that's", "plus", "and", "but", "so", "also", "then", "this", "these", "those", "it", "they", "everything"}
LEANING |= {"which", "save", "seven", "to"}
PAUSE = (0.2, 1.3)
TOLERANCE = 0.03


def _boundaries(sentences: list[dict], zones: list[list[float]], final_hit: float) -> tuple[list, list, float]:
    """(zones where a unit may end or start, the closing call to action's start, ...): a safe zone holding a sentence
    end; inside the call to action a comma clause too."""
    long_quiet = [z for z in zones if z[1] - z[0] >= 0.8 and 1.0 < z[0] < final_hit - 1.0]
    cta = long_quiet[-1][0] if long_quiet else final_hit
    ends = [s["end"] for s in sentences if s["text"].rstrip().endswith((".", "!", "?"))]
    commas = []
    for s in sentences:
        for i, ch in enumerate(s["text"]):
            if ch == "," and s["start"] >= cta - 0.5:
                commas.append(s["start"] + (s["end"] - s["start"]) * (i + 1) / max(1, len(s["text"])))
    marks = [(t, 0.5) for t in ends] + [(t, 0.8) for t in commas]
    inner = [z for z in zones if z[0] > 0.2 and z[1] < final_hit and any(z[0] - reach <= t <= z[1] + 0.8 for t, reach in marks)]
    return inner, ends, cta


def _said(sentences: list[dict], a: float, b: float) -> list[tuple[int, float]]:
    """A unit's content: each sentence overlapping a to b by more than 0.3 s, with the share of it inside (1.0 whole)."""
    content = []
    for i, s in enumerate(sentences):
        inside = min(b, s["end"]) - max(a, s["start"])
        if inside > 0.3:
            content.append((i, round(min(1.0, inside / max(1e-6, s["end"] - s["start"]) + 0.15), 1)))
    return content


def _opens(sentences: list[dict], zone: list[float], start_zone: list[float]) -> bool:
    if zone is start_zone:
        return True
    following = [s for s in sentences if s["start"] >= zone[0] - 0.4]
    words = following[0]["text"].strip().lower().split() if following else []
    return bool(words) and words[0].strip(",.;:!?") not in LEANING


def _join(a_zone: list[float], b_zone: list[float], bar: float) -> list[tuple[int, float]]:
    """(bars, pause) for each whole number of bars that joins an out-point in a_zone to an in-point in b_zone with a
    natural pause; a long b_zone (music before the voice, a wipe) may hold that much more silence."""
    out = []
    bridge = max(0.0, (b_zone[1] - b_zone[0]) - 0.3) if b_zone[1] - b_zone[0] >= 0.8 else 0.0
    for m in range(max(1, int((b_zone[0] - a_zone[1]) // bar) - 1), int((b_zone[1] - a_zone[0]) // bar) + 2):
        reachable = b_zone[0] - a_zone[1] - TOLERANCE <= m * bar <= b_zone[1] - a_zone[0] + TOLERANCE
        pause = b_zone[1] - a_zone[0] - m * bar
        if reachable and PAUSE[0] <= pause <= PAUSE[1] + bridge:
            out.append((m, round(pause, 3)))
    return out


def plan(sentences: list[dict], zones: list[list[float]], music: dict, target: float, most_units: int = 4, top: int = 10) -> list[dict]:
    """Scripts of target seconds, ranked: the most natural pauses first, then those opening the film, then fewer units."""
    bar, hit, end = music["bar"], music["final_hit"] or music["duration"], music["duration"]
    if not zones or not sentences:
        return []
    start_zone, end_zone = zones[0], max((z for z in zones if z[1] >= hit), key=lambda z: z[1] - z[0], default=zones[-1])
    inner, ends, cta = _boundaries(sentences, zones, hit)
    openers = [start_zone] + [z for z in inner if z[1] < cta and _opens(sentences, z, start_zone)]
    found: dict[tuple, dict] = {}

    def finish(first, steps):
        jumps = sum(m for _, _, m, _ in steps) * bar
        first_in_lo, first_in_hi = max(first[0], first[1] - 0.6), first[1]
        last_out_lo, last_out_hi = max(hit + 1.0, end_zone[0]), end
        lo, hi = last_out_lo - first_in_hi - jumps, last_out_hi - first_in_lo - jumps
        if not lo - 1 / 48 <= target <= hi + 1 / 48:
            return
        first_in = max(first_in_lo, min(first_in_hi, last_out_lo - jumps - target))
        units, previous_in = [], first_in
        for out_zone, in_zone, m, _ in steps:
            low, high = max(out_zone[0], in_zone[0] - m * bar), min(out_zone[1], in_zone[1] - m * bar)
            out = (low + high) / 2
            units.append([round(previous_in, 3), round(out, 3)])
            previous_in = out + m * bar
        units.append([round(previous_in, 3), round(first_in + target + jumps, 3)])
        if any(b - a < 0.5 for a, b in units):
            return
        content = tuple(part for a, b in units for part in _said(sentences, a, b))
        pauses = [p for _, _, _, p in steps]
        score = sum(abs(p - 0.5) for p in pauses) + (0.0 if first is start_zone else 0.3) + 0.2 * len(steps)
        words = [("" if share >= 1.0 else "...") + sentences[i]["text"] for i, share in content]
        script = {"units": units, "bars": [m for _, _, m, _ in steps], "pauses": pauses, "score": round(score, 3), "text": words}
        if content not in found or score < found[content]["score"]:
            found[content] = script

    def extend(first, steps, last_in):
        # a script may finish when its last unit runs into the button from the call to action (or is the only unit)
        if (not steps and first is start_zone) or (steps and last_in[0] >= cta - 0.5):
            finish(first, steps)
        if len(steps) + 1 >= most_units:
            return
        for out_zone in inner:
            # a unit holds at least one whole sentence, or is a music-only bridge inside one long quiet zone of the
            # call to action (the Posh end-card wipe, 60.515 to 61.555)
            bridge = bool(steps) and out_zone is last_in and out_zone[1] - out_zone[0] >= 0.8 and out_zone[0] >= cta - 0.5
            if not bridge and (out_zone[0] <= last_in[1] or not any(last_in[1] - 0.4 <= t <= out_zone[1] + 0.8 for t in ends)):
                continue
            for in_zone in inner:
                if in_zone[0] <= out_zone[1]:
                    continue
                for m, pause in sorted(_join(out_zone, in_zone, bar), key=lambda option: abs(option[1] - 0.5)):
                    extend(first, [*steps, (out_zone, in_zone, m, pause)], in_zone)

    for first in openers:
        extend(first, [], first)
    return sorted(found.values(), key=lambda s: s["score"])[:top]


def joins_by_hand(script_units: list[list[float]], bar: float) -> list[float]:
    """How far each join of a given script is from a whole number of bars (seconds), for checking a script by hand."""
    return [round(((b0 - a1) / bar - round((b0 - a1) / bar)) * bar, 3) for (_, a1), (b0, _) in itertools.pairwise(script_units)]
