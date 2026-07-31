import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .models import Claim, Edge, Source


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORTS_GENERATED = ROOT / "reports" / "generated"
PACKETS_GENERATED = ROOT / "proof" / "packets" / "generated"


class DataError(ValueError):
    pass


def load_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("%s: %s" % (path, exc))
    if not isinstance(value, dict):
        raise DataError("%s: expected a JSON object" % path)
    return value


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DataError("%s: %s" % (path, exc))
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DataError("%s:%d: %s" % (path, number, exc))
        if not isinstance(value, dict):
            raise DataError("%s:%d: expected a JSON object" % (path, number))
        rows.append(value)
    return rows


def _index_unique(items: Iterable[Any], label: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for item in items:
        if item.id in result:
            raise DataError("duplicate %s id %s" % (label, item.id))
        result[item.id] = item
    return result


def load_repository() -> Tuple[
    Dict[str, Any],
    Dict[str, Any],
    Dict[str, Source],
    Dict[str, Claim],
    List[Edge],
]:
    config = load_json(DATA / "config.json")
    target = load_json(DATA / "target.json")
    sources = _index_unique(
        (Source.from_dict(row) for row in load_jsonl(DATA / "sources.jsonl")),
        "source",
    )
    claims = _index_unique(
        (Claim.from_dict(row) for row in load_jsonl(DATA / "claims.jsonl")),
        "claim",
    )
    edges = [Edge.from_dict(row) for row in load_jsonl(DATA / "edges.jsonl")]
    return config, target, sources, claims, edges


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
