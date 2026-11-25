"""Shared CLI/server facade with bounded processes and input-ordered results."""

import logging
import math
import multiprocessing
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Executor, Future, ProcessPoolExecutor, wait
from pathlib import Path
from typing import TYPE_CHECKING

from mixconsole.analysis import analyze
from mixconsole.analysis.models import TrackAnalysis
from mixconsole.config import load_settings
from mixconsole.io import Audio
from mixconsole.mixscript.models import MixScript, RejectedCandidate
from mixconsole.plan.candidates import Candidate
from mixconsole.progress import (
    Cancelled,
    CancelToken,
    EventFlag,
    Progress,
    ProgressEvent,
    checkpoint,
)
from mixconsole.verify.metrics import SeamMetrics

__all__ = ["CancelToken", "Cancelled", "Progress", "ProgressEvent", "analyze_tracks"]
if TYPE_CHECKING:
    from mixconsole.analysis.backends.stems import StemSet

logger = logging.getLogger(__name__)


def _analyze_one(
    path: str,
    backends: Mapping[str, str] | None,
    use_cache: bool,
    cache_dir: str | None,
    flag: EventFlag,
) -> TrackAnalysis:
    return analyze(
        path, backends=backends, use_cache=use_cache, cache_dir=cache_dir, cancel=CancelToken(flag)
    )


def _process_pool(workers: int) -> Executor:
    return ProcessPoolExecutor(max_workers=workers)


def analyze_tracks(
    paths: Sequence[str | Path],
    *,
    backends: Mapping[str, str] | None = None,
    use_cache: bool = True,
    cache_dir: str | Path | None = None,
    workers: int | None = None,
    progress: Progress | None = None,
    cancel: CancelToken | None = None,
    executor_factory: Callable[[int], Executor] | None = None,
) -> list[TrackAnalysis]:
    """Report stages inline and completed tracks in a process pool.

    Cancellation stops new work and signals active processes at stage boundaries.
    A native DSP call already running completes before its next checkpoint. Results
    keep input order; pool size is capped at 32 and the number of input tracks.
    Defaults come from settings (workers defaults to min(4, CPU count)).
    """
    settings = load_settings()
    count = settings.workers if workers is None else workers
    if isinstance(count, bool) or not 1 <= count <= 32:
        raise ValueError("workers must be between 1 and 32")
    chosen = settings.backends if backends is None else backends
    root = settings.cache_dir if cache_dir is None else cache_dir
    cache = None if root is None else str(root)
    token = cancel or CancelToken()
    items = [str(p) for p in paths]
    total = len(items)
    checkpoint(progress, token, "analyze", 0.0, f"0/{total}")
    if not items:
        checkpoint(progress, token, "complete", 1.0)
        return []
    logger.info("analyzing %d tracks with %d workers", total, min(count, total))
    if count == 1 or total == 1:
        results: list[TrackAnalysis] = []
        for index, path in enumerate(items):

            def report(event: ProgressEvent, index: int = index) -> None:
                checkpoint(
                    progress, token, event.stage, (index + event.fraction) / total, event.message
                )

            results.append(
                analyze(
                    path,
                    backends=chosen,
                    use_cache=use_cache,
                    cache_dir=cache,
                    progress=report,
                    cancel=token,
                )
            )
        return results
    ordered: dict[int, TrackAnalysis] = {}
    factory: Callable[[int], Executor] = executor_factory or _process_pool
    with multiprocessing.Manager() as manager:
        flag = manager.Event()
        with factory(min(count, total)) as pool:
            futures: dict[Future[TrackAnalysis], int] = {}
            try:
                token.raise_if_cancelled()
                futures = {
                    pool.submit(_analyze_one, path, chosen, use_cache, cache, flag): i
                    for i, path in enumerate(items)
                }
                pending = set(futures)
                while pending:
                    token.raise_if_cancelled()
                    finished, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                    for future in sorted(finished, key=lambda f: futures[f]):
                        index = futures[future]
                        ordered[index] = future.result()
                        checkpoint(
                            progress,
                            token,
                            "analyze",
                            len(ordered) / total,
                            Path(items[index]).name,
                        )
            finally:
                flag.set()
                for future in futures:
                    future.cancel()
    return [ordered[i] for i in range(total)]


