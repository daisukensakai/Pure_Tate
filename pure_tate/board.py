import datetime
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from .artifacts import load_artifacts, load_migration
from .findings import findings_for_case
from .models import Claim, Source
from .store import ROOT, atomic_write_json, atomic_write_text, load_repository
from .targets import CONTEXT_REVISION
from .tasking import mathematics_tasks, review_tasks


CELL_STATUSES = {
    "untried",
    "stale_context",
    "awaiting_review",
    "reviewed_incomplete",
    "blocked_by_finding",
    "claimed_complete",
    "verified",
}


def _current_attempts() -> List[Dict[str, Any]]:
    return [
        item
        for item in load_artifacts("attempts")
        if "_error" not in item
        and item.get("context_revision") == CONTEXT_REVISION
    ]


def _current_reviews() -> List[Dict[str, Any]]:
    return [
        item
        for item in load_artifacts("reviews")
        if "_error" not in item
        and item.get("context_revision") == CONTEXT_REVISION
    ]


def _blocked_finding(task: Dict[str, Any]) -> Optional[str]:
    target = task["target"]
    for finding in findings_for_case(
        target["g"], target["n"], visible_only=True
    ):
        if (
            finding.get("kind") == "refutation"
            and task["approach_id"] in finding.get("impacts_approach_ids", [])
        ):
            return str(finding["id"])
    return None


def build_board(
    config: Optional[Dict[str, Any]] = None,
    claims: Optional[Dict[str, Claim]] = None,
    sources: Optional[Dict[str, Source]] = None,
) -> Dict[str, Any]:
    if config is None or claims is None or sources is None:
        config, _target, sources, claims, _edges = load_repository()
    tasks = mathematics_tasks(config, claims, sources)
    attempts = _current_attempts()
    reviews = _current_reviews()
    attempts_by_task: Dict[str, List[Dict[str, Any]]] = {}
    reviews_by_attempt: Dict[str, List[Dict[str, Any]]] = {}
    for attempt in attempts:
        attempts_by_task.setdefault(str(attempt.get("task_id")), []).append(attempt)
    for review in reviews:
        reviews_by_attempt.setdefault(str(review.get("attempt_id")), []).append(review)

    cells = []
    for task in tasks:
        matching = sorted(
            attempts_by_task.get(task["id"], []),
            key=lambda item: item.get("id", ""),
        )
        blocked = _blocked_finding(task)
        status = "blocked_by_finding" if blocked and not matching else "untried"
        current_attempt_id = None
        engines_tried = sorted(
            {
                str(attempt.get("engine"))
                for attempt in matching
                if isinstance(attempt.get("engine"), str) and attempt.get("engine")
            }
        )
        if matching:
            attempt = matching[-1]
            current_attempt_id = attempt.get("id")
            if (
                attempt.get("packet_sha256") != task.get("packet_sha256")
                or attempt.get("target") != task.get("target")
            ):
                status = "stale_context"
            else:
                attached = reviews_by_attempt.get(str(current_attempt_id), [])
                verdicts = [review.get("verdict") for review in attached]
                engines = {
                    review.get("reviewer_engine")
                    for review in attached
                    if review.get("verdict") == "confirmed"
                }
                if (
                    attempt.get("status") == "verified"
                    and verdicts.count("confirmed") >= 2
                    and len(engines) >= 2
                ):
                    status = "verified"
                elif any(
                    verdict in {"incomplete", "refuted"} for verdict in verdicts
                ):
                    status = "reviewed_incomplete"
                elif attempt.get("status") == "claimed_complete":
                    status = (
                        "claimed_complete"
                        if verdicts.count("confirmed") >= 2
                        and len(engines) >= 2
                        else "awaiting_review"
                    )
                elif not attached:
                    status = "awaiting_review"
                else:
                    # A proposed attempt is triaged after one independent pass.
                    # It cannot enter confirmation until it claims completeness.
                    status = "reviewed_incomplete"
        cells.append(
            {
                "task_id": task["id"],
                "case": {"g": task["target"]["g"], "n": task["target"]["n"]},
                "approach_id": task["approach_id"],
                "context_revision": task["context_revision"],
                "packet_id": task["packet_id"],
                "packet_sha256": task["packet_sha256"],
                "status": status,
                "attempt_id": current_attempt_id,
                "engines_tried": engines_tried,
                "blocking_finding_id": blocked,
            }
        )

    migration = load_migration()
    stale_attempts = [
        {
            "attempt_id": attempt_id,
            "task_id": record.get("task_id"),
            "status": record.get("assessment"),
            "reason": migration.get("reason"),
            "sha256": record.get("sha256"),
        }
        for attempt_id, record in sorted(migration.get("attempts", {}).items())
    ]
    counts = Counter(cell["status"] for cell in cells)
    portfolio = {
        "stale": len(stale_attempts) + counts["stale_context"],
        "active": sum(
            counts[item]
            for item in ("awaiting_review", "claimed_complete")
        ),
        "incomplete": counts["reviewed_incomplete"] + counts["blocked_by_finding"],
        "verified": counts["verified"],
        "untried": counts["untried"],
    }
    return {
        "schema_version": 2,
        "context_revision": CONTEXT_REVISION,
        "generated_on": datetime.date.today().isoformat(),
        "cell_count": len(cells),
        "cells": cells,
        "historical_stale_attempts": stale_attempts,
        "status_counts": dict(sorted(counts.items())),
        "portfolio": portfolio,
    }


