"""Pre-commit policy: no audio/weights and conventional commit subjects."""

import argparse
import re
import sys
from pathlib import Path

AUDIO = {
    ".wav",
    ".wave",
    ".flac",
    ".mp3",
    ".ogg",
    ".opus",
    ".aac",
    ".m4a",
    ".aif",
    ".aiff",
    ".au",
    ".wma",
}
WEIGHTS = {".pt", ".pth", ".safetensors", ".ckpt", ".onnx", ".h5", ".hdf5", ".tflite", ".pb"}
SUBJECT = re.compile(
    r"(?:feat|fix|test|docs|chore|refactor|perf|build|ci|style|revert)(?:\([a-z0-9_-]+\))?!?: .+"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit-msg", action="store_true")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    errors = []
    for name in args.paths:
        path = Path(name)
        if args.commit_msg:
            text = path.read_text()
            if not SUBJECT.fullmatch(text.splitlines()[0] if text else ""):
                errors.append(f"{name}: use a conventional commit subject")
            continue
        parts = path.parts
        fixture = len(parts) >= 2 and parts[:2] == ("tests", "fixtures")
        if path.suffix.lower() in WEIGHTS or (path.suffix.lower() in AUDIO and not fixture):
            errors.append(f"{name}: audio outside synthetic fixtures or model weights prohibited")
    for error in errors:
        print(error, file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