class MixResult:
    """Pair result and local artifact locations."""

    def __init__(
        self,
        script: "MixScript",
        chosen_id: str,
        metrics: "SeamMetrics | None",
        paths: dict[str, Path],
    ) -> None:
        self.mixscript = script
        self.chosen_id = chosen_id
        self.metrics = metrics
        self.paths = paths


_MATCHED = ("beatmatch_blend", "stem_handoff", "vocal_over_instrumental")


def stems_for(
    analysis: TrackAnalysis, samples: "Audio", role: str, cache_dir: str | Path | None = None
) -> "StemSet":
    """Stems of the analysed ``role`` window (a cache hit after analysis).

    Raises ValueError when the analysis has no stem windows (stems extra missing).
    """
    from mixconsole.analysis import cache
    from mixconsole.analysis.backends import stems as stem_backend

    window = (
        next((w for w in analysis.stems.windows if w.role == role), None)
        if analysis.stems
        else None
    )
    if window is None:
        raise ValueError("stem transitions need the stems extra (no stem windows were analysed)")
    frames = (round(window.start * 44100), round(window.end * 44100))
    return stem_backend.separate_window(
        samples, analysis.pcm_sha256, frames, cache_root=cache.cache_root(cache_dir)
    )


def _shift(stem_set: "StemSet", offset: int) -> "StemSet":
    from mixconsole.analysis.backends.stems import StemSet

    return StemSet(
        stem_set.start_frame - offset,
        stem_set.stems,
        stem_set.latency_frames,
        stem_set.model,
        stem_set.stats,
    )


