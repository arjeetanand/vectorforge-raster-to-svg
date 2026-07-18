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
