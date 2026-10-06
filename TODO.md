# TODO

## Original candidate rejection / 原唱候选全部否定后补充识别

- [x] Add “以上均没有 / None of the above” to homepage artist choices. Use the configured
  model once to identify another artist, validate against canonical catalog recordings, and
  wait for user confirmation before recommending. Show unmatched suggestions as unverified.

Scope: discovery API/service/schemas, shared model prompt, homepage/client/i18n/tests and docs.
Verification: failing regressions first; API pytest/Ruff/compile/evaluation; web tests/lint/
typecheck/build; browser confirmation/failure/narrow-layout checks; configured-model smoke;
legacy help/HTTP. One active task. Preserve credentials and stash; no database migration.

Acceptance 2026-10-06: failing API and UI regressions preceded implementation. All 206 API and
38 web tests pass; API Ruff/compile, web ESLint/typecheck/production build, unchanged offline
evaluation and legacy help/isolated HTTP 200 pass. The existing Docker API/web stack was rebuilt
and checked. An isolated real Edge browser with mocked responses verified loading, confirmation
before ranking, unverified display, distinct errors/manual retry, cancelled stale responses and
390px layout without horizontal overflow; screenshots were visually inspected. A separate live
browser using the configured model identified 晴天 as Jay Chou and correctly showed an unverified
suggestion because current providers did not return that recording. Live identification of
Shape of You matched Ed Sheeran; explicit API confirmation returned three related tracks.
These checks do not establish general original-artist accuracy or a new clean database startup.
Code review found no blocking correctness/security/architecture issues. No migration, credential,
dependency or generated output is committed; the pre-existing stash remains intact.

## Assistant reliability / 助手连接、主题推荐与失败重试

- [x] Fix verified TLS trust for the shared model adapter; keep basic recommendations available
  during model HTTP failures, distinguish listening themes from song titles, and avoid duplicate
  user messages on failed retries. Explicitly label local fallback and preserve deterministic ranking.

Scope: model adapter, Agent/core tools, explicit theme discovery, chat UI/tests and current-state docs.
Verification: regressions first; API pytest/Ruff/compile; web tests/lint/typecheck/build;
configured-model Docker/browser smoke, failure fallback, offline evaluation and legacy help/HTTP.
One active task; preserve existing credentials and stash. No database migration.

Acceptance 2026-10-06: regression tests reproduced TLS, fallback, theme ambiguity and duplicate
retry failures before fixes. All 177 API and 28 web tests pass, together with Ruff/compile,
ESLint/typecheck/production build and unchanged offline evaluation. The rebuilt existing Docker
stack is healthy; actual configured-model browser requests for `emo的歌` and `缓慢的歌` return
five recommendations. An isolated browser fault harness verified a failed send followed by
basic-mode recovery with one user message and a visible fallback notice. Console checks are
clean. Legacy help and isolated HTTP 200 pass; independent review found no blocking issues.
No migration or credential change; the existing stash is preserved. Theme retrieval still uses
available catalog metadata, not measured BPM or independently verified mood labels.

## Homepage recording identity / 首页原唱识别与歌手姓名

- [x] Resolve `匆匆那年` to the verified 王菲/Faye Wong artist, show preferred Chinese/English
  artist names separately from stored identity, and use one optional structured model hint for
  uncertain song seeds. Validate every hint against real provider tracks, label model matches,
  preserve deterministic ranking, and share the existing three-search/45-second limits.

Scope: target API discovery/name projections, homepage displays/tests, and current-state docs.
Verification: failing regressions first; API pytest/Ruff; web tests/lint/typecheck/build;
browser/live configured-model and failure fallback checks; legacy help/HTTP smoke. Keep the stash.

Acceptance 2026-10-06: failing regressions reproduced identity, display, model-transport,
identification and alias-metadata failures before fixes. All 157 API and 26 web tests pass;
Ruff/compile, ESLint/typecheck/production build, unchanged offline evaluation and independent
review pass. Browser checks using the existing Docker stack verified `匆匆那年` → 王菲 with five
different related tracks and preferred names across EN/中文; real configured DeepSeek-flash
identified `Shape of You` → Ed Sheeran and the UI marked the catalog match. Real model connection
failures retained local guidance or artist confirmation. Mocked regressions cover timeout,
hallucinated/malformed results, search/model budgets, manual override and unchanged feedback keys.
Legacy help and isolated HTTP 200 pass. No migration, credential or generated output is staged;
the prior stash remains intact. Existing-stack checks do not claim general model accuracy.

## DeepSeek startup compatibility / DeepSeek 启动兼容

- [x] Preserve the configured DeepSeek integration when rebuilding the merged homepage:
  explicitly disable thinking for the official DeepSeek host, keep JSON output and strict
  validation, and preserve other OpenAI-compatible request behavior. Reuse existing `.env`.

Scope: LLM adapter, focused provider tests, bilingual startup notes, and current-state docs.
Verification: failing transport regression first; API pytest/Ruff; Docker rebuild/readiness and
homepage/assistant HTTP checks using the existing configuration. Keep the other task's stash.

Acceptance 2026-10-05: transport regression first failed on both official DeepSeek URL forms;
all 105 API tests, Ruff/compile and independent review then passed. The configured DeepSeek-flash
returned a validated answer. Local Docker API/web rebuild and readiness passed against existing
PostgreSQL/Redis; homepage/assistant pages returned HTTP 200. Live discovery resolved `我好想你`
to sodagreen with three related songs and model guidance; Agent chat used the same real provider.
This is existing-stack verification, not a new disposable local clean start or general quality
evaluation. Existing development-only braces advisory still blocks full npm audit; the audit gate
is retained. Credentials and the other task's stash remain outside the commit.

## Homepage discovery correction / 首页推荐修复

- [x] Resolve song seeds before related-track recall, prefer verified original recordings over
  covers, exclude repeated seed versions from recommendations, and expose ambiguous matches.
  Add an EN/中文 interface switch while preserving music metadata and English theme headings.
  Reuse the assistant's optional server-side LLM configuration for grounded discovery guidance;
  deterministic recall/ranking remains authoritative. Preserve the legacy demo.

Scope: `apps/web` homepage components/client/tests, `services/api` recommendation domain/service,
additive `/v1/recommendations/discover` API/tests, and current-state documentation. Verification:
API pytest/Ruff, web Vitest/ESLint/typecheck/build, a targeted browser flow, and legacy help/HTTP smoke.

Acceptance 2026-10-05: 101 API tests and 22 web tests pass; Ruff/compile, ESLint/typecheck and
production Next build pass. Offline evaluation remains unchanged. Independent review covered
studio/live merging, version-word song titles, translated-title ambiguity, model failures,
concurrency and cancellation. Real browser checks verified live `我好想你` → sodagreen seed →
five different related tracks, immediate EN/中文 switching, persisted language, feedback/profile,
clean console and 320/768/1024/1440px layouts (including a corrected narrow form overflow).
The two default live providers returned results during this check; future availability is not
guaranteed. Legacy help and isolated HTTP 200 pass. Temporary SQLite was used for browser testing;
real LLM execution and live PostgreSQL were not tested. Model adapter integration is verified
with MockTransport, and no credentials or generated output belong in the focused commit.

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
