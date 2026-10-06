# TODO

## Password policy / 密码长度调整

- [x] Accept passwords longer than six characters across registration, login, password changes
  and administrator reset; retain case-insensitive username uniqueness and the 128-character cap.

Current checked-out item: none.

Acceptance 2026-10-06: focused failing tests preceded the policy change; 37 API auth/access tests
and all 72 web tests pass, as do Ruff/compile, ESLint/typecheck/build and legacy smoke. Real Edge
checks confirm six-character rejection in UI/API, seven-character registration/change/login,
case-insensitive duplicate registration returning 409, bilingual copy and 390px layout.
The browser harness now accepts the specified return to the original page after login.
Local API/web images are rebuilt and updated together; all four Compose services are healthy.

## Account login / 强制登录与账号个性化

- [x] 1. Record approved specification and identity ADR (documentation checkpoint).
- [x] 2. Accounts, revocable sessions, auth API, CSRF, Redis limits and local reset CLI.
- [x] 3. Business authentication, account feedback/profile and isolated Agent ownership.
- [x] 4. Same-origin transport, bilingual login/register/account UI and lifecycle guards.
- [x] 5. PostgreSQL/Compose/browser verification, deployment/CI and bilingual current-state docs.

Account-login items: all five completed sequentially.

Acceptance 2026-10-06: 276 API tests and 67 web tests pass; Ruff/compile, ESLint/types/build,
pip check, unchanged deterministic evaluation and legacy smoke pass. Failing regressions preceded
all behavior fixes. Real PostgreSQL checks cover restoration of the existing 0006 backup into a
separate project, 0006→0008 upgrade/rollback/upgrade, empty-database base→head, schema drift,
intentional vector(8) drift rejection, concurrent feedback and exact account-vector values.
Anonymous archives match the restored pre-upgrade copy. Original .env and four legacy files unchanged.

Real Compose Cookie/CSRF, two-device preferences, account/login-session isolation, JSON/SSE,
429/Retry-After and Redis-outage 503 checks pass. Interactive hidden-input admin reset revokes two
real sessions. Real Edge desktop and 390px cover registration→recommendation→feedback→logout→
another-device login, keyboard/remember login, Chinese UI, password-change revocation, cross-tab
clearing, isolated assistant history, Unicode passwords and automatic expiry; no page errors or
overflow. Local frontend/API are upgraded together at localhost:3000, all four services healthy.
Pre/post-upgrade database dumps and browser evidence stay outside Git in the local backup folder.

source-map-js is patched to 1.2.2; production npm audit is clean. Full audit retains five linked
high findings from the single unpatched development-only braces advisory. ADR-030 and tested audit
policy permit only that precise dev chain; other high/critical findings and audit failures block CI.
One existing Starlette/httpx test-client deprecation warning remains. Remote CI has not been run
for this local branch; no public HTTPS deployment or provider/model quality claim is made.

Follow-up (not started): remove the ADR-030 exception when upstream releases a braces patch.
Frontend checkpoint: 60 tests, lint, types and production build pass; login/register/protected
page HTTP smoke passes. Same-origin cookie/SSE proxy, bilingual forms, request cancellation and
cross-tab identity guards are implemented. Real container/browser verification follows in item 5.
Business checkpoint: all 269 API tests pass, including real-cookie anonymous route rejection,
cross-account/session isolation, portable preferences, concurrent feedback and credential-safe logs.
Ruff/compile/evaluation pass; migrations 0007/0008 preserve anonymous archives. Web integration next.
Authentication checkpoint: eight failing regressions preceded implementation; all 250 API tests,
Ruff and compile pass. Migration 0007 is additive; business identity switch is the next item.
Scope: target API/web, migrations, tests, deployment and docs. Acceptance: `docs/specs/account-login.md`.
Execute sequentially with focused tests and one commit per item. Preserve legacy sources, ranking,
anonymous archives, credentials and unrelated changes. No account claiming or assistant history sync.

## Model artist confirmation / 模型歌手确认与自行提供

- [x] Require confirmation of model-derived artists in initial discovery and the rejected-candidate
  branch; let users supply a different artist and verify a real recording before recommending.

Scope: discovery API/schema, homepage confirmation/recovery, focused regressions and bilingual docs.
Verification: failing regressions first; API pytest/Ruff/compile/evaluation, web tests/lint/types/build,
narrow browser confirmation/correction and cancellation checks, legacy smoke. Update running services
after acceptance; preserve catalog expansion, confirmed memory and deterministic ranking.

Acceptance 2026-10-06: first failing API/UI regressions demonstrated initial automatic recall and
the missing confirmation action. All 242 API / 49 web tests pass; Ruff/compile/evaluation,
ESLint/typecheck/build and legacy help/HTTP 200 pass. Tests cover initial and fallback model
confirmation, supplied artist verification, no recall or durable memory before confirmation,
same-provider revalidation, corrected-artist-only memory, input invalidation, failure retry,
duplicate prevention, cancellation and ignored late manual responses.
Actual configured-model/catalog checks in isolated and updated Compose Edge sessions at 390px
resolved 晴天 / 周杰伦 and 宠爱 / TFBOYS with zero recommendations before confirmation and five
after confirmation. Initial/manual and fallback/manual correction, source-link rejection/recovery,
query snapshots and language switching passed; no horizontal overflow or page errors. The live
manual flow supplied the real artist again; distinct wrong-to-correct artist behavior is covered
by simulated-provider regressions. Only the fallback's initial ambiguous choices were injected;
model, verification and recommendation calls were real. Reviewed actual pending/manual screenshots.
API/web were rebuilt and all four existing Compose services are healthy; database remains at 0006.
No migration, credential, ranking, legacy-source or stash changes. Temporary verification servers
were stopped after acceptance; no secret or generated output is included in the focused commit.

