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
remains unverified on this host. Phase 4 has not begun.

**Exit criteria:** relevance, personalization lift, diversity, and coverage are reproducibly
reported from versioned fixtures; feedback changes a later result.

## Phase 4 — Product client

Build the Next.js user flow: anonymous device bootstrap, recommendation input/results,
explanations, feedback, preference summary, and resilient loading/error states.

**Exit criteria:** browser and API integration tests cover the primary recommendation flow.

## Phase 5 — Single Agent, memory, RAG, and MCP

Add one allow-listed-tool Agent with current-session memory and durable preference summaries;
stream chat through SSE. Add music knowledge RAG for Q&A/explanation enhancement and expose a
minimal read-oriented MCP server.

**Exit criteria:** deterministic tests prove tool selection and trace each call; an absent LLM key
uses a documented local fallback.

## Phase 6 — Observability and release quality

Add structured logs, traces, latency/status/model/token/error metrics, CI quality gates, bilingual
README, evaluation report, demo fixtures, and clean-start verification.

**Exit criteria:** documented commands pass from a clean checkout and the README accurately
explains architecture, limitations, and interview talking points.
