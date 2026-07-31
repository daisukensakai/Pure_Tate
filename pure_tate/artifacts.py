import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from .store import ROOT, load_json


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_migration() -> Dict[str, Any]:
    return load_json(ROOT / "proof" / "migrations" / "context-v2.json")


def load_artifacts(kind: str) -> List[Dict[str, Any]]:
    if kind not in {"attempts", "reviews"}:
        raise ValueError("unknown artifact kind %r" % kind)
    prefix = "ATT" if kind == "attempts" else "REV"
    values: List[Dict[str, Any]] = []
    directory = ROOT / "proof" / kind
    for path in sorted(directory.glob(prefix + "-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            values.append({"_path": str(path), "_error": str(exc)})
            continue
        if not isinstance(value, dict):
            values.append({"_path": str(path), "_error": "expected JSON object"})
            continue
        value["_path"] = str(path)
        values.append(value)
    return values


def legacy_attempt_ids() -> set:
    return set(load_migration().get("attempts", {}))


def legacy_review_ids() -> set:
    return set(load_migration().get("reviews", {}))


def next_artifact_id(kind: str) -> str:
    if kind not in {"attempts", "reviews"}:
        raise ValueError("unknown artifact kind %r" % kind)
    prefix = "ATT" if kind == "attempts" else "REV"
    numbers = []
    for artifact in load_artifacts(kind):
        match = re.fullmatch(prefix + r"-(\d{4})", str(artifact.get("id", "")))
        if match:
            numbers.append(int(match.group(1)))
    return "%s-%04d" % (prefix, (max(numbers) if numbers else 0) + 1)
