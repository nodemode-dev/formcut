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
from pathlib import Path

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
    assert not local_runner.plan(22 * 10**9)["lowRam"] and local_runner.plan(26 * 10**9)["lowRam"]
    assert local_runner.plan(8 * 10**9, "low")["lowRam"] and not local_runner.plan(26 * 10**9, "normal")["lowRam"]
    assert local_runner.mflux_memory_flags(local_runner.plan(26 * 10**9)) == ["--low-ram", "--mlx-cache-limit-gb", "3.2"]
    # only --low-ram caps MLX's cache: a cap costs time on every step
    assert local_runner.mflux_memory_flags(local_runner.plan(8 * 10**9)) == []


def test_the_owners_mac_runs_krea_2_as_mflux_does_alone(monkeypatch):
    """A 24 GB Mac and a 4-bit Krea 2 checkpoint: until 2.1.7 formcut took --low-ram and capped MLX's cache at 2.4 GB,
    and a picture took 6.85 minutes against mflux's 3.7 alone. Now it runs as mflux does, the decode tiled."""
    monkeypatch.setattr(local_runner, "total_memory", lambda: 24 * 10**9)
    settings = local_runner.plan(15.8e9)
    assert not settings["lowRam"] and settings["vaeTiling"] and settings["cacheLimitGb"] is None
    assert local_runner.mflux_memory_flags(settings) == []


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


FAKE_KREA = """#!{python}
import json, sys
from PIL import Image
calls = json.load(open({recorded!r} + ".calls")) if __import__("os").path.exists({recorded!r} + ".calls") else []
calls.append(sys.argv[1:])
json.dump(calls, open({recorded!r} + ".calls", "w"))
json.dump(sys.argv[1:], open({recorded!r}, "w"))
start = sys.argv.index("--seed") + 1
seeds = []
for token in sys.argv[start:]:
    if token.startswith("--"):
        break
    seeds.append(token)
steps = int(sys.argv[sys.argv.index("--steps") + 1])
literal = __import__("os").environ.get("FAKE_LITERAL") == "1"  # a picture named otherwise than by its seed
for seed in seeds:
    __import__("time").sleep(float(__import__("os").environ.get("FAKE_DELAY", "0")))
    for k in range(steps + 1):
        __import__("time").sleep(float(__import__("os").environ.get("FAKE_STEP", "0")))
        sys.stderr.write("\\r" + str(k) + "/" + str(steps) + " [00:00<00:00]")
        sys.stderr.flush()
    out = sys.argv[sys.argv.index("--output") + 1]
    Image.new("RGB", (64, 64), "pink").save(out.replace("{{seed}}", "image") if literal else out.replace("{{seed}}", seed))
"""


OWNERS_PROMPT = """stunning woman in her late 20's with brown long hair near the bed. A realistic RAW photograph of a bright pastel bedroom. Detailed Emotions and Expressions, bl00m
<lora:Emotions V1:1.0> <lora:Detailer-KREA2_from -3 to 6:1.0> <lora:krea2_nose_slider_v1:-2.0>
Steps: 9, CFG scale: 1, Sampler: Euler a beta, Seed: 1554, Model: silly_krea2, width: 840, height: 1256, Version: ComfyUI, Model hash: 637580F9D0, Clip skip: 1"""


def test_a_civitai_prompt_is_read_as_automatic1111_writes_it():
    from app import prompt_data

    data = prompt_data.parse(OWNERS_PROMPT)
    assert data["prompt"].endswith("Detailed Emotions and Expressions, bl00m") and "<lora" not in data["prompt"]
    assert data["loras"] == [("Emotions V1", 1.0), ("Detailer-KREA2_from -3 to 6", 1.0), ("krea2_nose_slider_v1", -2.0)]
    params = data["params"]
    assert (params["steps"], params["seed"], params["model"], params["width"], params["height"]) == (9, 1554, "silly_krea2", 840, 1256)
    also = prompt_data.parse("a cat <lora:x> <lyco:y:0.5:0.2>\nNegative prompt: blurry\nSteps: 20, Size: 1024x768")
    assert also["loras"] == [("x", 1.0), ("y", 0.5)] and also["negative"] == "blurry" and also["params"]["width"] == 1024
    library = [
        {"file": "Emotions-V1.safetensors", "name": "Emotions V1"},
        {"file": "other.safetensors", "originalFile": "krea2_nose_slider_v1.safetensors"},
    ]
    assert prompt_data.match_lora("Emotions V1", library)["file"] == "Emotions-V1.safetensors"
    assert prompt_data.match_lora("krea2_nose_slider_v1", library)["file"] == "other.safetensors"


