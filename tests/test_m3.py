"""M3 stems + vocals: oracle (ground-truth) stems, constraints, render, verify, fallbacks."""

import io
import json
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from mixconsole.analysis import analyze, model_manager, registry
from mixconsole.analysis.backends import stems as stem_backend
from mixconsole.analysis.backends.vocals import HeuristicVocalBackend
from mixconsole.analysis.models import TrackAnalysis
from mixconsole.cli import app
from mixconsole.config import Settings
from mixconsole.io import SAMPLE_RATE, load_audio, write_audio
from mixconsole.mixscript import dumps_mixscript, load_mixscript
from mixconsole.plan import vocals as vq
from mixconsole.plan.candidates import Candidate, plan_pair
from mixconsole.plan.constraints import rejection_reason
from mixconsole.plan.families import families
from mixconsole.render.graph import STEM_FAMILIES, RenderInspection, render_transition
from mixconsole.score.heuristic import _PRIOR, key_reliability, score
from mixconsole.service import _candidate_script, mix_pair, stems_for
from mixconsole.testing.synth import generate_track
from mixconsole.verify.metrics import (
    bass_overlap_bars,
    verify_seam,
    vocal_overlap_seconds,
)
from tests.oracle import OracleSeparator, oracle_track

A_VOCALS = tuple(range(20, 26))
B_VOCALS = (*range(3), *range(8, 14), *range(20, 30))
settings = Settings().model_copy(update={"stems": "on"})


@dataclass
class Pair:
    root: Path
    oracle: OracleSeparator = field(default_factory=OracleSeparator)

    def build(self, patch: pytest.MonkeyPatch, key_b: str = "C major") -> "Pair":
        patch.setattr(registry, "stems_available", lambda: True)
        patch.setattr(stem_backend, "_separator", self.oracle)
        self.cache = self.root / "cache"
        self.audio_a = oracle_track(self.oracle, vocal_bars=A_VOCALS, seed=1)
        self.audio_b = oracle_track(self.oracle, vocal_bars=B_VOCALS, seed=2, key=key_b)
        self.path_a, self.path_b = self.root / "a.wav", self.root / "b.wav"
        write_audio(self.path_a, self.audio_a)
        write_audio(self.path_b, self.audio_b)
        self.a = analyze(self.path_a, backends={"vocals": "stems"}, cache_dir=self.cache)
        self.b = analyze(self.path_b, backends={"vocals": "stems"}, cache_dir=self.cache)
        return self

    a: TrackAnalysis = field(init=False)
    b: TrackAnalysis = field(init=False)


@pytest.fixture(scope="module")
def pair(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Pair]:
    patch = pytest.MonkeyPatch()
    yield Pair(tmp_path_factory.mktemp("m3-pair")).build(patch)
    patch.undo()


@pytest.fixture(scope="module")
def clash(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Pair]:
    patch = pytest.MonkeyPatch()
    yield Pair(tmp_path_factory.mktemp("m3-clash")).build(patch, key_b="F# major")
    patch.undo()


def stem_candidates(p: Pair, family: str | None = None) -> list[Candidate]:
    result = plan_pair(p.a, p.b, settings)
    return [c for c in result.candidates if c.family in ((family and (family,)) or STEM_FAMILIES)]


def render_candidate(p: Pair, candidate: Candidate) -> tuple[RenderInspection, np.ndarray, int]:
    script = _candidate_script(candidate, [p.a, p.b], alternatives=[candidate], rejected=[])
    stems = (
        stems_for(p.a, p.audio_a, "exit", p.cache),
        stems_for(p.b, p.audio_b, "entry", p.cache),
    )
    inspection = RenderInspection()
    pcm = render_transition(p.audio_a, p.audio_b, script, inspection=inspection, stems=stems)
    return inspection, pcm, round(candidate.exit_seconds * SAMPLE_RATE)


# ---- vocal activity -------------------------------------------------------------------


