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
    assert without_kernels == with_kernels
