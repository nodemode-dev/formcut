import math

from .catalogue import AUDIO_CHAINS, GRADES, TRANSITIONS, VIDEO_EFFECTS


def number(value, name, low=-100000, high=100000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Invalid ' + name)


def clip_values(clip):
    for name, low, high in [('sourceIn', 0, 86400), ('speed', 0.05, 16), ('volume', 0, 4), ('pan', -1, 1), ('fadeIn', 0, 86400), ('fadeOut', 0, 86400)]:
        if clip.get(name) is not None:
            number(clip[name], name, low, high)
    for point in clip.get('speedCurve') or []:
        number(point['t'], 'curve time', 0, 86400)
        number(point['speed'], 'curve speed', 0.05, 16)
    transform = clip.get('transform') or {}
    for prop in ('posX', 'posY', 'scale', 'rotation', 'opacity', 'width', 'height'):
        if prop in transform:
            number(transform[prop], prop)
    frames = clip.get('keyframes') or []
    if len(frames) > 20000:
        raise ValueError('Too many keyframes')
    for frame in frames:
        number(frame['t'], 'keyframe time', -86400, 86400)
        if frame.get('interp', 'linear') not in ('linear', 'hold', 'ease', 'easeIn', 'easeOut'):
            raise ValueError('Unknown interpolation')
        for key, value in frame.get('props', {}).items():
            if key not in ('posX', 'posY', 'scale', 'rotation', 'opacity'):
                raise ValueError('Unknown animated property')
            number(value, key)
    for field, allowed in [('effects', set(GRADES) | set(VIDEO_EFFECTS)), ('audioEffects', set(AUDIO_CHAINS))]:
        entries = clip.get(field) or []
        if len(entries) > 32:
            raise ValueError('Too many processors')
        for entry in entries:
            if entry.get('id') not in allowed:
                raise ValueError('Unknown processor')
            number(entry.get('amount', 1), 'processor amount', 0, 1)
            for key, value in (entry.get('params') or {}).items():
                number(value, key, -100, 100)
    transition = clip.get('transitionIn')
    if transition:
        if transition.get('type') not in TRANSITIONS:
            raise ValueError('Unknown transition')
        number(transition.get('duration', 0.5), 'transition duration', 0.01, 86400)
    cutout = clip.get('cutout')
    if cutout:
        if cutout.get('model') not in ('object-cutout', 'person-cutout'):
            raise ValueError('Unknown cutout model')
        number(cutout.get('threshold', 0.5), 'cutout threshold', 0, 1)
        number(cutout.get('feather', 0.1), 'cutout feather', 0.005, 0.5)
        for stroke in cutout.get('strokes', []):
            if stroke.get('mode') not in ('keep', 'erase'):
                raise ValueError('Invalid brush mode')
            number(stroke.get('radius', 0.02), 'brush radius', 0.001, 1)
            for point in stroke.get('points', []):
                if len(point) != 2:
                    raise ValueError('Invalid brush point')
                for coordinate in point:
                    number(coordinate, 'brush coordinate', -10, 10)
