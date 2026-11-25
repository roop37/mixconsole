"""FastAPI app: REST for projects/tracks/analyses/plans/renders/library, SSE for job progress.

Handlers are thin: long work is a job whose runner calls ``mixconsole.service``; reads come
from SQLite and the artifact folders. Every route except ``/api/v1/health`` needs the token
(``Authorization: Bearer`` or ``?token=`` for EventSource and <audio>).
"""

import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse

from mixconsole import __version__
from mixconsole.analysis.cache import load_analysis
from mixconsole.io import file_sha256
from mixconsole.mixscript import dumps_mixscript
from mixconsole.mixscript.models import MixScript
from mixconsole.server.auth import LOOPBACK_HOSTS, token_matches
from mixconsole.store.artifacts import (
    RESOLUTIONS,
    Lanes,
    Peaks,
    ensure_peaks,
    lanes_from,
    track_preview,
)
from mixconsole.store.diff import Change, diff_documents
from mixconsole.store.jobs import TERMINAL, Job, JobEvent
from mixconsole.store.library import LibraryStats, LibraryTrack
from mixconsole.store.project import (
    MixScriptDocument,
    MixScriptVersion,
    Project,
    ProjectInfo,
    RenderRecord,
    TrackRecord,
    valid_hash,
)
from mixconsole.store.workspace import Workspace

API = "/api/v1"
AUDIO_SUFFIXES = frozenset({".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus", ".aif", ".aiff"})
MAX_UPLOAD_BYTES = 2 * 1024**3
_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MEDIA = {
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".json": "application/json",
    ".html": "text/html; charset=utf-8",
}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TracksAdd(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=5000)


class AnalysisRequest(BaseModel):
    hashes: list[str] | None = Field(default=None, description="Default: all tracks.")


class PairRequest(BaseModel):
    a: str = Field(description="Outgoing track hash")
    b: str = Field(description="Incoming track hash")
    style: str = "auto"
    candidates: int = Field(default=3, ge=1, le=60)
    stems: Literal["off", "auto", "on"] | None = Field(
        default=None, description="Stem families for this request (default: the server setting)."
    )


class PlanRequest(PairRequest):
    parent_id: str | None = Field(default=None, description="MixScript version this re-plans.")
    locks: dict[str, Any] | None = Field(default=None, description="User locks the planner keeps.")


class RenderRequest(BaseModel):
    mixscript_id: str = Field(description="Saved MixScript version to render as-is.")
    format: Literal["wav", "flac"] = Field(default="wav", description="Audio container.")


class MixScriptCreate(BaseModel):
    document: dict[str, Any]
    parent_id: str | None = None
    track_a: str | None = None
    track_b: str | None = None
    label: str = Field(default="edit", max_length=200)


class ScanRequest(BaseModel):
    directory: str


class SystemInfo(BaseModel):
    version: str
    data_dir: str
    ram_budget_mb: int
    max_concurrent_jobs: int
    waveform_resolutions: list[int]


class Health(BaseModel):
    ok: bool
    version: str


class MixScriptDiff(BaseModel):
    base_id: str | None
    id: str
    changes: list[Change]


def _http(status: int, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail=message)