def _mflux_folder(folder, krea_layout=True):
    for part in ("text_encoder", "vae", "tokenizer"):
        (folder / part).mkdir(parents=True)
    (folder / "text_encoder" / "0.safetensors").write_bytes(b"x")
    (folder / "vae" / "0.safetensors").write_bytes(b"x")
    (folder / "tokenizer" / "tokenizer.json").write_text("{}")
    (folder / ("0.safetensors" if krea_layout else "transformer/0.safetensors")).parent.mkdir(exist_ok=True)
    (folder / ("0.safetensors" if krea_layout else "transformer/0.safetensors")).write_bytes(b"x")


def test_a_checkpoint_in_mflux_format_is_found_and_a_wrong_one_says_why(tmp_path, monkeypatch):
    from app import checkpoints

    monkeypatch.setattr(checkpoints, "FOLDER", tmp_path / "checkpoints")
    _mflux_folder(tmp_path / "checkpoints" / "krea-2" / "silly_krea2")
    _mflux_folder(tmp_path / "checkpoints" / "flux2-klein-4b" / "klein-tune", krea_layout=False)
    (tmp_path / "checkpoints" / "krea-2" / "half").mkdir()
    (tmp_path / "checkpoints" / "krea-2" / "comfy.safetensors").write_bytes(b"x")
    found = {entry["name"]: entry for entry in checkpoints.entries()}
    assert found["silly_krea2"]["usable"] and found["klein-tune"]["usable"] and found["silly_krea2"]["id"] == "ckpt:krea-2:silly_krea2"
    assert "missing text_encoder, vae, tokenizer" in found["half"]["problem"] and "convert it" in found["comfy.safetensors"]["problem"]
    assert checkpoints.find("krea-2", "Silly-Krea2")["name"] == "silly_krea2"


