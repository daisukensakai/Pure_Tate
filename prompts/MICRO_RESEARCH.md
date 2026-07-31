# Targeted Stage-2 literature research

This is a narrow follow-up question isolated by a mathematics attempt. It does not
reopen the cross-checked seven-pair reduction.

1. Verify the question's degree, weight, variation, and Tate twist before searching.
2. Search primary papers, arXiv versions, and forward citations through the current
   date.
3. Record theorem/page/equation locators, not vague paper-level summaries.
4. Separate proved Hodge-structure results from point counts, Euler characteristics,
   semisimplifications, predictions, and conjectures.
5. Say explicitly when the proposed residual group was formulated incorrectly.
6. For every public source record, include the search query family, exact URL,
   UTC retrieval timestamp, source type, SHA-256 of the fetched bytes, and explicit
   DOI/arXiv id/version fields (use null when inapplicable).

Return exactly one JSON object matching `research/followups/FOLLOWUP_TEMPLATE.json`.
Use `known_result_found` only when a cited theorem actually discharges the exact
group. Use `partial` for a corrected reduction or relevant but insufficient theorem,
and `no_result_found` only after recording the searches and dates performed.
