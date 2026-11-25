"""M1 acceptance against sample-exact synthetic annotations; no audio assets."""

import json
import os
import subprocess
import sys
import time
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from typer.testing import CliRunner

from mixconsole import TrackAnalysis, analyze
from mixconsole.analysis import registry
from mixconsole.analysis.backends.beats import LibrosaBeatBackend
from mixconsole.analysis.backends.key import ProfileKeyBackend, camelot
from mixconsole.analysis.backends.loudness import PyloudnormBackend
from mixconsole.analysis.cache import (
    cache_info,
    cache_root,
    clear_cache,
    load_analysis,
    save_analysis,
)
from mixconsole.analysis.features import extract
from mixconsole.analysis.models import schema_json
from mixconsole.cli import app
from mixconsole.io import write_audio
from mixconsole.testing.synth import generate_track

ROOT = Path(__file__).resolve().parents[1]
BPMS = (90, 100, 124, 128, 140, 174)
NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def f_measure(actual, expected, tolerance=0.070):
    # One-to-one temporal matching; duplicates cannot inflate precision/recall.
    actual, expected = sorted(actual), sorted(expected)
    i = j = hits = 0
    while i < len(actual) and j < len(expected):
        if abs(actual[i] - expected[j]) <= tolerance:
            hits += 1
            i += 1
            j += 1
        elif actual[i] < expected[j]:
            i += 1
        else:
            j += 1
    return 2 * hits / (len(actual) + len(expected)) if actual or expected else 1.0


@pytest.fixture(scope="session")
def tracks(tmp_path_factory):
    directory = tmp_path_factory.mktemp("analysis")
    results = {}
    for bpm in BPMS:
        audio, truth = generate_track(bpm=bpm, bars=16, seed=23)
        path = write_audio(directory / f"{bpm}.wav", audio)
        results[bpm] = (path, truth, analyze(path, cache_dir=directory / "cache"))
    return results


@pytest.mark.parametrize("bpm", BPMS)
def test_tempo_beats_downbeats_and_phrases(tracks, bpm):
    _, truth, result = tracks[bpm]
    assert abs(result.global_bpm - bpm) <= 0.1
    assert f_measure(result.beats, truth["beat_times"]) >= 0.95
    assert f_measure(result.downbeats, truth["downbeats"]) >= 0.95
    assert result.meter == 4
    assert [p.start for p in result.phrases] == truth["phrase_starts"]
    assert [p.start_bar for p in result.phrases] == [0, 8]
    assert all(p.length_bars == 8 for p in result.phrases)
    assert len(result.bars) == 16
    assert result.arrays["bar_energy"].shape == (16, 5)
    assert len(result.arrays["short_term_lufs"]) == int(np.ceil(result.duration / 0.1))
    assert result.vocal_activity is None


def test_schema_bytes(tracks):
    assert (ROOT / "schemas/track-analysis-v1.json").read_bytes() == schema_json().encode()
    result = tracks[128][2]
    assert (
        TrackAnalysis.model_validate_json(result.model_dump_json()).model_dump()
        == result.model_dump()
    )


@pytest.mark.parametrize("end_bpm", [95, 155])
def test_ramp(tmp_path, end_bpm):
    audio, truth = generate_track(bpm=125, end_bpm=end_bpm, bars=16)
    result = analyze(write_audio(tmp_path / "ramp.wav", audio), use_cache=False)
    assert len(result.tempo_map) >= 2
    assert (result.tempo_map[-1].bpm - result.tempo_map[0].bpm) * (end_bpm - 125) > 0
    assert f_measure(result.beats, truth["beat_times"]) >= 0.95
    assert f_measure(result.downbeats, truth["downbeats"]) >= 0.95


@pytest.fixture(scope="session")
def key_results():
    results = []
    for mode in ("major", "minor"):
        for tonic, note in enumerate(NOTES):
            audio, _ = generate_track(bars=4, key=f"{note} {mode}", percussion="none")
            result = ProfileKeyBackend().analyze(extract(audio, 44100))
            results.append((tonic, mode, result))
    return results


def test_24_keys(key_results):
    correct = sum(k.tonic == tonic and k.mode == mode for tonic, mode, k in key_results)
    assert correct / 24 >= 0.9
    for _, _, key in key_results:
        assert len(key.alternatives) == 3
        assert all((a.tonic, a.mode) != (key.tonic, key.mode) for a in key.alternatives)
        assert key.confidence >= key.alternatives[0].confidence


