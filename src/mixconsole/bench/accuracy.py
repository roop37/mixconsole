"""Synthetic accuracy suite: tempo, beats, downbeats, meter, key, sections under degradation."""

import shutil
import statistics
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np

from mixconsole.analysis import analyze, registry
from mixconsole.analysis.backends.loudness import pyloudnorm
from mixconsole.bench.metrics import beat_f_measure, mirex_key_score, tempo_acc1, tempo_acc2
from mixconsole.bench.results import BenchResult, new_result
from mixconsole.io import write_audio
from mixconsole.testing.synth import generate_track

Progress = Callable[[str], None]
NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def add_noise(audio: np.ndarray, snr_db: float | None, seed: int) -> np.ndarray:
    """White noise at ``snr_db`` relative to the track RMS (None = clean)."""
    if snr_db is None:
        return audio
    rms = float(np.sqrt(np.mean(audio**2)))
    noise = np.random.default_rng(seed).normal(0, rms / 10 ** (snr_db / 20), audio.shape)
    return (audio + noise).astype(audio.dtype)


def add_pink_noise(audio: np.ndarray, snr_db: float, seed: int) -> np.ndarray:
    """Seeded 1/f noise, scaled to a measured RMS SNR."""
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(audio.shape)
    spectrum = np.fft.rfft(white, axis=0)
    frequencies = np.fft.rfftfreq(len(audio), 1 / 44100)
    spectrum /= np.sqrt(np.maximum(frequencies[:, None], 1))
    noise = np.fft.irfft(spectrum, n=len(audio), axis=0)
    noise *= np.sqrt(np.mean(audio**2) / np.mean(noise**2)) / 10 ** (snr_db / 20)
    return (audio + noise).astype(np.float32)


def mp3_round_trip(audio: np.ndarray, root: Path) -> np.ndarray:
    """Encode at 128 kb/s then decode through ffmpeg, compensating encoder delay."""
    source = write_audio(root / "mp3-source.wav", audio)
    encoded = root / "mp3-roundtrip.mp3"
    decoded = root / "mp3-decoded.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-b:a",
            "128k",
            str(encoded),
        ],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(encoded), str(decoded)],
        check=True,
    )
    from mixconsole.io import load_audio

    return load_audio(decoded).samples


def _quiet(_message: str) -> None:
    """Default progress sink."""


