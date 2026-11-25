"""R2: unmeasured seam metrics are None (never a silent 0.0 pass) and the baseline is measured."""

import numpy as np

from mixconsole.io import SAMPLE_RATE
from mixconsole.render.graph import RenderInspection
from mixconsole.verify.metrics import verify_seam


def tone(seconds: float, hz: float, level: float = 0.3) -> np.ndarray:
    t = np.arange(round(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    mono = (level * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    return np.stack((mono, mono), axis=1)


def test_cut_without_inspection_reports_none_not_zero():
    audio = np.concatenate((tone(10, 220), tone(10, 220)))
    metric = verify_seam(audio, 10 * SAMPLE_RATE, 0, bpm=120)
    assert metric.drift_ms is None
    assert metric.low_overlap_bars is None
    assert metric.as_dict()["drift_ms"] is None
    assert metric.passed, metric.reason


def test_beatmatched_seam_with_unmeasurable_drift_fails():
    audio = np.concatenate((tone(10, 220), tone(10, 220)))
    silent = np.zeros((4 * SAMPLE_RATE, 2), dtype=np.float32)
    inspection = RenderInspection(
        source_b=silent,
        stretched_b=silent,
        contribution_a=tone(4, 60),
        contribution_b=np.zeros_like(tone(4, 60)),
        beat_warp=[[0, 0], [SAMPLE_RATE, SAMPLE_RATE], [2 * SAMPLE_RATE, 2 * SAMPLE_RATE]],
    )
    metric = verify_seam(audio, 10 * SAMPLE_RATE, 4 * SAMPLE_RATE, bpm=120, inspection=inspection)
    assert metric.drift_ms is None
    assert not metric.passed
    assert "drift not measurable" in metric.reason


def test_two_basslines_overlap_is_measured():
    a, b = tone(8, 55), tone(8, 65)
    audio = np.concatenate((tone(10, 220), a + b, tone(10, 220)))
    inspection = RenderInspection(contribution_a=a, contribution_b=b)
    metric = verify_seam(audio, 10 * SAMPLE_RATE, 8 * SAMPLE_RATE, bpm=120, inspection=inspection)
    assert metric.low_overlap_bars is not None
    assert metric.low_overlap_bars > 3  # 8 s at 120 BPM = 4 bars of simultaneous bass
    assert "low-band overlap" in metric.reason


def test_overlapping_seam_without_contributions_is_flagged():
    audio = np.concatenate((tone(10, 220), tone(10, 220)))
    inspection = RenderInspection()
    metric = verify_seam(audio, 10 * SAMPLE_RATE, 4 * SAMPLE_RATE, bpm=120, inspection=inspection)
    assert metric.low_overlap_bars is None
    assert "not measurable" in metric.reason
