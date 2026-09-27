#!/usr/bin/env python3
"""List a package in formcut's community registry (.docs/registry/effects-registry.json).

    python setup/registry_entry.py night-bus-by-ana.zip --description "White words, the spoken one rising in teal."
    python setup/registry_entry.py night-bus-by-ana.zip --add     # also copy the zip in and write the entry

The zip is what Share this look saves (or any package zip). It is checked the way formcut's installer checks a
package (effect_packages.load_package), its SHA-256 taken, and its entry printed: id, name, kind, author, description,
the raw GitHub URL it will have once merged, and the hash. With --add the zip is copied to .docs/registry/packages/
and the entry appended to the index; then open a pull request with both.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / ".docs" / "registry"
INDEX = REGISTRY / "effects-registry.json"
RAW = "https://raw.githubusercontent.com/nodemode-ai/formcut/main/.docs/registry/packages/"


def entry_for(data: bytes, description: str = "") -> dict:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.effect_packages import load_package

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        load_package(Path(folder))  # raises ValueError with the reason when formcut would refuse it
    return {
        "id": manifest["id"],
        "name": manifest["name"],
        "kind": manifest["kind"],
        "author": str(manifest.get("author") or "").strip() or "unknown",
        "description": description.strip() or manifest["name"],
        "url": RAW + f"{manifest['id']}.zip",
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--description", default="")
    parser.add_argument("--add", action="store_true", help="copy the zip into the registry and write its entry")
    args = parser.parse_args(argv)
    data = args.zip.read_bytes()
    try:
        entry = entry_for(data, args.description)
    except (ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"formcut would not install this package: {exc}", file=sys.stderr)
        return 1
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    if any(existing["id"] == entry["id"] for existing in index["packages"]):
        print(f"the registry already lists {entry['id']}; choose another name", file=sys.stderr)
        return 1
    print(json.dumps(entry, indent=1))
    if args.add:
        (REGISTRY / "packages" / f"{entry['id']}.zip").write_bytes(data)
        index["packages"].append(entry)
        INDEX.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"added: .docs/registry/packages/{entry['id']}.zip and its entry; open a pull request with both")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
