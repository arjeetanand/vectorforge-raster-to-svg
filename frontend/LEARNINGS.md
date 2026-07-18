
## E-046 — 2026-07-18 — Frontend conversion feedback
- Workstream: React workbench reliability
- Context/files: `frontend/src/App.tsx`, `frontend/src/styles.css`; users saw an immediate generic `Request failed (500)` while the API/worker were still starting or temporarily unavailable.
- Cause: submission failures stopped the flow after one response, and polling failures were surfaced as terminal errors even though the server job could still be running.
- Resolution: retain the idempotency key and automatically retry transient 5xx/network submission failures with short backoff; keep polling jobs alive after transient status errors; add an accessible progress banner for starting, queued, and processing states.
- Verification: run frontend lint, unit tests, and production build; manually confirm the banner remains visible during delayed API responses and that a successful retry reaches the existing queued/processing timeline.
- Prevention: treat transport failures separately from terminal job failures; only show the red error banner after retries are exhausted or the server explicitly returns a failed job.
