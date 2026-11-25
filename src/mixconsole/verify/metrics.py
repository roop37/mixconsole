# pyright: reportUnknownVariableType=false
"""Seam measurements computed on rendered audio and separated overlap signals."""

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfilt  # pyright: ignore[reportMissingTypeStubs]

from mixconsole.analysis.backends.loudness import PyloudnormBackend
from mixconsole.io import SAMPLE_RATE, Audio
from mixconsole.render.graph import RenderInspection
from mixconsole.render.limiter import true_peak_dbtp


@dataclass
class SeamMetrics:
    """Seam measurements. ``None`` means "not applicable or not measurable", never a pass.

    ``drift_ms`` applies only to beatmatched seams (a beat-warp map exists);
    ``low_overlap_bars`` needs the separated A/B contributions of an overlapping seam.
    """

    drift_ms: float | None
    loudness_dip_lu: float
    loudness_bump_lu: float
    true_peak_dbtp: float
    clicks: int
    low_overlap_bars: float | None
    passed: bool
    reason: str
    # Stem seams only (measured on the rendered, post-automation stems); None otherwise.
    vocal_overlap_seconds: float | None = None
    bass_overlap_bars: float | None = None
    stem_leakage: float | None = None

    def as_dict(self) -> dict[str, float | int | bool | str | None]:
        return vars(self).copy()


def _rms(audio: Audio) -> float:
    return (
        float(np.sqrt(np.mean(np.square(audio.astype(np.float64))) + 1e-12)) if len(audio) else 0.0
    )


def _short_lufs(audio: Audio) -> float:
    if not len(audio):
        return -120.0
    _, curve = PyloudnormBackend().analyze(audio, SAMPLE_RATE)
    return float(curve[0])


def _onset_offset(audio: Audio, frame: int) -> int | None:
    radius = round(0.02 * SAMPLE_RATE)
    if frame - radius < 1 or frame + radius >= len(audio):
        return None
    window = audio[frame - radius - 1 : frame + radius + 1]
    derivative = np.max(np.abs(np.diff(window, axis=0)), axis=1)
    if len(derivative) == 0 or float(derivative.max()) < 1e-4:
        return None
    return int(np.argmax(derivative)) - radius


def _drift(inspection: RenderInspection | None) -> float | None:
    """Median rendered-B onset offset from the target grid (ms); None when not beatmatched
    or when no beat attack could be measured."""
    if (
        inspection is None
        or inspection.source_b is None
        or inspection.stretched_b is None
        or not inspection.beat_warp
    ):
        return None
    offsets: list[float] = []
    for source, target in inspection.beat_warp[1:-1]:
        before = _onset_offset(inspection.source_b, source)
        after = _onset_offset(inspection.stretched_b, target)
        if before is not None and after is not None:
            # The source probe confirms a beat attack exists; phase is measured
            # from the rendered B attack against the target beat grid.
            offsets.append(abs(after) * 1000 / SAMPLE_RATE)
    return float(np.median(offsets)) if offsets else None


