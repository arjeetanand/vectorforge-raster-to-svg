# VectorForge learning log

This append-only log records every material implementation, configuration, test, and documentation change, plus every real build, test, or runtime error. Entries exclude credentials, raw uploads, and unredacted stack traces.

## 2026-07-18 — Change — project foundation

- **Workstream:** Lead / documentation governance
- **Files:** `LEARNINGS.md`, `.gitignore`, `README.md`, `docs/`
- **Why:** Establish the repository contract and the audit trail required for all later work.
- **Resolution:** Created the shared logging convention before parallel implementation begins.
- **Verification:** Entries will be reconciled against `git diff` and command results at every handoff.
- **Takeaway:** Workers report their changes and failures to the lead; only the lead serially updates this file to avoid concurrent-write loss.

## 2026-07-18 — Change — licensing and fixture policy

- **Workstream:** Lead / documentation governance
- **Files:** `LICENSE`, `docs/fixtures.md`
- **Why:** Make code distribution and test-asset provenance explicit before fixtures and model references are added.
- **Resolution:** Added MIT licensing and a restrictive fixture-attribution policy.
- **Verification:** Documentation is linked from the project root and kept outside worker-owned source boundaries.
- **Takeaway:** Generated fixtures are preferred because they are reproducible and avoid ambiguous licensing.

## 2026-07-18 — Change — continuous-integration baseline

- **Workstream:** Lead / QA
- **Files:** `.github/workflows/ci.yml`
- **Why:** Keep backend checks, frontend build checks, and container build verification repeatable for every integration.
- **Resolution:** Added an initial GitHub Actions workflow with separate backend, frontend, and Docker jobs.
- **Verification:** The workflow commands match the repository scripts and will be validated after worker handoffs complete.
- **Takeaway:** CI configuration must evolve with dependency and package-manager choices; integration review checks that it remains executable.

## 2026-07-18 — Change — asynchronous backend skeleton

- **Workstream:** API/worker
- **Files:** `backend/app/{api,core,services,main.py,db.py,models.py,schemas.py,tasks.py}`, `backend/Dockerfile`, `backend/requirements.txt`, `docker-compose.yml`
- **Why:** Implement durable queued vectorization jobs, shared artifact storage, health endpoints, and local Compose orchestration.
- **Resolution:** Added FastAPI routes, SQLAlchemy state records, Celery task lifecycle, Redis/PostgreSQL services, and cleanup scheduling.
- **Verification:** Source was compiled successfully with an isolated bytecode cache; runtime integration awaits dependency installation and Docker availability.
- **Takeaway:** API routes enqueue after database commit and keep worker exceptions out of user-facing responses.

## 2026-07-18 — Error E-001 — protected Python bytecode cache

- **Workstream:** API/worker
- **Context:** `python3 -m compileall backend/app`
- **Cause:** The environment redirected Python bytecode output to a protected macOS cache location.
- **Resolution:** Reran with `PYTHONPYCACHEPREFIX=/tmp/vectorforge-pycache`, which completed successfully.
- **Verification:** Compilation passed with the isolated cache path.
- **Prevention:** Use a writable temporary bytecode prefix for local Python verification in this workspace.

## 2026-07-18 — Error E-002 — unavailable Docker CLI

- **Workstream:** API/worker
- **Context:** Docker Compose configuration/build smoke test
- **Cause:** `docker` is not installed or not available on this machine's command path.
- **Resolution:** Kept Compose configuration in source; deferred container build and smoke validation to an environment with Docker.
- **Verification:** Blocker confirmed by `docker` command lookup.
- **Prevention:** CI retains a Docker build job so container validation runs where Docker is provided.

## 2026-07-18 — Error E-003 — missing local backend dependencies

- **Workstream:** API/worker
- **Context:** Runtime backend test/import attempt
- **Cause:** The active Python environment lacks SQLAlchemy and other declared project dependencies.
- **Resolution:** Deferred runtime tests until the project requirements are installed in an isolated environment.
- **Verification:** Dependency absence was identified before attempting a misleading application test.
- **Prevention:** Bootstrap the documented environment before running integration checks.

## 2026-07-18 — Change — deterministic CV-to-SVG pipeline

- **Workstream:** CV pipeline
- **Files:** `backend/app/pipeline/{image,segmentation,colors,contours,svg,types,vectorizer,vectorize}.py`, `backend/tests/test_pipeline.py`, `backend/requirements.txt`
- **Why:** Provide framework-independent raster validation, foreground detection, color/line extraction, contour simplification, cubic Bézier path generation, SVG output, and worker-facing preview artifacts.
- **Resolution:** Added the pure pipeline and focused tests for supported modes, holes, filtering, SVG output, and malformed inputs.
- **Verification:** Pipeline sources and tests compile; `git diff --check` passes.
- **Takeaway:** Keeping the vectorizer free of HTTP/database concerns lets the Celery task own artifact and lifecycle handling.

## 2026-07-18 — Error E-004 — pytest and CV dependencies absent

- **Workstream:** CV pipeline
- **Context:** `python -m pytest backend/tests/test_pipeline.py -q` and direct import smoke test
- **Cause:** The host Python environment lacks `pytest`, NumPy, OpenCV, and Pillow.
- **Resolution:** Recorded the exact runtime requirements; test execution is deferred until an isolated project environment is installed.
- **Verification:** Compilation remains successful without imported runtime dependencies.
- **Prevention:** Install `backend/requirements.txt` plus test tooling before backend test execution.

## 2026-07-18 — Change — containerized frontend delivery

- **Workstream:** Lead / integration
- **Files:** `frontend/Dockerfile`, `frontend/nginx.conf`, `docker-compose.yml`
- **Why:** The local Docker promise requires the React application to be a Compose service, not only a development-server command.
- **Resolution:** Added a Node build stage, Nginx static host, same-origin `/api/` proxy, and `frontend` Compose service on port 5173.
- **Verification:** Configuration will be checked by Docker CI; local Docker is unavailable (E-002).
- **Takeaway:** Same-origin proxying avoids production CORS and makes browser artifact links work consistently.

## 2026-07-18 — Error E-005 — frontend lint violations

- **Workstream:** Integration reviewer
- **Context:** `cd frontend && npm run lint`
- **Cause:** The polling effect did not satisfy the React hook dependency rule, and a shared formatting helper was exported from a fast-refresh component module.
- **Resolution:** Assigned the frontend workstream to correct the effect dependency shape and move or localize the helper before final verification.
- **Verification:** Rerun lint after the frontend handoff.
- **Prevention:** Treat hook dependency and fast-refresh lint rules as release gates, not style-only warnings.

## 2026-07-18 — Change — React VectorForge workbench

- **Workstream:** Frontend UI
- **Files:** `frontend/src/`, `frontend/{package.json,vite.config.ts,index.html}`, `frontend/package-lock.json`
- **Why:** Deliver the approved browser workbench with real upload, settings, queued-job polling, output previews, responsive layout, downloads, and accessible status/error states.
- **Resolution:** Added typed API client, reducer-based state machine, cleanup-aware polling, client input limits, responsive white/blue/violet interface, reducer tests, and a locked dependency graph.
- **Verification:** `npm run lint`, `npm run test`, and `npm run build` pass; browser validation remains unavailable (E-008).
- **Takeaway:** UI state maps directly to the backend job contract so failed jobs retain the original image/settings and offer a retry.

