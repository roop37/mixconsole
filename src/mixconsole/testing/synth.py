"""Small, original synthetic music fixtures; no recordings or model weights.

Bars and vocal bar indices are zero-based. BPM counts quarter notes. A time
signature's denominator defines the click pulse (6/8 has six eighth-note clicks).
The optional ramp is linear in musical quarter-note position, not wall time.
Ground-truth timestamps are rounded to the samples actually used by synthesis.
"""

import math
from typing import Literal, TypedDict

import numpy as np
from numpy.typing import NDArray

from mixconsole.io import SAMPLE_RATE, Audio


class GroundTruth(TypedDict):
    """Exact source annotations, with all times measured from file start in seconds."""

    sample_rate: int
    bpm: float
    end_bpm: float
    time_signature: tuple[int, int]
    beat_times: list[float]
    downbeats: list[float]
    phrase_starts: list[float]
    key: str
    vocal_regions: list[tuple[float, float]]
    music_start: float
    music_end: float
    duration: float
    seed: int


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _root_frequency(key: str) -> tuple[float, bool]:
    roots = {
        "C": 0,
        "C#": 1,
        "Db": 1,
        "D": 2,
        "D#": 3,
        "Eb": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "Gb": 6,
        "G": 7,
        "G#": 8,
        "Ab": 8,
        "A": 9,
        "A#": 10,
        "Bb": 10,
        "B": 11,
    }
    parts = key.split()
    if len(parts) != 2 or parts[0] not in roots or parts[1] not in ("major", "minor"):
        raise ValueError("key must be a note and mode, e.g. 'C major' or 'F# minor'")
    return 440.0 * 2 ** ((36 + roots[parts[0]] - 69) / 12), parts[1] == "minor"