def _low_overlap(inspection: RenderInspection | None, bpm: float) -> float | None:
    """Longest run (bars) where both tracks' < 150 Hz energy is active; None without
    separated contributions."""
    if inspection is None or inspection.contribution_a is None or inspection.contribution_b is None:
        return None
    sos = butter(2, 150, btype="lowpass", fs=SAMPLE_RATE, output="sos")
    a = np.asarray(sosfilt(sos, inspection.contribution_a, axis=0), dtype=np.float32)
    b = np.asarray(sosfilt(sos, inspection.contribution_b, axis=0), dtype=np.float32)
    block = max(1, SAMPLE_RATE // 20)
    blocks_a = [_rms(a[i : i + block]) for i in range(0, len(a), block)]
    blocks_b = [_rms(b[i : i + block]) for i in range(0, len(b), block)]
    threshold_a = max(1e-4, float(np.quantile(blocks_a, 0.9)) * 0.5)
    threshold_b = max(1e-4, float(np.quantile(blocks_b, 0.9)) * 0.5)
    current = longest = 0
    for start in range(0, min(len(a), len(b)), block):
        if (
            _rms(a[start : start + block]) > threshold_a
            and _rms(b[start : start + block]) > threshold_b
        ):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest * block / SAMPLE_RATE * bpm / 240


def _active_blocks(audio: Audio, block: int) -> np.ndarray:
    """Blocks whose RMS exceeds 10 % of the signal's own 95th-percentile block RMS."""
    rms = np.array([_rms(audio[i : i + block]) for i in range(0, len(audio), block)])
    if not len(rms):
        return np.zeros(0, dtype=bool)
    return rms > max(1e-3, float(np.quantile(rms, 0.95)) * 0.1)


def _stem_overlap(inspection: RenderInspection | None, stem: str) -> tuple[float, int] | None:
    """(total seconds, longest run in blocks) where A's and B's ``stem`` are both audible.

    Returns the block length in the second slot's unit via the caller (20 ms blocks).
    """
    if inspection is None:
        return None
    left = inspection.stem_contributions.get(f"a:{stem}")
    right = inspection.stem_contributions.get(f"b:{stem}")
    if left is None or right is None:
        return None
    block = SAMPLE_RATE // 50
    both = _active_blocks(left, block) & _active_blocks(right, block)
    longest = current = 0
    for flag in both:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return float(both.sum()) * block / SAMPLE_RATE, longest


def vocal_overlap_seconds(inspection: RenderInspection | None) -> float | None:
    """Seconds in which both the outgoing and incoming vocal stems are audible."""
    measured = _stem_overlap(inspection, "vocals")
    return None if measured is None else measured[0]


def bass_overlap_bars(
    inspection: RenderInspection | None, bpm: float, beats_per_bar: int
) -> float | None:
    """Longest run (bars) in which both bass stems are audible."""
    measured = _stem_overlap(inspection, "bass")
    if measured is None:
        return None
    return measured[1] * (SAMPLE_RATE // 50) / SAMPLE_RATE * bpm / (60 * beats_per_bar)


def stem_leakage(inspection: RenderInspection | None) -> float | None:
    """Separation bleed in the handoff window, in [0, 1]; None when it cannot be measured.

    For each deck, the vocal stem is compared with the drums, bass and other stems in 100 ms
    blocks where the vocal stem is audible: the leakage of a block is the largest absolute
    zero-lag normalised correlation with an instrumental stem (a clean separation leaves them
    uncorrelated; a vocal stem carrying hats, kicks or guitar copies correlates). Blocks are
    weighted by vocal energy; the result is the worse deck. Unmeasured (no stems, no audible
    vocal) is None, never 0. Demucs folds its residual into ``other``, so residual energy is
    part of the ``other`` correlation.
    """
    if inspection is None:
        return None
    block = SAMPLE_RATE // 10
    worst: float | None = None
    for deck in ("a", "b"):
        vocal = inspection.stem_sources.get(f"{deck}:vocals")
        others = [inspection.stem_sources.get(f"{deck}:{n}") for n in ("drums", "bass", "other")]
        if vocal is None or any(o is None for o in others):
            continue
        v = vocal.astype(np.float64).mean(axis=1)
        o = [x.astype(np.float64).mean(axis=1) for x in others if x is not None]
        total = weight = 0.0
        for start in range(0, len(v) - block + 1, block):
            seg = v[start : start + block]
            energy = float(np.sum(seg * seg))
            if energy < 1e-6 * block:
                continue
            corr = max(
                abs(float(np.dot(seg, x[start : start + block])))
                / (np.sqrt(energy * float(np.sum(x[start : start + block] ** 2))) + 1e-12)
                for x in o
            )
            total += corr * energy
            weight += energy
        if weight > 0:
            value = total / weight
            worst = value if worst is None else max(worst, value)
    return worst


def verify_seam(
    audio: Audio,
    seam_frame: int,
    overlap_frames: int,
    *,
    bpm: float,
    max_dip: float = 1.5,
    max_peak: float = -1.0,
    max_drift: float = 5.0,
    max_low_overlap: float = 1.0,
    max_vocal_overlap_beats: float = 1.0,
    max_stem_leakage: float = 0.25,
    beats_per_bar: int = 4,
    inspection: RenderInspection | None = None,
) -> SeamMetrics:
    """Measure level, peak, impulses, phase drift and low-band coexistence."""
    context = round(8 * 4 * 60 / bpm * SAMPLE_RATE)
    start = max(0, seam_frame - context)
    end = min(len(audio), seam_frame + overlap_frames + context)
    window = 3 * SAMPLE_RATE
    before = _short_lufs(audio[max(start, seam_frame - window) : seam_frame])
    after_start = min(end, seam_frame + overlap_frames)
    after = _short_lufs(audio[after_start : min(end, after_start + window)])
    if overlap_frames:
        midpoint = seam_frame + overlap_frames // 2
        middle = _short_lufs(
            audio[
                max(seam_frame, midpoint - window // 2) : min(after_start, midpoint + window // 2)
            ]
        )
    else:
        middle = _short_lufs(
            audio[max(start, seam_frame - window // 2) : min(end, seam_frame + window // 2)]
        )
    reference = (before + after) / 2
    dip = max(0.0, reference - middle)
    bump = max(0.0, middle - reference)
    around = audio[max(1, seam_frame - 256) : min(len(audio), seam_frame + overlap_frames + 256)]
    derivative = np.max(np.abs(np.diff(around, axis=0)), axis=1) if len(around) > 1 else np.empty(0)
    threshold = max(0.5, float(np.quantile(derivative, 0.999)) * 4) if len(derivative) else 0.5
    clicks = int(np.count_nonzero(derivative > threshold))
    peak = true_peak_dbtp(audio)
    drift = _drift(inspection)
    vocal_overlap = vocal_overlap_seconds(inspection)
    bass_overlap = bass_overlap_bars(inspection, bpm, beats_per_bar)
    # Stem seams measure the bass stems; whole-mix low bands would count the kicks.
    overlap = bass_overlap if bass_overlap is not None else _low_overlap(inspection, bpm)
    leakage = stem_leakage(inspection)
    failures: list[str] = []
    if leakage is not None and leakage > max_stem_leakage:
        failures.append(f"stem leakage {leakage:.2f} exceeds {max_stem_leakage:.2f}")
    if dip > max_dip:
        failures.append(f"loudness dip {dip:.2f} LU exceeds {max_dip:.2f}")
    if bump > max_dip:
        failures.append(f"loudness bump {bump:.2f} LU exceeds {max_dip:.2f}")
    if peak > max_peak + 0.01:
        failures.append(f"true peak {peak:.2f} dBTP exceeds {max_peak:.2f}")
    if clicks:
        failures.append(f"{clicks} off-grid impulses")
    beatmatched = inspection is not None and bool(inspection.beat_warp)
    if drift is None:
        if beatmatched:
            failures.append("beat-phase drift not measurable on a beatmatched seam")
    elif drift >= max_drift:
        failures.append(f"beat-phase drift {drift:.2f} ms exceeds {max_drift:.2f}")
    if overlap is None:
        if overlap_frames and inspection is not None:
            failures.append("low-band overlap not measurable on an overlapping seam")
    elif overlap > max_low_overlap:
        failures.append(f"low-band overlap {overlap:.2f} bars exceeds {max_low_overlap:.2f}")
    if vocal_overlap is not None and vocal_overlap > max_vocal_overlap_beats * 60 / bpm + 1e-9:
        failures.append(
            f"vocal overlap {vocal_overlap:.2f} s exceeds {max_vocal_overlap_beats:g} beat(s)"
        )
    return SeamMetrics(
        drift,
        float(dip),
        float(bump),
        float(peak),
        clicks,
        overlap,
        not failures,
        "; ".join(failures) or "passed",
        vocal_overlap,
        bass_overlap,
        leakage,
    )
