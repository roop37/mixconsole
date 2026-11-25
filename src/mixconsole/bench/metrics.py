"""Standard MIR evaluation metrics, implemented in-house (no GPL/AGPL evaluators)."""

from collections.abc import Sequence


def beat_f_measure(
    estimated: Sequence[float], reference: Sequence[float], tolerance: float = 0.070
) -> float:
    """F-measure with one-to-one matching inside ±``tolerance`` seconds (MIREX convention)."""
    est, ref = sorted(estimated), sorted(reference)
    i = j = hits = 0
    while i < len(est) and j < len(ref):
        if abs(est[i] - ref[j]) <= tolerance:
            hits += 1
            i += 1
            j += 1
        elif est[i] < ref[j]:
            i += 1
        else:
            j += 1
    if not est and not ref:
        return 1.0
    return 2 * hits / (len(est) + len(ref))


def tempo_acc1(estimated: float | None, reference: float, tolerance: float = 0.04) -> bool:
    """Acc1: estimate within ±4 % of the reference tempo."""
    return estimated is not None and abs(estimated - reference) <= tolerance * reference


def tempo_acc2(estimated: float | None, reference: float, tolerance: float = 0.04) -> bool:
    """Acc2: Acc1 allowing octave/metrical errors (x2, x½, x3, x⅓)."""
    if estimated is None:
        return False
    return any(
        abs(estimated - reference * factor) <= tolerance * reference * factor
        for factor in (1, 2, 0.5, 3, 1 / 3)
    )


def mirex_key_score(
    estimated_tonic: int, estimated_mode: str, reference_tonic: int, reference_mode: str
) -> float:
    """MIREX: exact 1, fifth above/below 0.5, relative 0.3, parallel 0.2, else 0."""
    if (estimated_tonic, estimated_mode) == (reference_tonic, reference_mode):
        return 1.0
    if estimated_mode == reference_mode and (estimated_tonic - reference_tonic) % 12 in (5, 7):
        return 0.5
    relative = (reference_tonic + (9 if reference_mode == "major" else 3)) % 12
    if estimated_mode != reference_mode and estimated_tonic == relative:
        return 0.3
    if estimated_mode != reference_mode and estimated_tonic == reference_tonic:
        return 0.2
    return 0.0