def run_accuracy(
    *,
    quick: bool = False,
    beats: str = "librosa",
    progress: Progress | None = None,
    tiny: bool = False,
) -> BenchResult:
    """Tempo sweep x SNR, meters, all 24 keys, and section cases.

    ``quick`` uses a coarser tempo grid (for CI smoke runs); the full run sweeps
    70-180 BPM in 2 BPM steps at clean, 30, 20 and 10 dB SNR. ``tiny`` shrinks every
    grid to one or two cases so the fast test suite can execute every code path.
    """
    say = progress or _quiet
    step = 120 if tiny else 10 if quick else 2
    snrs: list[float | None] = [None] if tiny else [None, 20] if quick else [None, 30, 20, 10]
    meter_bpms = (90,) if tiny else (90, 110, 150)
    notes = NOTES[:1] if tiny else NOTES
    ramp_ends = (95,) if tiny else (95, 155)
    phrase_cases = ((8, 2),) if tiny else ((4, 1), (8, 2), (16, 3))
    compression = ((30,), (2,)) if tiny else ((30, 20, 10), (2, 4))
    seeds = range(1) if tiny else range(3)
    condition_bpms = (110,) if tiny else (70, 90, 110, 128, 150, 180)
    bars = 8 if tiny else 16
    metrics: dict[str, float] = {}
    with tempfile.TemporaryDirectory(prefix="mixconsole-acc-") as tmp:
        root = Path(tmp)

        def run(audio: np.ndarray, name: str):
            return analyze(
                write_audio(root / f"{name}.wav", audio),
                backends={"beats": beats, "vocals": "heuristic"},
                use_cache=False,
            )

        for snr in snrs:
            label = "clean" if snr is None else f"snr{int(snr)}"
            acc1: list[bool] = []
            acc2: list[bool] = []
            beat_f: list[float] = []
            down_f: list[float] = []
            for i, bpm in enumerate(range(70, 181, step)):
                say(f"accuracy: tempo {bpm} BPM {label}")
                audio, truth = generate_track(
                    bpm=bpm, bars=bars, key=NOTES[i % 12] + " minor", seed=i
                )
                result = run(add_noise(audio, snr, seed=i), f"t{bpm}-{label}")
                acc1.append(tempo_acc1(result.global_bpm, bpm))
                acc2.append(tempo_acc2(result.global_bpm, bpm))
                beat_f.append(beat_f_measure(result.beats, truth["beat_times"]))
                down_f.append(beat_f_measure(result.downbeats, truth["downbeats"]))
            metrics[f"tempo_acc1_{label}"] = float(np.mean(acc1))
            metrics[f"tempo_acc2_{label}"] = float(np.mean(acc2))
            metrics[f"beat_f_mean_{label}"] = statistics.fmean(beat_f)
            metrics[f"beat_f_min_{label}"] = min(beat_f)
            metrics[f"downbeat_f_mean_{label}"] = statistics.fmean(down_f)

        meters: list[bool] = []
        for bpm in meter_bpms:
            say(f"accuracy: 3/4 at {bpm} BPM")
            audio, _ = generate_track(bpm=bpm, bars=bars, time_signature=(3, 4), seed=bpm)
            meters.append(run(add_noise(audio, 20, seed=bpm), f"w{bpm}").meter == 3)
        metrics["meter_3_4_rate_snr20"] = float(np.mean(meters))

        scores: list[float] = []
        for mode in ("major", "minor"):
            for tonic, note in enumerate(notes):
                say(f"accuracy: key {note} {mode}")
                audio, _ = generate_track(bpm=120, bars=8, key=f"{note} {mode}", seed=tonic)
                key = run(add_noise(audio, 20, seed=tonic), f"k{tonic}{mode}").key
                scores.append(mirex_key_score(key.tonic, key.mode, tonic, mode) if key else 0.0)
        metrics["key_mirex_score_snr20"] = statistics.fmean(scores)
        metrics["key_exact_rate_snr20"] = float(np.mean([s == 1.0 for s in scores]))

        say("accuracy: ramps, phrases, compression and loudness")
        for end in ramp_ends:
            audio, truth = generate_track(bpm=125, end_bpm=end, bars=bars, seed=9)
            result = run(audio, f"ramp-{end}")
            metrics[f"ramp_125_{end}_beat_f"] = beat_f_measure(result.beats, truth["beat_times"])
            metrics[f"ramp_125_{end}_downbeat_f"] = beat_f_measure(
                result.downbeats, truth["downbeats"]
            )
        exact: list[bool] = []
        for length, offset in phrase_cases:
            audio, truth = generate_track(
                bars=36, phrase_bars=length, phrase_offset_bars=offset, seed=17
            )
            result = run(audio, f"phrase-{length}")
            exact.append([p.start for p in result.phrases] == truth["phrase_starts"])
        metrics["phrase_exact_rate"] = float(np.mean(exact))
        meter = pyloudnorm.Meter(44100)
        lufs_errors: list[float] = []
        for snr in compression[0]:
            for drive in compression[1]:
                audio, truth = generate_track(bpm=124, bars=bars, seed=13)
                degraded = np.tanh(drive * add_noise(audio, snr, 13)).astype(np.float32)
                result = run(degraded, f"compression-{drive}-{snr}")
                metrics[f"compressed_drive{drive}_snr{snr}_beat_f"] = beat_f_measure(
                    result.beats, truth["beat_times"]
                )
                metrics[f"compressed_drive{drive}_snr{snr}_tempo_acc1"] = float(
                    tempo_acc1(result.global_bpm, 124)
                )
                reference = float(meter.integrated_loudness(degraded))
                if result.loudness.integrated_lufs is not None:
                    lufs_errors.append(abs(result.loudness.integrated_lufs - reference))
        metrics["lufs_error_mean"] = statistics.fmean(lufs_errors)
        metrics["lufs_error_max"] = max(lufs_errors)

        say("accuracy: sections")
        homogeneous: list[bool] = []
        for seed in seeds:
            audio, _ = generate_track(bpm=128, bars=32, seed=seed)
            homogeneous.append(len(run(add_noise(audio, 20, seed), f"h{seed}").sections) == 1)
        metrics["sections_homogeneous_single_rate_snr20"] = float(np.mean(homogeneous))
        drums, _ = generate_track(bpm=128, bars=16, key="C major", seed=3)
        pads, _ = generate_track(bpm=128, bars=8, key="C major", percussion="none", seed=4)
        result = run(add_noise(np.concatenate((drums, pads, drums)), 20, 0), "breakdown")
        bar = 60 / 128 * 4
        starts = [round(s.start / bar) for s in result.sections]
        metrics["sections_breakdown_exact_snr20"] = float(starts == [0, 16, 24])

        # Conditions omitted from the original M1H sweep. Keep a common, seeded
        # tempo grid so each backend sees the same signals and annotations.
        for condition in ("pink30", "pink20", "pink10", "swing", "sparse", "no_percussion", "mp3"):
            if condition == "mp3" and shutil.which("ffmpeg") is None:
                continue
            acc1: list[bool] = []
            acc2: list[bool] = []
            beat_scores: list[float] = []
            section_scores: list[bool] = []
            confidences: list[float] = []
            for bpm in condition_bpms:
                say(f"accuracy: {condition} {bpm} BPM")
                percussion = (
                    "sparse"
                    if condition == "sparse"
                    else "none"
                    if condition == "no_percussion"
                    else "both"
                )
                audio, truth = generate_track(
                    bpm=bpm,
                    bars=bars,
                    seed=bpm,
                    percussion=percussion,
                    timing_jitter_ms=10 if condition == "swing" else 0,
                )
                if condition.startswith("pink"):
                    audio = add_pink_noise(audio, int(condition[4:]), bpm)
                elif condition == "mp3":
                    audio = mp3_round_trip(audio, root)
                result = run(audio, f"{condition}-{bpm}")
                acc1.append(tempo_acc1(result.global_bpm, bpm))
                acc2.append(tempo_acc2(result.global_bpm, bpm))
                beat_scores.append(beat_f_measure(result.beats, truth["beat_times"]))
                section_scores.append(len(result.sections) == 1)
                confidences.append(result.beat_confidence)
            metrics[f"tempo_acc1_{condition}"] = float(np.mean(acc1))
            metrics[f"tempo_acc2_{condition}"] = float(np.mean(acc2))
            metrics[f"beat_f_mean_{condition}"] = statistics.fmean(beat_scores)
            metrics[f"sections_single_rate_{condition}"] = float(np.mean(section_scores))
            metrics[f"beat_confidence_mean_{condition}"] = statistics.fmean(confidences)

        audio, _ = generate_track(bpm=128, bars=32, seed=3, breakdown_bars=tuple(range(16, 24)))
        sectioned = run(audio, "inserted-breakdown")
        starts = [s.start / (60 / 128 * 4) for s in sectioned.sections]
        metrics["sections_inserted_breakdown_within_bar"] = float(
            len(starts) == 3 and abs(starts[1] - 16) <= 1 and abs(starts[2] - 24) <= 1
        )

    return new_result(
        "accuracy",
        metrics,
        backends=registry.versions(registry.selection({"beats": beats, "vocals": "heuristic"})),
        parameters={"tempo_step_bpm": step, "quick": int(quick), "beats": beats, "tiny": int(tiny)},
        notes=[
            "Synthetic signals with exact ground truth; not evidence of real-music accuracy.",
            "White/pink noise SNR is relative to track RMS.",
            "Swing adds seeded timing jitter up to 10 ms.",
            "Acc1/Acc2 use the ±4 % MIREX tolerance.",
        ],
    )