## 2026-07-18 — Error E-006 — sandboxed npm registry access

- **Workstream:** Frontend UI / integration
- **Context:** Initial dependency and lockfile creation attempt
- **Cause:** The sandbox could not resolve the npm registry and could not write its normal user log directory.
- **Resolution:** Retried the ordinary `npm install --package-lock-only --ignore-scripts` command with approved registry access; it created `frontend/package-lock.json` and reported no vulnerabilities.
- **Verification:** `npm ci`-compatible lockfile is present.
- **Prevention:** Create reproducible JavaScript locks in an environment with registry access, then use `npm ci` in CI and Docker.

## 2026-07-18 — Error E-007 — documentation patch context mismatch

- **Workstream:** Lead / integration
- **Context:** First consolidated documentation/configuration patch
- **Cause:** The patch targeted stale architecture text and failed verification before applying any changes.
- **Resolution:** Read the current files and reapplied the changes as an exact patch.
- **Verification:** The corrected API, architecture, and model documentation now match implementation names and routes.
- **Prevention:** Re-read shared files immediately before multi-file patches after concurrent workstream handoffs.

## 2026-07-18 — Error E-008 — local browser smoke-test unavailable

- **Workstream:** Frontend UI
- **Context:** Vite development-server and browser validation
- **Cause:** The sandbox denied port binding; a permitted retry did not retain a running process, and no Browser runtime was available.
- **Resolution:** Completed static frontend validation and left Docker/CI smoke checks for a browser-capable environment.
- **Verification:** Build, lint, and unit tests pass despite the rendering-environment blocker.
- **Prevention:** Use the Docker Compose frontend service or a browser-enabled workspace for visual interaction verification.

## 2026-07-18 — Change — optional local PyTorch segmentation

- **Workstream:** ML segmentation
- **Files:** `backend/app/ml/`, `backend/scripts/download_segmentation_model.py`, `backend/tests/test_ml_segmentation.py`, `backend/app/pipeline/vectorize.py`, `backend/app/core/config.py`, `backend/requirements.txt`
- **Why:** Implement the requested optional foreground model without runtime network downloads or misleading ML metadata.
- **Resolution:** Added local DeepLabV3-MobileNetV3-Large inference, worker selection/fallback metadata, configurable model path/device/digest, a full SHA-256-pinned atomic downloader, and tests for missing-model fallback.
- **Verification:** Compile, provider-selection, checksum, and downloader-help checks passed before final integration; full model inference requires provisioned weights.
- **Takeaway:** The deterministic OpenCV path remains usable with no model, while a requested unavailable model is visibly reported as a fallback.

## 2026-07-18 — Error E-009 — stale checkpoint URL during ML verification

- **Workstream:** ML segmentation
- **Context:** Initial optional-model downloader verification
- **Cause:** An outdated TorchVision checkpoint filename produced HTTP 403.
- **Resolution:** Reconciled the pinned TorchVision 0.20 artifact and replaced it with `deeplabv3_mobilenet_v3_large-fc3c493d.pth`, including its full SHA-256 digest.
- **Verification:** Local checksum matched the manifest after correction.
- **Prevention:** Pin model URLs and full digests together with the exact TorchVision version.

## 2026-07-18 — Error E-010 — ML check tooling limitations

- **Workstream:** ML segmentation
- **Context:** Final compile/test attempt
- **Cause:** `pytest` was absent and a follow-up compile command was rejected by the sandbox after prior successful isolated-cache checks.
- **Resolution:** Recorded the limitations; the integration environment will install the declared requirements before executing the full suite.
- **Verification:** Earlier isolated-cache compilation, provider fallback smoke tests, and downloader help passed.
- **Prevention:** Run the full Python suite in the project environment or CI rather than relying on host tooling.

## 2026-07-18 — Change — integration hardening

- **Workstream:** Lead / reviewer follow-up
- **Files:** `frontend/{Dockerfile,nginx.conf,package.json,src/App.tsx,src/styles.css}`, `docker-compose.yml`, `.github/workflows/ci.yml`, `backend/app/pipeline/vectorize.py`, `backend/scripts/train_segmentation.py`, `docs/`
- **Why:** Resolve reviewer findings around Compose delivery, locked frontend dependencies, model lifecycle docs, retry behavior, worker image-limit consistency, and CI coverage.
- **Resolution:** Added the frontend Compose service and same-origin proxy, explicit dependency versions and lockfile, frontend test CI step, health smoke, training CLI, corrected docs, settings-aware worker decode, and visible failed-job retry.
- **Verification:** Final static checks are being run after this log entry.
- **Takeaway:** Cross-workstream review is essential: individually valid components can still disagree on contract details and operational behavior.

## 2026-07-18 — Error E-011 — ML test module shadowing

- **Workstream:** Lead / backend verification
- **Context:** Python 3.12 pytest run, `test_requested_model_without_config_reports_worker_fallback`
- **Cause:** The package-level `vectorize` function shadowed the worker-facade module when `monkeypatch` resolved a dotted import path.
- **Resolution:** Imported `app.pipeline.vectorize` explicitly through `importlib` and patched its `get_settings` attribute directly.
- **Verification:** Rerunning the full backend suite after the correction.
- **Prevention:** Use explicit module imports in tests whenever package exports duplicate module names.

## 2026-07-18 — Error E-012 — incomplete mocked settings

- **Workstream:** Lead / backend verification
- **Context:** Rerun of the ML fallback test after settings-aware image decoding was added.
- **Cause:** The test's minimal settings double did not include the upload/pixel/processing limits now read by the worker facade.
- **Resolution:** Added the three production-limit fields to the test double.
- **Verification:** Rerunning the complete backend suite.
- **Prevention:** Keep test configuration doubles aligned with all fields consumed by the unit under test.

## 2026-07-18 — Error E-013 — backend lint failure

- **Workstream:** Lead / backend verification
- **Context:** Ruff check after the complete Python test suite passed.
- **Cause:** `backend/app/db.py` retained an unused SQLAlchemy `Session` import.
- **Resolution:** Removed the unused import.
- **Verification:** Rerunning lint, format, backend tests, and frontend checks.
- **Prevention:** Keep static analysis in the final validation chain, not only in CI.

## 2026-07-18 — Change — backend format normalization

- **Workstream:** Lead / final verification
- **Files:** Backend source and test files reported by Ruff.
- **Why:** The required format check found 15 files with noncanonical formatting after parallel implementation.
- **Resolution:** Applied `ruff format backend/app backend/tests`.
- **Verification:** The final test/lint/format chain is rerun after this entry.
- **Takeaway:** Apply the shared formatter once after multi-agent integration to prevent harmless style drift from blocking CI.

## 2026-07-18 — Error E-014 — incomplete offline npm cache

- **Workstream:** Lead / final verification
- **Context:** `npm ci --offline`
- **Cause:** The isolated npm cache did not contain every locked package, including `zod-validation-error`.
- **Resolution:** Performed a normal clean `npm ci` with approved registry access before validation.
- **Verification:** Clean install, lint, three frontend unit tests, production build, and audit all passed with zero reported vulnerabilities.
- **Prevention:** CI installs from the lockfile with registry access; local offline runs are optional and must not substitute for clean-install validation.

