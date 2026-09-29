# TODO

## Phase 0 — Audit and shared context

- [x] Inventory the legacy front end, proxy server, documentation, requirements, and ignore rules.
- [x] Describe current recommendation/search/provider/profile/cache behaviour and coupling.
- [x] Create shared context files: `AGENTS.md`, `PROJECT_PLAN.md`, `ARCHITECTURE.md`,
  `DECISIONS.md`, and `TODO.md`.
- [x] Preserve the legacy source files without a large migration.
- [x] Verify the legacy runtime with `python server.py --help` and an isolated HTTP 200 homepage check.

## Phase 1 — Foundation (complete; live Docker run unexecuted on this host)

- [x] Agree exact package versions and supported local runtime (Python 3.12, Node 24, API pins in `pyproject.toml`; web pins in its scaffold).
- [x] Add an isolated FastAPI health/device-contract foundation with focused tests.
- [x] Scaffold `apps/web`, `services/api`, and `infra` without deleting legacy files.
- [x] Add Compose, config templates, PostgreSQL/pgvector, Redis, health checks, and migration tooling.
- [x] Add API container, Compose data-service topology, `.env.example`, and pgvector extension initialization.
- [x] Check Compose topology statically; `docker compose up --build` remains unexecuted because Docker is unavailable on this host.
- [x] Add a fixture-backed vertical recommendation API, minimal web consumer, and tests.

## Phase 2 — Providers (complete)

- [x] Define canonical music/provider interfaces and capability metadata.
- [x] Migrate iTunes and NetEase as default adapters; keep QQ opt-in and label undocumented
  public web endpoints unverified.
- [x] Extract provider mappings with offline fixtures, bounded requests, source error isolation,
  last-operation health, registry, and three canonical search/discovery APIs.
- [x] Run a separate manual iTunes/NetEase smoke search on 2026-09-29; both returned one track.

## Phase 3 — Recommendation and profile (not started)

- [x] Extract recall, normalization, ranking, diversity, and explanation domain services.
- [x] Persist anonymous user preference and feedback in PostgreSQL.
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