def test_stem_vocal_bars_are_exact(pair: Pair) -> None:
    activity = pair.a.vocal_activity
    assert activity is not None
    assert activity.source == "stem"
    assert activity.confidence >= 0.8
    voiced = {i for i, fraction in enumerate(activity.per_bar) if fraction > 0.2}
    assert voiced == set(A_VOCALS)
    assert len(activity.per_bar) == len(pair.a.bars)
    assert len(activity.per_beat) == len(pair.a.beats)
    beats_per_bar = 4
    for bar in A_VOCALS:
        beats = activity.per_beat[bar * beats_per_bar : (bar + 1) * beats_per_bar]
        assert max(beats) > 0.5  # bursts occupy beats 1-2 of each bar
    b_voiced = {i for i, f in enumerate(pair.b.vocal_activity.per_bar) if f > 0.2}  # type: ignore[union-attr]
    assert b_voiced == set(B_VOCALS)


def test_lyric_gaps_are_at_least_300ms_and_follow_vocal_spans(pair: Pair) -> None:
    activity = pair.a.vocal_activity
    assert activity is not None
    assert all(g.end - g.start >= 0.3 - 1e-9 for g in activity.gaps)
    assert all(
        not any(s.start < g.end and g.start < s.end for s in activity.spans) for g in activity.gaps
    )
    # Within the vocal run (bars 20-25) the gaps are the ~1 s between bursts.
    inside = [g for g in activity.gaps if 20 * 1.875 < g.start < 25 * 1.875]
    assert len(inside) >= 4


def test_stems_info_records_windows_and_checkpoint(pair: Pair) -> None:
    info = pair.a.stems
    assert info is not None
    assert [w.role for w in info.windows] == ["exit", "entry"]
    assert info.model == stem_backend.MODEL_VERSION
    assert info.checkpoint_sha256 == model_manager.HTDEMUCS_SHA256
    assert pair.a.backend_versions["vocals"].startswith("stems@")
    assert pair.a.backend_versions["stems_checkpoint"] == model_manager.HTDEMUCS_SHA256


def test_heuristic_vocals_work_without_stems(tmp_path: Path) -> None:
    audio, truth = generate_track(bpm=128, bars=24, vocal_bars=tuple(range(8, 16)), seed=3)
    path = write_audio(tmp_path / "h.wav", audio)
    result = analyze(path, use_cache=False)
    activity = result.vocal_activity
    assert activity is not None
    assert activity.source == "heuristic"
    assert activity.confidence < 0.5
    assert result.stems is None
    assert len(activity.per_bar) == len(result.bars)
    assert HeuristicVocalBackend().name == "heuristic"
    assert truth["vocal_regions"]


def test_stems_request_without_extra_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "stems_available", lambda: False)
    assert registry.selection({"vocals": "stems"})["vocals"] == "heuristic"
    monkeypatch.setenv("MIXCONSOLE_STEMS", "auto")
    assert registry.selection(None)["vocals"] == "heuristic"
    monkeypatch.setattr(registry, "stems_available", lambda: True)
    assert registry.selection(None)["vocals"] == "stems"
    monkeypatch.setenv("MIXCONSOLE_STEMS", "off")
    assert registry.selection(None)["vocals"] == "heuristic"
    with pytest.raises(ValueError, match="unknown backend"):
        registry.selection({"vocals": "nope"})


def test_stem_failure_falls_back_to_heuristic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Broken:
        name, version = "htdemucs", "broken"

        def separate(self, audio: np.ndarray, start_frame: int) -> dict[str, np.ndarray]:
            raise RuntimeError("model crashed")

    monkeypatch.setattr(registry, "stems_available", lambda: True)
    monkeypatch.setattr(stem_backend, "_separator", Broken())
    audio, _ = generate_track(bpm=120, bars=8, seed=5)
    result = analyze(
        write_audio(tmp_path / "x.wav", audio), backends={"vocals": "stems"}, use_cache=False
    )
    assert result.vocal_activity is not None
    assert result.vocal_activity.source == "heuristic"
    assert result.backend_versions["vocals"].startswith("heuristic@")