def create_app(
    workspace: Workspace,
    token: str,
    *,
    allowed_hosts: Sequence[str] = (),
    cors_origins: Sequence[str] = (),
    ui_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="MixConsole API",
        generate_unique_id_function=lambda route: route.name,
        version=__version__,
        description="Local-first DJ transition engine. Bind: 127.0.0.1; token required.",
    )
    hosts = LOOPBACK_HOSTS | set(allowed_hosts)
    bearer = HTTPBearer(auto_error=False, description="Local token from <data dir>/server.token")

    @app.middleware("http")
    async def guard_host(request: Request, call_next: RequestResponseEndpoint) -> Response:  # pyright: ignore[reportUnusedFunction]
        # Defeats DNS rebinding: a page on evil.example resolving to 127.0.0.1 is refused.
        host = request.headers.get("host", "")
        name = host.rsplit(":", 1)[0] if not host.endswith("]") else host
        if name not in hosts:
            return JSONResponse({"detail": "host not allowed"}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    if cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    def require_token(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        token_query: Annotated[str | None, Query(alias="token", include_in_schema=False)] = None,
    ) -> None:
        supplied = credentials.credentials if credentials else token_query
        if not token_matches(token, supplied):
            raise HTTPException(
                status_code=401,
                detail="missing or invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    open_router = APIRouter(prefix=API)
    router = APIRouter(prefix=API, dependencies=[Depends(require_token)])

    def project_of(project_id: str) -> Project:
        project = workspace.projects.get(project_id)
        if project is None:
            raise _http(404, "project not found")
        return project

    def digest_of(value: str) -> str:
        if not valid_hash(value):
            raise _http(422, "track hash must be 64 hex characters")
        return value

    def track_of(project: Project, digest: str) -> TrackRecord:
        track = project.track(digest_of(digest))
        if track is None:
            raise _http(404, "track not found")
        return track

    def started(kind: str, params: dict[str, Any], project: str | None = None) -> Job:
        return workspace.jobs.submit(kind, params, project)

    # health / system ----------------------------------------------------------------------
    @open_router.get("/health", tags=["system"])
    def health() -> Health:
        return Health(ok=True, version=__version__)

    @router.get("/system", tags=["system"])
    def system() -> SystemInfo:
        return SystemInfo(
            version=__version__,
            data_dir=str(workspace.root),
            ram_budget_mb=workspace.jobs.budget,
            max_concurrent_jobs=workspace.jobs.max_concurrent,
            waveform_resolutions=list(RESOLUTIONS),
        )

    # projects -----------------------------------------------------------------------------
    @router.get("/projects", tags=["projects"])
    def list_projects() -> list[ProjectInfo]:
        return workspace.projects.list()

    @router.post("/projects", status_code=201, tags=["projects"])
    def create_project(body: ProjectCreate) -> ProjectInfo:
        return workspace.projects.create(body.name).info()

    @router.get("/projects/{project_id}", tags=["projects"])
    def get_project(project_id: str) -> ProjectInfo:
        return project_of(project_id).info()

    @router.delete("/projects/{project_id}", status_code=204, tags=["projects"])
    def delete_project(project_id: str) -> Response:
        project_of(project_id).delete()
        return Response(status_code=204)

    # tracks -------------------------------------------------------------------------------
    @router.get("/projects/{project_id}/tracks", tags=["tracks"])
    def list_tracks(project_id: str) -> list[TrackRecord]:
        return project_of(project_id).tracks()

    @router.post("/projects/{project_id}/tracks", status_code=201, tags=["tracks"])
    def add_tracks(project_id: str, body: TracksAdd) -> list[TrackRecord]:
        project = project_of(project_id)
        resolved: list[tuple[str, Path]] = []
        for raw in body.paths:
            path = Path(raw).expanduser()
            if not path.is_file():
                raise _http(422, f"not a file: {raw}")
            try:
                resolved.append((file_sha256(path), path.resolve()))
            except OSError as exc:
                raise _http(422, f"cannot read {raw}: {exc}") from exc
        return [project.add_track(digest, path)[0] for digest, path in resolved]

    @router.post(
        "/projects/{project_id}/uploads",
        status_code=201,
        tags=["tracks"],
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/octet-stream": {"schema": {"type": "string"}}},
            }
        },
    )
    async def upload_track(
        project_id: str, request: Request, name: Annotated[str, Query(max_length=200)]
    ) -> TrackRecord:
        """Add a track from the raw request body (browser drop). Stored under the project."""
        project = project_of(project_id)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._") or "track"
        if Path(safe).suffix.lower() not in AUDIO_SUFFIXES:
            raise _http(422, f"unsupported audio type: {Path(safe).suffix or name}")
        folder = project.artifacts / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        partial = folder / f".part-{uuid.uuid4().hex}"
        size = 0
        try:
            with partial.open("wb") as stream:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise _http(413, "upload too large")
                    stream.write(chunk)
            if size == 0:
                raise _http(422, "empty upload")
            digest = await asyncio.to_thread(file_sha256, partial)
            # One folder per content hash keeps the original file name for display.
            final = folder / digest[:16] / safe
            final.parent.mkdir(exist_ok=True)
            if final.exists():
                partial.unlink()
            else:
                partial.replace(final)
        finally:
            partial.unlink(missing_ok=True)
        return project.add_track(digest, final.resolve())[0]

    @router.get("/projects/{project_id}/tracks/{track_hash}", tags=["tracks"])
    def get_track(project_id: str, track_hash: str) -> TrackRecord:
        return track_of(project_of(project_id), track_hash)

    @router.delete("/projects/{project_id}/tracks/{track_hash}", status_code=204, tags=["tracks"])
    def delete_track(project_id: str, track_hash: str) -> Response:
        project = project_of(project_id)
        track_of(project, track_hash)
        project.remove_track(track_hash)
        return Response(status_code=204)

    # analyses and artifacts ----------------------------------------------------------------
    @router.post("/projects/{project_id}/analyses", status_code=202, tags=["analyses"])
    def start_analysis(project_id: str, body: AnalysisRequest) -> Job:
        project = project_of(project_id)
        hashes = [digest_of(h) for h in body.hashes] if body.hashes is not None else None
        for digest in hashes or []:
            track_of(project, digest)
        if hashes is None and not project.tracks():
            raise _http(422, "project has no tracks")
        return started("analyze", {"project_id": project_id, "hashes": hashes}, project_id)

    def analysis_file(project: Project, digest: str) -> Path:
        track_of(project, digest)
        located = project.analysis_path(digest)
        if located is None:
            raise _http(409, "track has not been analysed yet; POST /analyses first")
        return located

    @router.get("/projects/{project_id}/tracks/{track_hash}/analysis", tags=["analyses"])
    def get_analysis(project_id: str, track_hash: str) -> dict[str, Any]:
        located = analysis_file(project_of(project_id), track_hash)
        return json.loads(located.read_text(encoding="utf-8"))

    @router.get("/projects/{project_id}/tracks/{track_hash}/lanes", tags=["artifacts"])
    def get_lanes(project_id: str, track_hash: str) -> Lanes:
        return lanes_from(load_analysis(analysis_file(project_of(project_id), track_hash)))

    def peaks_file(project: Project, digest: str, resolution: int, ext: str) -> Path:
        track = track_of(project, digest)
        if resolution not in RESOLUTIONS:
            raise _http(422, f"resolution must be one of {list(RESOLUTIONS)}")
        folder = project.artifacts / "peaks" / digest
        try:
            ensure_peaks(folder, Path(track.path))
        except (OSError, ValueError) as exc:
            raise _http(409, f"cannot compute waveform: {exc}") from exc
        return folder / f"{resolution}.{ext}"

    @router.get("/projects/{project_id}/tracks/{track_hash}/waveform", tags=["artifacts"])
    def get_waveform(project_id: str, track_hash: str, resolution: int = 1024) -> Peaks:
        located = peaks_file(project_of(project_id), track_hash, resolution, "json")
        return Peaks.model_validate_json(located.read_bytes())

    @router.get(
        "/projects/{project_id}/tracks/{track_hash}/waveform.dat",
        tags=["artifacts"],
        response_class=FileResponse,
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    def get_waveform_dat(project_id: str, track_hash: str, resolution: int = 1024) -> FileResponse:
        located = peaks_file(project_of(project_id), track_hash, resolution, "dat")
        return FileResponse(located, media_type="application/octet-stream")

    @router.get(
        "/projects/{project_id}/tracks/{track_hash}/preview",
        tags=["artifacts"],
        response_class=FileResponse,
        responses={200: {"content": {"audio/ogg": {}, "audio/wav": {}}}},
    )
    def get_track_preview(project_id: str, track_hash: str) -> FileResponse:
        project = project_of(project_id)
        track = track_of(project, track_hash)
        try:
            located = track_preview(project.artifacts / "previews" / track_hash, Path(track.path))
        except (OSError, ValueError) as exc:
            raise _http(409, f"cannot build preview: {exc}") from exc
        return FileResponse(located, media_type=_MEDIA.get(located.suffix, "audio/wav"))

    # plans / mixscripts --------------------------------------------------------------------
    @router.post("/projects/{project_id}/plans", status_code=202, tags=["plans"])
    def start_plan(project_id: str, body: PlanRequest) -> Job:
        project = project_of(project_id)
        for digest in (body.a, body.b):
            track_of(project, digest)
        if body.style not in ("auto", "smooth", "club"):
            raise _http(422, "style must be auto, smooth or club")
        if body.parent_id is not None and project.mixscript(body.parent_id) is None:
            raise _http(404, "parent mixscript not found")
        return started("plan", {**body.model_dump(), "project_id": project_id}, project_id)

    @router.get("/projects/{project_id}/mixscripts", tags=["plans"])
    def list_mixscripts(project_id: str) -> list[MixScriptVersion]:
        return project_of(project_id).mixscripts()

    @router.get("/projects/{project_id}/mixscripts/{version_id}", tags=["plans"])
    def get_mixscript(project_id: str, version_id: str) -> MixScriptDocument:
        found = project_of(project_id).mixscript(version_id)
        if found is None:
            raise _http(404, "mixscript version not found")
        return found

    @router.post("/projects/{project_id}/mixscripts", status_code=201, tags=["plans"])
    def add_mixscript(project_id: str, body: MixScriptCreate) -> MixScriptVersion:
        project = project_of(project_id)
        try:
            script = MixScript.model_validate(body.document)
        except ValidationError as exc:
            raise _http(422, f"invalid MixScript: {exc.errors()[0]['msg']}") from exc
        try:
            return project.add_mixscript(
                json.loads(dumps_mixscript(script)),
                parent_id=body.parent_id,
                track_a=body.track_a,
                track_b=body.track_b,
                label=body.label,
            )
        except KeyError as exc:
            raise _http(404, "parent mixscript not found") from exc

    @router.get("/projects/{project_id}/mixscripts/{version_id}/diff", tags=["plans"])
    def diff_mixscript(
        project_id: str, version_id: str, against: str | None = None
    ) -> MixScriptDiff:
        project = project_of(project_id)
        current = project.mixscript(version_id)
        if current is None:
            raise _http(404, "mixscript version not found")
        base_id = against or current.parent_id
        base = project.mixscript(base_id) if base_id else None
        if base_id and base is None:
            raise _http(404, "comparison version not found")
        changes = diff_documents(base.document if base else {}, current.document)
        return MixScriptDiff(base_id=base_id, id=version_id, changes=changes)

    # renders ------------------------------------------------------------------------------
    @router.post("/projects/{project_id}/mixes", status_code=202, tags=["renders"])
    def start_mix(project_id: str, body: PairRequest) -> Job:
        """Plan + audition + verify + render a two-track handoff (service.mix_pair)."""
        project = project_of(project_id)
        for digest in (body.a, body.b):
            track_of(project, digest)
        if body.style not in ("auto", "smooth", "club"):
            raise _http(422, "style must be auto, smooth or club")
        return started("mix", {**body.model_dump(), "project_id": project_id}, project_id)

    @router.post("/projects/{project_id}/renders", status_code=202, tags=["renders"])
    def start_render(project_id: str, body: RenderRequest) -> Job:
        """Render a saved MixScript version exactly as stored."""
        project = project_of(project_id)
        if project.mixscript(body.mixscript_id) is None:
            raise _http(404, "mixscript version not found")
        return started(
            "render",
            {"project_id": project_id, "mixscript_id": body.mixscript_id, "format": body.format},
            project_id,
        )

    @router.get("/projects/{project_id}/renders", tags=["renders"])
    def list_renders(project_id: str) -> list[RenderRecord]:
        return project_of(project_id).renders()

    def render_of(project: Project, render_id: str) -> RenderRecord:
        found = project.render(render_id) if re.fullmatch(r"[0-9a-f]{12}", render_id) else None
        if found is None:
            raise _http(404, "render not found")
        return found

    @router.get("/projects/{project_id}/renders/{render_id}", tags=["renders"])
    def get_render(project_id: str, render_id: str) -> RenderRecord:
        return render_of(project_of(project_id), render_id)

    @router.get(
        "/projects/{project_id}/renders/{render_id}/files/{name}",
        tags=["renders"],
        response_class=FileResponse,
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    def get_render_file(project_id: str, render_id: str, name: str) -> FileResponse:
        """Audio/report artifact; supports HTTP Range requests (206) for seeking."""
        project = project_of(project_id)
        record = render_of(project, render_id)
        if not _FILE.match(name) or name not in record.files:
            raise _http(404, "file not found")
        located = project.render_dir(render_id) / name
        if not located.is_file():
            raise _http(404, "file not found")
        return FileResponse(
            located, media_type=_MEDIA.get(located.suffix, "application/octet-stream")
        )

    # library ------------------------------------------------------------------------------
    @router.get("/library/tracks", tags=["library"])
    def library_tracks(
        q: str | None = None,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        camelot: str | None = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[LibraryTrack]:
        return workspace.library.search(
            q=q, bpm_min=bpm_min, bpm_max=bpm_max, camelot=camelot, limit=limit, offset=offset
        )

    @router.get("/library/tracks/{track_hash}", tags=["library"])
    def library_track(track_hash: str) -> LibraryTrack:
        found = workspace.library.get(digest_of(track_hash))
        if found is None:
            raise _http(404, "track not in the library index")
        return found

    @router.get("/library/stats", tags=["library"])
    def library_stats() -> LibraryStats:
        return workspace.library.stats()

    @router.post("/library/scans", status_code=202, tags=["library"])
    def start_scan(body: ScanRequest) -> Job:
        if not Path(body.directory).expanduser().is_dir():
            raise _http(422, f"not a directory: {body.directory}")
        return started("scan", {"directory": body.directory})

    # jobs ---------------------------------------------------------------------------------
    @router.get("/jobs", tags=["jobs"])
    def list_jobs(
        state: str | None = None, limit: Annotated[int, Query(ge=1, le=500)] = 100
    ) -> list[Job]:
        return workspace.jobs.recent(state=state, limit=limit)

    @router.get("/jobs/{job_id}", tags=["jobs"])
    def get_job(job_id: str) -> Job:
        found = workspace.jobs.get(job_id)
        if found is None:
            raise _http(404, "job not found")
        return found

    @router.post("/jobs/{job_id}/cancel", tags=["jobs"])
    def cancel_job(job_id: str) -> Job:
        found = workspace.jobs.cancel(job_id)
        if found is None:
            raise _http(404, "job not found")
        return found

    @router.get("/jobs/{job_id}/history", tags=["jobs"])
    def job_history(job_id: str, after: int = 0) -> list[JobEvent]:
        """The same progress events as the SSE stream, as plain JSON (for polling clients)."""
        if workspace.jobs.get(job_id) is None:
            raise _http(404, "job not found")
        return workspace.jobs.events(job_id, after)

    @router.get(
        "/jobs/{job_id}/events",
        tags=["jobs"],
        response_class=StreamingResponse,
        responses={200: {"content": {"text/event-stream": {}}, "description": "SSE stream"}},
    )
    async def job_events(job_id: str, request: Request) -> StreamingResponse:
        """Server-sent events: ``progress`` (JobEvent) then ``end`` (final Job). Replays history."""
        if workspace.jobs.get(job_id) is None:
            raise _http(404, "job not found")
        last = request.headers.get("last-event-id", "")
        after = int(last) if last.isdigit() else 0

        async def stream() -> AsyncIterator[str]:
            cursor = after
            quiet = time.monotonic()
            while True:
                events = await asyncio.to_thread(workspace.jobs.events, job_id, cursor)
                for event in events:
                    cursor = event.seq
                    quiet = time.monotonic()
                    yield f"id: {event.seq}\nevent: progress\ndata: {event.model_dump_json()}\n\n"
                job = await asyncio.to_thread(workspace.jobs.get, job_id)
                if job is None:
                    return
                if job.state in TERMINAL and not events:
                    yield f"event: end\ndata: {job.model_dump_json()}\n\n"
                    return
                if await request.is_disconnected():
                    return
                if time.monotonic() - quiet > 15:
                    quiet = time.monotonic()
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0.1)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    app.include_router(open_router)
    app.include_router(router)
    app.state.workspace = workspace
    if ui_dir is not None:
        from fastapi.staticfiles import StaticFiles

        # Mounted last so every /api, /docs and /openapi.json route wins; the SPA uses hash routes.
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
    return app
