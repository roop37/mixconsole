"""HTTP API contract: auth, host guard, projects, jobs, SSE, artifacts, range requests."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mixconsole.io import write_audio
from mixconsole.server.app import API, create_app
from mixconsole.server.auth import issue_token, read_token, token_path
from mixconsole.store.workspace import Workspace
from mixconsole.testing.synth import generate_track

TOKEN = "t" * 32


def _audio(directory: Path, name: str, bpm: float, bars: int = 4) -> Path:
    audio, _ = generate_track(bpm=bpm, bars=bars, seed=int(bpm))
    return write_audio(directory / name, audio)


@pytest.fixture(scope="module")
def songs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    directory = tmp_path_factory.mktemp("songs")
    return _audio(directory, "a.wav", 120), _audio(directory, "b.wav", 124)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Workspace]:
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MIXCONSOLE_WORKERS", "1")
    space = Workspace(tmp_path / "data", ram_budget_mb=4096, max_concurrent=2)
    yield space
    space.close()


@pytest.fixture
def client(workspace: Workspace) -> Iterator[TestClient]:
    app = create_app(workspace, TOKEN, allowed_hosts=["testserver"])
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as test_client:
        yield test_client


def _finish(client: TestClient, job: dict[str, Any]) -> dict[str, Any]:
    done = client.app.state.workspace.jobs.wait(job["id"], timeout=50)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
    return done.model_dump()


@pytest.fixture
def waiter(client: TestClient, workspace: Workspace) -> Any:
    def wait(response: Any) -> dict[str, Any]:
        assert response.status_code == 202, response.text
        return workspace.jobs.wait(response.json()["id"], timeout=55).model_dump()

    return wait


def _project_with_tracks(client: TestClient, songs: tuple[Path, Path]) -> tuple[str, list[str]]:
    project = client.post(f"{API}/projects", json={"name": "demo"}).json()
    tracks = client.post(
        f"{API}/projects/{project['id']}/tracks", json={"paths": [str(p) for p in songs]}
    ).json()
    return project["id"], [t["hash"] for t in tracks]


def test_auth_and_host_guard(workspace: Workspace) -> None:
    app = create_app(workspace, TOKEN, allowed_hosts=["testserver"])
    with TestClient(app) as bare:
        assert bare.get(f"{API}/health").json()["ok"] is True
        assert bare.get(f"{API}/projects").status_code == 401
        assert (
            bare.get(f"{API}/projects", headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )
        assert bare.get(f"{API}/projects", params={"token": TOKEN}).status_code == 200
        assert (
            bare.get(f"{API}/projects", headers={"Authorization": f"Bearer {TOKEN}"}).status_code
            == 200
        )
        evil = bare.get(f"{API}/health", headers={"Host": "evil.example"})
        assert evil.status_code == 400
        assert bare.get(f"{API}/health", headers={"Host": "[::1]:8765"}).status_code == 200


def test_token_file_permissions(tmp_path: Path) -> None:
    first = issue_token(tmp_path)
    assert read_token(tmp_path) == first
    assert token_path(tmp_path).stat().st_mode & 0o777 == 0o600
    assert issue_token(tmp_path) != first
    assert read_token(tmp_path / "nowhere") is None


def test_projects_and_tracks(client: TestClient, songs: tuple[Path, Path]) -> None:
    assert client.get(f"{API}/projects").json() == []
    assert client.get(f"{API}/projects/doesnotexist").status_code == 404
    assert client.post(f"{API}/projects", json={"name": ""}).status_code == 422
    pid, hashes = _project_with_tracks(client, songs)
    assert client.get(f"{API}/projects/{pid}").json()["tracks"] == 2
    assert client.get(f"{API}/projects").json()[0]["id"] == pid
    again = client.post(f"{API}/projects/{pid}/tracks", json={"paths": [str(songs[0])]})
    assert again.json()[0]["hash"] == hashes[0]
    assert len(client.get(f"{API}/projects/{pid}/tracks").json()) == 2
    one = client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}").json()
    assert one["path"] == str(songs[0].resolve())
    assert one["analyzed"] is False
    bad = client.post(f"{API}/projects/{pid}/tracks", json={"paths": ["/no/such.wav"]})
    assert bad.status_code == 422
    assert client.get(f"{API}/projects/{pid}/tracks/xyz").status_code == 422
    assert client.get(f"{API}/projects/{pid}/tracks/{'0' * 64}").status_code == 404
    assert client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}/analysis").status_code == 409
    assert client.delete(f"{API}/projects/{pid}/tracks/{hashes[1]}").status_code == 204
    assert client.delete(f"{API}/projects/{pid}/tracks/{hashes[1]}").status_code == 404
    assert client.delete(f"{API}/projects/{pid}").status_code == 204
    assert client.get(f"{API}/projects/{pid}").status_code == 404
    assert client.get(f"{API}/system").json()["waveform_resolutions"] == [256, 1024, 4096, 16384]


def test_analysis_job_sse_and_artifacts(
    client: TestClient, songs: tuple[Path, Path], waiter: Any
) -> None:
    pid, hashes = _project_with_tracks(client, songs)
    response = client.post(f"{API}/projects/{pid}/analyses", json={})
    job_id = response.json()["id"]
    with client.stream("GET", f"{API}/jobs/{job_id}/events") as stream:
        body = "".join(stream.iter_text())
    assert "event: progress" in body
    assert body.rstrip().endswith("}")
    events = [
        json.loads(line[6:])
        for line in body.splitlines()
        if line.startswith("data: ") and '"seq"' in line
    ]
    assert [e["fraction"] for e in events] == sorted(e["fraction"] for e in events)
    end = json.loads(body.split("event: end\ndata: ")[1].splitlines()[0])
    assert end["state"] == "done"
    assert end["result"]["analyzed"] == hashes
    with client.stream(
        "GET", f"{API}/jobs/{job_id}/events", headers={"Last-Event-ID": str(events[-1]["seq"])}
    ) as replay:
        tail = "".join(replay.iter_text())
    assert "event: progress" not in tail
    assert "event: end" in tail
    history = client.get(f"{API}/jobs/{job_id}/history").json()
    assert [h["seq"] for h in history] == [e["seq"] for e in events]

    track = client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}").json()
    assert track["analyzed"] and round(track["bpm"]) == 120
    analysis = client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}/analysis").json()
    assert analysis["version"] == "track-analysis/v1"
    lanes = client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}/lanes").json()
    assert (
        len(lanes["beats"]) > 8 and lanes["bars"] and len(lanes["bar_energy"]) == len(lanes["bars"])
    )

    peaks = client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}/waveform?resolution=256").json()
    assert peaks["version"] == 2 and peaks["samples_per_pixel"] == 256 and peaks["bits"] == 8
    assert len(peaks["data"]) == 2 * peaks["length"]
    assert all(-128 <= v <= 127 for v in peaks["data"])
    assert max(peaks["data"]) > 20
    coarse = client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}/waveform?resolution=16384").json()
    assert coarse["length"] < peaks["length"]
    assert (
        client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}/waveform?resolution=7").status_code
        == 422
    )
    dat = client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}/waveform.dat?resolution=256")
    assert dat.headers["content-type"] == "application/octet-stream"
    assert len(dat.content) == 24 + len(peaks["data"])
    assert dat.content[:4] == (2).to_bytes(4, "little")

    preview = client.get(f"{API}/projects/{pid}/tracks/{hashes[0]}/preview")
    assert preview.status_code == 200 and len(preview.content) > 1000
    partial = client.get(
        f"{API}/projects/{pid}/tracks/{hashes[0]}/preview", headers={"Range": "bytes=0-99"}
    )
    assert partial.status_code == 206
    assert partial.content == preview.content[:100]

    library = client.get(f"{API}/library/tracks").json()
    assert {t["hash"] for t in library} == set(hashes)
    assert (
        client.get(f"{API}/library/tracks?bpm_min=123&bpm_max=130").json()[0]["hash"] == hashes[1]
    )
    assert client.get(f"{API}/library/tracks?q=a.wav").json()[0]["hash"] == hashes[0]
    assert client.get(f"{API}/library/tracks/{hashes[0]}").json()["camelot"]
    assert client.get(f"{API}/library/tracks/{'1' * 64}").status_code == 404
    assert client.get(f"{API}/library/stats").json()["tracks"] == 2
    assert any(j["id"] == job_id for j in client.get(f"{API}/jobs").json())
    assert client.get(f"{API}/jobs?state=done").json()


def test_plan_edit_diff_and_mix_range(
    client: TestClient, songs: tuple[Path, Path], waiter: Any
) -> None:
    pid, (a, b) = _project_with_tracks(client, songs)
    assert (
        client.post(f"{API}/projects/{pid}/plans", json={"a": a, "b": "0" * 64}).status_code == 404
    )
    assert (
        client.post(f"{API}/projects/{pid}/plans", json={"a": a, "b": b, "style": "x"}).status_code
        == 422
    )
    plan = waiter(client.post(f"{API}/projects/{pid}/plans", json={"a": a, "b": b}))
    assert plan["state"] == "done", plan
    first = plan["result"]["mixscript_id"]
    version = client.get(f"{API}/projects/{pid}/mixscripts/{first}").json()
    assert version["track_a"] == a and version["document"]["version"] == "mixscript/v1.1"

    edited = json.loads(json.dumps(version["document"]))
    edited["transitions"][0]["explanation"]["chosen_because"] = "hand edited"
    created = client.post(
        f"{API}/projects/{pid}/mixscripts",
        json={"document": edited, "parent_id": first, "label": "tweak"},
    )
    assert created.status_code == 201
    second = created.json()
    assert second["parent_id"] == first and second["seq"] == 2 and second["track_b"] == b
    diff = client.get(f"{API}/projects/{pid}/mixscripts/{second['id']}/diff").json()
    assert diff["base_id"] == first
    assert [c["op"] for c in diff["changes"]] == ["changed"]
    assert "chosen_because" in diff["changes"][0]["path"]
    assert client.get(f"{API}/projects/{pid}/mixscripts/{first}/diff").json()["changes"]
    assert (
        client.get(
            f"{API}/projects/{pid}/mixscripts/{first}/diff?against={second['id']}"
        ).status_code
        == 200
    )
    assert (
        client.get(f"{API}/projects/{pid}/mixscripts/{first}/diff?against=nope").status_code == 404
    )
    assert [v["id"] for v in client.get(f"{API}/projects/{pid}/mixscripts").json()] == [
        first,
        second["id"],
    ]
    bad = client.post(f"{API}/projects/{pid}/mixscripts", json={"document": {"version": "x"}})
    assert bad.status_code == 422
    orphan = client.post(
        f"{API}/projects/{pid}/mixscripts", json={"document": edited, "parent_id": "nope"}
    )
    assert orphan.status_code == 404
    assert client.get(f"{API}/projects/{pid}/mixscripts/nope").status_code == 404

    # Render the saved (edited) version, then the full mix pipeline.
    saved = waiter(
        client.post(f"{API}/projects/{pid}/renders", json={"mixscript_id": second["id"]})
    )
    assert saved["state"] == "done", saved
    mixed = waiter(
        client.post(f"{API}/projects/{pid}/mixes", json={"a": a, "b": b, "candidates": 1})
    )
    assert mixed["state"] == "done", mixed
    renders = client.get(f"{API}/projects/{pid}/renders").json()
    assert len(renders) == 2
    render = client.get(f"{API}/projects/{pid}/renders/{mixed['result']['render_id']}").json()
    assert {"mix.wav", "report.html", "report.json"} <= set(render["files"])
    url = f"{API}/projects/{pid}/renders/{render['id']}/files/mix.wav"
    full = client.get(url)
    assert full.status_code == 200 and full.headers["accept-ranges"] == "bytes"
    ranged = client.get(url, headers={"Range": "bytes=100-199"})
    assert ranged.status_code == 206
    assert ranged.headers["content-range"] == f"bytes 100-199/{len(full.content)}"
    assert ranged.content == full.content[100:200]
    tail = client.get(url, headers={"Range": "bytes=-50"})
    assert tail.status_code == 206 and tail.content == full.content[-50:]
    assert client.get(url, headers={"Range": "bytes=99999999-"}).status_code == 416
    assert client.get(url.replace("mix.wav", "..%2Fproject.sqlite")).status_code == 404
    assert client.get(url.replace("mix.wav", "nope.wav")).status_code == 404
    assert client.get(f"{API}/projects/{pid}/renders/zzzzzzzzzzzz").status_code == 404
    assert (
        client.get(f"{API}/projects/{pid}/renders/{render['id']}/files/report.html").status_code
        == 200
    )


def test_job_errors_cancel_and_history(
    client: TestClient, songs: tuple[Path, Path], waiter: Any, workspace: Workspace, tmp_path: Path
) -> None:
    pid, hashes = _project_with_tracks(client, songs)
    assert (
        client.post(f"{API}/projects/{pid}/analyses", json={"hashes": ["0" * 64]}).status_code
        == 404
    )
    empty = client.post(f"{API}/projects", json={"name": "empty"}).json()["id"]
    assert client.post(f"{API}/projects/{empty}/analyses", json={}).status_code == 422
    assert client.get(f"{API}/jobs/nope").status_code == 404
    assert client.post(f"{API}/jobs/nope/cancel").status_code == 404
    assert client.get(f"{API}/jobs/nope/events").status_code == 404
    assert client.get(f"{API}/jobs/nope/history").status_code == 404

    # A missing file fails the job with a readable error and keeps the history row.
    gone = tmp_path / "gone.wav"
    gone.write_bytes(songs[0].read_bytes())
    track = client.post(f"{API}/projects/{pid}/tracks", json={"paths": [str(gone)]}).json()[0]
    # Same bytes as a.wav => same hash => the stored path is replaced by the new one.
    assert track["hash"] == hashes[0]
    gone.unlink()
    failed = waiter(client.post(f"{API}/projects/{pid}/analyses", json={"hashes": [hashes[0]]}))
    assert failed["state"] == "failed" and "missing" in failed["error"]

    # Cancel: stall the runner on an event, cancel through the API.
    import threading

    gate = threading.Event()

    def slow(params: dict[str, Any], progress: Any, cancel: Any) -> dict[str, Any]:
        gate.set()
        for _ in range(500):
            cancel.raise_if_cancelled()
            threading.Event().wait(0.01)
        return {}

    workspace.jobs.runners["analyze"] = slow
    running = client.post(f"{API}/projects/{pid}/analyses", json={"hashes": [hashes[1]]}).json()
    assert gate.wait(10)
    cancelled = client.post(f"{API}/jobs/{running['id']}/cancel").json()
    final = workspace.jobs.wait(running["id"], 10)
    assert final.state == "cancelled", (cancelled, final)
    again = client.post(f"{API}/jobs/{running['id']}/cancel").json()
    assert again["state"] == "cancelled"


def test_scan_job_and_openapi(client: TestClient, songs: tuple[Path, Path], waiter: Any) -> None:
    done = waiter(client.post(f"{API}/library/scans", json={"directory": str(songs[0].parent)}))
    assert done["state"] == "done" and done["result"]["analyzed"] == 2
    assert (
        client.post(f"{API}/library/scans", json={"directory": "/no/such/dir"}).status_code == 422
    )
    again = waiter(client.post(f"{API}/library/scans", json={"directory": str(songs[0].parent)}))
    assert again["result"]["skipped"] == 2 and again["result"]["analyzed"] == 0
    schema = client.get("/openapi.json").json()
    assert len([m for p in schema["paths"].values() for m in p]) >= 30
    assert "bearerAuth" in json.dumps(schema) or "HTTPBearer" in json.dumps(schema)