@pytest.mark.parametrize(
    ("mode", "ordered"),
    [
        ("minor", ("G#", "D#", "A#", "F", "C", "G", "D", "A", "E", "B", "F#", "C#")),
        ("major", ("B", "F#", "C#", "G#", "D#", "A#", "F", "C", "G", "D", "A", "E")),
    ],
)
def test_camelot_all_24(mode, ordered):
    for number, note in enumerate(ordered, 1):
        assert camelot(NOTES.index(note), mode) == f"{number}{'A' if mode == 'minor' else 'B'}"


def test_loudness_edges_and_fade(tmp_path):
    from mixconsole.analysis.backends.loudness import pyloudnorm

    rng = np.random.default_rng(19)
    count = 44100 * 12
    spectrum = np.fft.rfft(rng.standard_normal(count))
    spectrum /= np.sqrt(np.maximum(np.fft.rfftfreq(count), 1 / count))
    mono = np.fft.irfft(spectrum, n=count)
    audio = np.repeat(mono[:, None], 2, axis=1).astype(np.float32)
    meter = pyloudnorm.Meter(44100)
    audio *= 10 ** ((-14 - meter.integrated_loudness(audio)) / 20)
    measured, curve = PyloudnormBackend().analyze(audio, 44100)
    assert abs(measured.integrated_lufs + 14) < 0.5
    # Cross-check rolling three-second LUFS against an independent 3s block meter.
    short = pyloudnorm.Meter(44100, block_size=3).integrated_loudness(audio[: 3 * 44100])
    assert abs(curve[0] - short) < 0.02
    assert measured.true_peak_dbtp >= 20 * np.log10(np.max(abs(audio))) - 0.02
    audio[-4 * 44100 :] *= np.linspace(1, 0, 4 * 44100, dtype=np.float32)[:, None]
    audio = np.pad(audio, ((round(0.31 * 44100), round(0.47 * 44100)), (0, 0)))
    result = analyze(write_audio(tmp_path / "pink.wav", audio), use_cache=False)
    assert abs(result.edges.silence_head - 0.31) < 0.05
    assert abs(result.edges.silence_tail - 0.47) < 0.05
    assert result.edges.fade_out
    assert not result.edges.hard_ending


def test_cache_hit_invalidation_and_exports(tracks, tmp_path, monkeypatch):
    path, _, _ = tracks[128]
    first = analyze(path, cache_dir=tmp_path)
    start = time.perf_counter()
    second = analyze(path, cache_dir=tmp_path)
    elapsed = time.perf_counter() - start
    assert second.cache_hit
    assert elapsed < 0.2
    assert first.model_dump(exclude={"arrays_sha256"}) == second.model_dump(
        exclude={"arrays_sha256"}
    )
    for name in first.arrays:
        np.testing.assert_array_equal(first.arrays[name], second.arrays[name])
    monkeypatch.setattr(registry.BEATS["librosa"], "version", "test-new-version")
    third = analyze(path, cache_dir=tmp_path)
    assert not third.cache_hit
    assert third.backend_versions["beats"] == "librosa@test-new-version"
    assert cache_info(tmp_path)["entries"] == 2
    destination = tmp_path / "export.json"
    save_analysis(third, destination)
    exported = load_analysis(destination)
    assert exported.beats == third.beats
    np.testing.assert_array_equal(exported.arrays["bar_energy"], third.arrays["bar_energy"])
    before = destination.read_bytes(), destination.with_suffix(".npz").read_bytes()
    save_analysis(third, destination)
    assert before == (destination.read_bytes(), destination.with_suffix(".npz").read_bytes())
    assert clear_cache(tmp_path) == 2
    assert destination.exists()


def test_no_cache_and_env(tracks, tmp_path, monkeypatch):
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "environment"))
    assert cache_root() == tmp_path / "environment"
    assert cache_root(tmp_path / "explicit") == tmp_path / "explicit"
    path = tracks[100][0]
    result = analyze(path, use_cache=False)
    assert not result.cache_hit
    assert not (tmp_path / "environment").exists()
    analyze(path)
    assert cache_info(tmp_path / "environment")["entries"] == 1


def test_corrupt_cache_recomputed(tracks, tmp_path):
    path = tracks[124][0]
    analyze(path, cache_dir=tmp_path)
    npz = next(tmp_path.rglob("analysis.npz"))
    npz.write_bytes(b"broken")
    result = analyze(path, cache_dir=tmp_path)
    assert not result.cache_hit
    assert analyze(path, cache_dir=tmp_path).cache_hit