## 2026-07-18 — Change — final verification complete

- **Workstream:** Lead / final verification
- **Files:** Entire repository validation surface
- **Why:** Confirm the integrated implementation is internally consistent after all workstreams and fixes.
- **Resolution:** Executed backend tests/lint/format checks, frontend clean install/lint/tests/build, and whitespace validation.
- **Verification:** Backend: 14 tests passed, Ruff check passed, 26 files formatted. Frontend: 3 tests passed, lint and production build passed, `npm ci` audit reported 0 vulnerabilities. `git diff --check` passed.
- **Takeaway:** Docker Compose/browser validation remains the only environment-blocked step because Docker and an in-app browser are unavailable locally; the Compose CI health smoke covers the container startup path.

## 2026-07-18 — Change — complete runbook

- **Workstream:** Lead / documentation
- **Files:** `README.md`, `docker-compose.yml`
- **Why:** Document complete Docker and local-development startup, usage, verification, optional model installation, and cleanup so the application can be run without prior project knowledge.
- **Resolution:** Added step-by-step commands and mounted the ignored `models/` directory read-only into API/worker containers for the optional pinned model.
- **Verification:** Compose configuration remains syntactically consistent; Docker execution requires a Docker-enabled environment.
- **Takeaway:** Operational docs must match volume mounts and runtime configuration, especially for optional model assets.

## 2026-07-18 — Change — container model-download support

- **Workstream:** Lead / documentation correction
- **Files:** `backend/Dockerfile`, `README.md`
- **Why:** Docker-first model installation requires the downloader script in the backend image.
- **Resolution:** Copied `scripts/` into the image and invoke the downloader with `docker compose run` against the mounted model directory.
- **Verification:** Docker build remains deferred to a Docker-capable environment.
- **Takeaway:** Docker-only onboarding must not require host Python dependencies.

## 2026-07-18 — Change — writable model bootstrap mount

- **Workstream:** Lead / Docker correctness
- **Files:** `docker-compose.yml`
- **Why:** The API container executes the explicit model downloader, which cannot write through a read-only bind mount.
- **Resolution:** Made the API model mount writable; the worker mount remains read-only for inference.
- **Verification:** Compose configuration was reviewed against the documented download command.
- **Takeaway:** Grant write access only to the bootstrap surface that needs it; inference remains read-only.

## 2026-07-18 — Error E-015 — incomplete local Vite installation

- **Workstream:** Lead / frontend debugging
- **Context:** Local development server reported a missing `vite/dist/node/chunks/dist.js` module.
- **Cause:** The referenced Vite directory was absent from `frontend/node_modules`, indicating an incomplete local dependency installation. Docker Compose itself had started the Nginx-served production frontend successfully.
- **Resolution:** Rebuilt dependencies with `npm ci` from `package-lock.json` and added repair instructions to the README.
- **Verification:** Vite's production build, ESLint, and all three frontend tests pass after the clean install; npm audit reported 0 vulnerabilities.
- **Prevention:** Use `npm ci` for clean local installs and dependency repairs.

## 2026-07-18 — Change — reproducible frontend image install

- **Workstream:** Lead / frontend debugging
- **Files:** `frontend/Dockerfile`
- **Why:** Keep Docker frontend dependency resolution identical to the repaired local dependency tree.
- **Resolution:** Replaced `npm install` with lockfile-enforced `npm ci` in the frontend build stage.
- **Verification:** The lockfile install, lint, tests, and Vite production build passed before the image change.
- **Takeaway:** Production images should consume the committed lockfile rather than resolve floating dependency metadata.

## 2026-07-18 — Change — local automatic vectorization recommendation

- **Workstream:** Lead / UX and CV heuristics
- **Files:** `frontend/src/{recommendation.ts,state.ts,state.test.ts,App.tsx,components.tsx,styles.css}`
- **Why:** Users should not need to guess whether an upload needs Line art or Illustration settings.
- **Resolution:** Added browser-local image statistics that recommend and automatically apply a mode, color count, smoothing, component filter, and segmentation default, with a visible explanation and manual override controls.
- **Verification:** Added pure heuristic tests for sparse single-ink and multi-color artwork; ESLint, five frontend tests, and the production build pass.
- **Takeaway:** Local CV heuristics are faster and more reliable for mode selection than an LLM, and avoid uploading image data solely for a recommendation.

## 2026-07-18 — Error E-016 — stale local Vite process after dependency repair

- **Workstream:** Lead / rendered frontend verification
- **Context:** Browser check at `http://localhost:5173` after the local `npm ci` repair.
- **Cause:** An already-running Vite process retained the earlier broken dependency state and continued showing the old missing-chunk overlay.
- **Resolution:** The source dependencies and production build are healthy; restart the local Vite process or use the Docker Compose Nginx frontend to load the repaired application.
- **Verification:** Browser DOM showed the normal workbench plus the stale Vite overlay; lint, five tests, and production build passed from the repaired source tree.
- **Prevention:** Always stop and restart the dev server after repairing `node_modules`.

## 2026-07-18 — Error E-017 — process inspection restricted

- **Workstream:** Lead / rendered frontend verification
- **Context:** Attempt to identify the stale local Vite process with `ps`.
- **Cause:** The execution sandbox denied process-list access.
- **Resolution:** Did not attempt to terminate or alter user processes; provided the safe manual restart procedure instead.
- **Verification:** Restriction was reported directly by the environment.
- **Prevention:** Treat process management as user-owned unless a supported environment interface is available.

## 2026-07-18 — Change — photo-like upload warning

- **Workstream:** Lead / recommendation quality
- **Files:** `frontend/src/{recommendation.ts,state.test.ts}`
- **Why:** A photo should not receive an unqualified Illustration recommendation because the pipeline is optimized for flat artwork.
- **Resolution:** Added a high-color-diversity/coverage guard that retains Illustration only as a fallback and clearly warns that photo results may be noisy.
- **Verification:** Added a photo-like recommendation unit test; frontend validation is rerun after this entry.
- **Takeaway:** Good automatic defaults include clear scope warnings, not just a mode choice.

## 2026-07-18 — Error E-018 — asynchronous recommendation could retain a prior upload

- **Workstream:** Lead / frontend state correction
- **Context:** Rapidly selecting a second image while browser-side recommendation analysis was still running.
- **Cause:** The selected file and prior download were cleared only after the asynchronous analysis finished; an older analysis response could also update state after a newer selection.
- **Resolution:** File selection now clears the previous job/download immediately. Recommendation results carry the exact file and object URL, and the reducer ignores responses for replaced files.
- **Verification:** Added a reducer test for a stale first-upload recommendation arriving after the second image is selected; `npm run lint`, `npm run test` (7 tests passed), `npm run build`, and `git diff --check` all passed on 2026-07-18.
- **Prevention:** Apply immediate user-intent state changes first, then guard deferred asynchronous results with their originating identity.

## 2026-07-18 — Error E-019 — browser file-control API did not expose file selection

