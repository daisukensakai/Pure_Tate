# Corrective TATE-SUPPORT turn (ATT-0124 validation repair)

This is exactly one corrective Claude turn. ATT-0124 was spent after harness
validation failure. Do not restart the mathematics. Copy the previous JSON,
apply the listed mechanical fix, and emit one complete artifact whose `id`
matches TASK.json / the output filename.

## Validator feedback

`target_interface_reference` cites undeclared interface claim(s): CLM-0120-1, CLM-0120-2, CLM-0120-3, CLM-0120-4, CLM-0120-5, CLM-0120-6

Those claim IDs exist on the verified dependency ATT-0120. They must also appear
in this artifact's `dependency_claim_ids`. Keep
`target_interface_reference.interface_attempt_id` equal to ATT-0120, and keep
`interface_claim_ids` a nonempty list that is a subset of `dependency_claim_ids`.

## Prior artifact

Read `PREVIOUS-ATT-0124.json` (injected). That is the parsed ATT-0124 JSON from
TRACE-0090. Keep the mathematical argument. Prefer a minimal edit that clears
the listed error.

Return exactly one JSON object matching the campaign attempt template. No
Markdown fences, no prose before or after the JSON.
