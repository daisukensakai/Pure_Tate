import datetime
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import CheckResult, Source
from .store import (
    ROOT,
    DataError,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    load_json,
)


CORPUS = ROOT / "corpus"
MANIFEST = CORPUS / "manifest.json"
RAW = CORPUS / "raw"
TEXT = CORPUS / "text"
CHUNKS = CORPUS / "chunks"
USER_AGENT = "PureTateResearch/0.1 (literature corpus)"
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_manifest() -> Dict[str, Any]:
    if not MANIFEST.exists():
        return {"schema_version": 1, "artifacts": []}
    return load_json(MANIFEST)


def _save_artifact(record: Dict[str, Any]) -> None:
    manifest = load_manifest()
    artifacts = manifest.setdefault("artifacts", [])
    key = (record["source_id"], record["kind"])
    artifacts[:] = [
        item
        for item in artifacts
        if (item.get("source_id"), item.get("kind")) != key
    ]
    artifacts.append(record)
    artifacts.sort(key=lambda item: (item["source_id"], item["kind"]))
    atomic_write_json(MANIFEST, manifest)


def artifact_for(source_id: str, kind: str) -> Optional[Dict[str, Any]]:
    for item in load_manifest().get("artifacts", []):
        if item.get("source_id") == source_id and item.get("kind") == kind:
            return item
    return None


def arxiv_pdf_url(source: Source) -> str:
    if not source.arxiv_id:
        raise ValueError("%s has no arXiv id" % source.id)
    return "https://arxiv.org/pdf/%s%s" % (
        source.arxiv_id,
        source.arxiv_version,
    )


def fetch_source(source: Source, timeout: int = 60) -> Dict[str, Any]:
    url = arxiv_pdf_url(source)
    request = urllib.request.Request(url)
    request.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content = response.read()
    if not content.startswith(b"%PDF"):
        raise ValueError("%s did not return a PDF" % url)
    digest = sha256_bytes(content)
    path = RAW / ("%s-%s.pdf" % (source.id, digest[:16]))
    atomic_write_bytes(path, content)
    record = {
        "source_id": source.id,
        "kind": "pdf",
        "path": str(path.relative_to(ROOT)),
        "sha256": digest,
        "bytes": len(content),
        "source_url": url,
        "source_version": source.arxiv_version,
        "created_on": datetime.date.today().isoformat(),
    }
    _save_artifact(record)
    return record