def test_fallbacks(tracks, tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(registry.importlib.util, "find_spec", lambda _: None)
    result = analyze(
        tracks[90][0], backends={"beats": "beat_this", "sections": "allin1"}, cache_dir=tmp_path
    )
    assert result.backend_versions["beats"].startswith("librosa@")
    assert result.backend_versions["sections"].startswith("novelty@")
    assert "falling back" in caplog.text
    with pytest.raises(ValueError, match="unknown backend"):
        analyze(tracks[90][0], backends={"beats": "typo"})


def test_runtime_fallback(tracks, tmp_path, monkeypatch):
    class BrokenBackend:
        name = "broken"
        version = "1"

        def analyze(self, *args):
            raise RuntimeError("unavailable device")

    monkeypatch.setitem(registry.BEATS, "broken", BrokenBackend())
    result = analyze(tracks[140][0], backends={"beats": "broken"}, cache_dir=tmp_path)
    assert result.backend_versions["beats"].startswith("librosa@")


@settings(max_examples=8, deadline=None, derandomize=True)
@given(
    bpm=st.floats(min_value=75, max_value=178, allow_nan=False),
    meter=st.sampled_from([3, 4]),
    head=st.sampled_from([0.0, 0.23, 0.75]),
)
def test_musical_properties(bpm, meter, head):
    audio, truth = generate_track(
        bpm=bpm, bars=4, time_signature=(meter, 4), silence_head=head, pad=False
    )
    result = LibrosaBeatBackend().analyze(extract(audio, 44100), 44100)
    assert all(a < b for a, b in pairwise(result.beats))
    assert set(result.downbeats) <= set(result.beats)
    assert f_measure(result.downbeats, truth["downbeats"]) >= 0.95
    from mixconsole.analysis.structure import bars_and_energy, phrases

    features = extract(audio, 44100)
    bars, energy = bars_and_energy(features, result.downbeats, len(audio) / 44100, 44100)
    assert {p.start for p in phrases(features, bars, energy)} <= set(result.downbeats)


@pytest.mark.parametrize("length", [1, 44100])
def test_silence(tmp_path, length):
    audio = np.zeros((length, 2), dtype=np.float32)
    result = analyze(write_audio(tmp_path / "silence.wav", audio), use_cache=False)
    assert result.beats == result.downbeats == result.phrases == []
    assert result.global_bpm is None
    assert result.loudness.integrated_lufs is None
    assert result.loudness.true_peak_dbtp is None
    assert np.isfinite(result.arrays["short_term_lufs"]).all()


def test_model_invariants(tracks):
    valid = tracks[128][2].model_dump()
    for changes in (
        {"beats": [1.0, 0.5]},
        {"downbeats": [0.12345]},
        {"duration": float("nan")},
        {"beat_confidence": 2},
    ):
        with pytest.raises(ValidationError):
            TrackAnalysis.model_validate(valid | changes)


def test_cli_analyze_cache(tracks, tmp_path):
    runner = CliRunner()
    paths = [str(tracks[bpm][0]) for bpm in (124, 128)]
    output = tmp_path / "out.json"
    result = runner.invoke(
        app,
        ["analyze", *paths, "--json", str(output), "--cache-dir", str(tmp_path / "cache")],
        env={"COLUMNS": "180"},
    )
    assert result.exit_code == 0, result.output
    assert "124.00" in result.output
    assert "128.00" in result.output
    assert len(json.loads(output.read_text())) == 2
    assert (tmp_path / "out-1.npz").is_file()
    assert (tmp_path / "out-2.npz").is_file()
    assert (
        "2 entries"
        in runner.invoke(app, ["cache", "info", "--cache-dir", str(tmp_path / "cache")]).output
    )
    assert (
        "Cleared 2 entries"
        in runner.invoke(app, ["cache", "clear", "--cache-dir", str(tmp_path / "cache")]).output
    )
    failure = runner.invoke(app, ["analyze", str(tmp_path / "absent.wav")])
    assert failure.exit_code == 1
    assert "Analysis failed:" in failure.output


def test_analyze_without_torch(tracks, tmp_path):
    code = """
import importlib.abc, sys
class NoNeural(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('torch','beat_this','allin1'):
            raise AssertionError('core attempted optional import')
sys.meta_path.insert(0,NoNeural())
from mixconsole import analyze
result = analyze(sys.argv[1],use_cache=False)
assert result.global_bpm > 0
"""
    subprocess.run([sys.executable, "-c", code, str(tracks[174][0])], check=True)


@pytest.mark.slow
def test_beat_this_local_checkpoint(tracks, tmp_path):
    if not os.environ.get("MIXCONSOLE_BEAT_THIS_CHECKPOINT"):
        pytest.skip("set MIXCONSOLE_BEAT_THIS_CHECKPOINT to an MIT checkpoint for model inference")
    pytest.importorskip("beat_this")
    result = analyze(tracks[128][0], backends={"beats": "beat_this"}, use_cache=False)
    assert result.backend_versions["beats"].startswith("beat_this@")
    assert len(result.beats) > 0
    assert set(result.downbeats) <= set(result.beats)


@pytest.mark.parametrize(("length", "offset"), [(4, 1), (8, 2), (16, 3)])
def test_phrase_length_and_offset(tmp_path, length, offset):
    audio, truth = generate_track(bars=36, phrase_bars=length, phrase_offset_bars=offset, seed=17)
    result = analyze(write_audio(tmp_path / "phrases.wav", audio), use_cache=False)
    assert [p.start for p in result.phrases] == truth["phrase_starts"]
    assert all(p.length_bars == length for p in result.phrases)


def test_sections_and_edge_types(tmp_path):
    from mixconsole.analysis.backends.cues import EdgeCueBackend
    from mixconsole.analysis.backends.sections import NoveltySectionBackend

    first, _ = generate_track(bars=4, key="C major", percussion="none")
    second, _ = generate_track(bars=4, key="F# minor", percussion="none")
    audio = np.concatenate((first, second))
    sections = NoveltySectionBackend().analyze(extract(audio, 44100), len(audio) / 44100)
    assert sections[0].start == 0
    assert sections[-1].end == len(audio) / 44100
    assert any(abs(s.start - len(first) / 44100) < 1 for s in sections[1:])
    assert all(s.label is None and s.source == "novelty" for s in sections)
    rng = np.random.default_rng(41)
    noise = (rng.normal(size=(44100 * 8, 2)) * 0.1).astype(np.float32)
    hard = EdgeCueBackend().analyze(np.pad(noise, ((0, 44100), (0, 0))), 44100, 120)
    assert hard.hard_ending
    assert not hard.fade_out
    noise[: 44100 * 4] *= np.linspace(0, 1, 44100 * 4, dtype=np.float32)[:, None]
    assert EdgeCueBackend().analyze(noise, 44100, 120).fade_in


def test_beat_this_adapter_without_weights(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from mixconsole.analysis.backends import beats

    audio, truth = generate_track(bars=4)
    calls = []

    class FakeModel:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def __call__(self, signal, sr):
            assert signal.ndim == 1
            assert sr == 44100
            return np.array(truth["beat_times"]), np.array(truth["downbeats"])

    modules = {
        "torch": SimpleNamespace(
            random=SimpleNamespace(fork_rng=lambda **_: nullcontext()),
            manual_seed=lambda seed: calls.append(seed),
        ),
        "beat_this.inference": SimpleNamespace(Audio2Beats=FakeModel),
    }
    monkeypatch.setenv("MIXCONSOLE_BEAT_THIS_CHECKPOINT", "local.ckpt")
    monkeypatch.setattr(beats, "import_module", modules.__getitem__)
    result = beats.BeatThisBackend().analyze(extract(audio, 44100), 44100)
    assert result.beats == truth["beat_times"]
    assert result.downbeats == truth["downbeats"]
    assert calls == [0, {"checkpoint_path": "local.ckpt", "device": "cpu", "dbn": False}]


def test_pcm_identity_across_files(tracks, tmp_path):
    source = tracks[128][0]
    original = analyze(source, cache_dir=tmp_path / "cache")
    other = tmp_path / "other.wav"
    # WAV decoders ignore trailing metadata; original file bytes still change.
    other.write_bytes(source.read_bytes() + b"additional-container-metadata")
    result = analyze(other, cache_dir=tmp_path / "cache")
    assert result.cache_hit
    assert result.pcm_sha256 == original.pcm_sha256
    assert result.file_sha256 != original.file_sha256
    assert result.file == str(other)
    assert cache_info(tmp_path / "cache")["entries"] == 1