- **Workstream:** Lead / rendered frontend verification
- **Context:** Attempting to exercise the local upload flow through the available browser-control binding.
- **Cause:** Its locator implementation does not provide a `setInputFiles` method.
- **Resolution:** Did not use a browser-script workaround to alter the user file input. Verified the recommendation and result invalidation logic with reducer/unit tests, and retained browser checks for the rendered application shell.
- **Verification:** The unavailable method reported `is not a function`; no user files or uploads were altered by the test attempt.
- **Prevention:** Check supported locator methods before planning browser-based file-upload automation.

## 2026-07-18 — Error E-020 — removed heuristic variable still referenced

- **Workstream:** Lead / recommendation correction
- **Context:** Frontend test run after replacing the broad white-background recommendation rule.
- **Cause:** The line-art confidence expression still referenced the deleted `lowDiversity` variable.
- **Resolution:** Replaced it with the new colour-family metric.
- **Verification:** ESLint, all 9 frontend tests, the TypeScript/Vite production build, and `git diff --check` passed.
- **Prevention:** Run the focused test suite immediately after simplifying heuristic inputs.

## 2026-07-18 — Change — multi-colour logo recommendation and result invalidation

- **Workstream:** Lead / vectorization UX and recommendation quality
- **Files:** `frontend/src/{recommendation.ts,state.ts,state.test.ts,App.tsx,components.tsx}`
- **Why:** A sparse red-and-blue logo on white was incorrectly classified as Line art, and changing completed-job settings could leave an old SVG visible and downloadable.
- **Resolution:** Recommendation now counts meaningful hue families, so multi-colour logos select Illustration even when the background is mostly white. Any actual settings change clears the previous job, previews, and downloads; the UI explicitly asks the user to vectorize again with the new settings.
- **Verification:** Added tests for sparse multi-colour logos and completed-result invalidation; ESLint, 9 tests, production build, and diff validation pass.
- **Takeaway:** Background-dominated images require artwork-colour features, while post-completion control changes must invalidate results derived from older options.

## 2026-07-18 — Error E-021 — browser screenshot API differs from workflow example

- **Workstream:** Lead / rendered frontend verification
- **Context:** Capturing required screenshot evidence after reloading the local frontend.
- **Cause:** The browser binding exposes screenshots on the tab object, not its `playwright` helper.
- **Resolution:** Used the supported tab screenshot method after confirming available methods.
- **Verification:** The resulting desktop screenshot showed the VectorForge workbench; page identity was `VectorForge`, no framework overlay was present, and browser console errors/warnings were empty.
- **Prevention:** Inspect the connected browser binding when its implementation differs from generic workflow examples.

## 2026-07-18 — Error E-022 — persistent browser session rejected a duplicate declaration

- **Workstream:** Lead / rendered frontend verification
- **Context:** Retrying screenshot capture in the existing persistent browser session.
- **Cause:** A previous failed attempt had already declared the same block-scoped variable.
- **Resolution:** Retried with unique variable names; no application code or user data was affected.
- **Verification:** The final screenshot and DOM/console checks completed successfully.
- **Prevention:** Use unique names or an isolated scope for retries in persistent interactive sessions.

## 2026-07-18 — Change — rendered frontend regression check

- **Workstream:** Lead / rendered frontend verification
- **Files:** Local frontend at `http://localhost:5173/`
- **Why:** A passing build alone does not establish that the frontend still renders correctly after state-flow changes.
- **Resolution:** Reloaded the workbench and checked page identity, meaningful content, framework-overlay absence, console health, and a desktop screenshot.
- **Verification:** All rendered shell checks passed. File selection could not be automated because the available browser binding lacks file-input support; reducer tests cover the selection and option-change flow.
- **Takeaway:** Keep browser evidence for rendered quality and unit tests for file-input states when the browser surface cannot safely perform a local upload.

## 2026-07-18 — Error E-023 — additional QA agent thread unavailable

- **Workstream:** Lead / regression-test coordination
- **Context:** Starting three independent testers plus a lead fixer for the requested four-workstream quality pass.
- **Cause:** The workspace agent-thread limit includes earlier completed workstreams, so creating or reactivating a third tester was rejected.
- **Resolution:** Started two independent QA testers and assigned the lead to execute the third backend/API/vector-output audit alongside defect fixes and centralized documentation.
- **Verification:** The two tester workstreams are active; the rejected orchestration call made no repository changes.
- **Prevention:** Reuse capacity where available and record test-coverage ownership rather than claiming unavailable parallel work.

## 2026-07-18 — Error E-024 — backend test runner unavailable in the current environment

- **Workstream:** Lead / backend and vector-output QA
- **Context:** Executing the repository backend test suite with `cd backend && pytest -q`.
- **Cause:** `pytest` is not installed or exposed on this host environment; backend dependencies are intentionally containerized.
- **Resolution:** Did not install or alter dependencies implicitly. Frontend validation continues locally; backend suite remains designated for the documented Docker/virtual-environment test command.
- **Verification:** Shell reported `command not found: pytest`; no backend tests are represented as passed in this environment.
- **Prevention:** State the required test runtime explicitly and preserve a separate CI/Docker backend test path.

## 2026-07-18 — Change — recommendation and re-vectorization run-guide clarification

- **Workstream:** Lead / user documentation
- **Files:** `README.md`
- **Why:** Users need to know why a sparse multi-colour logo selects Illustration and that control changes do not alter an already-created SVG.
- **Resolution:** Documented local automatic recommendation, practical mode definitions, explicit post-setting-change invalidation, and the required fresh Vectorize action.
- **Verification:** Documentation matches the reducer and workbench behavior introduced in the current regression fix.
- **Takeaway:** Explain both automatic defaults and the boundary between configuration and a completed asynchronous job.

## 2026-07-18 — Change — lead regression audit evidence

- **Workstream:** Lead / frontend and vector-output QA
- **Files/context:** Frontend test/build workflow and the user-provided illustrative SVG artifact.
- **Why:** The lead fulfilled the backend/vector-output tester role while additional agent capacity was unavailable.
- **Resolution:** Checked frontend lint, all 9 reducer/heuristic tests, production build, and diff whitespace. Checked that the illustrative output is XML-valid and contains six editable SVG paths with two fill colours.
- **Verification:** `npm run lint`, `npm run test`, `npm run build`, `git diff --check`, and `xmllint --noout` passed; backend Python tests remain unrun only because E-024 documents the missing local runner.
- **Takeaway:** Distinguish verified artifact structure from an end-to-end worker run when the required backend runtime is unavailable.

## 2026-07-18 — Error E-025 — status-poll failure made Retry ineffective

- **Workstream:** Frontend state QA / lead fix
- **Context:** A vectorization job is queued or processing, then a later status-poll request fails.
- **Cause:** The error state preserved the polling job, which correctly avoids duplicate work, but the Retry button called submission. Submission rejected the retained queued/processing job, so the UI could not recover.
- **Resolution:** Added a dedicated poll-retry state action and counter. Retry now preserves the existing job identifier, clears the transient error, and restarts only its polling effect; upload/submission failures still retry a new submission.
- **Verification:** Added a reducer regression test; ESLint, all 10 frontend tests, TypeScript/Vite production build, and `git diff --check` passed.
- **Prevention:** Model retry intent explicitly when a job-creation request and a status-poll request have different safe recovery actions.

