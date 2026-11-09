"""Write the browser demos' media into the app's interface, so the app opens each demo itself.

The demos in demo/ and demos/<name>/ carry their media as base64 JavaScript packs (file:// pages
cannot fetch files). This decodes each pack named in a demo's film.js manifest to
frontend/public/demos/<id>/<media id>.<ext>, with the manifest's first thumbnail as poster.jpg,
and writes manifest.json beside them. Vite copies frontend/public into the built interface.

    python3 scripts/extract_demo_media.py
"""

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMOS = {"edit": ROOT / "demo", "grade": ROOT / "demos" / "grade", "deliver": ROOT / "demos" / "deliver"}
EXT = {"video/mp4": ".mp4", "audio/mpeg": ".mp3", "audio/wav": ".wav", "image/jpeg": ".jpg", "image/png": ".png"}


def _payload(text: str) -> str:
    start = text.index("=", text.index("]") if text.startswith("(") else 0) + 1
    return text[start:].strip().rstrip(";").strip()


def extract(demo_id: str, folder: Path, out_root: Path) -> list[dict]:
    media = folder / "assets" / "media"
    manifest = json.loads(_payload((media / "film.js").read_text(encoding="utf-8")))
    out = out_root / demo_id
    out.mkdir(parents=True, exist_ok=True)
    items = []
    for item in manifest["items"]:
        ext = EXT[item["mime"]]
        packed = json.loads(_payload((media / f"{item['pack']}.js").read_text(encoding="utf-8")))
        name = f"{item['id']}{ext}"
        (out / name).write_bytes(base64.b64decode(packed))
        items.append({"id": item["id"], "name": item["name"], "kind": item["kind"], "file": name})
    thumb = next((item.get("thumb") for item in manifest["items"] if item.get("thumb")), None)
    if thumb:
        (out / "poster.jpg").write_bytes(base64.b64decode(thumb.split(",", 1)[1]))
    (out / "manifest.json").write_text(json.dumps({"items": items}, indent=1) + "\n", encoding="utf-8")
    return items


def main() -> None:
    out_root = ROOT / "frontend" / "public" / "demos"
    for demo_id, folder in DEMOS.items():
        items = extract(demo_id, folder, out_root)
        size = sum((out_root / demo_id / item["file"]).stat().st_size for item in items)
        print(f"{demo_id}: {len(items)} files, {size / 1e6:.1f} MB", file=sys.stderr)


if __name__ == "__main__":
    main()
