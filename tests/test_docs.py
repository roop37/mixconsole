"""Execute explicitly runnable docs blocks in isolated temporary directories."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"<!-- test -->\s*```(python|sh)\n(.*?)\n```", re.DOTALL)
CASES = [
    (path.relative_to(ROOT).as_posix(), index, lang, source)
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    for index, (lang, source) in enumerate(BLOCK.findall(path.read_text()))
]


@pytest.mark.parametrize(
    ("document", "index", "language", "source"),
    CASES,
    ids=[f"{d}:{i}:{lang}" for d, i, lang, _ in CASES],
)
def test_runnable_docs(document, index, language, source, tmp_path):
    env = os.environ.copy()
    env.update(
        MIXCONSOLE_CONFIG=str(tmp_path / "config.toml"),
        MIXCONSOLE_CACHE_DIR=str(tmp_path / "cache"),
        PYTHONPATH=str(ROOT / "src"),
        PATH=str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", ""),
    )
    command = (
        [sys.executable, "-c", source]
        if language == "python"
        else ["bash", "-euo", "pipefail", "-c", source]
    )
    result = subprocess.run(
        command, cwd=tmp_path, env=env, text=True, capture_output=True, timeout=60, check=False
    )
    assert result.returncode == 0, f"{document}:{index}\n{result.stdout}\n{result.stderr}"


def test_marked_blocks_are_collected():
    assert CASES
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]:
        text = path.read_text()
        assert text.count("<!-- test -->") == len(BLOCK.findall(text)), path
