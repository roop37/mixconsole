"""Export canonical MixScript v1 + v1.1 and TrackAnalysis v1 schemas from any directory."""

import argparse
import json
from pathlib import Path

from mixconsole.analysis.models import schema_json as analysis_schema_json
from mixconsole.bench.results import schema_json as bench_schema_json
from mixconsole.mixscript import schema_json


def artifacts() -> dict[Path, str]:
    root = Path(__file__).resolve().parents[1]
    outputs = {
        root / "schemas/mixscript-v1.json": schema_json("mixscript/v1"),
        root / "schemas/mixscript-v1.1.json": schema_json("mixscript/v1.1"),
        root / "schemas/track-analysis-v1.json": analysis_schema_json(),
        root / "schemas/bench-result-v1.json": bench_schema_json(),
    }
    lines = [
        "# MixScript v1.1 reference",
        "",
        "Generated from the JSON Schema; do not edit.",
        "",
        "Schema validation checks structure. Python validation also enforces references,",
        "unique IDs, ordered points, cue/play bounds and locks. M2 renders the",
        "supported stem-free families.",
        "",
    ]
    schema = json.loads(schema_json("mixscript/v1.1"))
    definitions = {"MixScript": schema, **schema.get("$defs", {})}
    for name, definition in definitions.items():
        lines += [f"## {name}", "", definition.get("description", ""), ""]
        if "properties" not in definition:
            continue
        lines += ["| Field | Required | Schema |", "| --- | --- | --- |"]
        for field, spec in definition["properties"].items():
            summary = json.dumps(spec, sort_keys=True, ensure_ascii=False).replace("|", "&#124;")
            summary = summary.replace("`", "&#96;")
            required = "yes" if field in definition.get("required", []) else "no"
            lines.append(f"| {field} | {required} | `{summary}` |")
        lines.append("")
    outputs[root / "docs/mixscript.md"] = "\n".join(lines).rstrip() + "\n"
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for destination, content in artifacts().items():
        if args.check:
            if not destination.exists() or destination.read_text(encoding="utf-8") != content:
                raise SystemExit(f"generated artifact drift: {destination}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
            print(destination)


if __name__ == "__main__":
    main()