def _candidate_script(
    candidate: "Candidate",
    analyses: list[TrackAnalysis],
    *,
    alternatives: list["Candidate"],
    rejected: list["RejectedCandidate"],
) -> "MixScript":
    from mixconsole.mixscript.models import (
        CandidateSummary,
        CuePoint,
        Effect,
        Explanation,
        KeyStrategy,
        MixScript,
        Provenance,
        TempoPoint,
        TempoStrategy,
        Track,
        TrackTarget,
        Transition,
    )
    from mixconsole.plan.candidates import effective_tempo
    from mixconsole.plan.families import families
    from mixconsole.score.heuristic import SCORER_VERSION

    a, b = analyses
    family = next(item for item in families() if item.name == candidate.family)
    automation, family_effects = family.automation(candidate)
    if candidate.seam_gain_db > 0:
        from mixconsole.mixscript.models import Effect, TrackTarget

        family_effects.append(
            Effect(
                id="seam_gain",
                name="seam_gain",
                target=TrackTarget(kind="track", track="deck_b"),
                params={"db": candidate.seam_gain_db},
            )
        )
    bpm = candidate.bpm or 120.0
    effective_bpm = effective_tempo(b, bpm) if b.global_bpm else bpm
    relative = abs(effective_bpm - bpm) / bpm

    def local_lufs(track: TrackAnalysis, second: float) -> float | None:
        values = track.arrays.get("short_term_lufs")
        if values is None or not len(values):
            return track.loudness.integrated_lufs
        index = min(len(values) - 1, max(0, round(second / track.loudness.hop_seconds)))
        value = float(values[index])
        return value if value > -80 else track.loudness.integrated_lufs

    loud_a = local_lufs(a, max(0, candidate.exit_seconds - 1.5))
    loud_b = local_lufs(b, candidate.entry_seconds + 1.5)
    ramp_bars = (
        math.ceil(200 * relative) if candidate.tempo_strategy == "ramp_b_to_a_then_back" else 0
    )
    beat_warp: list[list[int]] = []
    if candidate.family in _MATCHED and a.beats and b.beats:
        count = candidate.length_bars * a.meter
        a_grid = [t for t in a.beats if t >= candidate.exit_seconds - 0.001]
        b_grid = [t for t in b.beats if t >= candidate.entry_seconds - 0.001]
        scale = effective_bpm / b.global_bpm if b.global_bpm else 1.0
        for index in range(count + 1):
            target_time = (
                a_grid[index] - candidate.exit_seconds if index < len(a_grid) else index * 60 / bpm
            )
            source_index = index / scale
            base = int(source_index)
            fraction = source_index - base
            if base + 1 < len(b_grid):
                source_time = (
                    b_grid[base]
                    + fraction * (b_grid[base + 1] - b_grid[base])
                    - candidate.entry_seconds
                )
            elif base < len(b_grid):
                source_time = (
                    b_grid[base] - candidate.entry_seconds + fraction * 60 / (b.global_bpm or bpm)
                )
            else:
                source_time = index * 60 / effective_bpm
            beat_warp.append([round(source_time * 44100), round(target_time * 44100)])
        beat_warp[0] = [0, 0]
        beat_warp[-1][1] = round(candidate.duration * 44100)
    summary = [
        CandidateSummary(
            id=c.id,
            family=c.family,
            exit=CuePoint(beat=c.exit_seconds * (a.global_bpm or bpm) / 60, seconds=c.exit_seconds),
            entry=CuePoint(
                beat=c.entry_seconds * (b.global_bpm or bpm) / 60, seconds=c.entry_seconds
            ),
            length_bars=c.length_bars,
            score=c.score,
            score_breakdown=c.features,
        )
        for c in alternatives
    ]
    return MixScript(
        version="mixscript/v1.1",
        tracks={
            "deck_a": Track(
                content_sha256=a.pcm_sha256,
                duration=a.duration,
                sample_rate=a.sample_rate,
                display_name=Path(a.file).name,
            ),
            "deck_b": Track(
                content_sha256=b.pcm_sha256,
                duration=b.duration,
                sample_rate=b.sample_rate,
                display_name=Path(b.file).name,
            ),
        },
        transitions=[
            Transition(
                id="transition_1",
                from_track="deck_a",
                to_track="deck_b",
                family=candidate.family,
                exit=CuePoint(
                    beat=candidate.exit_seconds * (a.global_bpm or bpm) / 60,
                    seconds=candidate.exit_seconds,
                ),
                entry=CuePoint(
                    beat=candidate.entry_seconds * (b.global_bpm or bpm) / 60,
                    seconds=candidate.entry_seconds,
                ),
                length_bars=candidate.length_bars,
                beats_per_bar=a.meter,
                extensions={"render.beat_warp": beat_warp} if beat_warp else {},
                tempo=TempoStrategy(
                    strategy=candidate.tempo_strategy,
                    reference_track="deck_a",
                    tempo_map=[TempoPoint(beat=0, bpm=bpm)],
                ),
                key=KeyStrategy(strategy="none"),
                automation=automation,
                effects=[
                    *family_effects,
                    Effect(
                        id="tempo_match_b",
                        name="tempo_match",
                        target=TrackTarget(kind="track", track="deck_b"),
                        params={"effective_bpm": effective_bpm, "ramp_bars": float(ramp_bars)},
                    ),
                    Effect(
                        id="gain_match_b",
                        name="gain_match",
                        target=TrackTarget(kind="track", track="deck_b"),
                        params={
                            "db": max(
                                -6.0,
                                min(
                                    6.0,
                                    (loud_a or 0.0) - (loud_b or 0.0),
                                ),
                            )
                        },
                    ),
                ],
                explanation=Explanation(
                    chosen_because=(
                        f"Ranked {candidate.family} at {candidate.score:.3f} from "
                        "the score and hard constraints."
                    ),
                    score_breakdown=candidate.features,
                    rejected_candidates=rejected,
                ),
                candidates=summary,
            )
        ],
        provenance=Provenance(
            analysis_backends={
                **a.backend_versions,
                **{f"b_{k}": v for k, v in b.backend_versions.items()},
            },
            scorer_version=SCORER_VERSION,
            seed=0,
        ),
        extensions={"render.stretcher": "signalsmith@0.3.1"},
    )


def plan_pair(
    a: str | Path,
    b: str | Path,
    *,
    style: str = "auto",
    candidates: int = 3,
    locks: dict[str, object] | None = None,
    progress: Progress | None = None,
    cancel: CancelToken | None = None,
) -> MixResult:
    """Analyze and rank a pair without rendering."""
    from mixconsole.plan.candidates import plan_pair as make_plan

    if style not in ("auto", "smooth", "club") or candidates < 1:
        raise ValueError("style must be auto, smooth or club; candidates must be positive")
    analyses = analyze_tracks([a, b], progress=progress, cancel=cancel)
    checkpoint(progress, cancel, "plan", 0.0)
    plan = make_plan(analyses[0], analyses[1], load_settings(), style=style, locks=locks)
    if not plan.candidates:
        raise ValueError("no valid transition candidates")
    chosen = plan.candidates[0]
    script = _candidate_script(
        chosen, analyses, alternatives=plan.candidates[:candidates], rejected=plan.rejected
    )
    checkpoint(progress, cancel, "plan", 1.0)
    return MixResult(script, chosen.id, None, {})