## 2026-07-18 — Error E-026 — QA local-server and browser-upload limitations

- **Workstream:** Independent QA reconciliation
- **Context:** Running independent browser tests for recommendation and frontend state.
- **Cause:** The restricted sandbox denied a direct Vite listener, pre-existing local ports required Vite to select another port, and the browser binding could not complete the local file-chooser interaction. Process inspection was also denied by the sandbox.
- **Resolution:** QA reran the local server with permitted local-server access, performed rendered smoke checks on the selected local port, and used unit/reducer tests rather than script around file input security. No user file was submitted by automation.
- **Verification:** Both QA workstreams reported no Vite overlay or console errors in their rendered checks; the exact file-upload journey remains explicitly unverified in this environment.
- **Prevention:** Treat browser file upload and port restrictions as test-environment limitations, document them, and keep deterministic state tests for the same flow.

## 2026-07-18 — Change — three-stream regression pass completed

- **Workstream:** Recommendation QA, frontend-state QA, and lead backend/vector-output QA
- **Files/context:** Heuristic tests, reducer state tests, rendered frontend smoke check, README, and illustrative SVG validation.
- **Why:** Exercise different classes of stale-result, recommendation, retry, artifact, and rendered-UI regressions after the reported upload issue.
- **Resolution:** Corrected the multi-colour recommendation, completed-result invalidation, and poll-retry recovery defects; documented current behavior and QA limitations.
- **Verification:** Final frontend quality gate: lint passed, 10 tests passed, production build passed, and diff validation passed. Backend suite was not run locally only because E-024 documents the absent Python test runtime.
- **Takeaway:** Automated mode selection, asynchronous state, and transient polling failures need independent regression coverage before treating a conversion result as trustworthy.

## 2026-07-18 — Error E-027 — artifact-inspection command interpolation mistake

- **Workstream:** Lead / user output inspection
- **Context:** Initial local command to classify the two user-provided SVG exports.
- **Cause:** A JavaScript template expression contained unsupported shell parameter syntax.
- **Resolution:** Reissued a simpler read-only inspection command with explicit SVG paths.
- **Verification:** Both exports were successfully inspected without alteration.
- **Prevention:** Keep cross-language command interpolation simple and avoid shell syntax inside JavaScript template expressions.

## 2026-07-18 — Change — paired SVG export comparison

- **Workstream:** Lead / user output inspection
- **Files/context:** Two user-provided SVG downloads generated from the same uploaded artwork.
- **Why:** Determine whether changing the UI mode created a distinct vector result.
- **Resolution:** Compared checksums, byte content, XML validity, path count, and fill colours without retaining user-upload content in this log.
- **Verification:** The exports had identical SHA-256 digests and identical bytes. Each is valid SVG with nine coloured paths, demonstrating Illustration-style output rather than a Line art versus Illustration pair.
- **Takeaway:** Identical downloads indicate the same completed result or the same submitted options; they do not demonstrate that two modes were applied.

## 2026-07-18 — Error E-028 — preview artifact could disagree with downloadable SVG

- **Workstream:** Lead / artifact truthfulness correction
- **Context:** A completed-job screen visibly showed a rasterized preview, while the associated user-provided SVG contained only an SVG wrapper and no paths.
- **Cause:** The frontend preferred `preview.png` for the vector pane, and the worker accepted a result with zero eligible contours. Quantization can resemble the source even when all candidate components are filtered out.
- **Resolution:** The vector pane now prefers the same SVG URL exposed by Download SVG. The backend raises a dedicated no-path error before writing artifacts, and the worker records a clear unsupported/no-shape failure instead of a completed blank SVG.
- **Verification:** Inspected the affected artifact as valid XML with zero paths; added a frontend SVG-preference regression test and a backend no-path test. Frontend lint, 11 tests, production build, backend syntax compilation using a temporary cache, and diff validation pass.
- **Prevention:** A successful vectorization must have at least one editable path, and a user-facing SVG preview must use the download artifact itself.

## 2026-07-18 — Error E-029 — default Python bytecode cache path denied by sandbox

- **Workstream:** Lead / backend syntax verification
- **Context:** Running `python3 -m compileall backend/app` after the worker pipeline change.
- **Cause:** macOS attempted to write compiled bytecode under a protected user cache directory.
- **Resolution:** Reran compilation with `PYTHONPYCACHEPREFIX` directed to a permitted temporary directory.
- **Verification:** Backend source compiled successfully with the temporary cache; no project file was altered by the failed cache write.
- **Prevention:** Direct transient Python caches to a writable task-specific temporary location in restricted environments.

## 2026-07-18 — Change — document and spreadsheet limitation clarification

- **Workstream:** Lead / user documentation
- **Files:** `README.md`
- **Why:** A spreadsheet screenshot was submitted to an artwork vectorizer and exposed the prior zero-path success defect.
- **Resolution:** Explicitly documented that spreadsheet/document screenshots and dense text are outside the supported input class, and that no-path inputs now fail instead of exporting a blank SVG.
- **Verification:** Matches the worker no-path behavior introduced in E-028.
- **Takeaway:** Clear product boundaries prevent a raster preview from being mistaken for semantic document conversion.

## 2026-07-18 — Error E-030 — public sample download initially blocked by DNS sandboxing

- **Workstream:** Lead / sample test pack
- **Context:** Downloading public OpenCV sample images for local manual testing.
- **Cause:** The restricted execution sandbox could not resolve the public source host.
- **Resolution:** Repeated the exact public download with approved network access and saved only the selected test assets under `samples/`.
- **Verification:** Three raster assets downloaded successfully and were identified as valid JPEG/PNG files.
- **Prevention:** Use explicit, attributable public sources and request network approval when the sandbox blocks fixture retrieval.

## 2026-07-18 — Error E-031 — macOS `sips` could not rasterize SVG fixtures

- **Workstream:** Lead / sample test pack
- **Context:** Converting project-created SVG fixture artwork to PNG upload samples.
- **Cause:** The installed `sips` build could not extract SVG image data.
- **Resolution:** Used the local macOS Quick Look thumbnail renderer instead, then copied its valid PNG outputs into the sample folder.
- **Verification:** All generated PNG files identify as valid PNG images; the flat-logo fixture was visually inspected.
- **Prevention:** Do not assume every system image utility supports SVG rasterization; validate generated upload files by type and visual inspection.

## 2026-07-18 — Error E-032 — Quick Look thumbnail command required unsandboxed local execution

- **Workstream:** Lead / sample test pack
- **Context:** First local thumbnail-renderer invocation for SVG fixture conversion.
- **Cause:** The sandbox rejected a macOS path-filter initialization used by the Quick Look process.
- **Resolution:** Repeated the local conversion with approved execution, writing transient thumbnails only under `/tmp` before copying resulting PNGs into the project.
- **Verification:** All five project-created PNG fixtures were produced successfully.
- **Prevention:** Keep renderer intermediates outside the repository and seek scoped local execution approval when operating-system helpers require it.

## 2026-07-18 — Change — comprehensive local sample test pack

