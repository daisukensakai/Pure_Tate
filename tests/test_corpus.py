import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.corpus import _page_chunks, audit_corpus, sha256_bytes
from pure_tate.store import load_repository


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _config, _target, cls.sources, _claims, _edges = load_repository()

    def test_sha256_is_content_address(self):
        content = b"pinned source bytes"
        self.assertEqual(
            sha256_bytes(content), hashlib.sha256(content).hexdigest()
        )

    def test_chunks_preserve_pdf_page_numbers(self):
        text = "First paragraph.\n\nSecond paragraph.\fThird page."
        chunks = _page_chunks(text, max_chars=20)
        self.assertEqual([item["page"] for item in chunks], [1, 1, 2])
        self.assertEqual([item["ordinal"] for item in chunks], [0, 1, 0])

    def test_oversized_paragraph_remains_a_single_locatable_chunk(self):
        text = "x" * 100
        chunks = _page_chunks(text, max_chars=20)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["page"], 1)
        self.assertEqual(chunks[0]["text"], text)

    def test_integrity_audit_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus"
            raw = corpus / "raw"
            raw.mkdir(parents=True)
            artifact = raw / "source.pdf"
            artifact.write_bytes(b"%PDF-original")
            manifest = corpus / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "source_id": "SRC-0001",
                                "kind": "pdf",
                                "path": "corpus/raw/source.pdf",
                                "sha256": sha256_bytes(b"%PDF-original"),
                                "bytes": len(b"%PDF-original"),
                                "source_version": self.sources[
                                    "SRC-0001"
                                ].arxiv_version,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            patches = (
                mock.patch("pure_tate.corpus.ROOT", root),
                mock.patch("pure_tate.corpus.CORPUS", corpus),
                mock.patch("pure_tate.corpus.MANIFEST", manifest),
            )
            with patches[0], patches[1], patches[2]:
                clean = audit_corpus(self.sources)
                artifact.write_bytes(b"%PDF-tampered")
                tampered = audit_corpus(self.sources)
        self.assertTrue(clean.ok)
        self.assertTrue(any("sha256 mismatch" in item for item in tampered.errors))


if __name__ == "__main__":
    unittest.main()
