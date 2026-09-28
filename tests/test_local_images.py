"""Local image models, v2.0.7 and v2.0.8: a real progress bar (the model's own steps), a cancel that ends the model's process,
memory planned for the machine, LoRA stacks with strengths, FLUX.2 [klein] 4B and 9B, and a terminal that is not
flooded by the page asking after a job."""

from __future__ import annotations

import json
import logging
import struct
import sys
import threading
import time

import pytest
from app import klein, local_runner, loras
from app.main import app
from fastapi.testclient import TestClient

STEPS_SCRIPT = r"""
import sys, time
sys.stderr.write("Loading weights\n"); sys.stderr.flush(); time.sleep(0.3)
for k in range(5):
    sys.stderr.write(f"\r {k * 25}%|##  | {k}/4 [00:0{k}<00:04, 1.0it/s]"); sys.stderr.flush(); time.sleep(0.05)
sys.stderr.write("\n")
"""


def test_the_runner_turns_the_models_steps_into_progress():
    seen = []
    local_runner.run([sys.executable, "-c", STEPS_SCRIPT], 4, lambda v, m=None: seen.append((v, m)), lambda: False, "Stand-in")
    messages = [m for _, m in seen]
    assert messages[0] == "Loading Stand-in" and "Step 2 of 4" in messages and messages[-1] == "Finishing the picture"
    assert [v for v, _ in seen] == sorted(v for v, _ in seen)


def test_a_cancel_ends_the_models_process_and_a_failure_brings_its_output():
    stop = threading.Event()
    threading.Timer(0.4, stop.set).start()
    started = time.time()
    with pytest.raises(InterruptedError):
        local_runner.run([sys.executable, "-c", "import time; time.sleep(30)"], 4, lambda *a: None, stop.is_set, "Stand-in")
    assert time.time() - started < 8
    with pytest.raises(RuntimeError, match="out of memory"):
        local_runner.run(
            [sys.executable, "-c", "import sys; sys.stderr.write('out of memory'); sys.exit(2)"],
            4,
            lambda *a: None,
            lambda: False,
            "Stand-in",
        )


def test_memory_is_planned_for_the_machine(monkeypatch):
    monkeypatch.setattr(local_runner, "total_memory", lambda: 32 * 10**9)
    assert not local_runner.plan(8 * 10**9)["lowRam"] and local_runner.plan(22 * 10**9)["lowRam"]
    assert local_runner.plan(8 * 10**9, "low")["lowRam"] and not local_runner.plan(22 * 10**9, "normal")["lowRam"]
    flags = local_runner.mflux_memory_flags(local_runner.plan(22 * 10**9))
    assert flags[0] == "--low-ram" and flags[1:] == ["--mlx-cache-limit-gb", "3.2"]


def _safetensors(path, names, metadata=None):
    header = {name: {"dtype": "F32", "shape": [1], "data_offsets": [4 * i, 4 * i + 4]} for i, name in enumerate(names)}
    if metadata:
        header["__metadata__"] = metadata
    raw = json.dumps(header).encode()
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + b"\0" * 4 * len(names))
    return path


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(loras, "LIBRARY", tmp_path / "loras")
    return tmp_path


def test_the_library_takes_loras_and_lokr_and_refuses_the_rest(library):
    good = _safetensors(
        library / "a.safetensors",
        ["transformer.blocks.0.attn.to_q.lora_A.weight", "transformer.blocks.0.attn.to_q.lora_B.weight"],
        {"trigger_words": "neondrip"},
    )
    entry = loras.add(good, "Neon drip", "krea-2", "file")
    assert entry["format"] == "LoRA" and entry["triggers"] == "neondrip" and entry["base"] == "krea-2"
    lokr = _safetensors(library / "b.safetensors", ["lycoris_x.lokr_w1", "lycoris_x.lokr_w2"])
    assert loras.add(lokr, "Kr", "flux2-klein-4b", "file")["format"] == "LoKr"
    for names, reason in ((["x.lora_A.weight", "x.lora_magnitude_vector"], "DoRA"), (["model.weight"], "no LoRA")):
        with pytest.raises(ValueError, match=reason):
            loras.add(_safetensors(library / "c.safetensors", names), "x", "krea-2", "file")
    (library / "d.safetensors").write_bytes(b"not at all")
    with pytest.raises(ValueError, match="safetensors"):
        loras.add(library / "d.safetensors", "x", "krea-2", "file")


