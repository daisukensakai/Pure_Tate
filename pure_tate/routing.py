from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .store import DATA, ROOT, atomic_write_json, load_json


ENGINE_CONFIG = DATA / "engines.json"
HIGH_TIER_LEDGER = ROOT / "research" / "routing" / "high-tier-turns.json"


def load_routing_config() -> Dict[str, Any]:
    value = load_json(ENGINE_CONFIG)
    if not isinstance(value, dict):
        raise ValueError("data/engines.json must be an object")
    engines = value.get("engines")
    if not isinstance(engines, dict) or not engines:
        raise ValueError("data/engines.json has no engines object")
    rotation = value.get("prover_rotation")
    escalation = value.get("escalation_order")
    high_tier = value.get("high_tier_chain_engines")
    if not isinstance(rotation, list) or not rotation:
        raise ValueError("data/engines.json missing prover_rotation")
    if not isinstance(escalation, list) or not escalation:
        raise ValueError("data/engines.json missing escalation_order")
    if not isinstance(high_tier, list) or len(high_tier) != 2:
        raise ValueError("data/engines.json needs two high_tier_chain_engines")
    for name, items in (
        ("prover_rotation", rotation),
        ("escalation_order", escalation),
        ("high_tier_chain_engines", high_tier),
    ):
        if any(not isinstance(item, str) or not item for item in items):
            raise ValueError("%s entries must be non-empty strings" % name)
    unknown = sorted((set(rotation) | set(escalation) | set(high_tier)) - set(engines))
    if unknown:
        raise ValueError(
            "routing lists reference unknown engine(s): %s" % ", ".join(unknown)
        )
    return {
        "engines": engines,
        "prover_rotation": list(rotation),
        "escalation_order": list(escalation),
        "high_tier_chain_engines": list(high_tier),
    }


def _default_chain_ledger() -> Dict[str, Any]:
    # The preceding historical high-tier dispatch was GPT-5.6-Sol (codex), so
    # the first newly opened chain is Opus then GPT.
    return {
        "schema_version": 1,
        "last_chain_order": ["codex", "claude"],
        "chains": [],
        "seed": {
            "source": "historical-gpt-5.6-sol-dispatch",
            "last_engine": "codex",
        },
    }


def load_high_tier_ledger() -> Dict[str, Any]:
    if not HIGH_TIER_LEDGER.is_file():
        return _default_chain_ledger()
    value = load_json(HIGH_TIER_LEDGER)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("high-tier routing ledger is invalid")
    order = value.get("last_chain_order")
    chains = value.get("chains")
    configured = set(load_routing_config()["high_tier_chain_engines"])
    if (
        not isinstance(order, list)
        or set(order) != configured
        or not isinstance(chains, list)
    ):
        raise ValueError("high-tier routing ledger has invalid chain state")
    return value


def _write_high_tier_ledger(value: Dict[str, Any]) -> None:
    atomic_write_json(HIGH_TIER_LEDGER, value)


def high_tier_chain_order(
    chain_id: str, *, persist: bool = True
) -> List[str]:
    """Return the stable Opus/GPT order for one escalation chain.

    Chains alternate as units.  Individual model starts do not change the
    preference, which prevents a partial or deferred chain from flipping the
    next proof chain.
    """
    if not chain_id:
        raise ValueError("high-tier chain id is required")
    ledger = load_high_tier_ledger()
    for chain in ledger["chains"]:
        if chain.get("id") == chain_id:
            return list(chain["order"])
    previous = list(ledger["last_chain_order"])
    order = [previous[1], previous[0]]
    if persist:
        ledger["chains"].append(
            {"id": chain_id, "order": order, "pending": list(order), "dispatches": []}
        )
        ledger["last_chain_order"] = list(order)
        _write_high_tier_ledger(ledger)
    return order


