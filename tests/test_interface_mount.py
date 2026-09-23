"""The desktop app serves its interface from the engine (FORMCUT_DIST), mounted at "/".

A mount at "/" matches every path, and routes match in the order they are added,
so a route declared after the mount could never be reached there. Routes on the
app itself answered 404, 403 or 405 in the desktop app while working in
development, where Vite serves the interface instead.
"""

import os
import re
import subprocess
import sys

from conftest import ROOT

MAIN = ROOT / "backend" / "app" / "main.py"


def test_the_interface_is_mounted_after_every_route():
    lines = MAIN.read_text(encoding="utf-8").splitlines()
    mount = max(i for i, line in enumerate(lines) if 'app.mount("/"' in line)
    routes = [i for i, line in enumerate(lines) if re.match(r"@app\.(get|post|put|delete|patch|websocket)\(|app\.include_router\(", line)]
    assert routes and max(routes) < mount


def test_with_the_interface_mounted_the_apps_own_routes_answer(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>formcut</title>", encoding="utf-8")
    script = """
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
print(client.get("/api/packages").status_code, client.get("/api/locales").status_code,
      client.get("/api/diagnostics").status_code, client.get("/").status_code)
"""
    env = {**os.environ, "FORMCUT_DIST": str(tmp_path), "FORMCUT_DATA_DIR": str(tmp_path / "data")}
    run = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT / "backend", env=env, capture_output=True, text=True, timeout=120, check=True
    )
    assert run.stdout.split()[-4:] == ["200", "200", "200", "200"], run.stdout + run.stderr[-800:]
