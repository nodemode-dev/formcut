import hashlib
import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from PIL import ImageFont

from .assets import ROOT, asset_path

router = APIRouter(prefix='/api/assets', tags=['assets'])


def install_font(raw: bytes) -> dict:
    """Install a font file keyed by its content hash; a second import adds nothing."""
    if len(raw) > 32_000_000:
        raise HTTPException(413, 'Font exceeds 32 MB')
    ROOT.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(raw).hexdigest()[:32]
    record = ROOT / (key + '.json')
    path = ROOT / (key + '.font')
    if record.is_file() and path.is_file():
        existing = json.loads(record.read_text())
        existing['installed'] = False
        return existing
    path.write_bytes(raw)
    try:
        font = ImageFont.truetype(str(path), 20)
        family = font.getname()[0]
    except OSError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(422, 'This font cannot be loaded') from exc
    result = {'id': key, 'kind': 'font', 'name': family}
    record.write_text(json.dumps(result))
    return {**result, 'installed': True}


@router.post('/font', status_code=201)
def upload_font(file: UploadFile):
    return install_font(file.file.read(32_000_001))


def _legacy_upload_font(file: UploadFile):
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
    # weight and italic pick a face; bold keeps its original meaning when neither is set
    heavy = style.get('weight') is not None and int(style['weight']) >= 600 or style.get('weight') is None and style.get('bold', True)
    italic = bool(style.get('italic'))
    faces = []
    if heavy and italic:
        faces.append('DejaVuSans-BoldOblique.ttf')
    elif italic:
        faces.append('DejaVuSans-Oblique.ttf')
    faces.append('DejaVuSans-Bold.ttf' if heavy else 'DejaVuSans.ttf')
    candidates.extend(faces)
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)