- **Workstream:** Lead / manual acceptance testing
- **Files:** `samples/`, `samples/README.md`, `README.md`
- **Why:** Users need reproducible images to test supported artwork, edge cases, and validation failures without sharing private uploads.
- **Resolution:** Added attributable public photo/document/multi-colour samples plus project-created line-art, flat-logo, transparent-icon, noisy-sketch, blank, corrupt, and oversized cases. Added a manual test matrix, expected outcomes, provenance, and a README link.
- **Verification:** All raster assets were file-validated; generated logo PNG was visually inspected; `git diff --check` passes.
- **Takeaway:** A test pack should include both quality expectations for supported inputs and explicit failure expectations for unsupported or invalid inputs.

## 2026-07-18 — Error E-033 — repeat-upload recommendation state could look stale

- **Workstream:** Lead / repeat-upload frontend correction
- **Context:** Selecting a second image while the browser-local recommendation for the prior image was still pending, or selecting the same local file again after another upload.
- **Cause:** The new upload initially retained the prior image's visible option values until analysis completed, and the native file input retained its value, which can suppress a same-file change event.
- **Resolution:** New selection immediately resets to default options and an explicit “Analyzing new image” state. Conversion controls are disabled only during analysis while the upload control remains available for a newer replacement. Recommendation responses remain identity-guarded; analysis failure unlocks manual settings. The native file input now resets after every selection.
- **Verification:** Added two reducer tests for latest-upload application and analysis failure fallback. Frontend lint, 13 tests, production build, and diff validation passed. Rendered workbench check passed with no framework overlay or browser console errors.
- **Prevention:** Separate file replacement from recommendation completion, make pending analysis visible, and reset native file input values when same-file re-selection is supported.

## 2026-07-18 — Error E-034 — same-hue multi-colour icon classified as Line art

- **Workstream:** Lead / recommendation correction
- **Context:** A transparent icon with a yellow fill and brown outline was auto-selected as Line art.
- **Cause:** The heuristic counted broad hue families only; yellow and brown shared the same coarse hue bucket, even though they are distinct, prominent fill colours.
- **Resolution:** Added a prominent-artwork-palette count based on coarse RGB buckets and coverage. Two substantial fills now select Illustration even when their hue family is the same.
- **Verification:** Added a dedicated same-hue multi-fill recommendation test. Frontend lint, 14 tests, production build, diff validation, and rendered browser smoke checks passed with no console errors.
- **Prevention:** Combine hue-family analysis with palette separation and area coverage; hue alone cannot distinguish related fill colours from a single-ink mark.

## 2026-07-18 — Change — learning-log completeness audit

- **Workstream:** Lead / documentation governance
- **Files/context:** Entire `LEARNINGS.md` history, current repository changes, validation outputs, and user-reported conversion cases.
- **Why:** Confirm that every material implementation, configuration, documentation, test, tool/environment error, and correction is recorded in one safe, reviewable place.
- **Resolution:** Reconciled the log through errors E-001 to E-034. Entries cover backend/worker setup, CV and ML work, frontend changes, Docker/Vite issues, browser limitations, recommendation bugs, stale results, retry recovery, empty SVG prevention, samples, and all associated corrections.
- **Verification:** The log entries include cause, resolution, verification, and prevention for each recorded error, without credentials, raw user uploads, or unredacted traces. Current frontend validation remains green: lint, 14 tests, production build, and diff validation.
- **Takeaway:** Update this append-only log in the same turn as every meaningful change or real error; do not defer error documentation until later.

## 2026-07-18 — Change — resolved user-visible issues index

- **Workstream:** Lead / documentation governance
- **Files/context:** User-reported application behavior and the detailed entries in this log.
- **Why:** Numbered errors are complete but can be difficult to scan when testing the application manually.
- **Resolution:** Added this plain-language index of every observed user-visible issue and its correction. The detailed cause, verification, and prevention remain in the referenced entries.
- **Verification:** Each item below maps to an existing detailed learning/error entry; no unobserved problems were invented.
- **Takeaway:** Use this index for fast troubleshooting and the numbered entries for implementation detail.

### Resolved behavior checklist

| What was observed | What was corrected | Detailed entries |
| --- | --- | --- |
| Local Vite showed a missing `dist.js` module | Rebuilt locked dependencies with `npm ci`; Docker frontend uses `npm ci` too. | E-015, Vite-install change |
| A stale Vite process continued to show the old error overlay | Documented safe restart/hard-refresh procedure; verified clean rendering after restart. | E-016, E-017 |
| A new upload could retain an older recommendation/result | New upload immediately clears job/downloads; stale async recommendations are identity-ignored. | E-018 |
| Choosing the same local file again did not always trigger analysis | Native file input resets after selection. | E-033 |
| The second upload briefly displayed the first upload's settings | New upload resets to defaults, visibly analyzes, and blocks conversion until its own recommendation is ready. | E-033 |
| A sparse multi-colour logo on white was selected as Line art | The recommender now counts meaningful artwork colour families rather than background-dominated diversity. | multi-colour-logo change |
| Yellow fill plus brown outline was selected as Line art | The recommender now counts distinct prominent palette colours even inside one hue family. | E-034 |
| Changing settings left an earlier SVG visible/downloadable | Settings changes clear previous preview/downloads and require a new vectorization. | multi-colour-logo change |
| Retry after a polling/network failure did nothing | Retry now resumes polling the original job instead of attempting a blocked duplicate submission. | E-025 |
| Vector pane showed a raster preview while Download SVG was empty | The pane now uses the actual SVG URL and zero-path jobs fail without an SVG download. | E-028 |
| Spreadsheet/document screenshot could appear completed as an empty SVG | No-path jobs now fail clearly; README states documents and dense text are unsupported. | E-028, document-limitation change |
| Users lacked reliable inputs to test normal and failure flows | Added attributable sample images and a complete expected-results test matrix. | comprehensive-sample-pack change |
| Docker/host verification had environment-specific blockers | Documented Docker absence, Python/cache constraints, browser file-input limitations, port restrictions, and approved workarounds. | E-001 to E-004, E-019, E-024, E-026, E-029 to E-032 |
| Redis exits with code 0 after `docker compose down` | This is a normal clean shutdown, not an application failure; container logs should be checked only if it exits while Compose remains running. | Observation O-001 below |

## 2026-07-18 — Observation O-001 — Redis exit code 0 after Compose shutdown

- **Workstream:** Lead / Docker troubleshooting
- **Context:** User observed the Redis service report `exited with code 0` after stopping the Compose stack.
- **Cause:** Docker sends a normal termination signal during `docker compose down`; Redis exits cleanly with status 0.
- **Resolution:** No code change is needed. Treat it as an error only when Redis exits while `docker compose up` is expected to keep services running.
- **Verification:** Exit status 0 conventionally indicates successful process termination, unlike a nonzero crash status.
- **Prevention:** Check `docker compose ps` and service logs while the stack is running before diagnosing a clean teardown as a failure.

## 2026-07-18 — Error E-035 — external GitHub repository verification unavailable

