import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agents import engine_inventory, run_task
from .capabilities import audit_capabilities
from .board import build_board, next_task, write_board
from .cases import compact_pairs, enumerate_reduction_cases, unresolved_cases
from .citation import audit_citations
from .corpus import audit_corpus, extract_source, fetch_source, search_corpus
from .graph import ClaimGraph
from .online import online_source_audit
from .driver import drive
from .campaign_driver import drive_campaign, next_campaign_task
from .campaigns import (
    DEFAULT_CAMPAIGN,
    campaign_status,
    write_campaign_packet,
    write_campaign_status,
)
from .findings import adjudicate_finding
from .health import audit_engine_health
from .paired import recover_attempt_from_trace
from .packets import write_case_packets
from .proofs import audit_proofs, proof_status_report
from .research import audit_research_gate, stage_two_ready
from .reports import (
    case_report,
    corpus_report,
    findings_report,
    format_check_report,
    obstruction_report,
)
from .retrieval import compile_packet, search_claims
from .store import (
    DATA,
    PACKETS_GENERATED,
    REPORTS_GENERATED,
    ROOT,
    DataError,
    atomic_write_json,
    atomic_write_text,
    load_json,
    load_repository,
)
from .tasking import (
    mathematics_tasks,
    micro_research_tasks,
    research_tasks,
    review_tasks,
)
from .validate import validate_repository


def _print_check(result: Any) -> None:
    for error in result.errors:
        print("ERROR:", error)
    for warning in result.warnings:
        print("WARN:", warning)
    print(
        "%s — %d error(s), %d warning(s)"
        % ("PASS" if result.ok else "FAIL", len(result.errors), len(result.warnings))
    )


def _load():
    try:
        return load_repository()
    except (DataError, TypeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)


def command_validate(args: argparse.Namespace) -> int:
    config, target, sources, claims, edges = _load()
    result = validate_repository(config, target, sources, claims, edges)
    _print_check(result)
    if args.write:
        atomic_write_text(
            REPORTS_GENERATED / "VALIDATION.md",
            format_check_report("Repository validation", result),
        )
    return 0 if result.ok else 1


def command_audit(args: argparse.Namespace) -> int:
    config, _target, sources, claims, _edges = _load()
    result = audit_citations(
        sources,
        claims,
        int(config["citation_freshness_days"]),
        datetime.date.today(),
    )
    if args.online:
        result.extend(online_source_audit(sources, timeout=args.timeout))
    _print_check(result)
    if args.write:
        atomic_write_text(
            REPORTS_GENERATED / "CITATION_AUDIT.md",
            format_check_report("Citation audit", result),
        )
    return 0 if result.ok else 1


def _write_case_artifacts(degree: int, config: Dict[str, Any]) -> None:
    cases = enumerate_reduction_cases(degree, config)
    atomic_write_json(
        REPORTS_GENERATED / ("cases-%d.json" % degree),
        [case.as_dict() for case in cases],
    )
    atomic_write_text(
        REPORTS_GENERATED / ("CASES-%d.md" % degree),
        case_report(degree, config),
    )


def command_cases(args: argparse.Namespace) -> int:
    config, _target, _sources, _claims, _edges = _load()
    unresolved = unresolved_cases(args.degree, config)
    for case in unresolved:
        print("%d,%d\t%s" % (case.genus, case.markings, case.coverage_reason))
    print(
        "%d unresolved of %d required base pairs"
        % (
            len(unresolved),
            len(enumerate_reduction_cases(args.degree, config)),
        )
    )
    if args.write:
        _write_case_artifacts(args.degree, config)
    return 0


def command_replay(args: argparse.Namespace) -> int:
    config, _target, _sources, _claims, _edges = _load()
    expected_all = load_json(DATA / "expected_reductions.json")
    expected = [tuple(item) for item in expected_all.get(str(args.degree), [])]
    actual = compact_pairs(unresolved_cases(args.degree, config))
    if actual != expected:
        print("FAIL: degree-%d reduction replay mismatch" % args.degree)
        print(" expected:", expected)
        print(" actual:  ", actual)
        return 1
    print("PASS: degree-%d reduction replay -> %s" % (args.degree, actual))
    return 0


