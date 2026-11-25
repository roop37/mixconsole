"""MixScript validation, v1 → v1.1 upgrade, canonical JSON and schema export."""

import json
from pathlib import Path

from mixconsole.mixscript.migrations import upgrade
from mixconsole.mixscript.models import MixScript
from mixconsole.mixscript.v1 import MixScript as LegacyMixScript

__all__ = [
    "LATEST_VERSION",
    "MixScript",
    "dumps_mixscript",
    "load_mixscript",
    "schema_json",
    "upgrade",
]

LATEST_VERSION = "mixscript/v1.1"


def load_mixscript(path: str | Path, *, upgrade_to_latest: bool = False) -> MixScript:
    """Read and validate a UTF-8 MixScript file, including cross references.

    With ``upgrade_to_latest`` a v1 file is migrated to v1.1 (deterministic ids) in memory.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if upgrade_to_latest:
        data = upgrade(data)
    return MixScript.model_validate(data)


def dumps_mixscript(script: MixScript) -> str:
    """Canonical JSON text: sorted keys, 2-space indent, trailing newline, no NaN."""
    payload = script.model_dump(mode="json", exclude_defaults=True)
    payload["version"] = script.version
    return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"


def schema_json(version: str = "mixscript/v1") -> str:
    """Return stable JSON Schema bytes as text; semantic checks also require Pydantic."""
    if version not in ("mixscript/v1", "mixscript/v1.1"):
        raise ValueError("unsupported schema version")
    schema = (LegacyMixScript if version == "mixscript/v1" else MixScript).model_json_schema()
    if version == "mixscript/v1.1":
        schema["properties"]["version"] = {"const": version, "type": "string"}
        for name in ("Transition", "AutomationLane", "Effect"):
            definition = schema["$defs"][name]
            definition["required"].append("id")
            definition["properties"]["id"] = {"type": "string", "pattern": "^[A-Za-z0-9_-]+$"}
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:mixconsole:{version.replace('/', ':')}"
    return json.dumps(schema, indent=2, sort_keys=True, allow_nan=False) + "\n"