def _encode_preview(path: Path) -> Path:
    """Prefer local Opus; keep the WAV when ffmpeg or its encoder is absent."""
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return path
    encoded = path.with_suffix(".opus")
    command = [
        ffmpeg,
        "-nostdin",
        "-y",
        "-v",
        "error",
        "-i",
        str(path),
        "-map_metadata",
        "-1",
        "-c:a",
        "libopus",
        "-b:a",
        "96k",
        "-fflags",
        "+bitexact",
        "-flags:a",
        "+bitexact",
        str(encoded),
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode == 0 and encoded.is_file():
        path.unlink()
        return encoded
    encoded.unlink(missing_ok=True)
    return path


def _fmt(value: float | None, unit: str) -> str:
    """Render an optional measurement; None reads as "n/a" (not measured), never 0."""
    return "n/a" if value is None else f"{value:.2f} {unit}"


def mix_pair(
    a: str | Path,
    b: str | Path,
    *,
    style: str = "auto",
    candidates: int = 3,
    out: str | Path | None = None,
    report_dir: str | Path | None = None,
    progress: Progress | None = None,
    cancel: CancelToken | None = None,
) -> MixResult:
    """Plan, audition, render, verify and report a two-track handoff."""
    import json

    from mixconsole.io import SAMPLE_RATE, load_audio, write_audio
    from mixconsole.plan.candidates import plan_pair as make_plan
    from mixconsole.render import render_transition
    from mixconsole.render.graph import STEM_FAMILIES, RenderInspection
    from mixconsole.report.html import write_html
    from mixconsole.verify import verify_seam

    if style not in ("auto", "smooth", "club") or candidates < 1:
        raise ValueError("style must be auto, smooth or club; candidates must be positive")
    destination = Path(out or "out.wav")
    folder = Path(report_dir or destination.with_suffix(""))
    folder.mkdir(parents=True, exist_ok=True)
    analyses = analyze_tracks([a, b], progress=progress, cancel=cancel)
    audio_a, audio_b = load_audio(a), load_audio(b)
    if audio_a.pcm_sha256 != analyses[0].pcm_sha256 or audio_b.pcm_sha256 != analyses[1].pcm_sha256:
        raise ValueError("input PCM changed after analysis")
    checkpoint(progress, cancel, "plan", 0.0)
    plan = make_plan(analyses[0], analyses[1], load_settings(), style=style)
    if not plan.candidates:
        raise ValueError("no valid transition candidates")
    shortlist: list[Candidate] = []
    used_families: set[str] = set()
    for candidate in plan.candidates:
        if candidate.family not in used_families:
            shortlist.append(candidate)
            used_families.add(candidate.family)
        if len(shortlist) == candidates:
            break
    for candidate in plan.candidates:
        if len(shortlist) == candidates:
            break
        if candidate not in shortlist:
            shortlist.append(candidate)
    checkpoint(progress, cancel, "plan", 1.0)
    checks: list[dict[str, object]] = []
    chosen: Candidate | None = None
    measured: SeamMetrics | None = None

    stem_cache: dict[str, StemSet] = {}

    def stems_pair(a_offset: int, b_offset: int) -> "tuple[StemSet, StemSet]":
        cache_dir = load_settings().cache_dir
        if "a" not in stem_cache:
            stem_cache["a"] = stems_for(analyses[0], audio_a.samples, "exit", cache_dir)
            stem_cache["b"] = stems_for(analyses[1], audio_b.samples, "entry", cache_dir)
        return _shift(stem_cache["a"], a_offset), _shift(stem_cache["b"], b_offset)

    def excerpt(candidate: Candidate, script: MixScript) -> tuple["Audio", int, RenderInspection]:
        context = max(30.0, 8 * 4 * 60 / (candidate.bpm or 120))
        a_start = max(0, round((candidate.exit_seconds - context) * SAMPLE_RATE))
        a_end = min(
            len(audio_a.samples), round((candidate.exit_seconds + candidate.duration) * SAMPLE_RATE)
        )
        b_start = round(candidate.entry_seconds * SAMPLE_RATE)
        b_end = min(
            len(audio_b.samples),
            round((candidate.entry_seconds + candidate.duration + 2 * context) * SAMPLE_RATE),
        )
        local = script.model_copy(deep=True)
        local.transitions[0].exit.seconds = candidate.exit_seconds - a_start / SAMPLE_RATE
        local.transitions[0].entry.seconds = 0.0
        inspection = RenderInspection()
        pcm = render_transition(
            audio_a.samples[a_start:a_end],
            audio_b.samples[b_start:b_end],
            local,
            inspection=inspection,
            stems=stems_pair(a_start, b_start) if candidate.family in STEM_FAMILIES else None,
        )
        return pcm, round(local.transitions[0].exit.seconds * SAMPLE_RATE), inspection

    # Verify in score order so a higher-scored candidate (e.g. a stem handoff at another cue)
    # is not skipped just because a shortlisted candidate of another family passes. A family
    # that keeps failing verification is abandoned after four attempts unless it is shortlisted.
    render_order = list(plan.candidates)
    failures: dict[str, int] = {}
    for index, candidate in enumerate(render_order):
        if failures.get(candidate.family, 0) >= 4 and candidate not in shortlist:
            continue
        checkpoint(progress, cancel, "render", index / max(1, len(render_order)))
        script = _candidate_script(
            candidate, analyses, alternatives=shortlist, rejected=plan.rejected
        )
        try:
            pcm, seam, inspection = excerpt(candidate, script)
        except ValueError as exc:
            if candidate.family not in STEM_FAMILIES:
                raise
            checks.append({"candidate": candidate.id, "passed": False, "reason": str(exc)})
            continue
        checkpoint(progress, cancel, "verify", index / max(1, len(render_order)))
        metric = verify_seam(
            pcm,
            seam,
            round(candidate.duration * SAMPLE_RATE),
            bpm=candidate.bpm or 120,
            max_dip=load_settings().max_loudness_dip_lu,
            max_peak=load_settings().max_true_peak_dbtp,
            max_drift=load_settings().max_drift_ms,
            max_low_overlap=load_settings().max_low_overlap_bars,
            max_vocal_overlap_beats=load_settings().max_vocal_overlap_beats,
            beats_per_bar=candidate.beats_per_bar,
            inspection=inspection,
        )
        checks.append({"candidate": candidate.id, **metric.as_dict()})
        if (
            not metric.passed
            and candidate.family in ("beatmatch_blend", *STEM_FAMILIES)
            and metric.loudness_dip_lu > load_settings().max_loudness_dip_lu
            and metric.drift_ms is not None
            and metric.drift_ms < load_settings().max_drift_ms
            and metric.low_overlap_bars is not None
            and metric.low_overlap_bars <= load_settings().max_low_overlap_bars
            and metric.clicks == 0
        ):
            candidate.seam_gain_db = min(6.0, metric.loudness_dip_lu * 1.5)
            repaired_script = _candidate_script(
                candidate, analyses, alternatives=shortlist, rejected=plan.rejected
            )
            pcm, seam, inspection = excerpt(candidate, repaired_script)
            metric = verify_seam(
                pcm,
                seam,
                round(candidate.duration * SAMPLE_RATE),
                bpm=candidate.bpm or 120,
                inspection=inspection,
                max_dip=load_settings().max_loudness_dip_lu,
                max_peak=load_settings().max_true_peak_dbtp,
                max_drift=load_settings().max_drift_ms,
                max_low_overlap=load_settings().max_low_overlap_bars,
            )
            checks.append({"candidate": candidate.id + "_gain_adjusted", **metric.as_dict()})
        if candidate in shortlist:
            start = max(0, seam - 15 * SAMPLE_RATE)
            preview = folder / f"preview-{candidate.id}.wav"
            write_audio(preview, pcm[start : min(len(pcm), start + 30 * SAMPLE_RATE)])
            _encode_preview(preview)
        if not metric.passed:
            failures[candidate.family] = failures.get(candidate.family, 0) + 1
        if metric.passed and chosen is None:
            chosen, measured = candidate, metric
        if chosen is not None and all(
            any((folder / f"preview-{item.id}{ext}").exists() for ext in (".opus", ".wav"))
            for item in shortlist
        ):
            break
    if chosen is None:
        bpm = analyses[0].global_bpm or 120.0
        duration = 2 * analyses[0].meter * 60 / bpm
        chosen = Candidate(
            "fallback",
            "trim_crossfade",
            max(0.0, analyses[0].duration - analyses[0].edges.silence_tail - duration),
            analyses[1].edges.silence_head,
            2,
            bpm,
            "no_sync",
        )
        fallback = _candidate_script(
            chosen, analyses, alternatives=shortlist, rejected=plan.rejected
        )
        pcm, seam, inspection = excerpt(chosen, fallback)
        measured = verify_seam(
            pcm,
            seam,
            round(chosen.duration * SAMPLE_RATE),
            bpm=bpm,
            inspection=inspection,
        )
        checks.append({"candidate": "fallback", **measured.as_dict()})
    if chosen.id == "fallback" and measured and measured.loudness_dip_lu > 1.5:
        chosen.seam_gain_db = min(6.0, measured.loudness_dip_lu * 1.5)
        fallback = _candidate_script(
            chosen, analyses, alternatives=shortlist, rejected=plan.rejected
        )
        pcm, seam, inspection = excerpt(chosen, fallback)
        measured = verify_seam(
            pcm,
            seam,
            round(chosen.duration * SAMPLE_RATE),
            bpm=chosen.bpm or 120,
            inspection=inspection,
        )
        checks.append({"candidate": "fallback_boost", **measured.as_dict()})
    if measured is None or not measured.passed:
        raise ValueError(
            f"no candidate passed verification: {measured.reason if measured else 'unknown'}"
        )
    if chosen not in shortlist:
        shortlist[-1] = chosen
    rejected = plan.rejected
    script = _candidate_script(chosen, analyses, alternatives=shortlist, rejected=rejected)
    if not any((folder / f"preview-{chosen.id}{ext}").exists() for ext in (".opus", ".wav")):
        pcm, seam, _ = excerpt(chosen, script)
        start = max(0, seam - 15 * SAMPLE_RATE)
        preview = folder / f"preview-{chosen.id}.wav"
        write_audio(preview, pcm[start : min(len(pcm), start + 30 * SAMPLE_RATE)])
        _encode_preview(preview)
    explanation = script.transitions[0].explanation
    if explanation is not None:
        explanation.chosen_because = (
            f"Selected {chosen.family} after {len(checks)} verification checks; "
            f"drift {_fmt(measured.drift_ms, 'ms')}, "
            f"loudness dip {measured.loudness_dip_lu:.2f} LU, "
            f"peak {measured.true_peak_dbtp:.2f} dBTP."
        )
    full_stems = (
        (
            stems_for(analyses[0], audio_a.samples, "exit", load_settings().cache_dir),
            stems_for(analyses[1], audio_b.samples, "entry", load_settings().cache_dir),
        )
        if chosen.family in STEM_FAMILIES
        else None
    )
    rendered = render_transition(audio_a.samples, audio_b.samples, script, stems=full_stems)
    for summary in script.transitions[0].candidates:
        for extension in (".opus", ".wav"):
            preview = folder / f"preview-{summary.id}{extension}"
            if preview.exists():
                summary.preview_artifact = preview.name
                break
    referenced = {
        summary.preview_artifact
        for summary in script.transitions[0].candidates
        if summary.preview_artifact
    }
    for preview in folder.glob("preview-*"):
        if (
            preview.is_file()
            and preview.suffix in (".wav", ".opus")
            and preview.name not in referenced
        ):
            preview.unlink()
    checkpoint(progress, cancel, "report", 0.0)
    from mixconsole.mixscript import dumps_mixscript

    destination.parent.mkdir(parents=True, exist_ok=True)
    assert rendered is not None
    assert measured is not None
    write_audio(destination, rendered)
    plan_path = folder / "plan.mixscript.json"
    plan_path.write_text(dumps_mixscript(script), encoding="utf-8")
    report_json = folder / "report.json"
    report_json.write_text(
        json.dumps(
            {
                "mixscript": json.loads(dumps_mixscript(script)),
                "chosen_id": chosen.id,
                "metrics": measured.as_dict(),
                "verification": checks,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report_html = write_html(folder / "report.html", script, analyses[0], analyses[1], checks)
    checkpoint(progress, cancel, "report", 1.0)
    return MixResult(
        script,
        chosen.id,
        measured,
        {
            "audio": destination,
            "mixscript": plan_path,
            "report_json": report_json,
            "report_html": report_html,
        },
    )
