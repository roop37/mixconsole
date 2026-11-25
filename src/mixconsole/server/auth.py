"""Local token: a random secret in a 0600 file, required on every request except /health."""

import hmac
import os
import secrets
from pathlib import Path

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


def token_path(data_dir: Path) -> Path:
    return data_dir / "server.token"


def issue_token(data_dir: Path) -> str:
    """Create a fresh token for this server run (the previous one stops working)."""
    token = secrets.token_urlsafe(32)
    path = token_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(token + "\n")
    path.chmod(0o600)
    return token


def read_token(data_dir: Path) -> str | None:
    path = token_path(data_dir)
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def token_matches(expected: str, supplied: str | None) -> bool:
    return supplied is not None and hmac.compare_digest(expected.encode(), supplied.encode())
