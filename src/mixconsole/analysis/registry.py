"""Named backend registry, version provenance and transparent optional fallback."""

import importlib.util
import logging
from collections.abc import Callable, Mapping
from importlib.metadata import PackageNotFoundError, entry_points, version

from mixconsole.analysis.backends.beats import BeatThisBackend, LibrosaBeatBackend
from mixconsole.analysis.backends.cues import EdgeCueBackend
from mixconsole.analysis.backends.key import ProfileKeyBackend
from mixconsole.analysis.backends.loudness import PyloudnormBackend
from mixconsole.analysis.backends.sections import AllInOneBackend, NoveltySectionBackend
from mixconsole.analysis.interfaces import (
    Backend,
    BeatBackend,
    CueBackend,
    KeyBackend,
    LoudnessBackend,
    SectionBackend,
)
from mixconsole.analysis.model_manager import checkpoint_path
from mixconsole.io import file_sha256
from mixconsole.progress import Cancelled

logger = logging.getLogger(__name__)
BEATS: dict[str, BeatBackend] = {b.name: b for b in (LibrosaBeatBackend(), BeatThisBackend())}
KEYS: dict[str, KeyBackend] = {"profiles": ProfileKeyBackend()}
LOUDNESS: dict[str, LoudnessBackend] = {"pyloudnorm": PyloudnormBackend()}
SECTIONS: dict[str, SectionBackend] = {
    b.name: b for b in (NoveltySectionBackend(), AllInOneBackend())
}
CUES: dict[str, CueBackend] = {"edges": EdgeCueBackend()}
DEFAULTS = {
    "beats": "librosa",
    "key": "profiles",
    "loudness": "pyloudnorm",
    "sections": "novelty",
    "cues": "edges",
}


PLUGIN_GROUP = "mixconsole.backends"
FAMILY_GROUP = "mixconsole.families"  # reserved for M2 transition families
_KINDS: dict[str, dict[str, Backend]] = {
    "beats": BEATS,  # type: ignore[dict-item]
    "key": KEYS,  # type: ignore[dict-item]
    "loudness": LOUDNESS,  # type: ignore[dict-item]
    "sections": SECTIONS,  # type: ignore[dict-item]
    "cues": CUES,  # type: ignore[dict-item]
}
_plugins_loaded = False


def register(kind: str, backend: Backend) -> None:
    """Register a backend under ``kind``; names must not shadow built-ins."""
    if kind not in _KINDS:
        raise ValueError(f"unknown backend kind: {kind}")
    if not all(
        isinstance(getattr(backend, field, None), str) and getattr(backend, field)
        for field in ("name", "version")
    ) or not callable(getattr(backend, "analyze", None)):
        raise ValueError("backend must expose nonempty name/version and a callable analyze method")
    if backend.name in _KINDS[kind]:
        raise ValueError(f"backend {kind}={backend.name} already registered")
    _KINDS[kind][backend.name] = backend


def load_plugins() -> list[str]:
    """Load third-party backends from the ``mixconsole.backends`` entry-point group.

    Each entry point resolves to an object with ``kind``, ``name``, ``version`` and the
    kind's ``analyze`` method (or a zero-argument factory returning one). Broken plugins
    are logged and skipped; they never break core analysis.
    """
    global _plugins_loaded
    loaded: list[str] = []
    if _plugins_loaded:
        return loaded
    _plugins_loaded = True
    for entry in entry_points(group=PLUGIN_GROUP):
        try:
            obj = entry.load()
            backend = obj() if isinstance(obj, type) or not hasattr(obj, "analyze") else obj
            register(str(backend.kind), backend)
            loaded.append(f"{backend.kind}={backend.name}")
        except Exception as exc:
            logger.warning("skipping backend plugin %s: %s", entry.name, exc)
    return loaded


def selection(backends: Mapping[str, str] | None) -> dict[str, str]:
    load_plugins()
    names = DEFAULTS | dict(backends or {})
    registries: dict[str, Mapping[str, Backend]] = {
        "beats": BEATS,
        "key": KEYS,
        "loudness": LOUDNESS,
        "sections": SECTIONS,
        "cues": CUES,
    }
    for kind, name in names.items():
        if kind not in registries or name not in registries[kind]:
            raise ValueError(f"unknown backend {kind}={name}")
    if names["beats"] == "beat_this" and (
        importlib.util.find_spec("beat_this") is None or not checkpoint_path().is_file()
    ):
        logger.warning("beat_this unavailable (package/checkpoint); falling back to librosa")
        names["beats"] = "librosa"
    if names["sections"] == "allin1":
        logger.warning("allin1 is an optional stub (NATTEN caveat); falling back to novelty")
        names["sections"] = "novelty"
    return names


def versions(names: Mapping[str, str]) -> dict[str, str]:
    registries: dict[str, Mapping[str, Backend]] = {
        "beats": BEATS,
        "key": KEYS,
        "loudness": LOUDNESS,
        "sections": SECTIONS,
        "cues": CUES,
    }
    result = {kind: f"{name}@{registries[kind][name].version}" for kind, name in names.items()}
    # Bump when orchestration changes outputs (tempo map, sections, grid fill).
    result["pipeline"] = "analysis@3"
    for package in ("numpy", "scipy", "librosa", "pyloudnorm", "soundfile", "numba") + (
        ("beat-this", "torch", "torchaudio") if names["beats"] == "beat_this" else ()
    ):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "unavailable"
    if names["beats"] == "beat_this":
        result["beat_this_checkpoint"] = file_sha256(checkpoint_path())
    return result


def run[T](kind: str, names: dict[str, str], call: Callable[[str], T]) -> T:
    try:
        return call(names[kind])
    except Cancelled:
        raise
    except Exception as exc:
        if names[kind] == DEFAULTS[kind]:
            raise
        logger.warning("%s failed (%s); falling back to %s", names[kind], exc, DEFAULTS[kind])
        names[kind] = DEFAULTS[kind]
        return call(names[kind])
