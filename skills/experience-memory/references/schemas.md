# experience-memory payload schemas

Reference for the capture flow. The CLI validates structure; the
quality bars below are enforced by you, the capturing agent, because
they are not mechanically checkable.

## Attempt record (`experience.py attempt <topic> --json '...'`)

    {
      "repo": "asserts-adi",                  // optional but recommended
      "branch": "fix/onboarding",             // optional
      "task": "one line: what was attempted",  // required
      "outcome": "solved",                     // required: solved | partial | failed | abandoned
      "verification": "how the outcome was determined",  // required, non-empty
      "bundle_used": true                      // optional bool: was a bundle pulled this session?
    }

Quality bar: `verification` names the check that was actually run
(test output, node counts, an alert clearing), not an impression.

## Post (`experience.py post <topic> --json '...'`)

    {
      "attempt_id": 4,                         // required; must exist in this topic
      "claim": "the insight itself, one or two sentences",
      "load_bearing_assumption": "names a SPECIFIC tool, API, file, or invariant",
      "evidence": "a 1-2 sentence quote from real trace or output",
      "stance": "NEW",                         // NEW | AGREE | DISAGREE | SYNTHESIZE
      "stance_post_id": null,                  // required post id for non-NEW stances
      "proposed_change": "one concrete change for the next session on this topic",
      "predicted_outcome": "a falsifiable prediction a future session can check",
      "confidence": "medium"                   // high | medium | low
    }

Quality bars (reject your own draft if it misses any):

- The assumption names something concrete. "the build is flaky" fails;
  "testcontainers maps port 5432 before the container is ready" passes.
- The evidence is a quote from actual output, not a paraphrase.
- The prediction is falsifiable: a future session could run something
  and observe it wrong.
- Before choosing NEW, read the thread. Evidence that bears on an
  existing claim is an AGREE, DISAGREE, or SYNTHESIZE with a citation,
  not a duplicate NEW post.
- Generic advice ("write tests first") is never a valid claim.

## Bundle sections (written by the distiller, installed via `distill`)

    ## Transferable insights   <- actionable, scoped, conditional guidance
    ## Confirmed constraints   <- verified environment or API requirements
    ## Rejected hypotheses     <- falsified approaches, with untried variants kept
    ## Pitfalls                <- recurring errors and their triggers
    ## Checks                  <- validation strategies that caught real problems
    ## Next steps              <- prioritized open questions

All six headers required, in this order. Entries cite `(post N)` or
`(attempt N)`. Target under 150 lines.
