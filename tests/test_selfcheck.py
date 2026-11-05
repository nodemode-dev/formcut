"""The engine's selfcheck reports whether formcut's Rust kernels are in it.

setup/build_macos_app refuses an engine frozen without them; the other build
scripts do not build them yet, so their absence must not fail the selfcheck.
"""

import importlib.util
import json
import sys

import desktop_entry


def _run(capsys) -> tuple[int, dict]:
    code = desktop_entry.selfcheck()
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_the_selfcheck_says_whether_the_kernels_are_there(capsys):
    _, info = _run(capsys)
    assert info["native_kernels"] is (importlib.util.find_spec("formcut_native") is not None)


def test_missing_kernels_are_reported_without_failing_the_selfcheck(monkeypatch, capsys):
    with_kernels, _ = _run(capsys)
    monkeypatch.setitem(sys.modules, "formcut_native", None)
    without_kernels, info = _run(capsys)
    assert info["native_kernels"] is False
    assert info["native_error"].startswith(("ImportError", "ModuleNotFoundError"))
    assert without_kernels == with_kernels


def test_the_selfcheck_says_whether_pyav_imports(capsys):
    _, info = _run(capsys)
    if importlib.util.find_spec("av") is None:
        assert info["pyav"] is False
    else:
        import av

        assert info["pyav"] == av.__version__


def test_a_pyav_that_does_not_import_is_reported_without_failing_the_selfcheck(monkeypatch, capsys):
    with_av, _ = _run(capsys)
    monkeypatch.setitem(sys.modules, "av", None)
    without_av, info = _run(capsys)
    assert info["pyav"] is False
    assert info["pyav_error"].startswith(("ImportError", "ModuleNotFoundError"))
    assert without_av == with_av
