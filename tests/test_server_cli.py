"""`mixconsole serve` / `library` CLI, token handling and the generated API types."""

import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mixconsole.cli import app
from mixconsole.io import write_audio
from mixconsole.server.auth import read_token, token_matches
from mixconsole.store.diff import diff_documents
from mixconsole.testing.synth import generate_track

runner = CliRunner()


def test_serve_refuses_remote_bind_without_flag(tmp_path: Path) -> None:
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0", "--data-dir", str(tmp_path)])
    assert result.exit_code == 2
    assert "non-loopback" in result.output


def test_serve_starts_uvicorn_on_loopback_with_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uvicorn

    seen: dict[str, Any] = {}

    def fake_run(api: Any, **kwargs: Any) -> None:
        seen.update(kwargs)
        seen["app"] = api

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    result = runner.invoke(app, ["serve", "--data-dir", str(tmp_path / "d"), "--port", "9123"])
    assert result.exit_code == 0, result.output
    assert seen["host"] == "127.0.0.1" and seen["port"] == 9123
    token = read_token(tmp_path / "d")
    assert token and f"?token={token}" in result.output
    assert seen["app"].title == "MixConsole API"


def test_serve_reports_missing_server_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "uvicorn", None)
    result = runner.invoke(app, ["serve", "--data-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "mixconsole[server]" in result.output


def test_library_scan_and_list_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    music = tmp_path / "music"
    music.mkdir()
    for i in range(2):
        audio, _ = generate_track(bpm=100 + i * 10, bars=2, seed=i)
        write_audio(music / f"s{i}.wav", audio)
    data = str(tmp_path / "data")
    scan = runner.invoke(app, ["library", "scan", str(music), "--data-dir", data, "--workers", "1"])
    assert scan.exit_code == 0, scan.output
    assert "analyzed 2" in scan.output
    rescan = runner.invoke(app, ["library", "scan", str(music), "--data-dir", data])
    assert "up to date 2" in rescan.output
    listing = runner.invoke(app, ["library", "list", "--data-dir", data])
    assert listing.exit_code == 0 and "2 tracks" in listing.output
    (music / "bad.wav").write_bytes(b"junk")
    failing = runner.invoke(app, ["library", "scan", str(music), "--data-dir", data])
    assert failing.exit_code == 1


def test_token_compare_and_diff_helpers() -> None:
    assert token_matches("abc", "abc")
    assert not token_matches("abc", None)
    assert not token_matches("abc", "abd")
    changes = diff_documents({"a": [1, 2], "b": 1, "c": 3}, {"a": [1], "b": 2, "d": 4})
    assert {(c.path, c.op) for c in changes} == {
        ("/a/1", "removed"),
        ("/b", "changed"),
        ("/c", "removed"),
        ("/d", "added"),
    }
    assert [c.op for c in diff_documents([1], [1, 2])] == ["added"]
    assert diff_documents(1, 1) == []


def test_generated_api_types_are_current() -> None:
    import subprocess

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "gen_api_types.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": str(root / "src"), "PATH": ""},
    )
    assert result.returncode == 0, result.stdout + result.stderr
