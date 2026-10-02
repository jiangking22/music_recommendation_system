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

## Phase 3 — Recommendation and profile (implemented; live PostgreSQL unverified on this host)

- [x] Extract recall, normalization, ranking, diversity, and explanation domain services.
- [x] Persist anonymous user preference and feedback in PostgreSQL.
- [x] Add song/preference embeddings and offline evaluator fixtures.

## Phase 4 — Client (complete; browser desktop flow verified locally)

- [x] Build Next.js recommendation, feedback, preference, and explanation UI.
- [x] Add browser-facing tests and accessible loading/error states.

## Phase 5 — Agent/RAG/MCP (complete; offline and browser verified)

- [x] Add one bounded Agent with SSE, current-session memory, and long-term preference summary.
- [x] Add music knowledge RAG and a minimal read-only MCP tool surface.
- [x] Add Agent tool-selection and trace tests.

Acceptance 2026-09-30: 63 API tests and 12 frontend tests pass; ruff, Python compile,
web lint/typecheck/build pass. Offline PostgreSQL upgrade/downgrade SQL includes seeded knowledge
and pgvector. Browser recommendation/artist Q&A, SSE/tool status, and 320/768/1024/1440px layouts
verified. Legacy help and isolated HTTP homepage 200 verified; legacy files and ranking unchanged.
Live Docker/PostgreSQL and real LLM execution remained unverified at the Phase 5 acceptance.

## Phase 6 — Quality and release (complete; local Docker unexecuted)

- [x] Add observability, CI, Docker clean-start test, bilingual README, and evaluation report.


Acceptance 2026-09-30: 72 API tests and 12 web tests; Ruff/compile, ESLint/typecheck/build,
npm audit (zero findings), editable install/wheel fixture checks, complete offline PostgreSQL
upgrade/downgrade SQL, fixed evaluation and legacy help/HTTP 200 pass. A production Next server
returned HTTP 200 for homepage and /agent. Standard SDK stdio initialize/list/call and both
read-only music tools were verified using a real subprocess. Correlation/privacy tests cover
HTTP, Provider, SSE/thread/tool and optional model usage events; high-value body/error/CORS fixes
are verified. Bilingual README, demo, deployment, observability and screenshot placeholder docs
reflect implemented capabilities and limitations. GitHub Actions contains API/web/clean-start gates.

Docker CLI is absent on the author's Windows host: **local clean start not executed / 未实机执行**.
Static Compose/Dockerfile/environment and migration checks cannot prove live container success;
see the actual CI run for remote evidence. Real-model compatibility/quality remains unverified.
No ranking algorithm or legacy source was changed. Final phase delivery stays on
codex/phase1-foundation-review; push without merging main, then stop.

## Final public presentation / 公开展示收尾

- [x] Prepare main-facing README and review deployment/demo branch guidance; capture real offline
  browser screenshots if available, verify existing checks, commit and push the review branch only.

Acceptance 2026-10-02: main CI badge and clone instructions updated; deployment wording corrected,
DEMO reviewed without changes. Three real browser captures are included in README Preview, using
the existing production web build, offline FastAPI catalog/local Agent and a temporary SQLite test
database. No application logic changed. API 72 tests, web 12 tests, Ruff/compile, web lint/typecheck/
build, fixed evaluation and legacy HTTP smoke passed; browser console had no warnings/errors.
Pytest emitted one existing Starlette/httpx deprecation warning. Docker/PostgreSQL, live providers
and real LLMs remain outside this local verification; capture details are in docs/screenshots/README.md.
