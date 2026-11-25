"""Generate the lockfile license inventory; check offline using reviewed metadata.

--refresh reads installed metadata or versioned PyPI metadata for absent extras,
then records a portable snapshot. --check never accesses the network. All versions
(including optional/platform packages) must match; unknown licenses fail closed.
The gate checks distribution metadata, not every embedded native source notice.
"""

import argparse
import hashlib
import importlib.metadata
import json
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "scripts/licenses/metadata.json"
NOTICES = ROOT / "scripts/licenses/NOTICES.md"
ALLOWED = {
    "MIT",
    "ISC",
    "Apache-2.0",
    "MPL-2.0",
    "PSF-2.0",
    "Zlib",
    "0BSD",
    "CC0-1.0",
    "MIT-0",
    "Unlicense",
}
# Torch's optional CPU wheel reports BSL-1.0 for bundled Boost components.
# Review this narrow exception against torch's license notice at each version bump.
TORCH_BUNDLED = {"BSL-1.0"}
# Ambiguous legacy metadata reviewed against installed license files; version-bound
# overrides prevent new versions inheriting an unaudited exception.
REVIEWED = {
    ("mpmath", "1.3.0"): "BSD-3-Clause",
    ("sympy", "1.14.0"): "BSD-3-Clause",
    ("torchaudio", "2.11.1"): "BSD-2-Clause",
    ("colorama", "0.4.6"): "BSD-3-Clause",
    ("jinja2", "3.1.6"): "BSD-3-Clause",
    ("nodeenv", "1.12.0"): "BSD-3-Clause",
    ("numba", "0.68.1"): "BSD-2-Clause",
    ("scipy", "1.18.1"): "BSD-3-Clause",
}
CLASSIFIERS = {
    "MIT License": "MIT",
    "Apache Software License": "Apache-2.0",
    "ISC License (ISCL)": "ISC",
    "Python Software Foundation License": "PSF-2.0",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
}
ALIASES = {
    "Apache 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "BSD 3-Clause License": "BSD-3-Clause",
    "ISC License": "ISC",
    "PSFL": "PSF-2.0",
}


def lock_packages(root=ROOT):
    lock = tomllib.loads((root / "uv.lock").read_text())
    return sorted(
        (p for p in lock["package"] if p["name"] != "mixconsole"),
        key=lambda p: (p["name"], p["version"]),
    )


def normalize(name, version, expression, license_text, classifiers):
    if expression:
        return expression
    if (name, version) in REVIEWED:
        return REVIEWED[name, version]
    if license_text in ALIASES:
        return ALIASES[license_text]
    if re.fullmatch(r"[A-Za-z0-9.() +\-]+", license_text or "") and license_text != "UNKNOWN":
        return license_text
    for classifier in classifiers:
        if classifier.split(" :: ")[-1] in CLASSIFIERS:
            return CLASSIFIERS[classifier.split(" :: ")[-1]]
    raise ValueError(f"unreviewed license for {name}=={version}")


def read_metadata(package):
    name, version = package["name"], package["version"]
    upstream_version = version.split("+")[0]
    url = f"https://pypi.org/pypi/{name}/{upstream_version}/json"
    try:
        dist = importlib.metadata.distribution(name)
        if dist.version != version:
            raise importlib.metadata.PackageNotFoundError(name)
        metadata = dist.metadata
        expression = metadata.get("License-Expression", "")
        license_text = metadata.get("License", "")
        classifiers = metadata.get_all("Classifier", [])
        source = "installed METADATA"
    except importlib.metadata.PackageNotFoundError:
        with urllib.request.urlopen(url, timeout=30) as response:
            info = json.load(response)["info"]
        expression = info.get("license_expression") or ""
        license_text = info.get("license") or ""
        classifiers = info.get("classifiers") or []
        source = url
    license_id = normalize(name, upstream_version, expression, license_text, classifiers)
    return {
        "name": name,
        "version": version,
        "license": license_id,
        "license_expression": expression,
        "license_text_sha256": hashlib.sha256(license_text.encode()).hexdigest(),
        "classifiers": [c for c in classifiers if c.startswith("License")],
        "metadata_source": source,
        "url": f"https://pypi.org/project/{name}/{upstream_version}/",
        "source": package["source"],
    }


def allowed(expression, name):
    # LLVM exception adds permissions to allowed Apache-2.0; not a standalone license.
    expression = expression.replace("Apache-2.0 WITH LLVM-exception", "Apache-2.0")
    tokens = re.findall(r"[^\s()]+", expression)
    if not tokens:
        return False
    return all(
        t in {"AND", "OR"}
        or t in ALLOWED
        or (t in TORCH_BUNDLED and name == "torch")
        or re.fullmatch(r"BSD-\d-Clause(?:-Clear)?", t)
        or (t == "LGPL-2.1-or-later" and name == "soxr" and "soxr_ext" in NOTICES.read_text())
        for t in tokens
    )


def render(packages, records):
    by_key = {(r["name"], r["version"]): r for r in records}
    expected = {(p["name"], p["version"]) for p in packages}
    if set(by_key) != expected or len(records) != len(expected):
        raise ValueError("license metadata drift: run --refresh and review all new licenses")
    lines = [
        "# Third-party registry",
        "",
        "Generated by `uv run python scripts/third_party.py`; do not edit.",
        "",
        "All uv.lock distributions, including dev/docs and optional CPU neural dependencies.",
        "Licenses describe package metadata; bundled native notices also apply.",
        "The offline gate validates this versioned metadata snapshot and rejects unknown licenses.",
        "",
        "| Dependency | Version | License | URL |",
        "| --- | --- | --- | --- |",
    ]
    for package in packages:
        name, version = package["name"], package["version"]
        record = by_key[name, version]
        if record["source"] != package["source"]:
            raise ValueError(f"source drift: {name}")
        if name.startswith(("nvidia-", "cuda-")) or not allowed(record["license"], name):
            raise ValueError(f"license outside allowlist: {name}: {record['license']}")
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            dist = None
        if dist is not None and dist.version == version:
            md = dist.metadata
            actual = normalize(
                name,
                version.split("+")[0],
                md.get("License-Expression", ""),
                md.get("License", ""),
                md.get_all("Classifier", []),
            )
            if actual != record["license"]:
                raise ValueError(f"installed metadata drift: {name}")
        lines.append(f"| {name} | {version} | {record['license']} | [upstream]({record['url']}) |")
    lines += ["", NOTICES.read_text().strip(), ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.check and args.refresh:
        parser.error("--check and --refresh are mutually exclusive")
    packages = lock_packages()
    try:
        if args.refresh:
            records = [read_metadata(p) for p in packages]
            # Validate before replacing the reviewed snapshot.
            rendered = render(packages, records)
            SNAPSHOT.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
        else:
            rendered = render(packages, json.loads(SNAPSHOT.read_text()))
        destination = ROOT / "THIRD_PARTY.md"
        if args.check:
            if destination.read_text() != rendered:
                raise ValueError("THIRD_PARTY.md drift: run scripts/third_party.py")
            print(f"Third-party licenses: {len(packages)} locked distributions OK")
        else:
            destination.write_text(rendered)
            print(destination)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