def test_a_stack_resolves_to_paths_and_strengths_for_its_own_model(library):
    one = loras.add(_safetensors(library / "a.safetensors", ["a.lora_A.weight", "a.lora_B.weight"]), "One", "flux2-klein-4b", "file")
    two = loras.add(_safetensors(library / "b.safetensors", ["b.lora_down.weight", "b.lora_up.weight"]), "Two", "flux2-klein-4b", "file")
    pairs = loras.resolve(
        [{"id": one["id"], "scale": 0.7}, {"id": two["id"], "scale": 5}, {"id": one["id"], "scale": 1, "enabled": False}], "flux2-klein-4b"
    )
    assert [s for _, s in pairs] == [0.7, 2.0] and pairs[0][0].endswith("flux2-klein-4b/One.safetensors")
    assert loras.mflux_flags(pairs)[0] == "--lora-paths" and loras.mflux_flags(pairs)[-2:] == ["0.7", "2"]
    with pytest.raises(ValueError, match=r"made for FLUX\.2 \[klein\] 4B, not Krea 2"):
        loras.resolve([{"id": one["id"], "scale": 1}], "krea-2")


def test_the_lora_api_imports_lists_edits_and_removes(library):
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    data = _safetensors(library / "up.safetensors", ["u.lora_A.weight", "u.lora_B.weight"]).read_bytes()
    added = client.post("/api/loras/import", data={"base": "krea-2", "name": "Upload"}, files={"file": ("up.safetensors", data)})
    assert added.status_code == 200, added.text
    lora_id = added.json()["id"]
    assert [e["id"] for e in client.get("/api/loras?base=krea-2").json()["loras"]] == [lora_id]
    assert client.patch(f"/api/loras/{lora_id}", json={"scale": 0.6}).json()["scale"] == 0.6
    assert client.post("/api/loras/fetch", json={"url": "https://example.com/x.safetensors", "base": "krea-2"}).status_code == 400
    assert client.delete(f"/api/loras/{lora_id}").status_code == 200 and not client.get("/api/loras").json()["loras"]


def test_every_klein_file_is_pinned_and_gated_on_its_licence(tmp_path, monkeypatch):
    from app import model_manager

    monkeypatch.setattr(klein, "CONSENT_FILE", tmp_path / "klein-consent.json")
    for spec in klein.VARIANTS.values():
        for build in spec["builds"].values():
            files = model_manager.MODELS[build["model"]]["files"]
            assert files and all(path in model_manager.PINNED for path in files), build["model"]
            assert all("/resolve/" in url and "mflux-community/" in url for url in files.values())
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    # only the 4B: the 9B models' non-commercial licence does not fit formcut
    assert list(klein.VARIANTS) == ["flux2-klein-4b"] and not any("klein-9b" in key for key in model_manager.MODELS)
    assert client.post("/api/models/flux2-klein-4b-mlx-q4/download").status_code == 409
    assert client.post("/api/models/klein/consent", json={"variant": "flux2-klein-4b", "acceptLicence": False}).status_code == 400
    assert client.post("/api/models/klein/consent", json={"variant": "flux2-klein-4b", "acceptLicence": True}).json()["licenceAccepted"]
    terms = client.get("/api/models/klein/terms").json()["variants"]
    assert list(terms) == ["flux2-klein-4b"] and terms["flux2-klein-4b"]["licence"]["commercial"]


def test_klein_runs_with_its_stack_memory_and_progress_through_the_generator(tmp_path, monkeypatch, library):
    monkeypatch.setattr(klein, "CONSENT_FILE", tmp_path / "klein-consent.json")
    klein.record_consent("flux2-klein-4b", True)
    state = {
        "variant": "flux2-klein-4b",
        "licenceAccepted": True,
        "build": "mlx-q4",
        "filterInstalled": False,
        "filterRemoved": False,
        "removalAcknowledged": False,
        "warning": None,
        "ready": True,
        "reason": None,
    }
    monkeypatch.setattr(klein, "policy", lambda variant: state)
    recorded = tmp_path / "argv.json"
    fake = tmp_path / "mflux-generate-flux2"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "from PIL import Image\n"
        f"json.dump(sys.argv[1:], open({str(recorded)!r}, 'w'))\n"
        "for k in range(5): sys.stderr.write(f'\\r{k}/4 [00:00<00:00]'); sys.stderr.flush()\n"
        "Image.new('RGB', (64, 64), 'orange').save(sys.argv[sys.argv.index('--output') + 1])\n"
    )
    fake.chmod(0o755)
    monkeypatch.setattr(klein, "_cli", lambda: fake)
    one = loras.add(_safetensors(library / "a.safetensors", ["a.lora_A.weight", "a.lora_B.weight"]), "Style", "flux2-klein-4b", "file")
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    listed = next(g for g in client.get("/api/generate").json()["generators"] if g["id"] == "local:flux2-klein-4b")
    assert listed["options"]["loras"] == "flux2-klein-4b" and listed["options"]["memory"] == "auto"
    body = {
        "generator": "local:flux2-klein-4b",
        "prompt": "an orange square",
        "size": "1024x1024",
        "options": {"loras": [{"id": one["id"], "scale": 0.8}], "memory": "low"},
    }
    started = client.post("/api/generate", json=body)
    assert started.status_code == 202, started.text
    for _ in range(200):
        status = client.get(f"/api/jobs/{started.json()['job_id']}").json()
        if status["status"] in ("done", "error", "cancelled"):
            break
        time.sleep(0.05)
    assert status["status"] == "done", status
    argv = json.loads(recorded.read_text())
    assert argv[argv.index("--base-model") + 1] == "flux2-klein-4b" and argv[argv.index("--steps") + 1] == "4"
    assert argv[argv.index("--lora-scales") + 1] == "0.8" and "--low-ram" in argv and "--mlx-cache-limit-gb" in argv
    assert status["message"] == "Finishing the picture"


