#!/usr/bin/env python3
"""Fetch the pinned Liu-audit PDFs and extract searchable text."""
from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from pypdf import PdfReader

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
DEST = ROOT / "tmp" / "liu-audit"
USER_AGENT = "PureTateResearch/0.1 (literature corpus)"

SOURCES = [
    {
        "name": "liu-2509.02950v1",
        "url": "https://arxiv.org/pdf/2509.02950v1",
        "sha256": "ada191f5012a45d57640ef4333c6e64e218babdb22aee4579110e5d1f0c66d5a",
    },
    {
        "name": "canning-larson-2208.02357",
        "url": "https://arxiv.org/pdf/2208.02357v2",
        "sha256": None,
    },
    {
        "name": "clp-2307.08830",
        "url": "https://arxiv.org/pdf/2307.08830v3",
        "sha256": None,
    },
    {
        "name": "ionel-math9908060",
        "url": "https://arxiv.org/pdf/math/9908060v2",
        "sha256": None,
    },
]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url)
    request.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(request, timeout=120) as response:
        content = response.read()
    if not content.startswith(b"%PDF"):
        raise ValueError("%s did not return a PDF" % url)
    return content


def extract_text(pdf_path: Path, txt_path: Path) -> None:
    reader = PdfReader(str(pdf_path))
    pages = []
    for index, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").replace("\x00", "").strip()
        pages.append("===== PAGE %s =====\n%s" % (index, text))
    txt_path.write_text("\n\n".join(pages) + "\n", encoding="utf-8")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    report = []
    for item in SOURCES:
        pdf_path = DEST / (item["name"] + ".pdf")
        txt_path = DEST / (item["name"] + ".txt")
        if pdf_path.is_file():
            content = pdf_path.read_bytes()
        else:
            content = fetch(item["url"])
            pdf_path.write_bytes(content)
        digest = sha256_bytes(content)
        expected = item["sha256"]
        if expected and digest != expected:
            raise SystemExit(
                "hash mismatch for %s: got %s expected %s"
                % (item["name"], digest, expected)
            )
        extract_text(pdf_path, txt_path)
        report.append(
            {
                "name": item["name"],
                "bytes": len(content),
                "sha256": digest,
                "pdf": str(pdf_path.relative_to(ROOT)),
                "txt": str(txt_path.relative_to(ROOT)),
                "txt_bytes": txt_path.stat().st_size,
            }
        )
        print("%s  %s  %s bytes" % (item["name"], digest, len(content)))
    (DEST / "SOURCE-HASHES.json").write_text(
        __import__("json").dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
