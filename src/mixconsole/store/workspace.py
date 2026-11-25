"""Workspace = data dir with library index, projects and the job manager (+ job runners).

Runners only orchestrate: analysis, planning, mixing and scanning are the service facade's.
"""

import shutil
from pathlib import Path
from typing import Any

from mixconsole.analysis.cache import load_analysis, save_analysis
from mixconsole.analysis.models import TrackAnalysis
from mixconsole.config import data_root, load_settings, settings_override
from mixconsole.progress import CancelToken, Progress, ProgressEvent, checkpoint
from mixconsole.store.artifacts import ensure_peaks
from mixconsole.store.jobs import JobManager
from mixconsole.store.library import LibraryIndex, scan_library
from mixconsole.store.project import Project, ProjectStore

_STYLES = ("auto", "smooth", "club")


def _scaled(progress: Progress, low: float, high: float) -> Progress:
    def report(event: ProgressEvent) -> None:
        progress(ProgressEvent(event.stage, low + (high - low) * event.fraction, event.message))

    return report


class Workspace:
    def __init__(
        self,
        data_dir: str | Path | None = None,
        *,
        ram_budget_mb: int | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        self.root = data_root(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.projects = ProjectStore(self.root)
        self.library = LibraryIndex(self.root / "index.sqlite")
        settings = load_settings()
        self.jobs = JobManager(
            self.root / "jobs.sqlite",
            {
                "analyze": self._analyze,
                "plan": self._plan,
                "mix": self._mix,
                "render": self._render,
                "scan": self._scan,
            },
            ram_budget_mb=ram_budget_mb or settings.job_ram_mb,
            max_concurrent=max_concurrent or max(2, settings.workers),
        )

    def close(self) -> None:
        self.jobs.shutdown()

    # helpers --------------------------------------------------------------------------------
    def _project(self, params: dict[str, Any]) -> Project:
        project = self.projects.get(str(params["project_id"]))
        if project is None:
            raise ValueError("project not found (deleted?)")
        return project

    @staticmethod
    def _path(project: Project, digest: str) -> Path:
        track = project.track(digest)
        if track is None:
            raise ValueError(f"track {digest[:12]} is not in the project")
        if not Path(track.path).is_file():
            raise ValueError(f"track file is missing: {track.path}")
        return Path(track.path)

    @staticmethod
    def _style(params: dict[str, Any]) -> str:
        style = str(params.get("style", "auto"))
        if style not in _STYLES:
            raise ValueError("style must be auto, smooth or club")
        return style

    # runners --------------------------------------------------------------------------------
    def _analyze(
        self, params: dict[str, Any], progress: Progress, cancel: CancelToken
    ) -> dict[str, Any]:
        from mixconsole.service import analyze_tracks

        project = self._project(params)
        wanted = params.get("hashes") or [t.hash for t in project.tracks()]
        paths = [self._path(project, h) for h in wanted]
        results = analyze_tracks(paths, progress=_scaled(progress, 0, 0.9), cancel=cancel)
        for i, (digest, analysis, path) in enumerate(zip(wanted, results, paths, strict=True)):
            if analysis.file_sha256 != digest:
                raise ValueError(f"{path.name} changed on disk since it was added")
            ref = f"artifacts/analysis/{digest}.json"
            save_analysis(analysis, project.root / ref)
            project.set_analysis(
                digest, ref, analysis.duration, analysis.global_bpm, analysis.key.camelot
            )
            self.library.upsert(analysis, path)
            ensure_peaks(project.artifacts / "peaks" / digest, path)
            checkpoint(progress, cancel, "artifacts", 0.9 + 0.1 * (i + 1) / len(wanted), path.name)
        return {"analyzed": list(wanted)}

    def _pair(self, project: Project, params: dict[str, Any]) -> tuple[str, str, Path, Path]:
        a, b = str(params["a"]), str(params["b"])
        return a, b, self._path(project, a), self._path(project, b)

    def _plan(
        self, params: dict[str, Any], progress: Progress, cancel: CancelToken
    ) -> dict[str, Any]:
        import json

        from mixconsole.mixscript import dumps_mixscript
        from mixconsole.service import plan_pair

        project = self._project(params)
        a, b, path_a, path_b = self._pair(project, params)
        with settings_override(stems=params.get("stems")):
            result = plan_pair(
                path_a,
                path_b,
                style=self._style(params),
                candidates=int(params.get("candidates", 3)),
                locks=params.get("locks"),
                progress=progress,
                cancel=cancel,
            )
        version = project.add_mixscript(
            json.loads(dumps_mixscript(result.mixscript)),
            parent_id=params.get("parent_id"),
            track_a=a,
            track_b=b,
            label=str(params.get("label", "plan")),
        )
        return {"mixscript_id": version.id, "chosen_id": result.chosen_id}

    def _mix(
        self, params: dict[str, Any], progress: Progress, cancel: CancelToken
    ) -> dict[str, Any]:
        import json
        import uuid

        from mixconsole.mixscript import dumps_mixscript
        from mixconsole.service import mix_pair

        project = self._project(params)
        a, b, path_a, path_b = self._pair(project, params)
        render_id = uuid.uuid4().hex[:12]
        folder = project.render_dir(render_id)
        folder.mkdir(parents=True)
        try:
            with settings_override(stems=params.get("stems")):
                result = mix_pair(
                    path_a,
                    path_b,
                    style=self._style(params),
                    candidates=int(params.get("candidates", 3)),
                    out=folder / "mix.wav",
                    report_dir=folder,
                    progress=progress,
                    cancel=cancel,
                )
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        version = project.add_mixscript(
            json.loads(dumps_mixscript(result.mixscript)),
            parent_id=params.get("parent_id"),
            track_a=a,
            track_b=b,
            label="mix",
        )
        summary = result.metrics.as_dict() if result.metrics else {}
        files = sorted(p.name for p in folder.iterdir() if p.is_file())
        project.add_render(
            render_id,
            mixscript_id=version.id,
            audio="mix.wav",
            files=files,
            summary={"chosen_id": result.chosen_id, "metrics": summary},
            job_id=str(params.get("_job_id")) if params.get("_job_id") else None,
        )
        return {"render_id": render_id, "mixscript_id": version.id}

    def _render(
        self, params: dict[str, Any], progress: Progress, cancel: CancelToken
    ) -> dict[str, Any]:
        import uuid

        from mixconsole.io import load_audio, write_audio
        from mixconsole.mixscript.models import MixScript
        from mixconsole.render import render_transition
        from mixconsole.service import stems_for

        project = self._project(params)
        version = project.mixscript(str(params["mixscript_id"]))
        if version is None or not version.track_a or not version.track_b:
            raise ValueError("mixscript version not found or not bound to two tracks")
        script = MixScript.model_validate(version.document)
        path_a = self._path(project, version.track_a)
        path_b = self._path(project, version.track_b)
        checkpoint(progress, cancel, "decode", 0.1)
        left, right = load_audio(path_a), load_audio(path_b)
        if (
            left.pcm_sha256 != script.tracks["deck_a"].content_sha256
            or right.pcm_sha256 != script.tracks["deck_b"].content_sha256
        ):
            raise ValueError("track PCM hash mismatch against the MixScript")
        stems = None
        if script.transitions[0].family in ("stem_handoff", "vocal_over_instrumental"):
            analyses: list[TrackAnalysis] = []
            for digest in (version.track_a, version.track_b):
                located = project.analysis_path(digest)
                if located is None:
                    raise ValueError("stem transitions need analysed tracks")
                analyses.append(load_analysis(located))
            folder = load_settings().cache_dir
            stems = (
                stems_for(analyses[0], left.samples, "exit", folder),
                stems_for(analyses[1], right.samples, "entry", folder),
            )
        checkpoint(progress, cancel, "render", 0.3)
        audio = render_transition(left.samples, right.samples, script, stems=stems)
        render_id = uuid.uuid4().hex[:12]
        folder_out = project.render_dir(render_id)
        folder_out.mkdir(parents=True)
        name = "mix.flac" if params.get("format") == "flac" else "mix.wav"
        write_audio(folder_out / name, audio)
        project.add_render(
            render_id,
            mixscript_id=version.id,
            audio=name,
            files=[name],
            summary={"source": "saved mixscript"},
            job_id=None,
        )
        checkpoint(progress, cancel, "render", 1.0)
        return {"render_id": render_id}

    def _scan(
        self, params: dict[str, Any], progress: Progress, cancel: CancelToken
    ) -> dict[str, Any]:
        directory = Path(str(params["directory"])).expanduser()
        if not directory.is_dir():
            raise ValueError(f"not a directory: {directory}")
        summary = scan_library(directory, self.library, progress=progress, cancel=cancel)
        return {
            "found": summary.found,
            "analyzed": summary.analyzed,
            "skipped": summary.skipped,
            "failed": summary.failed,
            "errors": summary.errors,
        }
