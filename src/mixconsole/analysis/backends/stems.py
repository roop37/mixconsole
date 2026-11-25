"""Demucs htdemucs stem separation of the exit and entry windows only, cached on disk.

Only the last <= 60 s of the music of an outgoing track and the first <= 60 s of an
incoming track are separated (never the whole song). Stems are cached per
(pcm sha256, window frames, model version). The separator is a small protocol so the
core package never imports torch and tests can inject a deterministic oracle.

The residual ``mix - drums - bass - vocals`` is folded into ``other`` so that the four
stems re-sum to the original mix to float precision (the null test); Demucs alone only
approximates the mix.
"""

import io
import json
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from mixconsole.analysis.cache import atomic_write
from mixconsole.analysis.model_manager import (
    HTDEMUCS_NAME,
    HTDEMUCS_SHA256,
    HTDEMUCS_VERSION,
    htdemucs_dir,
    htdemucs_path,
)
from mixconsole.io import SAMPLE_RATE, Audio

logger = logging.getLogger(__name__)

STEM_NAMES = ("drums", "bass", "other", "vocals")
WINDOW_SECONDS = 60.0
MODEL_VERSION = HTDEMUCS_VERSION


def available() -> bool:
    """True when the stems extra is importable and the pinned checkpoint is cached."""
    import importlib.util

    return importlib.util.find_spec("demucs") is not None and htdemucs_path().is_file()


@dataclass
class StemSet:
    """Stems of one window. ``start_frame`` is the window start in the track's frames.

    ``latency_frames`` is the separator's processing delay per stem (0 for offline
    Demucs); the renderer compensates it when re-summing.
    """

    start_frame: int
    stems: dict[str, Audio]
    latency_frames: dict[str, int] = field(default_factory=dict[str, int])
    model: str = MODEL_VERSION
    stats: dict[str, float | str] = field(default_factory=dict[str, float | str])

    @property
    def frames(self) -> int:
        return len(next(iter(self.stems.values())))

    @property
    def end_frame(self) -> int:
        return self.start_frame + self.frames

    def slice(self, start: int, stop: int) -> dict[str, Audio]:
        """Stems for track frames [start, stop), zero padded outside the window."""
        result: dict[str, Audio] = {}
        for name, data in self.stems.items():
            out = np.zeros((max(0, stop - start), 2), dtype=np.float32)
            lo, hi = max(start, self.start_frame), min(stop, self.end_frame)
            if hi > lo:
                out[lo - start : hi - start] = data[lo - self.start_frame : hi - self.start_frame]
            result[name] = out
        return result


class Separator(Protocol):
    name: str
    version: str

    def separate(self, audio: Audio, start_frame: int) -> dict[str, Audio]:
        """Return drums/bass/other/vocals for ``audio`` (the window beginning at start_frame)."""
        ...


def window_frames(
    role: str, duration: float, silence_head: float, silence_tail: float
) -> tuple[int, int]:
    """Frame window: the last (exit) or first (entry) <= 60 s of the music."""
    total = round(duration * SAMPLE_RATE)
    music_start = round(silence_head * SAMPLE_RATE)
    music_end = max(music_start + 1, total - round(silence_tail * SAMPLE_RATE))
    length = round(WINDOW_SECONDS * SAMPLE_RATE)
    if role == "exit":
        return max(0, music_end - length), min(total, music_end)
    return min(music_start, total), min(total, music_start + length)


def peak_rss_mb() -> float:
    """Peak resident set size of this process in MB (0 where unavailable)."""
    try:
        import resource
    except ImportError:  # pragma: no cover - Windows
        return 0.0
    divisor = 1e6 if sys.platform == "darwin" else 1e3
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor, 1)


def pick_device(requested: str = "auto") -> str:
    torch: Any = import_module("torch")
    if requested != "auto":
        return requested
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class DemucsSeparator:
    """htdemucs via demucs.apply on CPU, Apple MPS or CUDA; weights from the model cache."""

    name = HTDEMUCS_NAME
    version = MODEL_VERSION

    def __init__(self, device: str = "auto") -> None:
        self.requested = device
        self.last_stats: dict[str, float | str] = {}
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            pretrained: Any = import_module("demucs.pretrained")
            folder = htdemucs_dir()
            recipe = Path(pretrained.REMOTE_ROOT) / "htdemucs.yaml"
            local = folder / "htdemucs.yaml"
            if not local.is_file():
                shutil.copyfile(recipe, local)
            self._model = pretrained.get_model("htdemucs", repo=folder)
            self._model.eval()
        return self._model

    def separate(self, audio: Audio, start_frame: int) -> dict[str, Audio]:
        torch: Any = import_module("torch")
        apply: Any = import_module("demucs.apply")
        model = self._load()
        device = pick_device(self.requested)
        tensor = torch.from_numpy(np.ascontiguousarray(audio.T))[None]
        started = time.perf_counter()
        with torch.no_grad():
            out = apply.apply_model(
                model, tensor, device=device, split=True, overlap=0.25, shifts=0, progress=False
            )
        seconds = time.perf_counter() - started
        self.last_stats = {
            "seconds": round(seconds, 3),
            "device": device,
            "peak_rss_mb": peak_rss_mb(),
            "window_seconds": round(len(audio) / SAMPLE_RATE, 3),
        }
        logger.info("separated %.1f s on %s in %.1f s", len(audio) / SAMPLE_RATE, device, seconds)
        sources: list[str] = list(model.sources)
        array = out[0].cpu().numpy()
        return {
            name: np.ascontiguousarray(array[sources.index(name)].T, dtype=np.float32)
            for name in ("drums", "bass", "other", "vocals")
        }