def board_markdown(board: Dict[str, Any]) -> str:
    portfolio = board["portfolio"]
    lines = [
        "# Stage-2 attack board",
        "",
        "- Corrected current-revision cells: %d" % board["cell_count"],
        "- Historical stale attempts: %d"
        % len(board["historical_stale_attempts"]),
        "- Portfolio: stale %(stale)d; active %(active)d; incomplete "
        "%(incomplete)d; verified %(verified)d; untried %(untried)d."
        % portfolio,
        "",
        "| task | case | approach | status | attempt/finding | engines |",
        "|---|---|---|---|---|---|",
    ]
    for cell in board["cells"]:
        detail = cell["attempt_id"] or cell["blocking_finding_id"] or ""
        engines = ",".join(cell.get("engines_tried") or [])
        lines.append(
            "| %s | (%d,%d) | %s | %s | %s | %s |"
            % (
                cell["task_id"],
                cell["case"]["g"],
                cell["case"]["n"],
                cell["approach_id"],
                cell["status"],
                detail,
                engines,
            )
        )
    lines.extend(["", "## Historical stale attempts", ""])
    for item in board["historical_stale_attempts"]:
        lines.append(
            "- `%s` → `%s`: `stale_context` (`%s`)."
            % (item["attempt_id"], item["task_id"], item["reason"])
        )
    lines.append("")
    return "\n".join(lines)


def write_board(board: Dict[str, Any]) -> None:
    output = ROOT / "reports" / "generated"
    atomic_write_json(output / "BOARD.json", board)
    atomic_write_text(output / "BOARD.md", board_markdown(board))


def next_task(
    phase: str,
    config: Optional[Dict[str, Any]] = None,
    claims: Optional[Dict[str, Claim]] = None,
    sources: Optional[Dict[str, Source]] = None,
    retry: bool = False,
    exclude_task_ids: Optional[set] = None,
) -> Optional[Dict[str, Any]]:
    if config is None or claims is None or sources is None:
        config, _target, sources, claims, _edges = load_repository()
    if phase == "review":
        pending = review_tasks()
        return pending[0] if pending else None
    if phase != "mathematics":
        raise ValueError("phase must be mathematics or review")
    tasks = mathematics_tasks(config, claims, sources)
    task_by_id = {task["id"]: task for task in tasks}
    board = build_board(config, claims, sources)
    eligible_statuses = {"untried"}
    if retry:
        eligible_statuses.add("reviewed_incomplete")
        eligible_statuses.add("stale_context")
    excluded = exclude_task_ids or set()
    eligible = [
        cell
        for cell in board["cells"]
        if cell["status"] in eligible_statuses and cell["task_id"] not in excluded
    ]
    if not eligible:
        return None
    case_load = Counter(
        (cell["case"]["g"], cell["case"]["n"])
        for cell in board["cells"]
        if cell["status"] not in {"untried", "blocked_by_finding"}
    )
    approach_load = Counter(
        cell["approach_id"]
        for cell in board["cells"]
        if cell["status"] not in {"untried", "blocked_by_finding"}
    )
    for task_id in excluded:
        task = task_by_id.get(task_id)
        if task is not None:
            case_load[(task["target"]["g"], task["target"]["n"])] += 1
            approach_load[task["approach_id"]] += 1
    eligible.sort(
        key=lambda cell: (
            max(
                case_load[(cell["case"]["g"], cell["case"]["n"])],
                approach_load[cell["approach_id"]],
            ),
            case_load[(cell["case"]["g"], cell["case"]["n"])]
            + approach_load[cell["approach_id"]],
            cell["task_id"],
        )
    )
    return task_by_id[eligible[0]["task_id"]]
