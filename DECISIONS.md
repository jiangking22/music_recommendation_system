# Architecture Decision Records / 架构决策记录

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
- New code avoids coupling to a 150k-line front-end script.
- A temporary dual-runtime period is intentional and must be called out in the README.

## ADR-002: One Agent with allow-listed tools

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use one orchestration Agent with a small tool registry: catalog search, recommendation,
feedback/profile update, and music knowledge retrieval. Traditional ranking owns candidate
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
