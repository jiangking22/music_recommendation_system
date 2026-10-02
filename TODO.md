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

## v1.0.0 release preparation / 正式发布准备

- [x] Audit merged main and its CI, prepare history-backed CHANGELOG and GitHub
  release notes, verify documentation/screenshots/Quick Start and existing quality gates.
  Documentation only; no core changes, license selection, tag or GitHub Release creation.

Acceptance 2026-10-02: main baseline `4c54239` matched origin and passed actual API/web/clean-start
CI run 36971477031. Local API 72 tests, web 12 tests, Ruff/compile, ESLint/typecheck/build, npm audit
(zero findings), pip check, wheel fixtures, full offline PostgreSQL migration SQL, fixed evaluation,
legacy help/HTTP and temporary SQLite/local Agent plus production web HTTP smoke passed.
All 17 Markdown files were checked: local file targets and 15 history links resolved. Three existing
screenshots were visually reviewed; no image or application source changed. README/deployment
now link actual CI evidence; architecture wording reflects Redis readiness and seed/limit input.

At preparation commit `b34eec3`, the [release audit](docs/releases/v1.0.0-readiness.md) held the tag
for missing LICENSE and unresolved version identity. That documentation commit was kept locally
without publishing at that stage. The owner subsequently chose MIT and version 1.0.0 below.

## Final v1.0.0 release / 最终正式发布

- [x] Finalize the owner-approved v1.0.0 release candidate: standard MIT License, project
  versions 1.0.0, existing release documentation and full local release verification.

Acceptance 2026-10-02: API 72 tests, Ruff, compile, offline evaluation, pip check, wheel fixtures
and both migration SQL directions passed. Web 12 tests, lint, typecheck, build and npm audit
(zero findings) passed. Legacy smoke and temporary API/production web HTTP smoke passed,
including OpenAPI application version 1.0.0 and local recommendation/feedback/Agent/RAG/context.
MIT clauses match the standard template. Independent release review found no new blockers;
dependency versions and all core behaviour are unchanged. `b34eec3` is preserved as an ancestor.

Publication procedure: add one release commit, push main normally, and require successful API,
web and clean-start CI on the exact main SHA before creating/pushing an annotated v1.0.0 tag.
Publish a regular GitHub Release from the existing notes. The
[release record](https://github.com/jiangking22/music_recommendation_system/releases/tag/v1.0.0)
contains the final SHA and actual CI run; that record is the publication outcome.

Scope: license/version/release material only; no core changes, dependency upgrades, force push,
rebase, history rewrite or new development phase. Real providers and paid LLMs are not used in checks.
