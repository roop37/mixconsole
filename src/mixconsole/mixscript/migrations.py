"""Pure, deterministic and idempotent v1 → v1.1 migration."""

from copy import deepcopy
from typing import Any

from mixconsole.mixscript.models import MixScript, Transition


def upgrade(data: dict[str, Any]) -> dict[str, Any]:
    """Assign positional IDs once; preserve existing IDs, extensions and point order."""
    script = deepcopy(data)
    MixScript.model_validate(script)
    if script["version"] == "mixscript/v1.1":
        return script
    used = set(script["tracks"])
    for transition in script["transitions"]:
        for obj in [
            transition,
            *transition.get("automation", []),
            *transition.get("effects", []),
            *transition.get("candidates", []),
        ]:
            if obj.get("id"):
                used.add(obj["id"])
    for index, transition in enumerate(script["transitions"]):
        objects = [(f"transition_{index}", transition)]
        for group in ("automation", "effects"):
            objects.extend(
                (f"transition_{index}_{group}_{i}", obj)
                for i, obj in enumerate(transition.get(group, []))
            )
        for base, obj in objects:
            if obj.get("id"):
                continue
            identifier = base
            suffix = 1
            while identifier in used:
                identifier = f"{base}_{suffix}"
                suffix += 1
            obj["id"] = identifier
            used.add(identifier)
    script["version"] = "mixscript/v1.1"
    MixScript.model_validate(script)
    return script


def validate_locks(before: Transition, after: Transition) -> None:
    """Planner boundary: reject edits to pinned values or removal of pinned lanes."""
    fields = {"exit", "entry", "length_bars", "family", "tempo", "key"}
    old_lanes = {lane.id: lane for lane in before.automation}
    new_lanes = {lane.id: lane for lane in after.automation}
    for lock in before.locks:
        old = getattr(before, lock) if lock in fields else old_lanes[lock]
        new = getattr(after, lock) if lock in fields else new_lanes.get(lock)
        if old != new:
            raise ValueError(f"locked value changed: {lock}")
