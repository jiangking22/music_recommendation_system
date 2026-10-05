# Architecture Decision Records / 架构决策记录

## ADR-021: Keep DeepSeek compatibility at the shared model adapter boundary

**Status:** Accepted
**Date:** 2026-10-05

Explicitly send `thinking: {type: disabled}` only when the configured URL hostname is exactly
`api.deepseek.com`. Both the homepage and assistant reuse this adapter and existing `LLM_*`
environment variables. Preserve JSON output mode and strict schema validation for every provider;
custom endpoints and lookalike domain names retain their existing request payload.

DeepSeek enables thinking by default; its [Chat Completions documentation](https://api-docs.deepseek.com/api/create-chat-completion/)
supports disabling it and requesting JSON output. This keeps reasoning within existing request
deadlines without introducing a new credential, changing the configured model or removing
structured output from unrelated providers. Mocked transport checks do not certify live quality.

## ADR-020: Resolve recording seeds before discovery; optional shared model guidance

**Status:** Accepted
**Date:** 2026-10-05

### Decision

Use a deterministic recording-resolution step before artist/attribute recall. Keep a small,
source-backed original-recording hint for the reported `我好想你` case; unknown multi-artist
matches require explicit artist selection. A single unlabelled match does not certify original
authorship. Filter alternate recordings before deduplication, exclude seed versions, and score
related artist/genre/tag/language factors explicitly alongside existing profile policy.
Bound each request to three registry operations and never pad a resolved song with unrelated
fixture tracks. Keep generic theme fallback and the existing recommendation response contract.

Add `/v1/recommendations/discover` for canonical seed metadata, ambiguity choices and explanation.
Reuse the assistant's configured LLM adapter for bounded prose only; errors preserve deterministic
results with local guidance. Translate homepage interface copy through an EN/中文 preference,
keeping music metadata and English theme headings unchanged.

### Consequences

Song discovery goes beyond a title search without handing recall/ranking to a model. Original
identification depends on source quality and bounded verified hints; incomplete upstream data
can produce fewer results or a request for clarification. Optional model prose can still be
inaccurate despite schema validation and grounding instructions; real-model quality is unverified.
No new dependency, database schema or legacy-runtime change is required.

## ADR-001: Incremental strangler migration from the legacy demo

**Status:** Accepted
**Date:** 2026-09-29

### Context

The repository contains a functioning static HTML/JavaScript demo with a Python standard
library proxy. The target platform requires a typed Next.js client, FastAPI service,
PostgreSQL/pgvector, Redis, tests, and Docker Compose.

### Decision

Build the target platform in new `apps/` and `services/` directories. Keep the legacy demo
unchanged until a replacement vertical slice is verified and documented.

### Consequences

- The demo remains runnable during the migration.
- New code avoids coupling to the large legacy front-end script.
- A temporary dual-runtime period is intentional and must be called out in the README.

## ADR-002: One Agent with allow-listed tools

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use one orchestration Agent with a small tool registry: recommendation, read-only profile,
music knowledge retrieval and explanation (Phase 5 refinement in ADR-014). Traditional ranking owns candidate
quality and ordering.

### Consequences

- Tool selection can be tested deterministically.
- The system does not add multi-Agent coordination, queues, or hidden recommendation policy.
- Agent output must include tool provenance when it recommends songs.

## ADR-003: Anonymous device identity, not account authentication

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Issue a random client-side device identifier and accept it in a validated request header.
Persist preference profile and conversation linkage against that identifier.

### Consequences

- The project demonstrates personalization without the security and product scope of signup.
- There is no cross-device identity guarantee.
- The API will rate-limit and validate the identifier; it must never grant privileged access.

## ADR-004: PostgreSQL with pgvector; Redis only for ephemeral data

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use PostgreSQL as the durable store and pgvector for song, preference, and knowledge vectors.
Use Redis only for sessions, cache, and rate-limit state.

### Consequences

- One durable database supports relational recommendation data and vector retrieval.
- Docker Compose must enable the pgvector extension via migration.
- Redis data can be discarded without losing users' durable preferences.

## ADR-005: Preserve and mine the legacy demo before migration

**Status:** Accepted

### Decision

Do not rewrite `app.js` or `server.py` in Phase 0. Treat the current user-visible behaviour as
an executable reference and migrate reusable logic only behind tests and canonical contracts.

### Consequences

- The legacy demo remains the only supported runtime during Phase 0.
- Existing provider mappings and rank heuristics become migration inputs, not target architecture.

## ADR-006: Limit target providers to verified adapters

**Status:** Accepted

### Decision

The target runtime will retain only two or three providers after an adapter verification spike.
Sources based on unstable public endpoints, scraped pages, or undocumented tokens remain optional
and never determine core availability.

### Consequences

- Provider capability and health are explicit.
- Multi-source recall remains a product feature without promising every legacy source indefinitely.

## ADR-007: Phase 1 persistence and startup

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use synchronous SQLAlchemy 2.0 with psycopg and Alembic for the small Phase 1 data surface.
The API container runs migrations before serving requests. `GET /health` is a liveness check;
`GET /health/ready` verifies PostgreSQL and Redis. Anonymous device IDs are the primary key of
`device_users` and grant no permissions. SQLite is used only for fast local repository/API tests.

### Consequences

- A failed migration prevents API startup instead of serving against an outdated schema.
- Tests prove repository behaviour without Docker; live PostgreSQL migration still needs a
  Docker-capable environment.
- Redis is a connected ephemeral dependency, not a source of durable device identity.

## ADR-008: Fixture recommendation chain for Phase 1

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Expose `POST /v1/recommendations` with a bounded seed and limit. A service asks a small domain
function to select canonical songs from a committed JSON fixture; it moves tag matches first
and otherwise preserves fixture order. The Next.js shell fetches this response on request.

### Consequences

- The Web → API → domain path is executable without music providers or a catalog import.
- The fixture selector is not a production recall or ranking policy and is replaced in Phase 3.

## ADR-009: Canonical tracks and bounded provider registry

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Represent external songs as a canonical Track with Artist, optional Album, ProviderSource,
duration, artwork, URL, language, genres/tags, popularity and a normalized title/artist key.
Keep source payload parsing inside adapters. Expose a MusicProvider Protocol and registry that
returns per-source ProviderResult errors alongside canonical tracks. Calls are sequential
(upstream concurrency one), limited to 25 results/source, use four-second HTTP timeouts, have
no retries, and cap response bodies at 1 MB. Health is last-operation status, not an active
network probe. The key prepares for later deduplication but Phase 2 does not merge or rank songs.

iTunes Search API is the documented default source. NetEase is a default best-effort adapter
to preserve the second legacy source, with `unverified` capability metadata; QQ is opt-in via
`ENABLE_QQ_PROVIDER`. Both NetEase and QQ depend on undocumented public web endpoints and may
fail independently. Spotify and YouTube Music remain legacy-only and unverified for the target
runtime.

### Consequences

- API and future recommendation code consume one schema and never inspect provider payloads.
- A source outage appears in `sources` without discarding healthy source results.
- Automatic tests use fixtures and mocked HTTP; they cannot certify live upstream availability.

## ADR-010: Deterministic Phase 3 recommendation policy

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Recall from the bounded Provider Registry plus a versioned local catalog. Normalize title and
artist variants for cross-provider deduplication while retaining every source ID. Rank with
explicit weights in `app/domain/policy.py`, apply deterministic artist/provider/genre diversity
penalties, and construct explanations from measured factors. Return scores and source errors.

### Consequences

An upstream outage leaves catalog recommendations available. Future Agent tooling may invoke
this recommender but cannot replace its recall, rank, or explanation policy. Provider metadata
quality and the small fallback catalog limit relevance until a larger verified catalog exists.

## ADR-011: Latest feedback wins and profiles are durable snapshots

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Store one rating per anonymous device and canonical track key. Atomic PostgreSQL upsert replaces
earlier feedback; recompute a bounded recent profile in the same transaction. Store normalized
artist, genre, tag, and language affinities as JSON, and consult current disliked track keys
when ranking. The device header links preferences but grants no authentication privileges.

### Consequences

Feedback changes later recommendations without Redis or an LLM. A client may supply metadata
for its own anonymous profile; input sizes are bounded. The profile uses the latest 200 ratings
with explicit recency decay, so very old ratings are not represented in the snapshot.

## ADR-012: Small deterministic embeddings and versioned offline evaluation

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use a 16-dimensional local SHA-256 feature hash for song and preference vectors. Persist vectors
in pgvector and expose a bounded repository cosine search; SQLite uses a local fallback for
offline tests. Embeddings do not silently modify ranking. Evaluate a committed five-song,
two-case fixture with relevance, personalization rank lift, attribute diversity, and coverage.

### Consequences

No paid API, model download, or training job is required. Hash collisions and tiny fixture size
limit retrieval and metric generalization; evaluation measures regression on fixed cases, not
real-user recommendation quality. Live pgvector migration/query verification awaits a PostgreSQL
runtime on a Docker-capable host.

## ADR-013: Browser API client and read-only profile projection

**Status:** Accepted
**Date:** 2026-09-29

### Decision

The Phase 4 Next.js page runs its interactive requests in the browser against the versioned
FastAPI endpoints. One API module owns the public base URL, device header, timeout, JSON parsing,
and error envelope. The browser persists only a random anonymous device ID. A new read-only
`GET /v1/profile` projects positive affinities and five recent ratings from Phase 3 tables; it
does not change the recommendation policy or persistence model.

### Consequences

The browser can show durable feedback and partial provider failures without an additional BFF.
Deployments must set `NEXT_PUBLIC_API_BASE_URL` to a browser-reachable API URL and allow the web
origin in `ALLOWED_ORIGINS`. The profile is tied to one browser identifier with no account
recovery or cross-device sync.

## ADR-014: One validated plan with replaceable LLM adapters

**Status:** Accepted
**Date:** 2026-09-30

### Decision

Separate Agent core/tools/memory/prompts/schemas/provider adapters. A local deterministic intent
router is the default and fallback when no Key exists. An optional OpenAI-compatible JSON adapter
implements the same `LLMProvider` contract. Validate a single plan before executing 1–4 distinct,
allowlisted calls, then validate a prose-only answer. No retries, autonomous replanning, feedback
writes, ranking mutation or multiple Agents. Canonical recommended items come exclusively from
the Phase 3 pipeline. SSE exposes public statuses, tool names and final output, never reasoning.

### Consequences

Mock transport and local routing make tests independent of keys/network. The local provider has
limited bilingual patterns; real model answers can still be inaccurate despite grounding prompts.
Schema checks protect structure, not factual truth. Four active requests and four worker slots per
event loop plus bounded I/O prevent unlimited concurrency; timeouts cannot terminate an already
running synchronous operation. Live model compatibility is unverified.

## ADR-015: PostgreSQL conversation context and derived preference summaries

**Status:** Accepted
**Date:** 2026-09-30

### Decision

Persist the last six turns and last seed per server-issued conversation UUID in PostgreSQL.
Bind each conversation to its validated anonymous device ID. Reject stale simultaneous writes
with a version check. Store a top-five affinity summary derived by the profile tool from existing
feedback. Use no accounts and no LLM-authored durable preference facts. Redis remains optional
for future ephemeral caching rather than required for Agent memory.

### Consequences

Context survives restarts and can be resumed by conversation ID. Device IDs remain identifiers
with no authentication guarantee. The frontend retains the conversation ID within its current
page only; history listing, deletion, TTL cleanup and cross-device sync are outside Phase 5.
Chat text is stored in bounded context rows but excluded from structured logs.

## ADR-016: Small lexical-guarded RAG and independent MCP-style search

**Status:** Accepted
**Date:** 2026-09-30

### Decision

Seed four versioned knowledge documents/chunks with local 16-dimensional text hash vectors.
Use PostgreSQL pgvector cosine candidates followed by lexical-overlap guarding and bounded
retrieval ranking. Knowledge aids Q&A and explanations only. Expose independent `music_search`
through an HTTP MCP-style schema/call façade using canonical input/output models and no LLM.

### Consequences

All fixtures and retrieval tests run offline. Hash collisions and sparse aliases limit semantics;
no relevant lexical evidence produces no answer material. The minimal MCP tools contract is not
a complete MCP transport or JSON-RPC server. No new dependency or large dataset is introduced.
SQLite verifies persistence/retrieval semantics, and offline Alembic SQL verifies PostgreSQL
DDL/fixture seeding; live pgvector execution remains unverified on this host.

## ADR-017: Correlated content-free JSON telemetry

**Status:** Accepted
**Date:** 2026-09-30

### Decision

Use a small ContextVar-based ASGI boundary and JSON event allowlist rather than a monitoring stack.
Carry request/trace IDs through HTTP, SSE, worker threads and outbound adapter headers. Log duration,
status, counts, model/provider and optional validated usage. Preserve the recommendation response's
request_id field but align it with the response header. Disable raw HTTP client/access logging in
the documented runtime. Never record request/chat/provider/LLM payloads or exception messages.

### Consequences

No collector or dashboard is required. Logs provide samples for later aggregation, not a complete
OTel trace or built-in histogram/alert service. SSE errors require event-level inspection after HTTP
200. A central body limit and generic unexpected-error envelope prevent unbounded JSON input and
sensitive exception disclosure. Anonymous device linkage still is not authentication.

## ADR-018: Add standard MCP stdio alongside the existing HTTP façade

**Status:** Accepted; supersedes ADR-016 only for the transport scope
**Date:** 2026-09-30

### Decision

Install official Python MCP SDK 1.30.0 as an optional exact-pinned extra. Use its supported v1
stdio API to expose read-only music_search and recommend_tracks, reusing MusicTools and the
recommendation service. Verify initialize/list/call with an actual SDK client subprocess. Preserve
Phase 5 HTTP routes and name them MCP-style façade. No remote MCP auth/HTTP endpoint in this phase.

### Consequences

Compatible local clients can actually invoke music tools without another service or an LLM. Stdio
stdout is reserved for protocol messages and logs use stderr. Recommendations are unpersonalized;
no private device data is exposed. SDK v1 remains maintained for security/critical fixes; a future
v2 migration must be deliberate. RAG and deterministic ranking decisions in ADR-016 remain intact.

## ADR-019: Offline release gates and explicit clean-start evidence

**Status:** Accepted
**Date:** 2026-09-30

### Decision

GitHub Actions runs API and web quality gates plus a disposable Compose project. Generate a unique
CI-only database credential at runtime; disable music providers and use the local Agent. Verify
migrations, pgvector query, Redis, readiness, web, recommendation, feedback/profile and local Agent
with the existing business layer. Ship typed package discovery, wheel fixtures and non-root
containers. Keep author-host verification distinct from CI-host verification.

### Consequences

Quality gates need dependency/image downloads but no real music/LLM API or Key. Author Windows has
no Docker, so local clean start is explicitly unexecuted; never infer success from static YAML/SQL.
The next Docker-capable run provides live evidence. Transitive Python packages and container tags
remain unlocked, which limits bit-for-bit reproducibility. No public deployment or main merge is
performed as part of the final engineering phase.
