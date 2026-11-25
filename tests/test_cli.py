"""CLI success/error behavior and dependency-free core import."""

import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mixconsole import __version__
from mixconsole.cli import app

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"mixconsole {__version__}"


def test_validate():
    result = runner.invoke(app, ["validate", str(ROOT / "examples/trim-crossfade.mixscript.json")])
    assert result.exit_code == 0
    assert "Valid mixscript/v1.1: 2 tracks, 1 transitions" in result.stdout


@pytest.mark.parametrize("contents", [b"{}", b"bad json", b"\xff"])
def test_validate_failure(tmp_path, contents):
    path = tmp_path / "bad.json"
    path.write_bytes(contents)
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 1
    assert "Invalid MixScript" in result.output
    assert "Traceback" not in result.output


def test_missing_mixscript(tmp_path):
    result = runner.invoke(app, ["validate", str(tmp_path / "absent.json")])
    assert result.exit_code == 1
    assert "Invalid MixScript" in result.output


def test_doctor_without_torch_or_ffmpeg(monkeypatch):
    monkeypatch.setattr("mixconsole.cli.importlib.util.find_spec", lambda _: None)
    monkeypatch.setattr("mixconsole.cli.shutil.which", lambda _: None)
    result = runner.invoke(app, ["doctor"], env={"COLUMNS": "150"})
    assert result.exit_code == 0
    for text in ("Python", "ffmpeg", "not found", "neural", "stems", "ui", "torch", "MPS", "CUDA"):
        assert text in result.stdout


def test_doctor_handles_broken_optional_torch(monkeypatch):
    monkeypatch.setattr("mixconsole.cli.importlib.util.find_spec", lambda _: object())

    def broken(_):
        raise OSError("unavailable native library")

    monkeypatch.setattr("mixconsole.cli.importlib.import_module", broken)
    result = runner.invoke(app, ["doctor"], env={"COLUMNS": "150"})
    assert result.exit_code == 0
    assert "probe failed" in result.stdout


def test_core_import_does_not_load_torch():
    code = """
import importlib.abc
import sys
class BlockTorch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'torch':
            raise AssertionError('torch must not be imported')
sys.meta_path.insert(0, BlockTorch())
import mixconsole
import mixconsole.cli
import mixconsole.io
import mixconsole.mixscript
import mixconsole.testing.synth
assert 'torch' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)
