import base64;
import io

from fastapi import UploadFile

from .assets import ShaderInput, asset_path, upload_lut, upload_shader
from .fonts import upload_font
from .media import MEDIA_DIR, ingest_path


def gather(project: dict):
    """Assets a template carries: fonts, LUTs, shaders, and fixed media.

    P4 adds the last of those. A clip that is not a slot is part of the
    template's design rather than something the person fills in, so its media
    (music, an overlay, a logo) must travel with the file or the template opens
    incomplete in an empty data directory.
    """
    found = {}
    for timeline in project['timelines']:
        for track in timeline['tracks']:
            for clip in track['clips']:
                for holder, field, suffix in [(clip, 'lutId', '.cube'), (clip, 'shaderId', '.wgsl'), (clip.get('textStyle') or {}, 'fontId', '.font')]:
                    key = holder.get(field)
                    if key and key not in found:
                        path = asset_path(key, suffix)
                        found[key] = {'type': field, 'source': base64.b64encode(path.read_bytes()).decode() if suffix == '.font' else path.read_text()}
    for timeline in project['timelines']:
        for track in timeline['tracks']:
            for clip in track['clips']:
                media_id = clip.get('mediaId')
                if not media_id or clip.get('templateSlot') or media_id in found:
                    continue
                matches = list(MEDIA_DIR.glob(f'{media_id}.*'))
                if not matches:
                    continue
                raw = matches[0].read_bytes()
                if len(raw) > 64_000_000:
                    # A template is a file people send each other; very large
                    # fixed media is left as a reference rather than bundled.
                    continue
                found[media_id] = {'type': 'mediaId', 'suffix': matches[0].suffix,
                                   'name': clip.get('label', 'Template media'),
                                   'source': base64.b64encode(raw).decode()}
    return found


def restore(item: dict):
    assets = item.get('assets', {})
    if not isinstance(assets, dict) or len(assets) > 128:
        raise ValueError('Invalid template assets')
    replacements = {}
    for key, asset in assets.items():
        source = asset['source']
        if not isinstance(source, str):
            raise ValueError('Asset source must be text')
        if asset['type'] == 'fontId':
            result = upload_font(UploadFile(filename='Template font.ttf', file=io.BytesIO(base64.b64decode(source, validate=True))))
        elif asset['type'] == 'lutId':
            result = upload_lut(UploadFile(filename='Template color.cube', file=io.BytesIO(source.encode())))
        elif asset['type'] == 'mediaId':
            staged = MEDIA_DIR.parent / ('template-' + key + asset.get('suffix', '.bin'))
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(base64.b64decode(source, validate=True))
            try:
                result = ingest_path(staged, asset.get('name', 'Template media'), extra={'source': 'template'})
            finally:
                staged.unlink(missing_ok=True)
        elif asset['type'] == 'shaderId':
            result = upload_shader(ShaderInput(name='Template shader', source=source))
        else:
            raise ValueError('Unknown template asset')
        replacements[key] = result['id']
    for timeline in item['project']['timelines']:
        for track in timeline['tracks']:
            for clip in track['clips']:
                # mediaId joins the rewritten fields: bundled fixed media is
                # ingested under a new id, so the clip must point at that one.
                for holder, field in [(clip, 'lutId'), (clip, 'shaderId'), (clip, 'mediaId'), (clip.get('textStyle') or {}, 'fontId')]:
                    if holder.get(field) in replacements:
                        holder[field] = replacements[holder[field]]
    item['assets'] = {replacements[key]: value for key, value in assets.items()}