# ---- stems: cache, null test, latency -------------------------------------------------


def test_null_test_stems_resum_to_original(pair: Pair) -> None:
    window = stem_backend.window_frames("exit", pair.a.duration, 0.0, pair.a.edges.silence_tail)
    stems = stem_backend.separate_window(
        pair.audio_a, pair.a.pcm_sha256, window, cache_root=pair.cache, separator=pair.oracle
    )
    original = pair.audio_a[window[0] : window[1]]
    summed = stem_backend.resum(stems.stems)
    error = float(np.sqrt(np.mean((summed - original) ** 2)))
    reference = float(np.sqrt(np.mean(original**2)))
    assert 20 * np.log10(error / reference + 1e-12) < -60
    gains = {"vocals": 0.0}
    without_vocals = stem_backend.resum(stems.stems, gains)
    assert not np.allclose(without_vocals, original)


def test_resum_compensates_latency() -> None:
    rng = np.random.default_rng(0)
    base = (rng.standard_normal((4000, 2)) * 0.1).astype(np.float32)
    delayed = np.concatenate((np.zeros((300, 2), np.float32), base))[:4000]
    summed = stem_backend.resum({"a": delayed, "b": base}, latency_frames={"a": 300})
    expected = base.copy()
    expected[: 4000 - 300] += base[: 4000 - 300]
    assert np.allclose(summed[:3000], expected[:3000], atol=1e-6)
    stem_set = stem_backend.StemSet(100, {"a": delayed}, {"a": 300})
    aligned = stem_backend.compensate(stem_set)
    assert aligned.latency_frames == {"a": 0}
    assert np.allclose(aligned.stems["a"][:3000], base[:3000])
    plain = stem_backend.StemSet(0, {"a": base})
    assert stem_backend.compensate(plain) is plain


def test_stem_cache_is_keyed_by_pcm_window_and_model(pair: Pair, tmp_path: Path) -> None:
    window = (0, 44100 * 5)
    samples = pair.audio_a
    calls = pair.oracle.calls
    first = stem_backend.separate_window(
        samples, pair.a.pcm_sha256, window, cache_root=tmp_path, separator=pair.oracle
    )
    assert pair.oracle.calls == calls + 1
    again = stem_backend.separate_window(
        samples, pair.a.pcm_sha256, window, cache_root=tmp_path, separator=pair.oracle
    )
    assert pair.oracle.calls == calls + 1  # cache hit
    assert np.array_equal(first.stems["vocals"], again.stems["vocals"])
    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert files == [
        f"stems/{pair.a.pcm_sha256}/oracle@1/0-220500.json",
        f"stems/{pair.a.pcm_sha256}/oracle@1/0-220500.npz",
    ]
    stem_backend.separate_window(
        samples, pair.a.pcm_sha256, (0, 44100 * 6), cache_root=tmp_path, separator=pair.oracle
    )
    assert pair.oracle.calls == calls + 2  # a different window is a different entry
    # A corrupt entry is recomputed rather than trusted.
    (tmp_path / files[1]).write_bytes(b"corrupt")
    stem_backend.separate_window(
        samples, pair.a.pcm_sha256, window, cache_root=tmp_path, separator=pair.oracle
    )
    assert pair.oracle.calls == calls + 3
    sliced = first.slice(-100, 200)
    assert sliced["drums"].shape == (300, 2)
    assert not sliced["drums"][:100].any()


def test_windows_are_at_most_sixty_seconds_of_the_music() -> None:
    start, end = stem_backend.window_frames("exit", 300.0, 1.0, 4.0)
    assert (end - start) / SAMPLE_RATE == 60.0
    assert end / SAMPLE_RATE == 296.0
    start, end = stem_backend.window_frames("entry", 300.0, 2.0, 4.0)
    assert (start / SAMPLE_RATE, (end - start) / SAMPLE_RATE) == (2.0, 60.0)
    start, end = stem_backend.window_frames("exit", 20.0, 0.0, 0.0)
    assert (start, end / SAMPLE_RATE) == (0, 20.0)


