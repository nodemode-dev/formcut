"""Krea 2 is optional: nothing downloads before its licence is accepted, and the content filter is always installed
with it (there is no option to install Krea 2 without it). If the person later removes the filter, Krea 2 keeps
running and every such picture carries the warning; a prompt sexualising minors is refused whatever happens; with the
filter present, a picture it flags is withheld."""

import hashlib
import json
import sys

import numpy as np
import pytest
from app import content_filter, krea2, model_manager
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(krea2, "CONSENT_FILE", tmp_path / "krea-2-consent.json")
    monkeypatch.setattr(krea2, "FOLDER", tmp_path / "krea-2")
    monkeypatch.setattr(krea2, "RUNTIME", tmp_path / "krea-2" / "runtime")
    return tmp_path


def test_the_licence_must_be_accepted(fresh):
    with pytest.raises(ValueError, match="accepted"):
        krea2.record_consent(False)
    assert krea2.policy()["reason"].startswith("the Krea 2 Community License Agreement has not been accepted")
    record = krea2.record_consent(True)
    assert record["filter"] == "installed with Krea 2" and "waiver" not in record
    assert (fresh / "krea-2" / "NOTICE.txt").read_text().strip() == krea2.NOTICE
    assert krea2.policy()["reason"] == "no Krea 2 build is installed"


def test_a_removed_filter_warns_and_does_not_stop_krea(fresh, monkeypatch):
    krea2.record_consent(True)
    monkeypatch.setattr(krea2, "installed_build", lambda: "mlx-q8")
    monkeypatch.setattr(content_filter, "installed", lambda: False)
    state = krea2.policy()
    assert state["ready"] and state["filterRemoved"] and not state["removalAcknowledged"]
    assert state["warning"] == krea2.REMOVED_WARNING
    for words in (
        "knowingly",
        "section 4.2",
        "Apache License, Version 2.0",
        "NodeMode",
        "any jurisdiction",
        "Reinstall the content filter",
    ):
        assert words in krea2.REMOVED_WARNING
    acknowledged = krea2.acknowledge_removal()
    assert acknowledged["removalAcknowledged"] and acknowledged["ready"]
    stored = json.loads((fresh / "krea-2-consent.json").read_text())
    assert stored["removalAcknowledged"]["sha256"] == hashlib.sha256(krea2.REMOVED_WARNING.encode()).hexdigest()
    monkeypatch.setattr(content_filter, "installed", lambda: True)
    assert not krea2.policy()["filterRemoved"] and krea2.policy()["warning"] is None


@pytest.mark.parametrize(
    ("prompt", "refused"),
    [
        ("a child flying a kite on a beach", False),
        ("a classical nude figure study, oil on canvas", False),
        ("nude photo of a 14 year old", True),
        ("sexy schoolgirl", True),
        ("naked toddler", True),
    ],
)
def test_the_prompt_guard_is_not_a_setting(prompt, refused):
    assert (krea2.prompt_refusal(prompt) is not None) == refused


def test_the_api_gates_install_and_download_on_the_licence(fresh):
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    terms = client.get("/api/models/krea-2/terms").json()
    assert terms["licence"]["url"] == krea2.LICENCE_URL and terms["removedWarning"] == krea2.REMOVED_WARNING
    assert terms["filter"]["name"] == "Falconsai/nsfw_image_detection" and len(terms["licence"]["summary"]) == 6
    assert client.post("/api/models/krea-2/install", json={}).status_code in (400, 409)
    assert client.post("/api/models/krea-2-mlx-q8/download").status_code == 409
    assert client.post("/api/models/krea-2/consent", json={"acceptLicence": False}).status_code == 400
    ok = client.post("/api/models/krea-2/consent", json={"acceptLicence": True})
    assert ok.status_code == 200 and ok.json()["licenceAccepted"]
    assert client.post("/api/models/krea-2/acknowledge-removal", json={}).status_code == 200


def test_every_krea_file_is_pinned_to_a_revision_and_kept_out_of_bulk_downloads():
    for key in ("krea-2-mlx-q8", "krea-2-mlx-q4", "krea-2-sdnq-int8", "nsfw-filter"):
        spec = model_manager.MODELS[key]
        assert spec["optional"]
        for name, url in spec["files"].items():
            assert len(model_manager.PINNED[name]) == 64
            assert "/resolve/main/" not in url
    assert all(
        not model_manager.MODELS[k].get("optional")
        for k in model_manager.MODELS
        if "GPL" not in model_manager.MODELS[k]["license"] and k.startswith("krea") is False and k != "nsfw-filter"
    )


def test_the_filter_reads_the_classifier_as_its_preprocessor_asks(monkeypatch):
    seen = {}

    class Session:
        def get_inputs(self):
            return [type("I", (), {"name": "pixel_values"})()]

        def run(self, _outputs, feed):
            seen["x"] = feed["pixel_values"]
            return [np.array([[0.0, 2.0]], np.float32)]

    monkeypatch.setattr(content_filter, "_load", Session)
    monkeypatch.setattr(content_filter, "_nsfw_index", 1)
    verdict = content_filter.check(np.full((360, 640, 3), 255, np.uint8))
    assert seen["x"].shape == (1, 3, 224, 224) and np.allclose(seen["x"], 1.0)
    assert verdict["withheld"] and verdict["nsfw"] == pytest.approx(0.8808, abs=1e-3)


def test_a_flagged_picture_is_withheld_and_a_removed_filter_lets_krea_run(fresh, monkeypatch, tmp_path):
    krea2.record_consent(True)
    state = {"ready": True, "reason": None, "build": "mlx-q8", "filterInstalled": True}
    monkeypatch.setattr(krea2, "policy", lambda: state)
    script = "import sys; from PIL import Image; Image.new('RGB', (64, 64), 'red').save(sys.argv[1])"
    monkeypatch.setattr(krea2, "_command", lambda build, prompt, out, *a: [sys.executable, "-c", script, str(out)])
    out = tmp_path / "picture.png"
    monkeypatch.setattr(content_filter, "check", lambda rgb: {"nsfw": 0.97, "withheld": True, "threshold": 0.5})
    with pytest.raises(ValueError, match="withheld"):
        krea2.generate_to_file("a red square", out, 256, 256, seed=1)
    assert not out.exists()
    monkeypatch.setattr(content_filter, "check", lambda rgb: {"nsfw": 0.01, "withheld": False, "threshold": 0.5})
    result = krea2.generate_to_file("a red square", out, 256, 256, seed=1)
    assert out.exists() and result["contentFilter"]["nsfw"] == 0.01 and result["notice"] == krea2.NOTICE and result["warning"] is None
    state["filterInstalled"] = False
    out.unlink()
    result = krea2.generate_to_file("a red square", out, 256, 256, seed=2)
    assert out.exists() and result["contentFilter"] == "removed" and result["warning"] == krea2.REMOVED_WARNING
    assert json.loads((fresh / "krea-2-consent.json").read_text())["runsWithoutFilter"]["count"] == 1
    with pytest.raises(ValueError, match="minors"):
        krea2.generate_to_file("naked child", out, 256, 256, seed=1)


def test_consent_is_written_as_json(fresh):
    krea2.record_consent(True)
    stored = json.loads((fresh / "krea-2-consent.json").read_text())
    assert stored["licence"]["version"] == krea2.LICENCE_VERSION
