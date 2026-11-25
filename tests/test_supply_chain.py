"""The license gate fails closed on drift and prohibited distributions."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("third_party", ROOT / "scripts/third_party.py")
assert spec is not None
assert spec.loader is not None
licenses = importlib.util.module_from_spec(spec)
spec.loader.exec_module(licenses)


def test_license_inventory_and_negative_drift_cases():
    packages = licenses.lock_packages()
    records = json.loads(licenses.SNAPSHOT.read_text())
    assert licenses.render(packages, records) == (ROOT / "THIRD_PARTY.md").read_text()
    with pytest.raises(ValueError, match="metadata drift"):
        licenses.render(packages, records[:-1])
    changed = [dict(record) for record in records]
    changed[0]["source"] = {"registry": "https://unreviewed.example"}
    with pytest.raises(ValueError, match="source drift"):
        licenses.render(packages, changed)
    changed[0] = {**records[0], "license": "GPL-3.0-only"}
    with pytest.raises(ValueError, match="outside allowlist"):
        licenses.render(packages, changed)


@pytest.mark.parametrize(
    "license_id", ["GPL-3.0-only", "AGPL-3.0", "LicenseRef-NVIDIA", "", "UNKNOWN", "CC-BY-NC-4.0"]
)
def test_disallowed_licenses(license_id):
    assert not licenses.allowed(license_id, "test-package")


def test_reviewed_lgpl_requires_documentation(monkeypatch, tmp_path):
    assert not licenses.allowed("LGPL-2.1-or-later", "arbitrary-package")
    notice = tmp_path / "NOTICES.md"
    notice.write_text("")
    monkeypatch.setattr(licenses, "NOTICES", notice)
    assert not licenses.allowed("LGPL-2.1-or-later", "soxr")


def test_lock_contains_only_cpu_optional_torch():
    packages = licenses.lock_packages()
    assert not any(p["name"].startswith(("nvidia-", "cuda-")) for p in packages)
    cpu = [p for p in packages if p["name"] == "torch" and "+cpu" in p["version"]]
    assert cpu
    assert all(p["source"]["registry"].endswith("/whl/cpu") for p in cpu)