def extract_source(source_id: str) -> Dict[str, Any]:
    pdf = artifact_for(source_id, "pdf")
    if not pdf:
        raise ValueError("%s has no fetched PDF artifact" % source_id)
    pdf_path = ROOT / pdf["path"]
    output_path = TEXT / ("%s.txt" % source_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    binary = shutil.which("pdftotext")
    if binary:
        process = subprocess.run(
            [binary, "-layout", str(pdf_path), str(output_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        if process.returncode != 0:
            raise RuntimeError("pdftotext failed: %s" % process.stderr.strip())
    else:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "PDF extraction requires pdftotext or the optional pypdf package"
            ) from exc
        reader = PdfReader(str(pdf_path))
        page_text = [(page.extract_text() or "").strip() for page in reader.pages]
        atomic_write_text(output_path, "\f".join(page_text))
    # pypdf (and some pdftotext builds) can embed NUL bytes that make
    # downstream readers treat the corpus as binary.
    content = output_path.read_bytes().replace(b"\x00", b"")
    output_path.write_bytes(content)
    digest = sha256_bytes(content)
    record = {
        "source_id": source_id,
        "kind": "text",
        "path": str(output_path.relative_to(ROOT)),
        "sha256": digest,
        "bytes": len(content),
        "derived_from_sha256": pdf["sha256"],
        "created_on": datetime.date.today().isoformat(),
    }
    _save_artifact(record)
    build_chunks(source_id)
    return record


def _page_chunks(text: str, max_chars: int = 5000) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for page_number, page in enumerate(text.split("\f"), 1):
        page = page.strip()
        if not page:
            continue
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", page) if item.strip()]
        buffer = ""
        ordinal = 0
        for paragraph in paragraphs:
            if buffer and len(buffer) + len(paragraph) + 2 > max_chars:
                chunks.append(
                    {"page": page_number, "ordinal": ordinal, "text": buffer}
                )
                ordinal += 1
                buffer = ""
            buffer = (buffer + "\n\n" + paragraph).strip()
        if buffer:
            chunks.append({"page": page_number, "ordinal": ordinal, "text": buffer})
    return chunks


def build_chunks(source_id: str, max_chars: int = 5000) -> Dict[str, Any]:
    text_artifact = artifact_for(source_id, "text")
    if not text_artifact:
        raise ValueError("%s has no text artifact" % source_id)
    text_path = ROOT / text_artifact["path"]
    chunks = _page_chunks(text_path.read_text(encoding="utf-8", errors="replace"), max_chars)
    output_path = CHUNKS / ("%s.jsonl" % source_id)
    payload = "".join(
        json.dumps(
            {
                "id": "%s-P%04d-C%02d"
                % (source_id, item["page"], item["ordinal"]),
                "source_id": source_id,
                **item,
            },
            sort_keys=True,
        )
        + "\n"
        for item in chunks
    )
    atomic_write_text(output_path, payload)
    digest = sha256_bytes(payload.encode("utf-8"))
    record = {
        "source_id": source_id,
        "kind": "chunks",
        "path": str(output_path.relative_to(ROOT)),
        "sha256": digest,
        "chunks": len(chunks),
        "derived_from_sha256": text_artifact["sha256"],
        "created_on": datetime.date.today().isoformat(),
    }
    _save_artifact(record)
    return record


def _tokens(value: str) -> set:
    return {match.group(0).lower() for match in TOKEN_RE.finditer(value)}


def search_corpus(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    query_tokens = _tokens(query)
    results = []
    for artifact in load_manifest().get("artifacts", []):
        if artifact.get("kind") != "chunks":
            continue
        path = ROOT / artifact["path"]
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            chunk = json.loads(line)
            chunk_tokens = _tokens(chunk["text"])
            score = len(query_tokens & chunk_tokens)
            if score:
                results.append((score, chunk["id"], chunk))
    results.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in results[:limit]]


def audit_corpus(sources: Dict[str, Source]) -> CheckResult:
    result = CheckResult()
    try:
        artifacts = load_manifest().get("artifacts", [])
    except DataError as exc:
        result.errors.append(str(exc))
        return result
    if not isinstance(artifacts, list):
        result.errors.append("corpus manifest artifacts must be a list")
        return result
    if not artifacts:
        result.warnings.append("corpus has no fetched source artifacts")
        return result

    seen = set()
    indexed = {}
    corpus_root = CORPUS.resolve()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            result.errors.append("corpus manifest contains a non-object artifact")
            continue
        source_id = artifact.get("source_id")
        kind = artifact.get("kind")
        key = (source_id, kind)
        if key in seen:
            result.errors.append("duplicate corpus artifact %r" % (key,))
        seen.add(key)
        indexed[key] = artifact
        if source_id not in sources:
            result.errors.append("corpus artifact cites unknown source %r" % source_id)
        if kind not in {"pdf", "text", "chunks"}:
            result.errors.append("%s has invalid artifact kind %r" % (source_id, kind))
        relative = artifact.get("path")
        if not isinstance(relative, str) or not relative:
            result.errors.append("%s/%s has no artifact path" % key)
            continue
        path = (ROOT / relative).resolve()
        try:
            path.relative_to(corpus_root)
        except ValueError:
            result.errors.append("%s/%s escapes the corpus directory" % key)
            continue
        if not path.is_file():
            result.errors.append("%s/%s artifact is missing: %s" % (*key, path))
            continue
        content = path.read_bytes()
        digest = sha256_bytes(content)
        if artifact.get("sha256") != digest:
            result.errors.append("%s/%s sha256 mismatch" % key)
        if kind in {"pdf", "text"} and artifact.get("bytes") != len(content):
            result.errors.append("%s/%s byte count mismatch" % key)
        if kind == "pdf":
            source = sources.get(source_id)
            if source and artifact.get("source_version") != source.arxiv_version:
                result.errors.append(
                    "%s PDF is not the catalogued arXiv version %s"
                    % (source_id, source.arxiv_version)
                )

    for (source_id, kind), artifact in indexed.items():
        parent_kind = {"text": "pdf", "chunks": "text"}.get(kind)
        if not parent_kind:
            continue
        parent = indexed.get((source_id, parent_kind))
        if parent is None:
            result.errors.append(
                "%s/%s lacks its %s provenance artifact"
                % (source_id, kind, parent_kind)
            )
        elif artifact.get("derived_from_sha256") != parent.get("sha256"):
            result.errors.append(
                "%s/%s provenance hash mismatch" % (source_id, kind)
            )
    return result
