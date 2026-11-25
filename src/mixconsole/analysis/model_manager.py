"""Checksum-pinned, optional model downloads into the MixConsole cache."""

import hashlib
import os
import tempfile
from pathlib import Path
from urllib.request import urlopen

from mixconsole.analysis.cache import cache_root

BEAT_THIS_URL = "https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/final0.ckpt"
BEAT_THIS_SHA256 = "8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331"


def checkpoint_path() -> Path:
    """Return the override or pinned checkpoint path, without downloading."""
    override = os.environ.get("MIXCONSOLE_BEAT_THIS_CHECKPOINT")
    return Path(override) if override else cache_root() / "models" / "beat_this" / "final0.ckpt"


def fetch_beat_this() -> Path:
    """Download the official MIT checkpoint once and reject altered bytes."""
    destination = cache_root() / "models" / "beat_this" / "final0.ckpt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if hashlib.sha256(destination.read_bytes()).hexdigest() == BEAT_THIS_SHA256:
            return destination
        raise ValueError(f"checkpoint hash mismatch: {destination}")
    fd, temporary = tempfile.mkstemp(prefix=".beat-this-", dir=destination.parent)
    try:
        digest = hashlib.sha256()
        with os.fdopen(fd, "wb") as output, urlopen(BEAT_THIS_URL, timeout=30) as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != BEAT_THIS_SHA256:
            raise ValueError("downloaded Beat This! checkpoint hash mismatch")
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination
