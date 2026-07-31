# Independent live-web novelty audit

Search the live web through the audit date. This is not a corpus-only task.

Use every query family in `TASK.json`. Record every load-bearing public source with
its exact URL, query family, UTC retrieval timestamp, source type, DOI and arXiv
identifier/version where present, and the SHA-256 of the exact fetched response bytes.
Distinguish an exact prior theorem from nearby methods, conjectures, unpublished
claims, and results with different weight, degree, markings, or coefficients.

The verdict is `no_prior_result`, `prior_result_found`, or `inconclusive`. A search
failure is `inconclusive`, never evidence of novelty. Return only the JSON artifact.
