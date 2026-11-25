"""M5 server additions: static console mount, browser uploads, per-request stems, FLAC renders."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from mixconsole.cli import app as cli_app
from mixconsole.config import load_settings, settings_override
from mixconsole.io import write_audio
from mixconsole.server.app import API, create_app
from mixconsole.server.ui import find_ui_dir
from mixconsole.store.workspace import Workspace
from mixconsole.testing.synth import generate_track

TOKEN = "u" * 32
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def built_ui(tmp_path: Path) -> Path:
    folder = tmp_path / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text("<!doctype html><title>MixConsole</title>", encoding="utf-8")
    (folder / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return folder


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Workspace]:
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MIXCONSOLE_WORKERS", "1")
    space = Workspace(tmp_path / "data", ram_budget_mb=4096, max_concurrent=2)
    yield space
    space.close()


def test_static_mount_serves_console_and_keeps_api_guarded(
    workspace: Workspace, built_ui: Path
) -> None:
    api = create_app(workspace, TOKEN, allowed_hosts=["testserver"], ui_dir=built_ui)
    with TestClient(api) as client:
        page = client.get("/")
        assert page.status_code == 200 and "MixConsole" in page.text
        assert page.headers["content-type"].startswith("text/html")
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get(f"{API}/health").json()["ok"] is True
        assert client.get(f"{API}/system").status_code == 401
        assert client.get(f"{API}/system", headers=AUTH).status_code == 200
        assert client.get("/openapi.json").status_code == 200
        # The DNS-rebinding guard also covers the static files.
        assert client.get("/", headers={"host": "evil.example"}).status_code == 400


def test_no_ui_dir_means_no_static_routes(workspace: Workspace) -> None:
    with TestClient(create_app(workspace, TOKEN, allowed_hosts=["testserver"])) as client:
        assert client.get("/").status_code == 404


def test_serve_ui_flag(tmp_path: Path, built_ui: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    seen: dict[str, Any] = {}
    monkeypatch.setattr(uvicorn, "run", lambda api, **kwargs: seen.update(app=api, **kwargs))  # pyright: ignore[reportUnknownLambdaType]
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["serve", "--ui", "--ui-dir", str(built_ui), "--data-dir", str(tmp_path / "d")],
    )
    assert result.exit_code == 0, result.output
    assert "Console         http://127.0.0.1:8765/?token=" in result.output
    with TestClient(seen["app"], base_url="http://127.0.0.1") as client:
        assert client.get("/").status_code == 200

    monkeypatch.delenv("MIXCONSOLE_UI_DIR", raising=False)
    missing = runner.invoke(
        cli_app, ["serve", "--ui-dir", str(tmp_path / "nope"), "--data-dir", str(tmp_path / "d2")]
    )
    assert missing.exit_code == 1 and "No built console" in missing.output


def test_find_ui_dir_precedence(
    tmp_path: Path, built_ui: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert find_ui_dir(built_ui) == built_ui
    assert find_ui_dir(tmp_path / "empty") is None
    monkeypatch.setenv("MIXCONSOLE_UI_DIR", str(built_ui))
    assert find_ui_dir(None) == built_ui


def test_upload_adds_a_track_and_dedupes(workspace: Workspace, tmp_path: Path) -> None:
    audio, _ = generate_track(bpm=120, bars=4, seed=3)
    wav = write_audio(tmp_path / "drop.wav", audio)
    with TestClient(create_app(workspace, TOKEN, allowed_hosts=["testserver"]), headers=AUTH) as c:
        pid = c.post(f"{API}/projects", json={"name": "p"}).json()["id"]
        url = f"{API}/projects/{pid}/uploads"
        first = c.post(url, params={"name": "My Song (1).wav"}, content=wav.read_bytes())
        assert first.status_code == 201, first.text
        again = c.post(url, params={"name": "other.wav"}, content=wav.read_bytes())
        assert again.json()["hash"] == first.json()["hash"]
        assert len(c.get(f"{API}/projects/{pid}/tracks").json()) == 1
        stored = Path(first.json()["path"])
        assert stored.is_file() and stored.name == "My_Song_1_.wav"
        assert stored.parent.parent.name == "uploads"
        assert ".." not in stored.name and "/" not in stored.name
        assert c.post(url, params={"name": "x.txt"}, content=b"abc").status_code == 422
        assert c.post(url, params={"name": "x.wav"}, content=b"").status_code == 422
        assert (
            c.post(
                f"{API}/projects/nope/uploads", params={"name": "x.wav"}, content=b"1"
            ).status_code
            == 404
        )
        assert not list(stored.parent.parent.glob(".part-*"))
        path_name = c.post(url, params={"name": "../../etc/evil.wav"}, content=wav.read_bytes())
        assert Path(path_name.json()["path"]).parent.parent == stored.parent.parent


def test_upload_size_cap(workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mixconsole.server.app.MAX_UPLOAD_BYTES", 10)
    with TestClient(create_app(workspace, TOKEN, allowed_hosts=["testserver"]), headers=AUTH) as c:
        pid = c.post(f"{API}/projects", json={"name": "p"}).json()["id"]
        big = c.post(f"{API}/projects/{pid}/uploads", params={"name": "a.wav"}, content=b"x" * 64)
        assert big.status_code == 413
        folder = workspace.projects.get(pid).artifacts / "uploads"  # pyright: ignore[reportOptionalMemberAccess]
        assert not list(folder.glob(".part-*"))


def test_settings_override_is_scoped() -> None:
    assert load_settings().stems == "off"
    with settings_override(stems="on", workers=None):
        assert load_settings().stems == "on"
        with settings_override(stems=None):
            assert load_settings().stems == "on"
    assert load_settings().stems == "off"


def test_stems_param_validated_and_plan_notes_it(workspace: Workspace, tmp_path: Path) -> None:
    a, _ = generate_track(bpm=120, bars=24, seed=1)
    b, _ = generate_track(bpm=124, bars=24, seed=2)
    pa, pb = write_audio(tmp_path / "a.wav", a), write_audio(tmp_path / "b.wav", b)
    with TestClient(create_app(workspace, TOKEN, allowed_hosts=["testserver"]), headers=AUTH) as c:
        pid = c.post(f"{API}/projects", json={"name": "p"}).json()["id"]
        tracks = c.post(f"{API}/projects/{pid}/tracks", json={"paths": [str(pa), str(pb)]}).json()
        ha, hb = tracks[0]["hash"], tracks[1]["hash"]
        bad = c.post(f"{API}/projects/{pid}/plans", json={"a": ha, "b": hb, "stems": "maybe"})
        assert bad.status_code == 422
        job = c.post(f"{API}/projects/{pid}/plans", json={"a": ha, "b": hb, "stems": "auto"})
        assert job.status_code == 202
        done = workspace.jobs.wait(job.json()["id"], timeout=55)
        assert done.state == "done", done.error
        doc = c.get(f"{API}/projects/{pid}/mixscripts/{done.result['mixscript_id']}").json()  # pyright: ignore[reportOptionalSubscript]
        assert "Stems: auto" in doc["document"]["transitions"][0]["explanation"]["chosen_because"]
        # A saved version renders as FLAC on request.
        render = c.post(
            f"{API}/projects/{pid}/renders",
            json={"mixscript_id": done.result["mixscript_id"], "format": "flac"},  # pyright: ignore[reportOptionalSubscript]
        )
        finished = workspace.jobs.wait(render.json()["id"], timeout=55)
        assert finished.state == "done", finished.error
        record = c.get(f"{API}/projects/{pid}/renders/{finished.result['render_id']}").json()  # pyright: ignore[reportOptionalSubscript]
        assert record["audio"] == "mix.flac" and record["files"] == ["mix.flac"]
        flac = c.get(f"{API}/projects/{pid}/renders/{record['id']}/files/mix.flac")
        assert flac.status_code == 200 and flac.content[:4] == b"fLaC"
