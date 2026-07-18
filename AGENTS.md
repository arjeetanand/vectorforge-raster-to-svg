# Agent working agreement

Read `PROJECT.md` and `LEARNINGS.md` before changing VectorForge.

## Boundaries

- Make the smallest change that fulfills your assigned workstream.
- Preserve existing user changes. Do not reset, delete, or overwrite unrelated
  work.
- Do not add a new external integration, model download at inference time, or
  product scope outside `PROJECT.md`.
- Never put raw uploads, credentials, tokens, or unredacted stack traces in
  source files, docs, test fixtures, or `LEARNINGS.md`.

## Ownership and integration

- Avoid editing the same file as another agent. Report cross-boundary changes
  to the lead rather than making speculative edits.
- If a database field is needed, use a backwards-compatible migration strategy;
  `create_all()` does not alter an existing PostgreSQL table.
- Tests must be deterministic and must not depend on network access, GPUs, or
  downloaded weights.
- If a command fails, record the concise cause and safe resolution in
  `LEARNINGS.md` before handoff. Log material changes there as well.

## Handoff format

Report:

1. Files changed and user-visible/API behavior.
2. Tests run and results.
3. Errors encountered and their learning-log entries.
4. Remaining risks or dependencies.

The lead performs final conflict resolution, runs the complete available test
suite, and reconciles `git diff` against `LEARNINGS.md`.