def generate_track(
    *,
    bpm: float = 120,
    bars: int = 8,
    time_signature: tuple[int, int] = (4, 4),
    phrase_bars: int = 8,
    phrase_offset_bars: int = 0,
    key: str = "C major",
    percussion: Literal["click", "kick", "both", "sparse", "none"] = "both",
    bass: bool = True,
    pad: bool = True,
    vocal_bars: tuple[int, ...] = (),
    silence_head: float = 0,
    silence_tail: float = 0,
    end_bpm: float | None = None,
    timing_jitter_ms: float = 0,
    breakdown_bars: tuple[int, ...] = (),
    seed: int = 0,
) -> tuple[Audio, GroundTruth]:
    """Generate stereo float32 audio and exact beat/phrase/key/vocal annotations.

    Accented downbeats and seeded noise crashes mark bars and phrases.
    phrase_offset_bars shifts crash markers without changing the beat/bar grid. Bass is
    a root sine at octave 2; pads are major/minor triads. Vocals are windowed
    harmonic bursts with formant-shaped amplitudes, not speech. Silence is exact.
    """
    end = bpm if end_bpm is None else end_bpm
    if not all(math.isfinite(v) and v > 0 for v in (bpm, end)):
        raise ValueError("BPM endpoints must be finite and positive")
    numerator, denominator = time_signature
    if (
        not _is_integer(bars)
        or bars < 1
        or not _is_integer(phrase_bars)
        or phrase_bars < 1
        or not _is_integer(numerator)
        or numerator < 1
        or not _is_integer(denominator)
        or denominator not in (1, 2, 4, 8, 16, 32)
    ):
        raise ValueError("bars/phrase_bars and time signature must be positive integers")
    if not _is_integer(phrase_offset_bars) or not 0 <= phrase_offset_bars < phrase_bars:
        raise ValueError("phrase_offset_bars must be within the phrase grid")
    if not all(math.isfinite(v) and v >= 0 for v in (silence_head, silence_tail)):
        raise ValueError("silence durations must be finite and non-negative")
    if any(not _is_integer(b) or b < 0 or b >= bars for b in vocal_bars):
        raise ValueError("vocal_bars must contain zero-based bar indices within the track")
    if percussion not in ("click", "kick", "both", "sparse", "none"):
        raise ValueError("unknown percussion mode")
    if not math.isfinite(timing_jitter_ms) or not 0 <= timing_jitter_ms <= 10:
        raise ValueError("timing_jitter_ms must be between 0 and 10")
    if any(not _is_integer(b) or b < 0 or b >= bars for b in breakdown_bars):
        raise ValueError("breakdown_bars must contain valid bar indices")
    if not _is_integer(seed) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    root, minor = _root_frequency(key)
    rng = np.random.default_rng(seed)
    pulse_count = bars * numerator
    quarters = np.arange(pulse_count + 1, dtype=np.float64) * (4 / denominator)
    slope = (end - bpm) / float(quarters[-1])
    if abs(slope) < 1e-12:
        seconds = quarters * 60 / bpm
    else:
        seconds = 60 / slope * np.log1p(slope * quarters / bpm)
    head_frames = round(silence_head * SAMPLE_RATE)
    pulse_frames = np.rint(seconds * SAMPLE_RATE).astype(np.int64) + head_frames
    if timing_jitter_ms:
        jitter = rng.uniform(-timing_jitter_ms, timing_jitter_ms, pulse_count)
        jitter[::numerator] = 0  # Keep downbeat/bar annotations on the nominal grid.
        pulse_frames[:-1] += np.rint(jitter * SAMPLE_RATE / 1000).astype(np.int64)
    if np.any(np.diff(pulse_frames) < 2):
        raise ValueError("tempo is too fast for the sample rate")
    music_end = int(pulse_frames[-1])
    total_frames = music_end + round(silence_tail * SAMPLE_RATE)
    audio = np.zeros((total_frames, 2), dtype=np.float32)

    def add(start: int, signal: NDArray[np.float64], pan: float = 0) -> None:
        count = min(len(signal), music_end - start)
        if count > 0:
            audio[start : start + count, 0] += (signal[:count] * (1 - pan * 0.25)).astype(
                np.float32
            )
            audio[start : start + count, 1] += (signal[:count] * (1 + pan * 0.25)).astype(
                np.float32
            )

    for index, frame in enumerate(pulse_frames[:-1]):
        start = int(frame)
        count = int(pulse_frames[index + 1] - frame)
        t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
        accent = 1.0 if index % numerator == 0 else 0.55
        in_breakdown = index // numerator in breakdown_bars
        if not in_breakdown and percussion in ("click", "both"):
            click = np.zeros(count, dtype=np.float64)
            click[0] = 0.3 * accent
            add(start, click)
        if not in_breakdown and (
            percussion in ("kick", "both")
            or (percussion == "sparse" and index % numerator in (0, 2))
        ):
            phase = 2 * np.pi * (48 * t + 65 * 0.025 * (1 - np.exp(-t / 0.025)))
            add(start, 0.23 * accent * np.sin(phase) * np.exp(-t / 0.055))
        if (
            percussion not in ("none", "sparse")
            and not in_breakdown
            and index % (phrase_bars * numerator) == phrase_offset_bars * numerator
        ):
            crash = rng.standard_normal(min(count, round(SAMPLE_RATE * 0.25)))
            crash *= 0.035 * np.exp(-np.arange(len(crash)) / (SAMPLE_RATE * 0.055))
            crash[0] = 0  # Preserve exact downbeat click amplitude.
            add(start, crash, pan=0.5)
        if bass:
            envelope = np.minimum(t / 0.008, 1) * np.minimum((count / SAMPLE_RATE - t) / 0.03, 1)
            add(start, 0.1 * np.sin(2 * np.pi * root * t) * envelope)

    if pad:
        t = np.arange(music_end - head_frames, dtype=np.float64) / SAMPLE_RATE
        envelope = np.minimum(t / 0.1, 1) * np.minimum((len(t) / SAMPLE_RATE - t) / 0.1, 1)
        chord = np.zeros_like(t)
        for semitone in (0, 3 if minor else 4, 7):
            chord += 0.025 * np.sin(2 * np.pi * root * 4 * 2 ** (semitone / 12) * t)
        add(head_frames, chord * envelope, pan=-0.3)

    regions: list[tuple[float, float]] = []
    for bar in sorted(set(vocal_bars)):
        start = int(pulse_frames[bar * numerator])
        stop = int(pulse_frames[(bar + 1) * numerator])
        burst_start = start + (stop - start) // 4
        burst_end = start + 3 * (stop - start) // 4
        t = np.arange(burst_end - burst_start, dtype=np.float64) / SAMPLE_RATE
        voice = np.zeros_like(t)
        for harmonic in range(1, 25):
            frequency = 145 * harmonic
            weight = sum(math.exp(-0.5 * ((frequency - f) / 160) ** 2) for f in (700, 1200, 2500))
            voice += (0.025 * weight / math.sqrt(harmonic)) * np.sin(2 * np.pi * frequency * t)
        add(burst_start, voice * np.sin(np.pi * np.arange(len(t)) / len(t)) ** 2, pan=0.1)
        regions.append((burst_start / SAMPLE_RATE, burst_end / SAMPLE_RATE))

    # A fixed global scale avoids clipping without data-dependent normalization.
    audio *= np.float32(0.8)
    beats = (pulse_frames[:-1] / SAMPLE_RATE).tolist()
    truth: GroundTruth = {
        "sample_rate": SAMPLE_RATE,
        "bpm": bpm,
        "end_bpm": end,
        "time_signature": time_signature,
        "beat_times": beats,
        "downbeats": beats[::numerator],
        "phrase_starts": beats[phrase_offset_bars * numerator :: numerator * phrase_bars],
        "key": key,
        "vocal_regions": regions,
        "music_start": head_frames / SAMPLE_RATE,
        "music_end": music_end / SAMPLE_RATE,
        "duration": total_frames / SAMPLE_RATE,
        "seed": seed,
    }
    return audio, truth
