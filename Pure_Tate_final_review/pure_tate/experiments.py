import datetime
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from .campaigns import EXPERIMENT_RESULT_DIR, load_campaign
from .store import ROOT, atomic_write_json


OCI_DIGEST_RE = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")


def container_runtime() -> str:
    for binary in ("docker", "podman"):
        if shutil.which(binary):
            return binary
    return ""


def experiment_tasks(campaign_id: str) -> List[Dict[str, Any]]:
    campaign = load_campaign(campaign_id)
    results: Dict[str, List[Dict[str, Any]]] = {}
    for path in EXPERIMENT_RESULT_DIR.glob("EXP-*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("campaign_id") == campaign_id:
            value["_path"] = str(path)
            results.setdefault(str(value.get("experiment_id")), []).append(value)
    tasks = []
    for experiment in campaign["experiments"]:
        prior = sorted(
            results.get(experiment["id"], []), key=lambda item: item.get("id", "")
        )
        if any(item.get("reproduced") is True for item in prior):
            continue
        if not OCI_DIGEST_RE.fullmatch(experiment["image"]):
            raise ValueError("experiment image is not pinned by OCI digest")
        if experiment.get("platform") != "linux/amd64":
            raise ValueError("experiment platform must be pinned to linux/amd64")
        script = ROOT / experiment["script"]
        tasks.append(
            {
                "id": "TASK-E-%s" % experiment["id"],
                "phase": "experiment",
                "role": "deterministic-computational-experiment",
                "campaign_id": campaign_id,
                "campaign_revision": campaign["campaign_revision"],
                "context_revision": campaign["context_revision"],
                "experiment_id": experiment["id"],
                "subproblem_id": experiment["subproblem_id"],
                "image": experiment["image"],
                "software_version": experiment["software_version"],
                "platform": experiment["platform"],
                "script": experiment["script"],
                "script_sha256": (
                    hashlib.sha256(script.read_bytes()).hexdigest()
                    if script.is_file()
                    else None
                ),
                "reproduction_of": (
                    str(Path(prior[-1]["_path"]).relative_to(ROOT))
                    if prior
                    else None
                ),
                "expected_stdout_sha256": (
                    prior[-1].get("stdout_sha256") if prior else None
                ),
                "output": "experiments/results/%s-run-%04d.json"
                % (experiment["id"], len(prior) + 1),
                "status": "ready",
            }
        )
    return tasks


def run_experiment(
    task: Dict[str, Any],
    output: Path,
    timeout: int = 3600,
    reproduce_of: str = "",
) -> Dict[str, Any]:
    if output.exists():
        raise ValueError("refusing to overwrite an existing experiment artifact")
    runtime = container_runtime()
    if not runtime:
        raise RuntimeError(
            "Docker/Podman unavailable; Macaulay2 integration test skipped explicitly"
        )
    image = str(task.get("image", ""))
    if not OCI_DIGEST_RE.fullmatch(image):
        raise ValueError("experiment image must be pinned by digest")
    script = ROOT / str(task.get("script", ""))
    if not script.is_file():
        raise ValueError("experiment script is missing")
    actual_script_hash = hashlib.sha256(script.read_bytes()).hexdigest()
    if actual_script_hash != task.get("script_sha256"):
        raise ValueError("experiment script hash mismatch")
    command = [
        runtime,
        "run",
        "--rm",
        "--platform",
        task["platform"],
        "--network",
        "none",
        "-v",
        "%s:/work:ro" % script.parent.resolve(),
        image,
        "M2",
        "--script",
        "/work/" + script.name,
    ]
    version_command = [
        runtime,
        "run",
        "--rm",
        "--platform",
        task["platform"],
        "--network",
        "none",
        image,
        "M2",
        "--version",
    ]
    version_process = subprocess.run(
        version_command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    version_output = (version_process.stdout or version_process.stderr).strip()
    if version_process.returncode or task["software_version"] not in version_output:
        raise RuntimeError(
            "Macaulay2 image version mismatch: %s" % version_output[:1000]
        )
    process = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if process.returncode:
        raise RuntimeError(
            "Macaulay2 experiment failed: %s"
            % (process.stderr or process.stdout).strip()[:1000]
        )
    stdout = process.stdout
    reproduction_reference = reproduce_of or str(
        task.get("reproduction_of") or ""
    )
    stdout_sha256 = hashlib.sha256(stdout.encode("utf-8")).hexdigest()
    if reproduction_reference and stdout_sha256 != task.get(
        "expected_stdout_sha256"
    ):
        raise ValueError(
            "independent experiment reproduction produced a different stdout hash"
        )
    record = {
        "schema_version": 1,
        "id": output.stem,
        "campaign_id": task["campaign_id"],
        "campaign_revision": task["campaign_revision"],
        "experiment_id": task["experiment_id"],
        "subproblem_id": task["subproblem_id"],
        "image": image,
        "software_version": task["software_version"],
        "software_version_output": version_output,
        "software_version_output_sha256": hashlib.sha256(
            version_output.encode("utf-8")
        ).hexdigest(),
        "platform": task["platform"],
        "script": task["script"],
        "script_sha256": actual_script_hash,
        "stdout": stdout,
        "stdout_sha256": stdout_sha256,
        "stderr": process.stderr,
        "command": command,
        "version_command": version_command,
        "runtime": runtime,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "reproduction_of": reproduction_reference or None,
        "reproduced": bool(reproduction_reference),
        "proof_use": "hypothesis_only",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output, record)
    return record
