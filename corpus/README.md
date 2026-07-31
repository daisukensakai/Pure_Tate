# Corpus artifacts

The local `manifest.json` records content-addressed source artifacts. It starts from
`manifest.example.json`; the manifest, downloaded PDFs, extracted text, and chunks are
rebuildable and ignored by Git.

Extraction uses `pdftotext` when available and otherwise the optional `pypdf`
dependency (`pip install -e '.[corpus]'`).

```bash
python3 -m pure_tate fetch-source SRC-0002
python3 -m pure_tate extract-source SRC-0002
python3 -m pure_tate corpus-search "Theorem 1.5 boundary"
python3 -m pure_tate corpus-audit
```

Acquisition never changes the claims database. A research agent must extract an atomic
claim with an exact theorem/page locator and pass the citation gate separately.
The integrity audit rehashes every artifact, checks its derivation chain, and rejects a
PDF whose recorded arXiv version no longer matches the source catalogue.
