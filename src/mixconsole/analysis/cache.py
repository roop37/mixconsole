"""Content/version addressed JSON + NPZ; atomic replacement and pair integrity checks."""

import hashlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from mixconsole.analysis.models import TrackAnalysis


def cache_root(cache_dir: str | Path | None = None) -> Path:
    return Path(
        cache_dir or os.environ.get("MIXCONSOLE_CACHE_DIR", "~/.cache/mixconsole")
    ).expanduser()


def cache_path(root: Path, pcm_hash: str, versions: dict[str, str]) -> Path:
    fingerprint = hashlib.sha256(json.dumps(versions, sort_keys=True).encode()).hexdigest()[:24]
    name = versions["beats"].split("@")[0]
    return root / pcm_hash / f"{name}@{fingerprint}"


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_analysis(analysis: TrackAnalysis, destination: str | Path) -> None:
    """Export JSON and a sibling NPZ; JSON is the final commit/integrity record."""
    path = Path(destination)
    npz = path.with_suffix(".npz")
    if path.suffix.lower() != ".json":
        raise ValueError("analysis destination must have a JSON extension")
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        short_term_lufs=analysis.arrays["short_term_lufs"],
        bar_energy=analysis.arrays["bar_energy"],
    )
    payload = buffer.getvalue()
    stored = analysis.model_copy(deep=True)
    stored.arrays_sha256 = hashlib.sha256(payload).hexdigest()
    stored.loudness.short_term_lufs.file = npz.name
    stored.bar_energy.file = npz.name
    atomic_write(npz, payload)
    atomic_write(path, (stored.model_dump_json(indent=2) + "\n").encode())


def load_analysis(path: str | Path) -> TrackAnalysis:
    source = Path(path)
    analysis = TrackAnalysis.model_validate_json(source.read_bytes())
    refs = [analysis.loudness.short_term_lufs, analysis.bar_energy]
    if any(Path(r.file).name != r.file or r.file != refs[0].file for r in refs):
        raise ValueError("NPZ must be a sibling file")
    data = (source.parent / refs[0].file).read_bytes()
    if hashlib.sha256(data).hexdigest() != analysis.arrays_sha256:
        raise ValueError("analysis JSON/NPZ integrity mismatch")
    with np.load(io.BytesIO(data), allow_pickle=False) as archive:
        for ref in refs:
            values = np.asarray(archive[ref.key], dtype=np.float64)
            if list(values.shape) != ref.shape or not np.isfinite(values).all():
                raise ValueError("invalid analysis array")
            analysis.arrays[ref.key] = values
    return analysis


def read_cached(path: Path) -> TrackAnalysis | None:
    try:
        result = load_analysis(path / "analysis.json")
    except (OSError, ValueError, KeyError, EOFError):
        return None
    result.mark_cache_hit()
    return result


def cache_info(root: Path) -> dict[str, int]:
    files = list(root.rglob("*")) if root.is_dir() else []
    return {
        "entries": sum(p.name == "analysis.json" for p in files),
        "bytes": sum(p.stat().st_size for p in files if p.is_file()),
    }


def clear_cache(root: Path) -> int:
    """Remove recognized cache entries only, preserving unrelated files."""
    count = 0
    if root.is_dir():
        for directory in root.iterdir():
            if (
                directory.is_dir()
                and not directory.is_symlink()
                and len(directory.name) == 64
                and all(c in "0123456789abcdef" for c in directory.name)
            ):
                for entry in directory.iterdir():
                    if (
                        entry.is_dir()
                        and not entry.is_symlink()
                        and "@" in entry.name
                        and (entry / "analysis.json").is_file()
                    ):
                        shutil.rmtree(entry)
                        count += 1
                if not any(directory.iterdir()):
                    directory.rmdir()
        index = root / "files"
        if index.is_dir() and not index.is_symlink():
            for file in index.glob("*.json"):
                file.unlink()
    return count


def read_index(root: Path, file_hash: str) -> str | None:
    try:
        value: Any = json.loads((root / "files" / f"{file_hash}.json").read_text())
        pcm = str(value["pcm_sha256"])
        if len(pcm) == 64 and all(c in "0123456789abcdef" for c in pcm):
            return pcm
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None