# ---- planning: families, constraints, guarantees ---------------------------------------


def test_stem_families_plan_and_never_overlap_vocals_or_bass(pair: Pair) -> None:
    found = stem_candidates(pair)
    assert {c.family for c in found} >= {"stem_handoff"}
    assert all(c.variant == "classic" for c in found if c.family == "stem_handoff")
    checked = 0
    for candidate in found[:6]:
        inspection, pcm, _ = render_candidate(pair, candidate)
        assert np.isfinite(pcm).all()
        beat = 60 / (candidate.bpm or 120)
        assert (vocal_overlap_seconds(inspection) or 0.0) <= beat + 1e-9
        assert bass_overlap_bars(inspection, candidate.bpm or 120, 4) == 0.0
        checked += 1
    assert checked >= 3  # six candidates are rendered and measured


def test_vocal_exit_happens_at_a_lyric_gap(pair: Pair) -> None:
    activity = pair.a.vocal_activity
    assert activity is not None
    for candidate in stem_candidates(pair, "stem_handoff"):
        out_beat = candidate.params["vocal_out_beat"]
        moment = candidate.exit_seconds + (out_beat - 0.1) * 60 / (candidate.bpm or 120)
        in_gap = any(g.start - 1e-6 <= moment < g.end for g in activity.gaps)
        assert in_gap or not vq.active_at(activity, moment)
        # B's vocals enter strictly after A's have faded out.
        assert candidate.params["vocal_in_beat"] >= out_beat + 0.5


def test_vocal_over_instrumental_requires_key_and_vocal_free_intro(pair: Pair, clash: Pair) -> None:
    ok = plan_pair(pair.a, pair.b, settings)
    reasons = {r.reason for r in ok.rejected if r.family == "vocal_over_instrumental"}
    assert "incoming track has vocals in its intro" in reasons
    # B's vocals start at beat 0 so the pure acapella-over-intro never survives here.
    assert not [c for c in ok.candidates if c.family == "vocal_over_instrumental"]
    bad_key = plan_pair(clash.a, clash.b, settings)
    key_reasons = {r.reason for r in bad_key.rejected if r.family == "vocal_over_instrumental"}
    assert any("keys are not compatible" in r for r in key_reasons)


def test_vocal_over_instrumental_with_clean_intro(tmp_path: Path) -> None:
    patch = pytest.MonkeyPatch()
    try:
        patch.setattr(registry, "stems_available", lambda: True)
        oracle = OracleSeparator()
        patch.setattr(stem_backend, "_separator", oracle)
        audio_a = oracle_track(oracle, vocal_bars=tuple(range(18, 27)), seed=11)
        audio_b = oracle_track(oracle, vocal_bars=tuple(range(20, 30)), seed=12)
        write_audio(tmp_path / "a.wav", audio_a)
        write_audio(tmp_path / "b.wav", audio_b)
        a = analyze(tmp_path / "a.wav", backends={"vocals": "stems"}, cache_dir=tmp_path / "c")
        b = analyze(tmp_path / "b.wav", backends={"vocals": "stems"}, cache_dir=tmp_path / "c")
        pair = Pair(tmp_path)
        pair.a, pair.b, pair.audio_a, pair.audio_b, pair.cache = (
            a,
            b,
            audio_a,
            audio_b,
            tmp_path / "c",
        )
        found = stem_candidates(pair, "vocal_over_instrumental")
        assert found
        candidate = found[0]
        assert candidate.variant == "acapella"
        inspection, _, _ = render_candidate(pair, candidate)
        assert bass_overlap_bars(inspection, candidate.bpm or 120, 4) == 0.0
        assert (vocal_overlap_seconds(inspection) or 0.0) <= 60 / (candidate.bpm or 120)
        # A's vocals are audible while A's drums are not (acapella over B's instrumental).
        vocals_a = inspection.stem_contributions["a:vocals"]
        drums_a = inspection.stem_contributions["a:drums"]
        quarter = len(vocals_a) // 4
        assert float(np.abs(vocals_a[:quarter]).max()) > 0.01
        assert float(np.abs(drums_a[-quarter:]).max()) < 1e-6
    finally:
        patch.undo()


