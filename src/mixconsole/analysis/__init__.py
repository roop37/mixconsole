"""Core analysis API. Neural packages and weights are never imported by default."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast

from mixconsole.analysis import cache, registry
from mixconsole.analysis.features import extract
from mixconsole.analysis.interfaces import VocalContext
from mixconsole.analysis.models import ArrayRef, TrackAnalysis
from mixconsole.analysis.structure import bar_sections, bars_and_energy, phrases, tempo_map
from mixconsole.io import file_sha256, load_audio
from mixconsole.progress import CancelToken, Progress, checkpoint

__all__ = ["TrackAnalysis", "analyze"]


def analyze(
    path: str | Path,
    *,
    backends: Mapping[str, str] | None = None,
    use_cache: bool = True,
    cache_dir: str | Path | None = None,
    progress: Progress | None = None,
    cancel: CancelToken | None = None,
) -> TrackAnalysis:
    """Analyze local audio using named backends, with transparent optional fallback.

    `backends` keys: beats, key, loudness, sections, cues, vocals. The fixed analysis seed
    is zero. `use_cache=False` performs no cache reads/writes. Long numeric arrays
    are available in `result.arrays`; use cache.save_analysis for portable export.
    """

    def stage(name: str, fraction: float) -> None:
        checkpoint(progress, cancel, name, fraction, str(path))

    stage("cache", 0.0)
    source = Path(path)
    names = registry.selection(backends)
    versions = registry.versions(names)
    root = cache.cache_root(cache_dir)
    digest = file_sha256(source)
    if use_cache:
        pcm = cache.read_index(root, digest)
        if pcm:
            result = cache.read_cached(cache.cache_path(root, pcm, versions))
            if (
                result is not None
                and result.backend_versions == versions
                and result.pcm_sha256 == pcm
            ):
                result.file = str(source)
                result.file_sha256 = digest
                stage("complete", 1.0)
                return result
    stage("decode", 0.1)
    audio = load_audio(source)
    if use_cache:
        result = cache.read_cached(cache.cache_path(root, audio.pcm_sha256, versions))
        if result is not None and result.backend_versions == versions:
            result.file = str(source)
            result.file_sha256 = audio.file_sha256
            cache.atomic_write(
                root / "files" / f"{digest}.json",
                json.dumps({"pcm_sha256": audio.pcm_sha256}).encode(),
            )
            stage("complete", 1.0)
            return result
    stage("features", 0.2)
    features = extract(audio.samples, audio.sample_rate)
    stage("beats", 0.3)
    beats = registry.run(
        "beats", names, lambda name: registry.BEATS[name].analyze(features, audio.sample_rate)
    )
    stage("key", 0.4)
    key = registry.run("key", names, lambda name: registry.KEYS[name].analyze(features))
    stage("loudness", 0.5)
    loudness, curve = registry.run(
        "loudness",
        names,
        lambda name: registry.LOUDNESS[name].analyze(audio.samples, audio.sample_rate),
    )
    stage("sections", 0.6)
    sections = registry.run(
        "sections", names, lambda name: registry.SECTIONS[name].analyze(features, audio.duration)
    )
    bpm, tempo = tempo_map(beats.beats, audio.duration)
    stage("cues", 0.7)
    edges = registry.run(
        "cues",
        names,
        lambda name: registry.CUES[name].analyze(audio.samples, audio.sample_rate, bpm),
    )
    stage("structure", 0.8)
    bars, energy = bars_and_energy(features, beats.downbeats, audio.duration, audio.sample_rate)
    stage("vocals", 0.85)
    vocals = registry.run(
        "vocals",
        names,
        lambda name: registry.VOCALS[name].analyze(
            VocalContext(
                audio.samples,
                audio.pcm_sha256,
                audio.duration,
                beats.beats,
                bars,
                edges,
                features,
                root if use_cache else None,
            )
        ),
    )
    result = TrackAnalysis(
        file=str(source),
        file_sha256=audio.file_sha256,
        pcm_sha256=audio.pcm_sha256,
        duration=audio.duration,
        sample_rate=audio.sample_rate,
        beats=beats.beats,
        beat_confidence=beats.confidence,
        downbeats=beats.downbeats,
        meter=cast(Literal[3, 4], beats.meter),
        tempo_map=tempo,
        global_bpm=bpm,
        bars=bars,
        phrases=phrases(features, bars, energy),
        sections=bar_sections(features, bars, energy, audio.duration, sections),
        key=key,
        loudness=loudness,
        bar_energy=ArrayRef(
            key="bar_energy",
            shape=list(energy.shape),
            columns=["rms", "onset_strength", "low", "mid", "high"],
        ),
        edges=edges,
        vocal_activity=vocals.activity,
        stems=vocals.stems,
        backend_versions=registry.versions(names),
    )
    stage("cache_write", 0.9)
    result.arrays.update(short_term_lufs=curve, bar_energy=energy)
    if use_cache:
        directory = cache.cache_path(root, audio.pcm_sha256, result.backend_versions)
        cache.save_analysis(result, directory / "analysis.json")
        cache.atomic_write(
            root / "files" / f"{digest}.json", json.dumps({"pcm_sha256": audio.pcm_sha256}).encode()
        )
    stage("complete", 1.0)
    return result