def test_the_terminal_is_not_flooded_by_job_polls():
    from app.main import _QuietPolls

    quiet = _QuietPolls()

    def record(method, path, code):
        return logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d', ("127.0.0.1:1", method, path, "1.1", code), None
        )

    assert not quiet.filter(record("GET", "/api/jobs/96c8", 200))
    assert quiet.filter(record("GET", "/api/jobs/96c8", 404)) and quiet.filter(record("POST", "/api/generate", 202))


def test_a_file_dropped_into_its_models_folder_is_offered(library):
    folder = loras.LIBRARY / "krea-2"
    folder.mkdir(parents=True)
    _safetensors(folder / "dropped style.safetensors", ["d.lora_A.weight", "d.lora_B.weight"], {"trigger_words": "dr0p"})
    (folder / "broken.safetensors").write_bytes(b"nothing here")
    listed = {entry["file"]: entry for entry in loras.entries("krea-2")}
    dropped, broken = listed["dropped style.safetensors"], listed["broken.safetensors"]
    assert dropped["id"] == "krea-2/dropped style" and dropped["usable"] and dropped["triggers"] == "dr0p"
    assert dropped["source"] == "dropped into the folder" and not broken["usable"] and "safetensors" in broken["problem"]
    assert loras.resolve([{"id": dropped["id"], "scale": 0.5}], "krea-2")[0][0].endswith("dropped style.safetensors")
    with pytest.raises(ValueError, match="cannot be used"):
        loras.resolve([{"id": broken["id"], "scale": 1}], "krea-2")
    assert (loras.LIBRARY / "flux2-klein-4b").is_dir()  # each model's folder is there to drop into


def test_the_library_of_v2_0_7_moves_into_the_models_folders(library):
    old = loras.LIBRARY / "neon-1234abcd"
    old.mkdir(parents=True)
    _safetensors(old / "adapter.safetensors", ["n.lora_A.weight", "n.lora_B.weight"])
    (old / "lora.json").write_text(json.dumps({"id": "neon-1234abcd", "name": "Neon", "base": "krea-2", "scale": 0.8}))
    [entry] = loras.entries()
    assert entry["id"] == "krea-2/neon-1234abcd" and entry["name"] == "Neon" and entry["scale"] == 0.8 and not old.exists()


def test_a_civitai_link_chooses_the_folder_and_checks_the_hash(library, monkeypatch):
    import hashlib

    payload = _safetensors(library / "civ.safetensors", ["c.lora_A.weight", "c.lora_B.weight"]).read_bytes()
    found = {
        "versionId": "2766256",
        "name": "Spectrum",
        "file": "X.safetensors",
        "bytes": len(payload),
        "download": "https://civitai.com/api/download/models/2766256",
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
        "triggers": "ZX_style",
        "civitaiBase": "Flux.2 Klein 4B-base",
        "base": "flux2-klein-4b",
        "headers": {},
    }
    monkeypatch.setattr(loras, "civitai_version", lambda url: dict(found))
    monkeypatch.setattr(loras, "_download", lambda url, part, headers, report, cancelled: part.write_bytes(payload))
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})

    def fetched(body):
        started = client.post("/api/loras/fetch", json=body)
        if started.status_code != 202:
            return started.json()
        for _ in range(100):
            status = client.get(f"/api/jobs/{started.json()['job_id']}").json()
            if status["status"] in ("done", "error"):
                return status
            time.sleep(0.05)
        return status

    done = fetched({"url": "https://civitai.com/models/2566/spectrum?modelVersionId=2766256"})
    assert (
        done["status"] == "done"
        and done["result"]["lora"]["id"] == "flux2-klein-4b/Spectrum"
        and done["result"]["lora"]["triggers"] == "ZX_style"
    )
    assert "Krea 2" in fetched({"url": "https://civitai.com/api/download/models/2766256", "base": "krea-2"})["detail"]
    found["sha256"] = "0" * 64
    assert "SHA-256" in fetched({"url": "https://civitai.com/api/download/models/2766256", "name": "Again"})["error"]
    found.update(base=None, civitaiBase="Flux.2 Klein 9B")
    assert "Flux.2 Klein 9B" in fetched({"url": "https://civitai.com/models/2324991"})["detail"]