def test_key_clash_uses_a_drums_only_handoff(clash: Pair) -> None:
    found = stem_candidates(clash, "stem_handoff")
    assert found
    assert all(c.variant == "drums_only" for c in found)
    for candidate in found[:3]:
        inspection, _, _ = render_candidate(clash, candidate)
        # Only the drums may overlap; harmony and vocals never do.
        for stem in ("bass", "other", "vocals"):
            left = inspection.stem_contributions[f"a:{stem}"]
            right = inspection.stem_contributions[f"b:{stem}"]
            # Sample-wise: wherever A's stem is non-zero B's is exactly zero.
            assert float((np.abs(left) * np.abs(right)).max()) == 0.0, stem
        drums_a = inspection.stem_contributions["a:drums"]
        drums_b = inspection.stem_contributions["b:drums"]
        both = (np.abs(drums_a).max(axis=1) > 1e-3) & (np.abs(drums_b).max(axis=1) > 1e-3)
        assert both.any()


def test_key_clash_competes_and_is_weighted_by_key_confidence(clash: Pair) -> None:
    plan = plan_pair(clash.a, clash.b, settings)
    families_found = {c.family for c in plan.candidates}
    assert "stem_handoff" in families_found
    drums_only = next(c for c in plan.candidates if c.family == "stem_handoff")
    assert drums_only.features["family_prior"] == pytest.approx(1.0)
    blend = replace(drums_only, family="beatmatch_blend", variant="")
    assert score(blend, clash.a, clash.b, "auto")["family_prior"] == pytest.approx(0.25)
    # An unreliable key estimate weakens the clash rule (it blends towards the normal prior).
    unsure_a = clash.a.model_copy(deep=True)
    unsure_a.key.confidence = 0.1
    weak = score(blend, unsure_a, clash.b, "auto")
    assert weak["family_prior"] > 0.25
    assert key_reliability(unsure_a, clash.b) < key_reliability(clash.a, clash.b) == 1.0
    chance = clash.a.model_copy(deep=True)
    chance.key.confidence = 1 / 24
    assert key_reliability(chance, clash.b) == 0.0
    # With zero key reliability the clash rule has no weight: the normal blend prior returns.
    assert score(blend, chance, clash.b, "auto")["family_prior"] == pytest.approx(
        _PRIOR["auto"]["beatmatch_blend"]
    )


def test_blends_with_colliding_stem_vocals_are_rejected(pair: Pair) -> None:
    plan = plan_pair(pair.a, pair.b, settings)
    reasons = [r.reason for r in plan.rejected if r.family in ("beatmatch_blend", "trim_crossfade")]
    assert any(r.startswith("lead vocals would overlap") for r in reasons)
    survivors = [c for c in plan.candidates if c.family not in STEM_FAMILIES and c.length_bars]
    for candidate in survivors:
        assert rejection_reason(pair.a, pair.b, candidate, settings, {}) is None


def test_without_stems_the_families_are_not_applicable(tmp_path: Path) -> None:
    audio, _ = generate_track(bpm=128, bars=32, vocal_bars=(10, 11), seed=8)
    path = write_audio(tmp_path / "plain.wav", audio)
    a = analyze(path, use_cache=False)
    b = analyze(path, use_cache=False)
    assert a.stems is None
    result = plan_pair(a, b, settings)
    assert not [c for c in result.candidates if c.family in STEM_FAMILIES]
    reasons = {r.family: r.reason for r in result.rejected if r.candidate_id.endswith("_na")}
    assert set(reasons) == set(STEM_FAMILIES)
    assert all("install the 'stems' extra" in r for r in reasons.values())
    assert any(f.name == "stem_handoff" for f in families())