def command_obstruction(args: argparse.Namespace) -> int:
    config, _target, _sources, claims, _edges = _load()
    report = obstruction_report(config, claims, degree=16)
    output = Path(args.output) if args.output else REPORTS_GENERATED / "OBSTRUCTION.md"
    atomic_write_text(output, report)
    print(output)
    return 0


def command_packet(args: argparse.Namespace) -> int:
    config, _target, sources, claims, edges = _load()
    graph = ClaimGraph(claims, edges)
    try:
        packet = compile_packet(
            args.claim,
            claims,
            sources,
            graph,
            int(config["proof_packet_claim_limit"]),
            int(config["proof_packet_source_limit"]),
        )
    except ValueError as exc:
        print("ERROR:", exc)
        return 1
    output = (
        Path(args.output)
        if args.output
        else PACKETS_GENERATED / ("%s.md" % args.claim)
    )
    atomic_write_text(output, packet)
    print(output)
    return 0


def command_search(args: argparse.Namespace) -> int:
    _config, _target, _sources, claims, _edges = _load()
    for claim in search_claims(args.query, claims, args.limit):
        print("%s\t%s\t%s" % (claim.id, claim.verification_status, claim.title))
    return 0


def command_proof_audit(args: argparse.Namespace) -> int:
    config, _target, sources, claims, _edges = _load()
    result = audit_proofs(claims)
    _print_check(result)
    if args.write:
        board = build_board(config, claims, sources)
        atomic_write_text(
            REPORTS_GENERATED / "PROOF_AUDIT.md",
            proof_status_report(claims, board),
        )
    return 0 if result.ok else 1