_separator: Separator | None = None


def default_separator(device: str | None = None) -> Separator:
    """Process-wide Demucs separator; the device comes from settings (stems_device)."""
    global _separator
    if _separator is None:
        from mixconsole.config import load_settings

        _separator = DemucsSeparator(device or load_settings().stems_device)
    return _separator


def fold_residual(mix: Audio, stems: dict[str, Audio]) -> dict[str, Audio]:
    """Make the stems sum to the mix exactly by assigning the residual to ``other``."""
    folded = {name: np.asarray(stems[name], dtype=np.float32) for name in STEM_NAMES}
    others = (folded["drums"].astype(np.float64) + folded["bass"] + folded["vocals"]).astype(
        np.float32
    )
    folded["other"] = (mix.astype(np.float64) - others).astype(np.float32)
    return folded


def _path(root: Path, pcm_sha256: str, version: str, start: int, end: int) -> Path:
    return root / "stems" / pcm_sha256 / version / f"{start}-{end}"


def _read(base: Path) -> StemSet | None:
    try:
        meta = json.loads(base.with_suffix(".json").read_text())
        with np.load(base.with_suffix(".npz"), allow_pickle=False) as archive:
            stems = {name: np.asarray(archive[name], dtype=np.float32) for name in STEM_NAMES}
        if any(s.ndim != 2 or s.shape[1] != 2 for s in stems.values()):
            return None
        return StemSet(
            int(meta["start_frame"]),
            stems,
            {k: int(v) for k, v in meta.get("latency_frames", {}).items()},
            str(meta["model"]),
            dict(meta.get("stats", {})),
        )
    except (OSError, ValueError, KeyError, EOFError):
        return None


def _write(base: Path, result: StemSet) -> None:
    buffer = io.BytesIO()
    np.savez(buffer, **result.stems)  # pyright: ignore[reportArgumentType]
    atomic_write(base.with_suffix(".npz"), buffer.getvalue())
    meta = {
        "start_frame": result.start_frame,
        "model": result.model,
        "latency_frames": result.latency_frames,
        "stats": result.stats,
        "checkpoint_sha256": HTDEMUCS_SHA256,
    }
    atomic_write(base.with_suffix(".json"), (json.dumps(meta, sort_keys=True) + "\n").encode())


def separate_window(
    samples: Audio,
    pcm_sha256: str,
    window: tuple[int, int],
    *,
    cache_root: Path | None,
    separator: Separator | None = None,
) -> StemSet:
    """Stems for track frames [window), from the cache or a fresh separation."""
    start, end = window
    chosen = separator or default_separator()
    base = _path(cache_root, pcm_sha256, chosen.version, start, end) if cache_root else None
    if base is not None and (cached := _read(base)) is not None:
        return cached
    chunk = np.ascontiguousarray(samples[start:end])
    separated = fold_residual(chunk, chosen.separate(chunk, start))
    stats = dict(getattr(chosen, "last_stats", {}))
    result = StemSet(start, separated, dict.fromkeys(STEM_NAMES, 0), chosen.version, stats)
    if base is not None:
        _write(base, result)
    return result


def compensate(stem_set: StemSet) -> StemSet:
    """Advance each stem by its separator latency so all stems line up with the dry mix."""
    if not any(stem_set.latency_frames.values()):
        return stem_set
    aligned: dict[str, Audio] = {}
    for name, data in stem_set.stems.items():
        shift = stem_set.latency_frames.get(name, 0)
        aligned[name] = (
            np.concatenate((data[shift:], np.zeros((shift, 2), dtype=np.float32)))
            if shift > 0
            else data
        )
    return StemSet(
        stem_set.start_frame,
        aligned,
        dict.fromkeys(aligned, 0),
        stem_set.model,
        stem_set.stats,
    )


def resum(
    stems: dict[str, Audio],
    gains: dict[str, Any] | None = None,
    latency_frames: dict[str, int] | None = None,
) -> Audio:
    """Sum stems with per-stem gain (scalar or per-frame curve) and latency compensation.

    A stem delayed by ``latency`` frames is advanced by that many frames, zero padded at
    the end, so every stem lines up with the dry mix.
    """
    frames = len(next(iter(stems.values())))
    total = np.zeros((frames, 2), dtype=np.float64)
    for name, data in stems.items():
        shift = (latency_frames or {}).get(name, 0)
        aligned = data[shift:] if shift > 0 else data
        gain = (gains or {}).get(name, 1.0)
        gain = np.asarray(gain, dtype=np.float64)
        gain = gain[: len(aligned), None] if gain.ndim else gain
        total[: len(aligned)] += aligned.astype(np.float64) * gain
    return total.astype(np.float32)


__all__ = [
    "MODEL_VERSION",
    "STEM_NAMES",
    "WINDOW_SECONDS",
    "DemucsSeparator",
    "Separator",
    "StemSet",
    "available",
    "compensate",
    "default_separator",
    "fold_residual",
    "pick_device",
    "resum",
    "separate_window",
    "window_frames",
]