## Automatic recording resolution / 自动扩展检索与成功记录记忆

- [x] Implement one shared, bounded recording resolver for discovery, rejected candidates and
  manual platform/link recovery; revalidate confirmation references and persist only confirmed
  platform recordings. Add a migration, bilingual UI/reports, regressions and documentation.

Scope: API providers/services/repository/schema/migration, web recovery and confirmation, docs.
Verification: full API pytest/Ruff/compile/evaluation; web tests/lint/types/build; live platform,
model and narrow-browser recovery checks; legacy smoke. Update existing services after acceptance.
Feasibility 2026-10-06: MusicBrainz recording search responds successfully; Kugou connection fails
and Kuwo returns an illegal-request rejection. Keep those two explicitly unavailable until a
stable adapter can be verified. Brave remains optional and requires its own server-side key.

Acceptance 2026-10-06: 240 API and 44 web tests pass, including expansion to another catalog,
manual-link recovery, confirmation-only memory, stale records, homonyms, expired references,
request/deadline caps, punctuation variants, real-ID adapter validation and four outbound slots.
Ruff/compile/evaluation, ESLint/typecheck/build, PostgreSQL migration SQL in both directions and
legacy help/HTTP 200 pass. Live provider detail probes verified Apple TW, NetEase, QQ IDs/mids and
MusicBrainz metadata; Kugou/Kuwo stay unavailable, Brave's live key-dependent branch is unverified.
An isolated Edge browser exercised actual configured-model rejection and manual link recovery:
before confirmation no recommendations, after confirmation five recommendations; subsequent 宠爱
query used remembered QQ detail first. 晴天 and 宠爱 both returned five recommendations. The 390px
layout has no horizontal overflow or page errors; actual screenshots were reviewed. Initial empty
and ambiguous responses were injected only to reach recovery branches; subsequent model/catalog/
confirmation calls were real. Standalone source/model availability can still vary.
Existing Compose services were restarted after Docker Desktop was found stopped; the existing
database volume was retained and a pre-migration dump saved outside the repository. API/web were
rebuilt, PostgreSQL reached migration 0006 and actual confirmation/upsert/revalidation succeeded.
Both temporary verification servers were stopped. Canonical recommendation scoring, legacy source,
credentials and the existing stash remain unchanged. Documentation records current capabilities;
the success memory is not model training or authorship certification.

## Domestic catalog coverage / Apple 未命中时的国内曲库补充

- [x] Enable the existing QQ catalog adapter by default alongside iTunes and NetEase; verify
  宠爱 through real QQ recordings, and retain the same sources for recommendation and refresh.
  Preserve explicit opt-out, offline mode, canonical validation and existing query/deadline caps.

Scope: provider configuration/Compose, focused API regressions, evidence links on matched model
suggestions, bilingual docs. Regressions first; API pytest/Ruff/compile/evaluation, web tests/lint/
types/build, live 宠爱 browser and rejection/confirmation checks, legacy smoke. One active task;
no model configuration, credentials, migration or deterministic scoring change.

Acceptance 2026-10-06: failing API and UI regressions reproduced QQ-disabled misses and missing
evidence links. All 218 API / 41 web tests pass, along with Ruff/compile, ESLint/typecheck/build,
unchanged evaluation and legacy help/HTTP 200. Rebuilt existing Compose services are healthy;
only the local QQ boolean changed in `.env`, with other settings preserved and the file unstaged.
An isolated real Edge browser resolved 宠爱 / TFBOYS to QQ track 102210521 and returned five related
tracks from Apple, QQ and NetEase. A separate harness injected only ambiguous initial choices;
the following real configured-model rejection lookup and actual confirmed discovery matched QQ,
showed its evidence link, and returned five recommendations. 390px layout and browser errors were
checked; screenshots inspected. Review confirmed three-source/three-operation caps, canonical
validation, explicit QQ opt-out, offline mode and deterministic ranking remain intact. Source
availability/authorship accuracy is not guaranteed; no dependency, migration, secret or generated
output is staged, and the existing stash remains intact.

## Online recording verification / 未匹配模型建议的联网核实与推荐

- [x] Verify model suggestions missing from default sources against additional official Apple
  storefronts, expose the evidence link, and carry the verified storefront through confirmation
  and recommendation refresh. Keep ranking deterministic and bound all lookups.

Scope: iTunes adapter/registry, original identification and discovery schemas/routes, homepage
confirmation/client/tests and current-state docs. Verification: regressions first; API pytest/
Ruff/compile/evaluation; web tests/lint/typecheck/build; live model/catalog/browser confirmation
and responsive checks; legacy help/HTTP. One active task, no migration or credential change.

Acceptance 2026-10-06: failing regressions preceded regional verification and storefront propagation.
All 216 API and 40 web tests pass; Ruff/compile, ESLint/typecheck/build, unchanged evaluation and
legacy help/isolated HTTP 200 pass. Existing Docker API/web services were rebuilt. An isolated real
Edge browser verified evidence links, confirmation before recommendation, cancellation/error retry
and 390px layout; screenshots were inspected. With the configured live model, 晴天 / 周杰伦 matched
Apple TW track 535824738; confirmation returned five real recommendations. Source attribution was
reviewed and corrected so non-Apple matches never claim an Apple storefront. Query count remains
three; all-source misses remain unverified, not forced recommendations. No migration, dependency,
credential, generated output or ranking change; the existing stash is preserved. This is evidence
for the observed catalog gap, not a general accuracy or worldwide coverage guarantee.

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
