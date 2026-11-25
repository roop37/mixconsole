"""Structural diff between two MixScript documents (JSON-pointer paths)."""

from typing import Any, cast

from pydantic import BaseModel


class Change(BaseModel):
    path: str
    op: str  # "added" | "removed" | "changed"
    before: Any = None
    after: Any = None


def diff_documents(before: object, after: object, path: str = "") -> list[Change]:
    if isinstance(before, dict) and isinstance(after, dict):
        left = cast(dict[str, Any], before)
        right = cast(dict[str, Any], after)
        out: list[Change] = []
        for key in sorted(set(left) | set(right)):
            sub = f"{path}/{key}"
            if key not in left:
                out.append(Change(path=sub, op="added", after=right[key]))
            elif key not in right:
                out.append(Change(path=sub, op="removed", before=left[key]))
            else:
                out += diff_documents(left[key], right[key], sub)
        return out
    if isinstance(before, list) and isinstance(after, list):
        old = cast(list[Any], before)
        new = cast(list[Any], after)
        out = []
        for i in range(max(len(old), len(new))):
            sub = f"{path}/{i}"
            if i >= len(old):
                out.append(Change(path=sub, op="added", after=new[i]))
            elif i >= len(new):
                out.append(Change(path=sub, op="removed", before=old[i]))
            else:
                out += diff_documents(old[i], new[i], sub)
        return out
    if before == after:
        return []
    return [Change(path=path or "/", op="changed", before=before, after=after)]
