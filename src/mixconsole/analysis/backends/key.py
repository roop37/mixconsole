"""Original CQT profile ensemble; no external key-finder code or model weights."""

from typing import Literal

import numpy as np

from mixconsole.analysis.features import Features
from mixconsole.analysis.models import Key, KeyAlternative

# Tonic order: C C# D D# E F F# G G# A A# B.
MAJOR_CAMELOT = ("8B", "3B", "10B", "5B", "12B", "7B", "2B", "9B", "4B", "11B", "6B", "1B")
MINOR_CAMELOT = ("5A", "12A", "7A", "2A", "9A", "4A", "11A", "6A", "1A", "8A", "3A", "10A")
# Published numeric profiles (Krumhansl-Kessler and Temperley), not source code.
# Third pair is an original EDM-oriented triadic profile, not a trained model.
PROFILES = np.array(
    [
        [
            [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
            [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17],
        ],
        [
            [5, 2, 3.5, 2, 4.5, 4, 2, 4.5, 2, 3.5, 1.5, 4],
            [5, 2, 3.5, 4.5, 2, 4, 2, 4.5, 3.5, 2, 1.5, 4],
        ],
        [[6, 0, 1, 0, 4, 1, 0, 4, 0, 1, 0, 1], [6, 0, 1, 4, 0, 1, 0, 4, 1, 0, 1, 0]],
    ],
    dtype=np.float64,
)


def camelot(tonic: int, mode: Literal["major", "minor"]) -> str:
    if tonic not in range(12) or mode not in ("major", "minor"):
        raise ValueError("invalid tonic or mode")
    return (MAJOR_CAMELOT if mode == "major" else MINOR_CAMELOT)[tonic]


class ProfileKeyBackend:
    name = "profiles"
    version = "1"

    def analyze(self, features: Features) -> Key:
        chroma = features.chroma.mean(axis=1)
        chroma = chroma / max(float(np.linalg.norm(chroma)), 1e-12)
        scores: list[float] = []
        for mode in range(2):
            for tonic in range(12):
                profiles = np.roll(PROFILES[:, mode], tonic, axis=1)
                profiles = profiles / np.linalg.norm(profiles, axis=1, keepdims=True)
                scores.append(float(np.mean(profiles @ chroma)))
        probabilities = np.exp((np.array(scores) - max(scores)) * 18)
        probabilities /= probabilities.sum()
        order = np.argsort(-probabilities)

        def candidate(index: int) -> KeyAlternative:
            mode: Literal["major", "minor"] = "major" if index < 12 else "minor"
            return KeyAlternative(
                tonic=index % 12,
                mode=mode,
                camelot=camelot(index % 12, mode),
                confidence=float(probabilities[index]),
            )

        best = candidate(int(order[0]))
        return Key(**best.model_dump(), alternatives=[candidate(int(i)) for i in order[1:4]])