def test_stem_families_need_a_beatmatchable_pair(tmp_path: Path, pair: Pair) -> None:
    slow = pair.b.model_copy(deep=True)
    slow.global_bpm = 90.0  # >8 % away: no_sync
    result = plan_pair(pair.a, slow, settings)
    assert not [c for c in result.candidates if c.family in STEM_FAMILIES]
    assert any(
        r.reason == "stem transitions need a beatmatchable pair"
        for r in result.rejected
        if r.family == "stem_handoff"
    )


# ---- render + verify -------------------------------------------------------------------


def test_stem_render_is_deterministic_and_needs_stems(pair: Pair) -> None:
    candidate = stem_candidates(pair, "stem_handoff")[0]
    _, first, _ = render_candidate(pair, candidate)
    _, second, _ = render_candidate(pair, candidate)
    assert np.array_equal(first, second)
    script = _candidate_script(candidate, [pair.a, pair.b], alternatives=[candidate], rejected=[])
    with pytest.raises(ValueError, match="needs separated stems"):
        render_transition(pair.audio_a, pair.audio_b, script)
    lanes = script.transitions[0].automation
    assert {(lane.target.kind, getattr(lane.target, "stem", None)) for lane in lanes} == {
        ("stem", s) for s in ("drums", "bass", "other", "vocals")
    }
    assert len(lanes) == 8
    assert load_mixscript_roundtrip(script)


def load_mixscript_roundtrip(script) -> bool:  # type: ignore[no-untyped-def]
    from mixconsole.mixscript import MixScript

    again = MixScript.model_validate_json(dumps_mixscript(script))
    return dumps_mixscript(again) == dumps_mixscript(script)