def test_the_owners_civitai_prompt_runs_with_its_loras_checkpoint_steps_seed_and_size(tmp_path, monkeypatch, library):
    from app import checkpoints, krea2

    monkeypatch.setattr(checkpoints, "FOLDER", tmp_path / "checkpoints")
    _mflux_folder(tmp_path / "checkpoints" / "krea-2" / "silly_krea2")
    monkeypatch.setattr(krea2, "CONSENT_FILE", tmp_path / "krea-2-consent.json")
    state = {
        "licenceAccepted": True,
        "ready": True,
        "reason": None,
        "build": "mlx-q8",
        "filterInstalled": False,
        "filterRemoved": True,
        "removalAcknowledged": False,
        "warning": krea2.REMOVED_WARNING,
    }
    monkeypatch.setattr(krea2, "policy", lambda: state)
    runtime = tmp_path / "runtime"
    (runtime / "bin").mkdir(parents=True)
    recorded = tmp_path / "argv.json"
    fake = runtime / "bin" / "mflux-generate-krea2"
    fake.write_text(FAKE_KREA.format(python=sys.executable, recorded=str(recorded)))
    fake.chmod(0o755)
    monkeypatch.setattr(krea2, "RUNTIME", runtime)
    folder = loras.LIBRARY / "krea-2"
    folder.mkdir(parents=True)
    for name in ("Emotions V1", "Detailer-KREA2_from -3 to 6", "krea2_nose_slider_v1"):
        _safetensors(folder / f"{name}.safetensors", ["a.lora_A.weight", "a.lora_B.weight"])
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    listed = next(g for g in client.get("/api/generate").json()["generators"] if g["id"] == "local:ckpt:krea-2:silly_krea2")
    assert listed["ready"] and listed["options"]["loras"] == "krea-2"
    started = client.post("/api/generate", json={"generator": "local:krea-2", "prompt": OWNERS_PROMPT, "size": "1024x1024"})
    assert started.status_code == 202, started.text
    for _ in range(200):
        status = client.get(f"/api/jobs/{started.json()['job_id']}").json()
        if status["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert status["status"] == "done", status
    argv = json.loads(recorded.read_text())
    value = lambda flag: argv[argv.index(flag) + 1]  # noqa: E731
    assert value("--model").endswith("checkpoints/krea-2/silly_krea2") and value("--prompt").endswith("bl00m")
    assert (value("--steps"), value("--seed"), value("--width"), value("--height")) == ("9", "1554", "832", "1248")
    loras_given = [(argv[i + 1].rsplit("/", 1)[1], argv[i + 2]) for i, flag in enumerate(argv) if flag == "--lora"]
    assert loras_given == [
        ("Emotions V1.safetensors", "1"),
        ("Detailer-KREA2_from -3 to 6.safetensors", "1"),
        ("krea2_nose_slider_v1.safetensors", "-2"),
    ]
    assert "--base-model" not in argv and "--lora-paths" not in argv and value("--scheduler") == "euler" and "--guidance" not in argv
    assert value("--output").endswith("-{seed}.png")
    notes = " | ".join(status["result"]["notes"])
    assert "Model silly_krea2: the checkpoint" in notes and "Sampler Euler a beta: mflux's euler" in notes and "made 832x1248" in notes
    missing = client.post("/api/generate", json={"generator": "local:krea-2", "prompt": "a room <lora:Nowhere:0.5>"})
    assert missing.status_code == 400 and "Nowhere" in missing.json()["detail"] and "krea-2" in missing.json()["detail"]


def test_krea_2s_command_is_what_mflux_0_20_parses(tmp_path):
    from pathlib import Path

    from app import krea2

    settings = {"lowRam": False, "vaeTiling": True, "cacheLimitGb": 2.4}
    sampling = {"scheduler": "euler", "guidance": 3.5, "negative": "blurry", "bake": False}
    argv = krea2._command(
        "mlx-q4",
        "a room",
        tmp_path / "x-{seed}.png",
        832,
        1248,
        1554,
        9,
        [("a.safetensors", 1.0), ("b.safetensors", -2.0)],
        settings,
        None,
        [1554, 42, 7],
        sampling,
    )
    assert argv[0].endswith("mflux-generate-krea2") and "--base-model" not in argv
    joined = " ".join(argv[1:])
    for part in (
        "--seed 1554 42 7",
        "--lora a.safetensors 1 --lora b.safetensors -2",
        "--no-bake-lora",
        "--scheduler euler",
        "--guidance 3.5 --negative-prompt blurry",
        "--vae-tiling",
        "--mlx-cache-limit-gb 2.4",
    ):
        assert part in joined, part
    plain = krea2._command(
        "mlx-q8",
        "a room",
        tmp_path / "x.png",
        1024,
        1024,
        1,
        8,
        [],
        {"lowRam": True, "vaeTiling": False, "cacheLimitGb": 2.4},
        None,
        None,
        {},
    )
    assert "--guidance" not in plain and "--negative-prompt" not in plain and "--low-ram" in plain and "--vae-tiling" not in plain
    assert (
        krea2._four_bit("mlx-q8", Path("silly-krea-2-mix-mlx-q4"))
        and not krea2._four_bit("mlx-q8", Path("silly_krea2"))
        and krea2._four_bit("mlx-q4", None)
    )


def test_the_decode_is_tiled_when_memory_is_short(monkeypatch):
    monkeypatch.setattr(local_runner, "total_memory", lambda: 12 * 10**9)
    assert local_runner.plan(4.6e9)["vaeTiling"] and not local_runner.plan(2e9)["vaeTiling"]
    assert not local_runner.plan(4.6e9, "low")["vaeTiling"] and not local_runner.plan(4.6e9, "normal")["vaeTiling"]
    # a model that would not fit runs --low-ram, which tiles already
    assert local_runner.plan(10e9)["lowRam"] and not local_runner.plan(10e9)["vaeTiling"]


def test_several_krea_pictures_come_from_one_run_of_mflux(tmp_path, monkeypatch, library):
    from app import krea2

    monkeypatch.setattr(krea2, "CONSENT_FILE", tmp_path / "krea-2-consent.json")
    state = {
        "licenceAccepted": True,
        "ready": True,
        "reason": None,
        "build": "mlx-q4",
        "filterInstalled": False,
        "filterRemoved": True,
        "removalAcknowledged": False,
        "warning": krea2.REMOVED_WARNING,
    }
    monkeypatch.setattr(krea2, "policy", lambda: state)
    runtime = tmp_path / "runtime"
    (runtime / "bin").mkdir(parents=True)
    recorded = tmp_path / "argv.json"
    fake = runtime / "bin" / "mflux-generate-krea2"
    fake.write_text(FAKE_KREA.format(python=sys.executable, recorded=str(recorded)))
    fake.chmod(0o755)
    monkeypatch.setattr(krea2, "RUNTIME", runtime)
    (loras.LIBRARY / "krea-2").mkdir(parents=True)
    _safetensors(loras.LIBRARY / "krea-2" / "style.safetensors", ["a.lora_A.weight", "a.lora_B.weight"])
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    body = {"generator": "local:krea-2", "prompt": "a room <lora:style:0.7>", "count": 3, "options": {"seed": 40, "scheduler": "euler"}}
    started = client.post("/api/generate", json=body)
    assert started.status_code == 202, started.text
    messages = set()
    for _ in range(300):
        status = client.get(f"/api/jobs/{started.json()['job_id']}").json()
        messages.add(status.get("message"))
        if status["status"] in ("done", "error"):
            break
        time.sleep(0.02)
    assert status["status"] == "done", status
    calls = json.loads((tmp_path / "argv.json.calls").read_text())
    assert len(calls) == 1 and " ".join(calls[0]).count("--seed 40 41 42") == 1 and "--scheduler euler" in " ".join(calls[0])
    assert "--no-bake-lora" in calls[0]  # the 4-bit build keeps its LoRA unbaked
    assert len(status["result"]["media"]) == 3


def _krea_standin(tmp_path, monkeypatch):
    from app import krea2

    monkeypatch.setattr(krea2, "CONSENT_FILE", tmp_path / "krea-2-consent.json")
    state = {
        "licenceAccepted": True,
        "ready": True,
        "reason": None,
        "build": "mlx-q8",
        "filterInstalled": False,
        "filterRemoved": True,
        "removalAcknowledged": False,
        "warning": krea2.REMOVED_WARNING,
    }
    monkeypatch.setattr(krea2, "policy", lambda: state)
    runtime = tmp_path / "runtime"
    (runtime / "bin").mkdir(parents=True)
    recorded = tmp_path / "argv.json"
    fake = runtime / "bin" / "mflux-generate-krea2"
    fake.write_text(FAKE_KREA.format(python=sys.executable, recorded=str(recorded)))
    fake.chmod(0o755)
    monkeypatch.setattr(krea2, "RUNTIME", runtime)
    return recorded


def _finished(client, body):
    started = client.post("/api/generate", json=body)
    if started.status_code != 202:
        return started
    for _ in range(300):
        status = client.get(f"/api/jobs/{started.json()['job_id']}").json()
        if status["status"] in ("done", "error"):
            return status
        time.sleep(0.02)
    return status


def test_image_to_image_starts_from_a_library_picture_or_the_playheads_frame(tmp_path, monkeypatch, library):
    from app import media
    from PIL import Image

    recorded = _krea_standin(tmp_path, monkeypatch)
    picture = tmp_path / "start.png"
    Image.new("RGB", (400, 300), "teal").save(picture)
    item = media.ingest_path(picture, "start.png")
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    listed = next(g for g in client.get("/api/generate").json()["generators"] if g["id"] == "local:krea-2")
    assert listed["options"]["image"] == 0.4
    done = _finished(
        client,
        {
            "generator": "local:krea-2",
            "prompt": "the same room at night",
            "size": "source",
            "options": {"image": {"mediaId": item["id"]}, "imageStrength": 0.6},
        },
    )
    assert done["status"] == "done", done
    argv = json.loads(recorded.read_text())
    source = argv[argv.index("--image") + 1]
    assert argv[argv.index("--image") + 2] == "0.6" and (argv[argv.index("--width") + 1], argv[argv.index("--height") + 1]) == (
        "400",
        "288",
    )
    assert not Path(source).exists() and "started from the image at influence 0.6" in done["result"]["notes"]
    # the playhead's frame, rendered from the project; Civitai's Denoising strength read as 1 minus it
    clip = {
        "id": "c",
        "kind": "text",
        "label": "c",
        "start": 0,
        "duration": 1,
        "textStyle": {"content": "hello", "size": 8, "color": "#ffffff"},
    }
    project = {
        "title": "p",
        "width": 320,
        "height": 180,
        "fps": 30,
        "duration": 1,
        "activeTimeline": 0,
        "timelines": [{"id": "p", "name": "p", "tracks": [{"id": "t", "name": "V", "clips": [clip]}]}],
    }
    done = _finished(
        client,
        {
            "generator": "local:krea-2",
            "prompt": "a sign\nSteps: 8, Denoising strength: 0.7",
            "options": {"image": {"project": project, "time": 0.5}},
        },
    )
    assert done["status"] == "done", done
    argv = json.loads(recorded.read_text())
    assert argv[argv.index("--image") + 2] == "0.3" and (argv[argv.index("--width") + 1], argv[argv.index("--height") + 1]) == (
        "320",
        "256",
    )
    refused = client.post("/api/generate", json={"generator": "local:krea-2", "prompt": "x", "options": {"image": {"nothing": 1}}})
    assert refused.status_code == 400


def test_seed_minus_one_is_random_and_the_seed_used_is_in_the_file_and_the_library(tmp_path, monkeypatch, library):
    from app import krea2, media, prompt_data
    from PIL import Image

    recorded = _krea_standin(tmp_path, monkeypatch)
    (loras.LIBRARY / "krea-2").mkdir(parents=True)
    _safetensors(loras.LIBRARY / "krea-2" / "Emotions V1.safetensors", ["a.lora_A.weight", "a.lora_B.weight"])
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    body = {
        "generator": "local:krea-2",
        "prompt": "a quiet room <lora:Emotions V1:0.8>",
        "size": "1024x1024",
        "options": {"seed": -1, "steps": 6},
    }
    done = _finished(client, body)
    assert done["status"] == "done", done
    argv = json.loads(recorded.read_text())
    used = int(argv[argv.index("--seed") + 1])
    assert done["result"]["seeds"] == [used] and argv[argv.index("--steps") + 1] == "6"
    [item] = done["result"]["media"]
    assert item["seed"] == used and item["steps"] == 6 and item["loras"] == [{"file": "Emotions V1", "scale": 0.8}]
    stored = next(media.MEDIA_DIR.glob(f"{item['id']}.*"))
    with Image.open(stored) as picture:
        parameters = picture.text["parameters"]
    assert f"Seed: {used}" in parameters and "Steps: 6" in parameters and "<lora:Emotions V1:0.8>" in parameters
    # the text, pasted back, asks for the same picture
    again = prompt_data.parse(parameters)
    assert again["params"]["seed"] == used and again["params"]["steps"] == 6 and again["loras"] == [("Emotions V1", 0.8)]
    assert again["params"]["model"] == "krea-2" and again["prompt"] == "a quiet room"
    assert done["result"]["warning"] == krea2.REMOVED_WARNING  # the filter removed and not yet acknowledged


def test_the_filter_warning_stops_once_acknowledged(tmp_path, monkeypatch, library):
    from app import krea2

    _krea_standin(tmp_path, monkeypatch)
    state = krea2.policy()
    monkeypatch.setattr(krea2, "policy", lambda: {**state, "removalAcknowledged": True})
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    done = _finished(client, {"generator": "local:krea-2", "prompt": "a quiet room", "options": {"seed": 7}})
    assert done["status"] == "done", done
    assert "warning" not in done["result"] and done["result"]["seeds"] == [7]


def test_the_terminal_shows_the_models_own_progress_bar(monkeypatch):
    import io

    out = io.StringIO()
    monkeypatch.setattr(sys, "__stderr__", out)
    monkeypatch.delenv("FORMCUT_QUIET_PROGRESS", raising=False)
    script = STEPS_SCRIPT + "\nimport os\nsys.stderr.write('columns ' + os.environ.get('COLUMNS', '?') + '\\n')\n"
    local_runner.run([sys.executable, "-c", script], 4, lambda *a, **k: None, lambda: False, "Stand-in")
    text = out.getvalue()
    # the model's tqdm output itself, as it came, between formcut's opening and closing lines; no bar of formcut's
    assert text.startswith("formcut: Stand-in\n  ") and "2/4 [00:02<00:04, 1.0it/s]" in text and "\r" in text
    assert sys.executable in text.split("\n")[1]  # the command itself, to set beside mflux run by hand
    assert "formcut: Stand-in: done in" in text and "Stand-in  [" not in text
    assert "columns " in text and "columns ?" not in text  # tqdm is told the terminal's width


def test_the_page_gets_tqdms_reading_elapsed_left_and_rate():
    readings = []

    def report(value, message=None, **fields):
        if "timing" in fields:
            readings.append(fields["timing"])

    script = r"""
import sys, time
for k, stamp in enumerate(["[00:00<?, ?it/s]", "[00:03<00:21,  7.02s/it]", "[00:05<00:10,  1.95it/s]"]):
    sys.stderr.write("\r 10%|#  | " + str(k) + "/8 " + stamp); sys.stderr.flush(); time.sleep(0.05)
sys.stderr.write("\n")
"""
    local_runner.run([sys.executable, "-c", script], 8, report, lambda: False, "Stand-in")
    steps = [r for r in readings if not r.get("loading")]
    assert {"step": 1, "steps": 8, "elapsed": "00:03", "remaining": "00:21", "rate": "7.02s/it"} in steps
    assert {"step": 2, "steps": 8, "elapsed": "00:05", "remaining": "00:10", "rate": "1.95it/s"} in steps


def test_a_continuous_session_keeps_the_model_loaded_and_takes_a_new_prompt(tmp_path, monkeypatch, library):
    from app import media
    from PIL import Image

    _krea_standin(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_DELAY", "0.25")
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    listed = next(g for g in client.get("/api/generate").json()["generators"] if g["id"] == "local:krea-2")
    assert listed["options"]["continuous"] is True
    started = client.post(
        "/api/generate", json={"generator": "local:krea-2", "prompt": "a red room", "options": {"seed": -1, "steps": 4, "continuous": True}}
    )
    assert started.status_code == 202, started.text
    job = started.json()["job_id"]

    def made(at_least):
        for _ in range(400):
            status = client.get(f"/api/jobs/{job}").json()
            if len(status.get("made") or []) >= at_least or status["status"] != "running":
                return status
            time.sleep(0.05)
        return status

    first = made(2)
    assert len(first["made"]) >= 2 and first["seeds"] == [item["seed"] for item in first["made"]]
    changed = client.post(f"/api/generate/sessions/{job}/prompt", json={"prompt": "a blue room <lora:gone:1>"})
    assert changed.status_code == 200 and changed.json()["prompt"] == "a blue room"
    later = made(len(first["made"]) + 2)
    assert client.delete(f"/api/jobs/{job}").status_code == 200
    for _ in range(200):
        ended = client.get(f"/api/jobs/{job}").json()
        if ended["status"] != "running":
            break
        time.sleep(0.05)
    assert ended["status"] == "cancelled"
    calls = json.loads((tmp_path / "argv.json.calls").read_text())
    assert len(calls) == 1  # one process: the model loaded once for every picture
    argv = calls[0]
    assert "--prompt-file" in argv and "--prompt" not in argv
    seeds = argv[argv.index("--seed") + 1 : argv.index("--steps")]
    assert len(seeds) == 500 and [str(s) for s in later["seeds"]] == seeds[: len(later["seeds"])]
    prompts = [item["prompt"] for item in later["made"]]
    assert prompts[0] == "a red room" and prompts[-1] == "a blue room"
    stored = next(media.MEDIA_DIR.glob(f"{later['made'][-1]['id']}.*"))
    with Image.open(stored) as picture:
        assert f"Seed: {later['made'][-1]['seed']}" in picture.text["parameters"]
    assert client.post(f"/api/generate/sessions/{job}/prompt", json={"prompt": "x"}).status_code == 404


def test_a_session_takes_each_picture_before_the_next_is_made(tmp_path, monkeypatch, library):
    from app import krea2

    _krea_standin(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_DELAY", "0.8")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("a room", encoding="utf-8")
    staging = tmp_path / "staging"
    staging.mkdir()
    taken, stop, handed = [], {"now": False}, set()

    def on_picture(seed, path):
        # when a picture is handed over, the next one has not been written yet
        pending = [p for p in staging.glob("*.png") if p != path and p not in handed]
        handed.add(path)
        taken.append((seed, path.is_file(), len(pending)))
        if len(taken) == 3:
            stop["now"] = True

    import contextlib

    with contextlib.suppress(InterruptedError):
        krea2.run_continuous(prompt, staging, on_picture, 256, 256, steps=2, cancelled=lambda: stop["now"])
    assert len(taken) >= 3 and all(whole and pending == 0 for _, whole, pending in taken[:3])


def test_the_page_shows_session_pictures_by_id():
    from pathlib import Path as P

    source = (P(__file__).resolve().parents[1] / "frontend" / "src" / "ui" / "studio-tools.ts").read_text(encoding="utf-8")
    assert "const fresh = partial.filter((item) => !shown.has(item.id));" in source and "partial.length > shown.size" not in source


def test_the_previews_frames_are_let_go_before_a_model_runs():
    import numpy as np
    from app import render_api
    from app.frame_cache import FrameCache

    cache = FrameCache({"fps": 30}, limit=8)
    for i in range(3):
        cache.frames[(i, "orig")] = np.zeros((1080, 1920, 3), np.uint8)
    with render_api._lock:
        render_api._sessions["test-free"] = {"cache": cache}
    try:
        assert render_api.release_frames() >= 3 * 1080 * 1920 * 3 and not cache.frames
    finally:
        with render_api._lock:
            render_api._sessions.pop("test-free", None)


def test_unticking_continuous_finishes_the_picture_in_hand_then_stops(tmp_path, monkeypatch, library):
    _krea_standin(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_DELAY", "0.3")
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    started = client.post(
        "/api/generate",
        json={"generator": "local:krea-2", "prompt": "a green room", "options": {"seed": -1, "steps": 4, "continuous": True}},
    )
    job = started.json()["job_id"]
    for _ in range(400):
        status = client.get(f"/api/jobs/{job}").json()
        if status.get("made"):
            break
        time.sleep(0.05)
    asked_with = len(status["made"])
    assert client.post(f"/api/generate/sessions/{job}/finish").json()["finishing"] is True
    for _ in range(400):
        status = client.get(f"/api/jobs/{job}").json()
        if status["status"] != "running":
            break
        time.sleep(0.05)
    # not cancelled: done, the picture in hand finished and saved, nothing after it
    assert status["status"] == "done", status
    made = status["result"]["media"]
    assert asked_with <= len(made) <= asked_with + 1 and all(item["seed"] for item in made)
    time.sleep(0.8)
    assert len(json.loads((tmp_path / "argv.json.calls").read_text())) == 1
    assert client.post(f"/api/generate/sessions/{job}/finish").status_code == 404


def test_the_page_reads_the_step_tqdm_shows_now_not_the_one_before():
    """tqdm writes a carriage return and then its reading, so the reading on screen is the unfinished line. Until 2.1.9
    formcut waited for the next step's carriage return, a whole step behind the terminal (the owner's screenshot:
    2/8 [01:58<05:56] on the page against 3/8 [03:18<05:43] in the terminal)."""
    import threading as th

    got = []

    def report(value, message=None, **fields):
        got.append((round(value, 3), message, fields.get("timing")))

    script = r"""
import sys, time
sys.stderr.write("\r  0%|    | 0/4 [00:00<?, ?it/s]"); sys.stderr.flush(); time.sleep(0.2)
sys.stderr.write("\r 50%|##  | 2/4 [01:10<01:10, 35.00s/it]"); sys.stderr.flush()
time.sleep(2.0)
sys.stderr.write("\n")
"""
    runner = th.Thread(target=local_runner.run, args=([sys.executable, "-c", script], 4, report, lambda: False, "Stand-in"))
    runner.start()
    time.sleep(1.2)  # the stand-in is still on step 2, its line not yet ended
    now = [entry for entry in got if entry[2] and not entry[2].get("loading")]
    runner.join()
    assert now and now[-1][2] == {"elapsed": "01:10", "remaining": "01:10", "rate": "35.00s/it", "step": 2, "steps": 4}
    assert now[-1][0] == 0.5 and now[-1][1] == "Step 2 of 4"  # the bar's share is tqdm's own 50%


def _session(client, prompt, steps=4):
    started = client.post(
        "/api/generate", json={"generator": "local:krea-2", "prompt": prompt, "options": {"seed": -1, "steps": steps, "continuous": True}}
    )
    return started.json()["job_id"]


def _until(client, job, test, tries=600):
    for _ in range(tries):
        status = client.get(f"/api/jobs/{job}").json()
        if test(status):
            return status
        time.sleep(0.02)
    return status


def test_a_picture_named_otherwise_is_shown_before_the_next_begins(tmp_path, monkeypatch, library):
    """mflux writing the same name each time (not the seed's): each picture still taken as soon as it is whole."""
    _krea_standin(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_DELAY", "1.2")
    monkeypatch.setenv("FAKE_LITERAL", "1")
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    job = _session(client, "a grey room")
    first = _until(client, job, lambda s: len(s.get("made") or []) >= 1)
    shown_at = time.time()
    second = _until(client, job, lambda s: len(s.get("made") or []) >= 2)
    client.delete(f"/api/jobs/{job}")
    _until(client, job, lambda s: s["status"] != "running")
    # the first was shown during the pause before the second picture (1.2 s), not when the second began its steps
    assert len(first["made"]) == 1 and len(second["made"]) == 2 and time.time() - shown_at > 0.8
    assert first["made"][0]["seed"] == second["seeds"][0] and second["seeds"][0] != second["seeds"][1]


def test_unticking_mid_picture_finishes_that_picture_not_the_one_before(tmp_path, monkeypatch, library):
    """The owner's case: Continuous unticked while picture 2 was being made. Picture 2 is finished and saved, then the
    session stops; until 2.1.10 saving picture 1 late ended the session and picture 2 was lost."""
    _krea_standin(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_DELAY", "0.1")
    monkeypatch.setenv("FAKE_STEP", "0.15")  # each step takes its time, as Krea 2's do
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    job = _session(client, "a yellow room", steps=6)
    # picture 1 saved, picture 2 under way (its second step drawn)
    _until(client, job, lambda s: len(s.get("made") or []) >= 1 and "Picture 2: Step 2" in (s.get("message") or ""))
    asked = client.post(f"/api/generate/sessions/{job}/finish").json()
    assert asked["after"] == 2
    ended = _until(client, job, lambda s: s["status"] != "running")
    assert ended["status"] == "done" and len(ended["result"]["media"]) == 2
