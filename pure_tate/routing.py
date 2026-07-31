from typing import Any, Dict, Iterable, List, Optional, Sequence

from .store import DATA, load_json


ENGINE_CONFIG = DATA / "engines.json"


def load_routing_config() -> Dict[str, Any]:
    value = load_json(ENGINE_CONFIG)
    if not isinstance(value, dict):
        raise ValueError("data/engines.json must be an object")
    engines = value.get("engines")
    if not isinstance(engines, dict) or not engines:
        raise ValueError("data/engines.json has no engines object")
    rotation = value.get("prover_rotation")
    escalation = value.get("escalation_order")
    if not isinstance(rotation, list) or not rotation:
        raise ValueError("data/engines.json missing prover_rotation")
    if not isinstance(escalation, list) or not escalation:
        raise ValueError("data/engines.json missing escalation_order")
    if any(not isinstance(item, str) or not item for item in rotation):
        raise ValueError("prover_rotation entries must be non-empty strings")
    if any(not isinstance(item, str) or not item for item in escalation):
        raise ValueError("escalation_order entries must be non-empty strings")
    unknown = sorted(
        (set(rotation) | set(escalation)) - set(engines)
    )
    if unknown:
        raise ValueError(
            "routing lists reference unknown engine(s): %s" % ", ".join(unknown)
        )
    return {
        "engines": engines,
        "prover_rotation": list(rotation),
        "escalation_order": list(escalation),
    }


def next_rotation_engine(
    math_attempt_ordinal: int,
    rotation: Sequence[str],
    allowed: Optional[Sequence[str]] = None,
) -> str:
    if math_attempt_ordinal < 0:
        raise ValueError("math_attempt_ordinal must be non-negative")
    sequence = _filter_allowed(rotation, allowed)
    if not sequence:
        raise ValueError("no prover engines remain after applying the allowlist")
    return sequence[math_attempt_ordinal % len(sequence)]


def next_escalation_engine(
    used_engines: Iterable[str],
    escalation: Sequence[str],
    exclude: Iterable[str] = (),
    allowed: Optional[Sequence[str]] = None,
) -> Optional[str]:
    blocked = {engine for engine in used_engines if engine} | {
        engine for engine in exclude if engine
    }
    for engine in _filter_allowed(escalation, allowed):
        if engine not in blocked:
            return engine
    return None


def select_prover_for_cell(
    math_attempt_ordinal: int,
    used_engines: Iterable[str],
    rotation: Sequence[str],
    escalation: Sequence[str],
    allowed: Optional[Sequence[str]] = None,
) -> Optional[str]:
    used = [engine for engine in used_engines if engine]
    if used:
        return next_escalation_engine(
            used,
            escalation,
            allowed=allowed,
        )
    return next_rotation_engine(
        math_attempt_ordinal,
        rotation,
        allowed=allowed,
    )


def select_reviewer(
    prover: Optional[str],
    used_reviewers: Iterable[str],
    escalation: Sequence[str],
    allowed: Optional[Sequence[str]] = None,
) -> Optional[str]:
    exclude = [prover] if prover else []
    return next_escalation_engine(
        used_reviewers,
        escalation,
        exclude=exclude,
        allowed=allowed,
    )


def _filter_allowed(
    engines: Sequence[str], allowed: Optional[Sequence[str]]
) -> List[str]:
    if allowed is None:
        return list(engines)
    allowed_set = set(allowed)
    return [engine for engine in engines if engine in allowed_set]
