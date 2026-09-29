# TODO

## Phase 0 — Audit and shared context

- [x] Inventory the legacy front end, proxy server, documentation, requirements, and ignore rules.
- [x] Describe current recommendation/search/provider/profile/cache behaviour and coupling.
- [x] Create shared context files: `AGENTS.md`, `PROJECT_PLAN.md`, `ARCHITECTURE.md`,
  `DECISIONS.md`, and `TODO.md`.
- [x] Preserve the legacy source files without a large migration.
- [ ] Verify the legacy runtime with `python server.py --help` before closing Phase 0.

## Phase 1 — Foundation (not started)

- [ ] Agree exact package versions and supported local runtime.
- [ ] Scaffold `apps/web`, `services/api`, and `infra` without deleting legacy files.
- [ ] Add Compose, config templates, PostgreSQL/pgvector, Redis, health checks, and migration tooling.
- [ ] Add a fixture-backed vertical recommendation API and tests.

## Phase 2 — Providers (not started)

- [ ] Define canonical song/provider interfaces and provider capability metadata.
- [ ] Verify and retain 2–3 stable providers; mark unverified sources optional.
- [ ] Extract provider mappings with fixtures, timeouts, error isolation, and health telemetry.

## Phase 3 — Recommendation and profile (not started)

- [ ] Extract recall, normalization, ranking, diversity, and explanation domain services.
- [ ] Persist anonymous user preference and feedback in PostgreSQL.
- [ ] Add song/preference embeddings and offline evaluator fixtures.

## Phase 4 — Client (not started)

- [ ] Build Next.js recommendation, feedback, preference, and explanation UI.
- [ ] Add browser-facing tests and accessible loading/error states.

## Phase 5 — Agent/RAG/MCP (not started)

- [ ] Add one bounded Agent with SSE, current-session memory, and long-term preference summary.
- [ ] Add music knowledge RAG and a minimal read-only MCP tool surface.
- [ ] Add Agent tool-selection and trace tests.

## Phase 6 — Quality and release (not started)

- [ ] Add observability, CI, Docker clean-start test, bilingual README, and evaluation report.