- **Workstream:** Lead / publication verification
- **Context:** Read-only verification attempt after the user pushed the repository to GitHub.
- **Cause:** The external page fetch returned a cache miss and search did not yet surface the repository; this can occur for a private repository or a newly indexed public repository.
- **Resolution:** Did not alter repository visibility, remote settings, or Git history. Accepted the user's confirmed push and recorded the external-verification limitation.
- **Verification:** The GitHub URL was supplied by the user; no public-index claim is made without a successful fetch.
- **Prevention:** Verify private/new repositories from the authenticated GitHub session or local `git remote -v` rather than relying only on external indexing.

## 2026-07-18 — Change — persistent project and agent guidance

- **Workstream:** Lead / multi-agent integration
- **Files:** `PROJECT.md`, `AGENTS.md`
- **Why:** The reliability roadmap now spans API, CV, ML, UI, tests, and documentation. Agents need a single source of truth to prevent unsupported scope, inconsistent product claims, or unsafe logging.
- **Resolution:** Added a concise project contract covering supported inputs, architecture, segmentation precedence, model policy, quality-report semantics, validation, and agent handoff rules.
- **Verification:** The guides were created before the current specialist workstreams began and explicitly require `LEARNINGS.md` reconciliation.
- **Prevention:** Future agent work must read these documents before implementation and stay within its assigned file boundary.

## 2026-07-18 — Change — frontend quality report and idempotent submission

- **Workstream:** Lead / frontend reliability
- **Files:** `frontend/src/{api.ts,api.test.ts,App.tsx,components.tsx,styles.css}`
- **Why:** A completed SVG needs understandable quality evidence, and a retried upload must not accidentally create duplicate jobs.
- **Resolution:** Added typed quality-report mapping and an accessible conversion-quality panel. The browser now supplies one `Idempotency-Key` per pending submission, reuses it after a transient POST failure, and creates a fresh key only after the API has confirmed a job or the source/settings change.
- **Verification:** `npm run lint`, `npm run test` (15 tests), and `npm run build` passed.
- **Prevention:** Keep frontend and API quality-field names aligned through typed mapping tests, and preserve a pending idempotency key until a POST receives a confirmed job response.

## 2026-07-18 — Change — quality-report documentation

- **Workstream:** Lead / product documentation
- **Files:** `README.md`, `docs/api.md`, `docs/quality.md`
- **Why:** A heuristic quality score can be misleading unless its limits, warnings, and model-fallback behavior are clearly documented.
- **Resolution:** Documented the quality panel, field meanings, correct interpretation of `good`/`review`/`unsupported`, empty-SVG prevention, model fallback provenance, and idempotent API usage.
- **Verification:** Documentation links resolve within the repository and match the typed frontend contract.
- **Prevention:** Treat quality metrics as explainable indicators, never as unqualified accuracy or fidelity claims.

## 2026-07-18 — Error E-036 — delegated frontend workstream sandbox rejection

- **Workstream:** Frontend specialist delegation
- **Context:** The assigned agent attempted its required read-only inspection of project guidance and frontend files.
- **Cause:** The sandbox rejected the agent session due to a coordination-session risk flag before it could inspect or edit files.
- **Resolution:** No files were changed by that agent. The lead implemented the frontend task within the shared workspace and validated it locally.
- **Verification:** The agent reported the blocked read-only command; frontend lint, tests, and build passed after the lead implementation.
- **Prevention:** Keep delegated task scope narrow and reassign blocked work to the lead rather than attempting a prohibited sandbox workaround.

## 2026-07-18 — Error E-037 — local Python test environment absent

- **Workstream:** Lead / backend validation
- **Context:** Attempt to run `backend/tests` through the documented `.venv/bin/python` environment.
- **Cause:** The repository has no local `.venv` interpreter at this time.
- **Resolution:** Did not install dependencies implicitly. Frontend checks were run; backend runtime tests remain for Docker Compose or an explicitly bootstrapped Python environment.
- **Verification:** The command safely reported that the project virtual environment is unavailable.
- **Prevention:** Run the documented environment bootstrap before backend test execution, or use the Docker Compose/CI test environment.

## 2026-07-18 — Change — explainable quality diagnostics and input-fit warnings

- **Workstream:** CV quality specialist
- **Files:** `backend/app/pipeline/{quality.py,colors.py,types.py,vectorizer.py,vectorize.py,__init__.py}`, `backend/tests/test_pipeline.py`
- **Why:** A visually plausible preview alone cannot tell a user whether the generated SVG is complete, over-complex, or based on input outside the supported artwork scope.
- **Resolution:** Added deterministic JSON-safe quality reports with score, level, warnings, foreground coverage, editable paths, retained colours, removed noise components, preview-similarity indicator, SVG complexity, input assessment, and model provenance. Added conservative photo/document/spreadsheet/screenshot detection that warns rather than silently claiming success; zero-path output still fails safely.
- **Verification:** The integrated backend suite passed 25 tests; focused quality tests cover normal artwork, low similarity, dense complexity, photo-like, and document-like inputs.
- **Prevention:** Treat all quality values as explainable output-health indicators, never as guaranteed artistic fidelity or model accuracy.

## 2026-07-18 — Change — idempotent API and retry-safe worker ownership

- **Workstream:** API reliability specialist
- **Files:** `backend/app/{models.py,db.py,api/routes.py,schemas.py,tasks.py}`, `backend/tests/test_api_contracts.py`
- **Why:** Retrying an upload or redelivering a queue message must not create duplicate jobs or rewrite completed artifacts.
- **Resolution:** Added a unique idempotency-key index, backward-compatible additive database migration, source-digest/options comparison, safe `409` conflict responses, duplicate staging-artifact cleanup, atomic queued-to-processing worker claims, and persisted nullable diagnostics.
- **Verification:** API-contract tests cover same-request replay, conflicting reuse, legacy schema migration, and ignoring processing/completed/failed worker tasks; all backend tests pass.
- **Prevention:** Let the database uniqueness constraint be the final authority for concurrent submissions, and only allow workers to claim jobs in `queued` state.

## 2026-07-18 — Change — structured pretrained-model provenance

- **Workstream:** Lead / ML lifecycle
- **Files:** `backend/app/pipeline/vectorize.py`, `backend/app/schemas.py`, `backend/tests/test_ml_segmentation.py`, `frontend/src/{api.ts,api.test.ts,components.tsx}`, `docs/{model.md,quality.md}`
- **Why:** A single display string cannot adequately explain which foreground masker ran or why the optional pretrained model fell back.
- **Resolution:** Persisted safe model metadata for the existing TorchVision DeepLabV3-MobileNetV3-Large checkpoint: request flag, provider, architecture, checkpoint name/digest, and fallback reason. The UI maps and displays fallback information; no inference-time download or additional model was added.
- **Verification:** Added model-provenance unit coverage and frontend API mapping coverage; backend and frontend suites pass.
- **Prevention:** Store only reviewed provenance and compact fallback reasons—never checkpoint paths or raw loader exceptions.

## 2026-07-18 — Change — backend API test dependency

- **Workstream:** Lead / test infrastructure
- **Files:** `backend/requirements.txt`
- **Why:** FastAPI's `TestClient` requires `httpx`, but the backend test requirements did not declare it.
- **Resolution:** Pinned `httpx==0.28.1` alongside the backend requirements.
- **Verification:** The complete backend suite now collects and passes in a clean Python 3.12 virtual environment.
- **Prevention:** Add explicit test-only runtime dependencies to the same reproducible requirements file used by CI.

