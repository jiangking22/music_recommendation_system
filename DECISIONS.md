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
