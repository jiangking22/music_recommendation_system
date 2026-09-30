# Project Plan: Agentic Music Recommendation Platform

## Product goal

Turn the existing local demo into a portfolio-ready platform where software engineering is the
foundation, deterministic recommendation is the core business capability, and one bounded
tool-calling Agent is the differentiator. The plan deliberately avoids microservices,
Kubernetes, complex DDD, account registration, and multi-Agent orchestration.

## Legacy baseline

The legacy application is a browser-side orchestration layer backed by a Python standard-library
proxy. It already demonstrates multi-source recall, artist disambiguation, heuristic ranking,
local preference learning, and feedback metrics. It has no typed API contract, durable database,
automated tests, dependency management, or service boundary.

## Phase 0 — Audit and shared context (complete)

Deliver the repository audit and the shared files named in `TODO.md`. Preserve the legacy runtime.

**Exit criteria:** documentation is internally consistent; `python server.py --help` works; no
target-runtime code or runtime dependency is introduced.

## Phase 1 — Engineering foundation (complete; Docker runtime unverified locally)

Introduce the target directory scaffold, FastAPI service, Next.js TypeScript client, Compose,
PostgreSQL/pgvector, Redis, configuration validation, health checks, migrations, and test/lint
commands. Deliver one small, end-to-end recommendation response using fixture data.

Supported local runtime for this phase: Python 3.12 and Node.js 24. API dependencies are
exactly pinned in `services/api/pyproject.toml`; the web scaffold will commit an npm lockfile.

**Exit criteria:** a clean clone starts with Docker Compose where Docker is available, and one
API integration test passes. On a host without Docker, validate Compose topology and generated
migration SQL statically, and record that live container startup was not executed.

## Phase 2 — Canonical catalog and provider adapters (implemented; offline verified)

Canonical Track, Artist, Album, ProviderSource and capability/result contracts now separate
provider payloads from the API. iTunes and NetEase adapters are enabled by default; QQ is an
opt-in adapter. iTunes Search API is documented by Apple. NetEase and QQ use legacy public web
endpoints without provider stability guarantees and remain explicitly unverified. All three have
offline fixture mapping tests. The provider registry uses bounded sequential calls with per-call
timeouts and returns partial results plus source errors. `/v1/providers`,
`/v1/providers/health`, and `/v1/tracks/search` expose the canonical contract.

Live upstream availability is intentionally not inferred from fixture tests. A separate manual
smoke test on 2026-09-29 returned one track from each default provider; this does not guarantee
future availability. The Phase 1 fixture recommendation path remains unchanged.

**Exit criteria:** a provider outage yields partial results, never an opaque full failure.

## Phase 3 — Recommendation core and durable personalization (implemented; offline verified)

Move multi-source recall, canonical deduplication, profile features, song/user embeddings,
reranking, explanations, feedback persistence, and offline evaluation into testable domain code.

The API now recalls from Provider Registry and a local fallback catalog, merges variants across
providers, scores with a deterministic policy, reranks for diversity, and returns factor-based
explanations. Device feedback and affinity snapshots persist in PostgreSQL tables; the latest
rating per track wins. Local 16-dimensional song/user embeddings use pgvector storage and a
minimal similarity query. The versioned offline evaluator reports all four exit metrics. SQLite
tests and PostgreSQL migration SQL were verified without Docker; live PostgreSQL execution
remains unverified on this host.

**Exit criteria:** relevance, personalization lift, diversity, and coverage are reproducibly
reported from versioned fixtures; feedback changes a later result.

## Phase 4 — Product client (implemented; desktop browser flow verified locally)

The Next.js client now creates and reuses a random browser device ID, consumes the real
recommendation pipeline, and offers seed/limit input, artwork-led results, provenance,
explanations, like/dislike, and a small durable preference profile. A thin read-only
`GET /v1/profile` endpoint exposes the existing snapshot and five recent ratings. Loading,
empty, error, and partial-provider states are explicit. Component/API tests and a local
browser run cover the main flow; 390px phone, 768px tablet, and 1024px desktop layouts were
visually checked on this host.

**Exit criteria:** browser and API integration tests cover the primary recommendation flow.

## Phase 5 — Single Agent, memory, RAG, and MCP (complete; offline and browser verified)

One bounded Agent now plans up to four approved profile/recommend/knowledge/explanation calls
and composes a validated answer. An optional OpenAI-compatible adapter and default local router
share one provider contract. PostgreSQL migrations add six-turn conversation context, derived
preference summaries and a four-document pgvector knowledge fixture. JSON/SSE chat endpoints
feed the simple `/agent` Next.js page. Independent read-only MCP-style HTTP search exposes schemas
and canonical outputs; full MCP transport is intentionally outside this minimum interface.

**Exit criteria:** offline tests prove provider replacement, tool selection/trace, limits,
persistence, RAG, MCP schemas, chat/SSE and frontend flow. An absent Key uses a documented local
fallback. Tests/lint/build and legacy smoke pass before one focused commit and push on
`codex/phase1-foundation-review`; stop here without beginning Phase 6. Live PostgreSQL/pgvector
and real-model availability remain explicitly unverified on this host.

Acceptance on 2026-09-30: 63 API tests, 12 web tests, API ruff/compile check, web lint/typecheck/build,
offline PostgreSQL upgrade/downgrade SQL, real-browser recommendation/artist flows and responsive
layouts, plus legacy help/HTTP 200. Phase 6 remains not started.

## Phase 6 — Observability and release quality

Add structured logs, traces, latency/status/model/token/error metrics, CI quality gates, bilingual
README, evaluation report, demo fixtures, and clean-start verification.

**Exit criteria:** documented commands pass from a clean checkout and the README accurately
explains architecture, limitations, and interview talking points.
