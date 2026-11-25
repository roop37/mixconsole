"""Original local self-similarity checkerboard novelty; bounded linear memory."""

from importlib import import_module

import numpy as np

from mixconsole.analysis.features import Features, FloatArray, ndimage, signal
from mixconsole.analysis.models import Section


def novelty(features: Features) -> FloatArray:
    matrix = np.vstack((features.chroma, features.mfcc))
    matrix = (matrix - matrix.mean(axis=1, keepdims=True)) / np.maximum(
        matrix.std(axis=1, keepdims=True), 1e-6
    )
    matrix /= np.maximum(np.linalg.norm(matrix, axis=0), 1e-6)
    # Mean cross/self similarities of adjacent windows equal squared distance
    # between their mean vectors; no full quadratic N x N similarity matrix.
    width = max(2, round(2 * features.sr / features.hop))
    smooth = np.asarray(
        ndimage.uniform_filter1d(matrix, size=width, axis=1, mode="nearest"), dtype=np.float64
    )
    left = np.roll(smooth, width // 2, axis=1)
    right = np.roll(smooth, -width // 2, axis=1)
    curve = np.sum((right - left) ** 2, axis=0)
    curve[:width] = 0
    curve[-width:] = 0
    return np.asarray(curve, dtype=np.float64)


class NoveltySectionBackend:
    name = "novelty"
    version = "3"

    def analyze(self, features: Features, duration: float) -> list[Section]:
        curve = novelty(features)
        peaks, _ = signal.find_peaks(
            curve,
            distance=max(1, round(4 * features.sr / features.hop)),
            prominence=max(0.05, float(curve.max()) * 0.2),
        )
        starts = [0.0] + [
            float(features.times[p]) for p in peaks if 0 < features.times[p] < duration
        ]
        return [
            Section(start=a, end=b, source=self.name)
            for a, b in zip(starts, [*starts[1:], duration], strict=True)
        ]


class AllInOneBackend:
    """Reserved adapter, deliberately unavailable pending NATTEN/platform validation."""

    name = "allin1"
    version = "stub-1"

    def analyze(self, features: Features, duration: float) -> list[Section]:
        import_module("allin1")
        raise NotImplementedError(
            "allin1 adapter is a stub; NATTEN and madmom require separate review"
        )
