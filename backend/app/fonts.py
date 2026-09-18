import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from PIL import ImageFont

from .assets import ROOT, asset_path

router = APIRouter(prefix='/api/assets', tags=['assets'])


@router.post('/font', status_code=201)
def upload_font(file: UploadFile):
    raw = file.file.read(32_000_001)
    if len(raw) > 32_000_000:
        raise HTTPException(413, 'Font exceeds 32 MB')
    ROOT.mkdir(parents=True, exist_ok=True)
    key = uuid.uuid4().hex
    path = ROOT / (key + '.font')
    path.write_bytes(raw)
    try:
        font = ImageFont.truetype(str(path), 20)
        family = font.getname()[0]
    except OSError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(422, 'This font cannot be loaded') from exc
    result = {'id': key, 'kind': 'font', 'name': family}
    (ROOT / (key + '.json')).write_text(json.dumps(result))
    return result


def title_font(style, size):
    if style.get('fontId'):
        return ImageFont.truetype(str(asset_path(style['fontId'], '.font')), size)
    text = str(style.get('content', ''))
    candidates = [os.environ.get('FORMCUT_FONT_PATH', '')]
    if any(ord(char) > 0x2e80 for char in text):
        candidates.extend(['/System/Library/Fonts/PingFang.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'msyh.ttc')])
    candidates.append('DejaVuSans-Bold.ttf' if style.get('bold', True) else 'DejaVuSans.ttf')
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)