def command_recover_trace(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else None
    try:
        receipt = recover_attempt_from_trace(args.trace, output)
    except (OSError, RuntimeError, ValueError) as exc:
        print("ERROR:", exc)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def command_fetch_source(args: argparse.Namespace) -> int:
    _config, _target, sources, _claims, _edges = _load()
    source = sources.get(args.source_id)
    if source is None:
        print("ERROR: unknown source %s" % args.source_id)
        return 1
    try:
        artifact = fetch_source(source, timeout=args.timeout)
    except (OSError, RuntimeError, ValueError) as exc:
        print("ERROR:", exc)
        return 1
    print("%s\t%s" % (artifact["sha256"], artifact["path"]))
    return 0


def command_extract_source(args: argparse.Namespace) -> int:
    _config, _target, sources, _claims, _edges = _load()
    if args.source_id not in sources:
        print("ERROR: unknown source %s" % args.source_id)
        return 1
    try:
        artifact = extract_source(args.source_id)
    except (OSError, RuntimeError, ValueError) as exc:
        print("ERROR:", exc)
        return 1
    print("%s\t%s" % (artifact["sha256"], artifact["path"]))
    return 0


def command_corpus_search(args: argparse.Namespace) -> int:
    try:
        matches = search_corpus(args.query, args.limit)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("ERROR:", exc)
        return 1
    for chunk in matches:
        snippet = " ".join(chunk["text"].split())[:240]
        print("%s\t%s" % (chunk["id"], snippet))
    print("%d chunk(s)" % len(matches))
    return 0


def command_corpus_audit(args: argparse.Namespace) -> int:
    _config, _target, sources, _claims, _edges = _load()
    result = audit_corpus(sources)
    _print_check(result)
    if args.write:
        atomic_write_text(
            REPORTS_GENERATED / "CORPUS_AUDIT.md",
            format_check_report("Corpus integrity audit", result),
        )
    return 0 if result.ok else 1


def command_research_audit(args: argparse.Namespace) -> int:
    config, _target, sources, claims, _edges = _load()
    result = audit_research_gate(config, claims, sources)
    _print_check(result)
    if args.write:
        atomic_write_text(
            REPORTS_GENERATED / "RESEARCH_GATE.md",
            format_check_report("Independent research gate", result),
        )
    return 0 if result.ok else 1


def command_tasks(args: argparse.Namespace) -> int:
    config, _target, sources, claims, _edges = _load()
    if args.phase == "research":
        tasks = research_tasks()
    elif args.phase == "micro-research":
        tasks = micro_research_tasks(claims)
    elif args.phase == "mathematics":
        try:
            if args.write:
                write_case_packets(
                    compact_pairs(unresolved_cases(16, config)), claims
                )
            tasks = mathematics_tasks(config, claims, sources)
        except RuntimeError as exc:
            print("ERROR:", exc)
            return 2
    else:
        tasks = review_tasks()
    if args.write:
        output = (
            Path(args.output)
            if args.output
            else ROOT / "tasks" / "generated" / ("%s.json" % args.phase)
        )
        atomic_write_json(output, tasks)
        print(output)
    else:
        print(json.dumps(tasks, indent=2, sort_keys=True))
    return 0


def command_engines(args: argparse.Namespace) -> int:
    try:
        inventory = engine_inventory()
    except (ValueError, DataError) as exc:
        print("ERROR:", exc)
        return 1
    for item in inventory:
        declared = item.get("declared_capabilities", {})
        print(
            "%s\t%s\tresearch=%s\tmathematics=%s\treview=%s\t%s"
            % (
                item["id"],
                "available" if item["available"] else "missing",
                ",".join(declared.get("research", [])) or "none",
                ",".join(declared.get("mathematics", [])) or "none",
                ",".join(declared.get("review", [])) or "none",
                item["model"],
            )
        )
    return 0


def command_capability_audit(args: argparse.Namespace) -> int:
    try:
        records = audit_capabilities(
            args.engines,
            phases=("research", "finding-audit", "novelty"),
            live=args.live,
            timeout=args.timeout,
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print("ERROR:", exc)
        return 1
    print(json.dumps(records, indent=2, sort_keys=True))
    return 0 if all(item["status"] == "pass" for item in records) else 1


def command_engine_health(args: argparse.Namespace) -> int:
    try:
        record = audit_engine_health(
            args.engine,
            live=args.live,
            level=args.level,
            timeout=args.timeout,
            inactivity_timeout=args.inactivity_timeout,
            model_override=args.model,
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print("ERROR:", exc)
        return 1
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record.get("status") == "pass" else 1


def command_agent_run(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("ERROR:", exc)
        return 1
    tasks = manifest if isinstance(manifest, list) else [manifest]
    matches = [
        task
        for task in tasks
        if isinstance(task, dict) and task.get("id") == args.task_id
    ]
    if len(matches) != 1:
        print("ERROR: expected exactly one task named %s" % args.task_id)
        return 1
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    try:
        artifact = run_task(
            matches[0], args.engine, output, timeout=args.timeout
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print("ERROR:", exc)
        return 1
    print("%s\t%s" % (artifact["id"], output))
    return 0


def command_stage(args: argparse.Namespace) -> int:
    config, _target, sources, claims, _edges = _load()
    reduction = claims["RED-0001"]
    result = audit_research_gate(config, claims, sources)
    research_ready = stage_two_ready(config, claims, sources)
    mathematics_ready = False
    packet_errors = []
    if research_ready:
        for task in mathematics_tasks(config, claims, sources):
            path = ROOT / task["input_packet"]
            if not path.is_file():
                packet_errors.append("missing " + task["input_packet"])
                continue
            import hashlib

            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != task["packet_sha256"]:
                packet_errors.append("stale " + task["input_packet"])
        mathematics_ready = not packet_errors
    print(
        "Research gate %s: RED-0001 is %s; required %s"
        % (
            "READY" if research_ready else "BLOCKED",
            reduction.verification_status,
            config["research_completion_status"],
        )
    )
    print(
        "Mathematics context %s: revision-2 case packets %s"
        % (
            "READY" if mathematics_ready else "BLOCKED",
            "match their manifests" if mathematics_ready else "need regeneration",
        )
    )
    for error in result.errors:
        print("ERROR:", error)
    for warning in result.warnings:
        print("WARN:", warning)
    for error in sorted(set(packet_errors)):
        print("ERROR:", error)
    try:
        campaign_packet = write_campaign_packet(DEFAULT_CAMPAIGN)
        campaign_path = ROOT / campaign_packet["packet_path"]
        import hashlib

        campaign_ready = (
            campaign_path.is_file()
            and hashlib.sha256(campaign_path.read_bytes()).hexdigest()
            == campaign_packet["packet_sha256"]
        )
    except (OSError, ValueError, DataError) as exc:
        campaign_ready = False
        print("ERROR: focused campaign context:", exc)
    print(
        "Focused campaign context %s: C66-001 revision-2 packet %s"
        % (
            "READY" if campaign_ready else "BLOCKED",
            "is hash-matched" if campaign_ready else "needs regeneration",
        )
    )
    return 0 if research_ready and mathematics_ready and campaign_ready else 2


def command_board(args: argparse.Namespace) -> int:
    config, _target, sources, claims, _edges = _load()
    board = build_board(config, claims, sources)
    if args.write:
        write_board(board)
        print(REPORTS_GENERATED / "BOARD.json")
        print(REPORTS_GENERATED / "BOARD.md")
    else:
        print(json.dumps(board, indent=2, sort_keys=True))
    return 0


def command_next(args: argparse.Namespace) -> int:
    config, _target, sources, claims, _edges = _load()
    if args.campaign:
        task = next_campaign_task(
            args.campaign, args.phase, retry=args.retry
        )
    elif args.phase == "micro-research":
        tasks = micro_research_tasks(claims)
        task = tasks[0] if tasks else None
    else:
        task = next_task(
            args.phase, config, claims, sources, retry=args.retry
        )
    if task is None:
        print("No eligible %s task." % args.phase)
        return 2
    print(json.dumps(task, indent=2, sort_keys=True))
    return 0


def command_finding_adjudicate(args: argparse.Namespace) -> int:
    try:
        record = adjudicate_finding(
            args.finding,
            args.action,
            args.reason,
            target_id=args.target,
            adjudicator=args.adjudicator,
        )
    except (OSError, ValueError) as exc:
        print("ERROR:", exc)
        return 1
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def command_drive(args: argparse.Namespace) -> int:
    try:
        if args.campaign:
            result = drive_campaign(
                args.campaign,
                args.steps,
                research_engines=args.research_engines or [],
                prover_engines=args.prover_engines,
                review_engines=args.review_engines,
                timeout=args.timeout,
                dry_run=args.dry_run,
                retry=args.retry,
            )
        else:
            result = drive(
                args.steps,
                prover_engines=args.prover_engines,
                review_engines=args.review_engines,
                timeout=args.timeout,
                dry_run=args.dry_run,
                retry=args.retry,
            )
    except (OSError, RuntimeError, ValueError) as exc:
        print("ERROR:", exc)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["stop_reason"] not in {
        "artifact_validation_failure",
        "audit_failure",
        "engine_failure",
        "capability_failure",
        "validation_failure",
        "contradictory_novelty_audits",
        "interrupted",
        "health_failure",
    } else 1


def command_campaign_status(args: argparse.Namespace) -> int:
    try:
        status = (
            write_campaign_status(args.campaign)
            if args.write
            else campaign_status(args.campaign)
        )
    except (OSError, ValueError, DataError) as exc:
        print("ERROR:", exc)
        return 1
    print(json.dumps(status, indent=2, sort_keys=True))
    if args.write:
        print(REPORTS_GENERATED / ("%s-STATUS.json" % args.campaign))
        print(REPORTS_GENERATED / ("%s-STATUS.md" % args.campaign))
    return 0


def command_all(args: argparse.Namespace) -> int:
    config, target, sources, claims, edges = _load()
    validation = validate_repository(config, target, sources, claims, edges)
    citations = audit_citations(
        sources,
        claims,
        int(config["citation_freshness_days"]),
        datetime.date.today(),
    )
    corpus_integrity = audit_corpus(sources)
    research_gate = audit_research_gate(config, claims, sources)
    if validation.ok and citations.ok and corpus_integrity.ok and research_gate.ok:
        write_case_packets(
            compact_pairs(unresolved_cases(16, config)), claims
        )
    proofs = audit_proofs(claims)
    combined_ok = (
        validation.ok
        and citations.ok
        and proofs.ok
        and corpus_integrity.ok
        and research_gate.ok
    )
    _print_check(validation)
    _print_check(citations)
    _print_check(proofs)
    _print_check(corpus_integrity)
    _print_check(research_gate)
    if not combined_ok:
        return 1

    for degree in (14, 16):
        _write_case_artifacts(degree, config)
    atomic_write_text(
        REPORTS_GENERATED / "VALIDATION.md",
        format_check_report("Repository validation", validation),
    )
    atomic_write_text(
        REPORTS_GENERATED / "CITATION_AUDIT.md",
        format_check_report("Citation audit", citations),
    )
    atomic_write_text(
        REPORTS_GENERATED / "CORPUS_AUDIT.md",
        format_check_report("Corpus integrity audit", corpus_integrity),
    )
    atomic_write_text(
        REPORTS_GENERATED / "RESEARCH_GATE.md",
        format_check_report("Independent research gate", research_gate),
    )
    atomic_write_text(
        REPORTS_GENERATED / "CORPUS.md", corpus_report(sources, claims)
    )
    atomic_write_text(
        REPORTS_GENERATED / "OBSTRUCTION.md",
        obstruction_report(config, claims, degree=16),
    )
    atomic_write_text(
        REPORTS_GENERATED / "FINDINGS.md",
        findings_report(),
    )
    graph = ClaimGraph(claims, edges)
    packet = compile_packet(
        "RED-0001",
        claims,
        sources,
        graph,
        int(config["proof_packet_claim_limit"]),
        int(config["proof_packet_source_limit"]),
    )
    atomic_write_text(PACKETS_GENERATED / "RED-0001.md", packet)
    pairs = compact_pairs(unresolved_cases(16, config))
    write_case_packets(pairs, claims)
    math_tasks = mathematics_tasks(config, claims, sources)
    atomic_write_json(
        ROOT / "tasks" / "generated" / "research.json", research_tasks()
    )
    atomic_write_json(
        ROOT / "tasks" / "generated" / "micro-research.json",
        micro_research_tasks(claims),
    )
    atomic_write_json(
        ROOT / "tasks" / "generated" / "mathematics.json", math_tasks
    )
    atomic_write_json(
        ROOT / "tasks" / "generated" / "review.json", review_tasks()
    )
    board = build_board(config, claims, sources)
    write_board(board)
    atomic_write_text(
        REPORTS_GENERATED / "PROOF_AUDIT.md",
        proof_status_report(claims, board),
    )
    atomic_write_text(
        REPORTS_GENERATED / "PORTFOLIO.md",
        proof_status_report(claims, board),
    )
    write_campaign_packet(DEFAULT_CAMPAIGN)
    write_campaign_status(DEFAULT_CAMPAIGN)
    from .experiments import experiment_tasks
    from .novelty import novelty_tasks
    from .tasking import campaign_mathematics_tasks, finding_audit_tasks

    atomic_write_json(
        ROOT / "tasks" / "generated" / "campaign-C66-001-mathematics.json",
        campaign_mathematics_tasks(DEFAULT_CAMPAIGN),
    )
    atomic_write_json(
        ROOT / "tasks" / "generated" / "campaign-C66-001-finding-audit.json",
        finding_audit_tasks(DEFAULT_CAMPAIGN),
    )
    atomic_write_json(
        ROOT / "tasks" / "generated" / "campaign-C66-001-experiment.json",
        experiment_tasks(DEFAULT_CAMPAIGN),
    )
    atomic_write_json(
        ROOT / "tasks" / "generated" / "campaign-C66-001-novelty.json",
        novelty_tasks(DEFAULT_CAMPAIGN),
    )
    atomic_write_json(
        ROOT / "tasks" / "generated" / "campaign-C66-001-review.json",
        [
            task
            for task in review_tasks()
            if task.get("campaign_id") == DEFAULT_CAMPAIGN
        ],
    )
    from .paired import dry_run_preview
    from .campaigns import campaign_packet_record, load_campaign

    paired_campaign = load_campaign(DEFAULT_CAMPAIGN)
    paired_packet = campaign_packet_record(DEFAULT_CAMPAIGN)
    atomic_write_json(
        ROOT / "tasks" / "generated" / "campaign-C66-001-paired-preview.json",
        dry_run_preview(
            paired_campaign,
            paired_packet,
            paired_campaign["paired_attempt_policy"]["engine_order"],
            paired_campaign["batch_step_limit"],
        ),
    )

    replay_namespace = argparse.Namespace(degree=14)
    if command_replay(replay_namespace) != 0:
        return 1
    replay_namespace = argparse.Namespace(degree=16)
    if command_replay(replay_namespace) != 0:
        return 1
    print(
        "Generated revision-2 case packets, revision-3 C66 campaign packet/status, manifests, "
        "board, findings, and reports."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pure-tate",
        description="Source-audited research and proof harness.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--write", action="store_true")
    validate_parser.set_defaults(func=command_validate)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--online", action="store_true")
    audit_parser.add_argument("--timeout", type=int, default=15)
    audit_parser.add_argument("--write", action="store_true")
    audit_parser.set_defaults(func=command_audit)

    cases_parser = subparsers.add_parser("cases")
    cases_parser.add_argument("--degree", type=int, required=True)
    cases_parser.add_argument("--write", action="store_true")
    cases_parser.set_defaults(func=command_cases)

    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--degree", type=int, required=True)
    replay_parser.set_defaults(func=command_replay)

    obstruction_parser = subparsers.add_parser("obstruction")
    obstruction_parser.add_argument("--output")
    obstruction_parser.set_defaults(func=command_obstruction)

    packet_parser = subparsers.add_parser("packet")
    packet_parser.add_argument("--claim", required=True)
    packet_parser.add_argument("--output")
    packet_parser.set_defaults(func=command_packet)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.set_defaults(func=command_search)

    proof_parser = subparsers.add_parser("proof-audit")
    proof_parser.add_argument("--write", action="store_true")
    proof_parser.set_defaults(func=command_proof_audit)

    fetch_parser = subparsers.add_parser("fetch-source")
    fetch_parser.add_argument("source_id")
    fetch_parser.add_argument("--timeout", type=int, default=60)
    fetch_parser.set_defaults(func=command_fetch_source)

    extract_parser = subparsers.add_parser("extract-source")
    extract_parser.add_argument("source_id")
    extract_parser.set_defaults(func=command_extract_source)

    corpus_search_parser = subparsers.add_parser("corpus-search")
    corpus_search_parser.add_argument("query")
    corpus_search_parser.add_argument("--limit", type=int, default=10)
    corpus_search_parser.set_defaults(func=command_corpus_search)

    corpus_audit_parser = subparsers.add_parser("corpus-audit")
    corpus_audit_parser.add_argument("--write", action="store_true")
    corpus_audit_parser.set_defaults(func=command_corpus_audit)

    research_parser = subparsers.add_parser("research-audit")
    research_parser.add_argument("--write", action="store_true")
    research_parser.set_defaults(func=command_research_audit)

    tasks_parser = subparsers.add_parser("tasks")
    tasks_parser.add_argument(
        "--phase",
        choices=("research", "micro-research", "mathematics", "review"),
        required=True,
    )
    tasks_parser.add_argument("--write", action="store_true")
    tasks_parser.add_argument("--output")
    tasks_parser.set_defaults(func=command_tasks)

    engines_parser = subparsers.add_parser("engines")
    engines_parser.set_defaults(func=command_engines)

    capability_parser = subparsers.add_parser("capability-audit")
    capability_parser.add_argument("--engines", nargs="+", required=True)
    capability_parser.add_argument("--live", action="store_true")
    capability_parser.add_argument("--timeout", type=int, default=60)
    capability_parser.set_defaults(func=command_capability_audit)

    health_parser = subparsers.add_parser("engine-health")
    health_parser.add_argument("--engine", required=True)
    health_parser.add_argument("--live", action="store_true")
    health_parser.add_argument(
        "--level", choices=("basic", "tools", "artifact"), default="artifact"
    )
    health_parser.add_argument("--timeout", type=int, default=180)
    health_parser.add_argument("--inactivity-timeout", type=int, default=60)
    health_parser.add_argument("--model")
    health_parser.set_defaults(func=command_engine_health)

    agent_parser = subparsers.add_parser("agent-run")
    agent_parser.add_argument("--manifest", required=True)
    agent_parser.add_argument("--task-id", required=True)
    agent_parser.add_argument("--engine", required=True)
    agent_parser.add_argument("--output", required=True)
    agent_parser.add_argument("--timeout", type=int, default=3600)
    agent_parser.set_defaults(func=command_agent_run)

    stage_parser = subparsers.add_parser("stage")
    stage_parser.set_defaults(func=command_stage)

    board_parser = subparsers.add_parser("board")
    board_parser.add_argument("--write", action="store_true")
    board_parser.set_defaults(func=command_board)

    next_parser = subparsers.add_parser("next")
    next_parser.add_argument(
        "--phase",
        choices=(
            "micro-research",
            "finding-audit",
            "novelty",
            "experiment",
            "mathematics",
            "review",
            "forced-proof",
            "trace-mining",
            "standard-fallback",
        ),
        required=True,
    )
    next_parser.add_argument("--campaign")
    next_parser.add_argument("--retry", action="store_true")
    next_parser.set_defaults(func=command_next)

    drive_parser = subparsers.add_parser("drive")
    drive_parser.add_argument("--steps", type=int, required=True)
    drive_parser.add_argument("--campaign")
    drive_parser.add_argument("--research-engines", nargs="+")
    drive_parser.add_argument("--prover-engines", nargs="+", required=True)
    drive_parser.add_argument("--review-engines", nargs="+", required=True)
    drive_parser.add_argument("--timeout", type=int, default=3600)
    drive_parser.add_argument("--dry-run", action="store_true")
    drive_parser.add_argument("--retry", action="store_true")
    drive_parser.set_defaults(func=command_drive)

    campaign_status_parser = subparsers.add_parser("campaign-status")
    campaign_status_parser.add_argument(
        "--campaign", default=DEFAULT_CAMPAIGN
    )
    campaign_status_parser.add_argument("--write", action="store_true")
    campaign_status_parser.set_defaults(func=command_campaign_status)

    recover_trace_parser = subparsers.add_parser("recover-trace")
    recover_trace_parser.add_argument("--trace", required=True)
    recover_trace_parser.add_argument("--output")
    recover_trace_parser.set_defaults(func=command_recover_trace)

    adjudicate_parser = subparsers.add_parser("finding-adjudicate")
    adjudicate_parser.add_argument("--finding", required=True)
    adjudicate_parser.add_argument(
        "--action", choices=("corroborate", "retire", "merge"), required=True
    )
    adjudicate_parser.add_argument("--target")
    adjudicate_parser.add_argument("--reason", required=True)
    adjudicate_parser.add_argument("--adjudicator", default="human")
    adjudicate_parser.set_defaults(func=command_finding_adjudicate)

    all_parser = subparsers.add_parser("all")
    all_parser.set_defaults(func=command_all)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
