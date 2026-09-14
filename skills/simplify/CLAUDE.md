# Simplify development notes

`SKILL.md` contains the complete workflow. Keep it prompt-only and bounded to behavior-preserving cleanup. `README.md` documents invocation and scope. `agents/openai.yaml` is generated.

## Contracts

- Explicit invocation only. Keep both `invocation: user` and `disable-model-invocation: true`.
- Default and path targets select uncommitted changes, not the full branch or all code in a directory.
- PR edits require a matching local head without overlapping user work.
- Four independent read-only lenses cover reuse, simplification, efficiency, and abstraction. Only the main agent edits.
- Parallel execution follows host permissions; unavailable delegation falls back to sequential review.
- Repository rules and observed conventions override reviewer preference.
- No correctness-review claim, behavior changes, architectural rewrites, or forced findings.

## Validation

After editing `SKILL.md`, run `npm run generate`, `npm run validate`, and `npm test`. Check that the generated Codex policy disables implicit invocation and that no Cursor rule is emitted. Do not edit version fields or generated files by hand.

Static validation checks packaging, not model behavior. For a live evaluation, exercise these cases in a disposable checkout:

1. No uncommitted changes: stop without switching to branch review.
2. A path with changed and unchanged files: review only selected changes.
3. A PR whose head differs from the checkout: ask before editing.
4. An existing helper with different error or side-effect behavior: do not reuse it.
5. An unnecessary wrapper with no contract or caller need: apply local simplification and run its tests.
6. Duplicate reviewer suggestions: apply one verified fix without overlapping edits.
7. No parallel-agent support: disclose and review sequentially.
8. An incidental correctness concern: report separately without repairing it as cleanup.
9. A test failure introduced by cleanup: fix or undo only that cleanup, preserving prior edits.