def record_high_tier_dispatch(chain_id: str, engine: str) -> None:
    ledger = load_high_tier_ledger()
    for chain in ledger["chains"]:
        if chain.get("id") != chain_id:
            continue
        if engine not in chain.get("order", []):
            raise ValueError("engine is not assigned to high-tier chain")
        if engine in chain.get("pending", []):
            chain["pending"].remove(engine)
        chain.setdefault("dispatches", []).append(engine)
        _write_high_tier_ledger(ledger)
        return
    raise ValueError("high-tier chain is not open: %s" % chain_id)


def high_tier_chain_state(chain_id: str) -> Optional[Dict[str, Any]]:
    for chain in load_high_tier_ledger()["chains"]:
        if chain.get("id") == chain_id:
            return dict(chain)
    return None


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


def _next_high_tier(
    used: set[str],
    order: Sequence[str],
    allowed: Optional[Sequence[str]],
) -> Optional[str]:
    remaining = [engine for engine in order if engine not in used]
    if not remaining:
        return None
    # A chain must not skip a temporarily unavailable first high-tier slot and
    # use its partner: the first slot remains pending for a later dispatch.
    preferred = remaining[0]
    return preferred if preferred in _filter_allowed([preferred], allowed) else None


def next_escalation_engine(
    used_engines: Iterable[str],
    escalation: Sequence[str],
    exclude: Iterable[str] = (),
    allowed: Optional[Sequence[str]] = None,
    *,
    high_tier_order: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Choose the next forward-only retry engine.

    ``escalation`` contains Grok and Qwen.  The two model high-tier tail is
    supplied separately so every proof chain can freeze its own pair order.
    """
    used = {engine for engine in used_engines if engine}
    blocked = used | {engine for engine in exclude if engine}
    high = list(high_tier_order or load_routing_config()["high_tier_chain_engines"])
    base = list(escalation)
    if "grok" in used and "qwen" not in used:
        return "qwen" if "qwen" in _filter_allowed(["qwen"], allowed) else None
    if "qwen" in used:
        return _next_high_tier(blocked, high, allowed)
    used_high = used.intersection(high)
    if used_high:
        # A fresh Opus/GPT proof starts at its own high-tier stage.  Its retry
        # can only use the other model, independent of chain preference.
        remaining = [engine for engine in high if engine not in used_high]
        if len(remaining) != 1:
            return None
        candidate = remaining[0]
        return candidate if candidate in _filter_allowed([candidate], allowed) else None
    for engine in base:
        if engine not in blocked and engine in _filter_allowed([engine], allowed):
            return engine
    return None


def select_prover_for_cell(
    math_attempt_ordinal: int,
    used_engines: Iterable[str],
    rotation: Sequence[str],
    escalation: Sequence[str],
    allowed: Optional[Sequence[str]] = None,
    *,
    chain_id: Optional[str] = None,
    persist_chain: bool = True,
) -> Optional[str]:
    used = {engine for engine in used_engines if engine}
    if not used:
        return next_rotation_engine(math_attempt_ordinal, rotation, allowed=allowed)
    needs_pair = "qwen" in used or bool(
        used.intersection(load_routing_config()["high_tier_chain_engines"])
    )
    order = None
    if needs_pair and chain_id:
        order = high_tier_chain_order(chain_id, persist=persist_chain)
    return next_escalation_engine(
        used,
        escalation,
        allowed=allowed,
        high_tier_order=order,
    )


def select_reviewer(
    prover: Optional[str],
    used_reviewers: Iterable[str],
    escalation: Sequence[str],
    allowed: Optional[Sequence[str]] = None,
) -> Optional[str]:
    exclude = [prover] if prover else []
    # Review selection does not open a proof escalation chain; the configured
    # high-tier ordering is only a deterministic fallback for reviewers.
    blocked = {engine for engine in used_reviewers if engine} | set(exclude)
    sequence = list(escalation) + list(load_routing_config()["high_tier_chain_engines"])
    for engine in _filter_allowed(sequence, allowed):
        if engine not in blocked:
            return engine
    return None


def _filter_allowed(
    engines: Sequence[str], allowed: Optional[Sequence[str]]
) -> List[str]:
    if allowed is None:
        return list(engines)
    allowed_set = set(allowed)
    return [engine for engine in engines if engine in allowed_set]