def test_verify_measures_vocal_and_bass_overlap_on_stems() -> None:
    frames = SAMPLE_RATE * 8
    t = np.arange(frames) / SAMPLE_RATE
    tone = (0.3 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    stereo = np.stack((tone, tone), axis=1)
    silent = np.zeros_like(stereo)
    quiet = stereo * np.float32(0.0)
    inspection = RenderInspection(
        contribution_a=stereo,
        contribution_b=stereo,
        stem_contributions={
            "a:vocals": stereo,
            "b:vocals": np.concatenate((silent[: frames // 2], stereo[: frames // 2])),
            "a:bass": stereo,
            "b:bass": np.concatenate((quiet[: frames // 4], stereo[: frames * 3 // 4])),
        },
    )
    assert vocal_overlap_seconds(inspection) == pytest.approx(4.0, abs=0.05)
    # 6 s of simultaneous bass at 120 BPM / 4 beats per bar is 3 bars.
    assert bass_overlap_bars(inspection, 120.0, 4) == pytest.approx(3.0, abs=0.05)
    mix = np.concatenate((stereo, stereo))
    metrics = verify_seam(mix, frames, frames, bpm=120.0, inspection=inspection)
    assert not metrics.passed
    assert "vocal overlap" in metrics.reason
    assert "low-band overlap" in metrics.reason
    assert metrics.vocal_overlap_seconds == pytest.approx(4.0, abs=0.05)
    assert metrics.bass_overlap_bars == pytest.approx(3.0, abs=0.05)
    assert verify_seam(mix, frames, 0, bpm=120.0).vocal_overlap_seconds is None
    assert vocal_overlap_seconds(None) is None
    assert bass_overlap_bars(RenderInspection(), 120.0, 4) is None


# ---- end to end ------------------------------------------------------------------------


def test_mix_pair_with_stems_end_to_end(
    pair: Pair, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MIXCONSOLE_STEMS", "auto")
    monkeypatch.setenv("MIXCONSOLE_WORKERS", "1")
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(pair.cache))
    monkeypatch.setenv("MIXCONSOLE_CANDIDATES_PER_FAMILY", "3")
    monkeypatch.setenv("MIXCONSOLE_MAX_CANDIDATES", "12")
    result = mix_pair(
        pair.path_a, pair.path_b, out=tmp_path / "mix.wav", report_dir=tmp_path / "r", candidates=3
    )
    assert result.metrics is not None
    assert result.metrics.passed
    script = result.mixscript
    assert script.transitions[0].family in STEM_FAMILIES
    assert result.metrics.vocal_overlap_seconds is not None
    assert result.metrics.vocal_overlap_seconds <= 60 / (
        script.transitions[0].tempo.tempo_map[0].bpm
    )
    assert result.metrics.bass_overlap_bars == 0.0
    page = result.paths["report_html"].read_text()
    assert "Vocal overlap (s)" in page
    report = json.loads(result.paths["report_json"].read_text())
    assert report["metrics"]["bass_overlap_bars"] == 0.0
    assert load_mixscript(result.paths["mixscript"]).transitions[0].automation
    # `mixconsole render` replays the plan from the cached stems.
    out = tmp_path / "replay.wav"
    run = CliRunner().invoke(
        app,
        [
            "render",
            str(result.paths["mixscript"]),
            "--track",
            f"deck_a={pair.path_a}",
            "--track",
            f"deck_b={pair.path_b}",
            "-o",
            str(out),
        ],
    )
    assert run.exit_code == 0, run.output
    assert np.array_equal(load_audio(out).samples, load_audio(result.paths["audio"]).samples)


def test_cli_render_reports_missing_stems(
    pair: Pair, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = stem_candidates(pair, "stem_handoff")[0]
    script = _candidate_script(candidate, [pair.a, pair.b], alternatives=[candidate], rejected=[])
    plan = tmp_path / "plan.json"
    plan.write_text(dumps_mixscript(script))
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "empty-cache"))
    monkeypatch.setenv("MIXCONSOLE_STEMS", "off")
    run = CliRunner().invoke(
        app,
        [
            "render",
            str(plan),
            "--track",
            f"deck_a={pair.path_a}",
            "--track",
            f"deck_b={pair.path_b}",
            "-o",
            str(tmp_path / "x.wav"),
        ],
    )
    assert run.exit_code == 1
    assert "stems extra" in run.output


def test_stems_for_requires_windows(pair: Pair) -> None:
    plain = pair.a.model_copy(update={"stems": None})
    with pytest.raises(ValueError, match="stems extra"):
        stems_for(plain, pair.audio_a, "exit", pair.cache)


# ---- model manager and CLI -------------------------------------------------------------


def test_htdemucs_model_manager_is_checksum_pinned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("MIXCONSOLE_HTDEMUCS_DIR", raising=False)
    assert (
        model_manager.htdemucs_path() == tmp_path / "models" / "htdemucs" / "955717e8-8726e21a.th"
    )
    assert model_manager.HTDEMUCS_SHA256.startswith("8726e21a")  # file name embeds the prefix
    monkeypatch.setattr(model_manager, "urlopen", lambda *_a, **_k: io.BytesIO(b"tampered"))
    with pytest.raises(ValueError, match="hash mismatch"):
        model_manager.fetch_htdemucs()
    assert not list((tmp_path / "models" / "htdemucs").glob(".htdemucs-*"))
    target = model_manager.htdemucs_path()
    target.write_bytes(b"bad")
    with pytest.raises(ValueError, match="hash mismatch"):
        model_manager.fetch_htdemucs()
    monkeypatch.setenv("MIXCONSOLE_HTDEMUCS_DIR", str(tmp_path / "elsewhere"))
    assert model_manager.htdemucs_dir() == tmp_path / "elsewhere"
    monkeypatch.setattr(model_manager, "_sha256_file", lambda _p: model_manager.HTDEMUCS_SHA256)
    monkeypatch.setenv("MIXCONSOLE_HTDEMUCS_DIR", str(tmp_path / "models" / "htdemucs"))
    assert model_manager.fetch_htdemucs() == target
    assert stem_backend.available() == (
        __import__("importlib.util").util.find_spec("demucs") is not None
    )


def test_models_fetch_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = CliRunner()
    monkeypatch.setattr(model_manager, "fetch_htdemucs", lambda: tmp_path / "w.th")
    ok = runner.invoke(app, ["models", "fetch", "htdemucs"])
    assert ok.exit_code == 0
    assert model_manager.HTDEMUCS_SHA256 in ok.output

    def fail() -> Path:
        raise ValueError("offline")

    monkeypatch.setattr(model_manager, "fetch_htdemucs", fail)
    assert runner.invoke(app, ["models", "fetch", "htdemucs"]).exit_code == 1
    assert runner.invoke(app, ["models", "fetch", "other"]).exit_code != 0
    monkeypatch.setattr(model_manager, "fetch_beat_this", lambda: tmp_path / "b.ckpt")
    assert runner.invoke(app, ["models", "fetch", "beat_this"]).exit_code == 0


def test_plan_queries() -> None:
    from mixconsole.analysis.models import Span, VocalActivity

    activity = VocalActivity(
        source="stem",
        confidence=0.9,
        stem_regions=[Span(start=0, end=20)],
        spans=[Span(start=1, end=3), Span(start=5, end=6)],
        gaps=[Span(start=3, end=5), Span(start=6, end=9)],
        per_bar=[],
        per_beat=[],
    )
    assert vq.next_gap_time(activity, 0.5, 4) == 0.5  # already vocal free
    assert vq.next_gap_time(activity, 2.0, 4) == 3.0
    assert vq.next_gap_time(activity, 2.0, 2.5) is None
    assert vq.covered(activity.spans, 0, 10) == pytest.approx(3.0)
    assert vq.active_at(activity, 2.0)
    assert not vq.active_at(None, 2.0)
    other = activity.model_copy(deep=True)
    assert vq.overlap_seconds(activity, other, 0, 0, 10, 1.0) == pytest.approx(3.0)
    assert vq.overlap_seconds(activity, other, 0, 1, 10, 1.0) == pytest.approx(1.0)


def test_demucs_separator_runs_a_tiny_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exercises the real DemucsSeparator code path with a random tiny HDemucs (no weights)."""
    pytest.importorskip("demucs")
    from importlib import import_module

    hdemucs = import_module("demucs.hdemucs")
    pretrained = import_module("demucs.pretrained")
    model = hdemucs.HDemucs(channels=4, sources=list(stem_backend.STEM_NAMES))
    model.eval()
    loads: list[str] = []

    def fake_get_model(name: str, repo: Path | None = None) -> object:
        loads.append(name)
        return model

    monkeypatch.setenv("MIXCONSOLE_HTDEMUCS_DIR", str(tmp_path))
    monkeypatch.setattr(pretrained, "get_model", fake_get_model)
    monkeypatch.setattr(stem_backend, "_separator", None)
    separator = stem_backend.default_separator("cpu")
    assert stem_backend.default_separator("cpu") is separator
    rng = np.random.default_rng(1)
    audio = (rng.standard_normal((SAMPLE_RATE * 2, 2)) * 0.05).astype(np.float32)
    parts = separator.separate(audio, 0)
    assert set(parts) == set(stem_backend.STEM_NAMES)
    assert all(p.shape == audio.shape and p.dtype == np.float32 for p in parts.values())
    assert separator.last_stats["device"] == "cpu"  # type: ignore[attr-defined]
    assert float(separator.last_stats["seconds"]) > 0  # type: ignore[attr-defined]
    assert float(separator.last_stats["peak_rss_mb"]) > 0  # type: ignore[attr-defined]
    separator.separate(audio, 0)
    assert loads == ["htdemucs"]  # the model is loaded once
    assert (tmp_path / "htdemucs.yaml").is_file()
    folded = stem_backend.separate_window(
        audio, "0" * 64, (0, len(audio)), cache_root=tmp_path / "c", separator=separator
    )
    assert float(np.abs(stem_backend.resum(folded.stems) - audio).max()) < 1e-6
    assert folded.stats["device"] == "cpu"
    assert stem_backend.pick_device("cpu") == "cpu"
    assert stem_backend.pick_device("auto") in ("cpu", "mps", "cuda")
    assert stem_backend.peak_rss_mb() > 0