## 2026-07-18 — Change — quality and idempotency user documentation

- **Workstream:** Lead / documentation
- **Files:** `README.md`, `docs/api.md`, `docs/quality.md`, `docs/model.md`
- **Why:** New diagnostics, fallback provenance, and replay behavior require correct interpretation by users and API consumers.
- **Resolution:** Documented quality fields and limitations, `good`/`review`/`unsupported` states, idempotency semantics, model provenance, and fine-tuning as a future user-dataset capability rather than a from-scratch training claim.
- **Verification:** Internal documentation links resolve and match the API/TypeScript contracts.
- **Prevention:** Update API and model documentation whenever response fields or lifecycle guarantees change.

## 2026-07-18 — Error E-038 — quality-specialist temporary test invocation had no application import path

- **Workstream:** CV quality specialist
- **Context:** Focused backend test attempts in temporary environments.
- **Cause:** The temporary Python invocation did not have `backend/` on `PYTHONPATH`; an earlier shell command also treated `celery[redis]` as an unquoted glob.
- **Resolution:** No production change was made for the temporary command. The lead later ran the documented test command using `PYTHONPATH=backend` in a Python 3.12 project environment.
- **Verification:** Full backend test suite passes after integration.
- **Prevention:** Quote package extras in shell commands and always run backend tests with the repository's backend import path.

## 2026-07-18 — Error E-039 — missing HTTP client blocked API-contract test collection

- **Workstream:** Lead / backend validation
- **Context:** First full `pytest` run after creating the local Python 3.12 environment.
- **Cause:** `fastapi.testclient` requires `httpx`, which was not present in the declared backend requirements.
- **Resolution:** Added pinned `httpx==0.28.1` and installed it into the ignored local test environment.
- **Verification:** Rerun collected all tests and passed 25 tests.
- **Prevention:** Keep FastAPI test-client dependencies explicit in `backend/requirements.txt`.

## 2026-07-18 — Error E-040 — success-fixture artwork was correctly filtered as noise

- **Workstream:** Lead / backend validation
- **Context:** Two worker-facade tests expected a completed SVG from a one-pixel mark or a blank white image.
- **Cause:** Production component filtering correctly removes tiny isolated noise and blank inputs correctly produce no SVG paths.
- **Resolution:** Replaced the test fixtures with clear filled black marks while retaining separate blank-image failure coverage.
- **Verification:** Both worker-facade tests pass as part of the 25-test backend suite.
- **Prevention:** Test successful vectorization with artwork larger than the configured minimum component area; test empty/noise inputs as failures.

## 2026-07-18 — Error E-041 — API-contract test lint violation

- **Workstream:** Lead / backend validation
- **Context:** Ruff check after the backend test suite passed.
- **Cause:** `test_api_contracts.py` imported SQLAlchemy's `Session` type without using it.
- **Resolution:** Removed the unused import and ran Ruff formatting/checks again.
- **Verification:** Ruff check and format check pass for all backend app and test files.
- **Prevention:** Run static analysis after adding test infrastructure, not only after application-code changes.

## 2026-07-18 — Error E-042 — validation command used the frontend directory for backend paths

- **Workstream:** Lead / integration validation
- **Context:** A combined frontend/backend check executed `compileall backend/app backend/tests` while its working directory was `frontend/`.
- **Cause:** Relative backend paths were resolved under `frontend/`.
- **Resolution:** Reran bytecode compilation and whitespace checks from the repository root with an isolated temporary bytecode cache.
- **Verification:** Backend sources/tests compile successfully from the correct directory.
- **Prevention:** Keep frontend and backend verification commands in separate working-directory steps.

## 2026-07-18 — Error E-043 — sandbox restrictions affected local test servers and browser file injection

- **Workstream:** Lead / rendered UI validation
- **Context:** Starting Vite/Uvicorn in the restricted sandbox and uploading a non-sensitive sample fixture through the browser-control file chooser.
- **Cause:** The sandbox denied local port binding until approved elevation; the browser-control surface later rejected `setFiles` with a permission restriction even though the file was a repository sample. An initial screenshot call also used an unsupported Playwright screenshot method instead of the tab-level capture method.
- **Resolution:** Started Vite with approved local-server permission, verified desktop and 390px mobile workbench shells, used the supported tab screenshot method, and relied on frontend/API contract tests for upload/result behavior. No user upload was transmitted.
- **Verification:** Browser checks found the correct title/workbench content, no framework overlay, and no console warnings/errors; frontend lint, 15 tests, and production build passed.
- **Prevention:** Use approved local-server execution for rendered checks, the documented file-chooser flow only where browser permissions allow it, and tab-level screenshots in this browser surface.

## 2026-07-18 — Error E-044 — local Python bootstrap needed the project package tool and writable cache access

- **Workstream:** Lead / backend validation
- **Context:** Creating and populating the ignored Python 3.12 test environment.
- **Cause:** The fresh environment intentionally had no `pip`, and the sandbox could not write the package tool's normal user cache.
- **Resolution:** Used the installed `uv` package tool and approved cache/network access to create `.venv` and install the declared pinned dependencies. The environment remains ignored by Git.
- **Verification:** Imports succeeded and the backend suite passed 25 tests.
- **Prevention:** Use `uv pip` or bootstrap `pip` explicitly for fresh lightweight environments; request only the scoped permission needed for dependency installation.

## 2026-07-18 — Error E-045 — local API health could not be inspected in the current environment

- **Workstream:** Lead / user-reported 500 diagnosis
- **Context:** Checked `http://localhost:8000/healthz` and `/readyz` while investigating the UI’s repeated `Request failed (500)` message.
- **Cause:** No API process was reachable in this environment, and the Docker CLI was unavailable, so container logs could not be collected here.
- **Resolution:** Did not invent a backend root cause. The user should run the documented Compose log/health commands to distinguish API, database, Redis, or worker failure.
- **Verification:** Source-level checks and 25 backend tests pass; the failure remains environment/runtime-specific until the user supplies the API/worker log line.
- **Prevention:** Keep `/healthz`, `/readyz`, and `docker compose logs api worker postgres redis --tail=100` as the first production troubleshooting checks.

## E-047 — 2026-07-18 — README project guide
- Workstream: documentation
- Context/files: `README.md`; the previous guide covered startup but did not explain the complete processing pipeline, supported users/inputs, API lifecycle, quality metadata, troubleshooting, or current scope in one place.
- Cause: documentation had grown across separate architecture, API, model, quality, and sample files without a single end-to-end entry point.
- Resolution: rewrote the README to document the product purpose, architecture, raster-to-SVG stages, Docker and local development, UI behavior, segmentation, pretrained model policy, REST polling/idempotency, quality diagnostics, tests, troubleshooting, limitations, roadmap, and licensing.
- Verification: confirmed all referenced documentation paths exist and reviewed commands against the current Compose services and scripts.
- Prevention: update README and the relevant focused document together whenever a user-visible workflow, API contract, supported input, or deployment command changes.
