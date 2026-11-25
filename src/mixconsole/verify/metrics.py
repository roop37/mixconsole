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
    drift_ms: float
    loudness_dip_lu: float
    loudness_bump_lu: float
    true_peak_dbtp: float
    clicks: int
    low_overlap_bars: float
    passed: bool
    reason: str

    def as_dict(self) -> dict[str, float | int | bool | str]:
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


def _drift(inspection: RenderInspection | None) -> float:
    if (
        inspection is None
        or inspection.source_b is None
        or inspection.stretched_b is None
        or not inspection.beat_warp
    ):
        return 0.0
    offsets: list[float] = []
    for source, target in inspection.beat_warp[1:-1]:
        before = _onset_offset(inspection.source_b, source)
        after = _onset_offset(inspection.stretched_b, target)
        if before is not None and after is not None:
            # The source probe confirms a beat attack exists; phase is measured
            # from the rendered B attack against the target beat grid.
            offsets.append(abs(after) * 1000 / SAMPLE_RATE)
    return float(np.median(offsets)) if offsets else 0.0


def _low_overlap(inspection: RenderInspection | None, bpm: float) -> float:
    if inspection is None or inspection.contribution_a is None or inspection.contribution_b is None:
        return 0.0
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
    overlap = _low_overlap(inspection, bpm)
    failures: list[str] = []
    if dip > max_dip:
        failures.append(f"loudness dip {dip:.2f} LU exceeds {max_dip:.2f}")
    if bump > max_dip:
        failures.append(f"loudness bump {bump:.2f} LU exceeds {max_dip:.2f}")
    if peak > max_peak + 0.01:
        failures.append(f"true peak {peak:.2f} dBTP exceeds {max_peak:.2f}")
    if clicks:
        failures.append(f"{clicks} off-grid impulses")
    if drift >= max_drift:
        failures.append(f"beat-phase drift {drift:.2f} ms exceeds {max_drift:.2f}")
    if overlap > max_low_overlap:
        failures.append(f"low-band overlap {overlap:.2f} bars exceeds {max_low_overlap:.2f}")
    return SeamMetrics(
        drift,
        float(dip),
        float(bump),
        float(peak),
        clicks,
        overlap,
        not failures,
        "; ".join(failures) or "passed",
    )
