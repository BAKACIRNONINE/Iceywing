from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .util import state_home


def _path() -> Path:
    path = state_home() / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def append(event: dict[str, Any]) -> None:
    row = dict(event)
    row.setdefault("timestamp", int(time.time()))
    with _path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def all_events() -> list[dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def operations(repo: Path) -> list[dict[str, Any]]:
    target = str(repo.resolve())
    grouped = {}
    for event in all_events():
        if event.get("repo") != target:
            continue
        opid = event.get("operation_id")
        if not opid:
            continue
        item = grouped.setdefault(opid, {"operation_id": opid, "events": []})
        item["events"].append(event)
        item.update(event)

    result = list(grouped.values())
    result.sort(
        key=lambda item: max(e.get("timestamp", 0) for e in item["events"]),
        reverse=True,
    )
    return result


def latest(repo: Path) -> dict[str, Any] | None:
    rows = operations(repo)
    return rows[0] if rows else None
