import base64;
import io

from fastapi import UploadFile

from .assets import ShaderInput, asset_path, upload_lut, upload_shader
from .fonts import upload_font


def gather(project: dict):
    found = {}
    for timeline in project['timelines']:
        for track in timeline['tracks']:
            for clip in track['clips']:
                for holder, field, suffix in [(clip, 'lutId', '.cube'), (clip, 'shaderId', '.wgsl'), (clip.get('textStyle') or {}, 'fontId', '.font')]:
                    key = holder.get(field)
                    if key and key not in found:
                        path = asset_path(key, suffix)
                        found[key] = {'type': field, 'source': base64.b64encode(path.read_bytes()).decode() if suffix == '.font' else path.read_text()}
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
        elif asset['type'] == 'shaderId':
            result = upload_shader(ShaderInput(name='Template shader', source=source))
        else:
            raise ValueError('Unknown template asset')
        replacements[key] = result['id']
    for timeline in item['project']['timelines']:
        for track in timeline['tracks']:
            for clip in track['clips']:
                for holder, field in [(clip, 'lutId'), (clip, 'shaderId'), (clip.get('textStyle') or {}, 'fontId')]:
                    if holder.get(field) in replacements:
                        holder[field] = replacements[holder[field]]
    item['assets'] = {replacements[key]: value for key, value in assets.items()}
