# Spec: Agentic Music Recommendation Platform

## Objective

Transform the legacy multi-source music demo into a job-search-ready engineering project.
It must demonstrate: a production-shaped web/API foundation, explainable recommendation,
and a bounded tool-calling Agent. The initial audience is interviewers and developers who
can run the full stack locally without external paid services.

## Tech stack

- Web: Next.js and TypeScript.
- API: Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic.
- Data: PostgreSQL with pgvector and Redis.
- Runtime: Docker Compose.
- Tests: pytest for API/domain tests; Vitest/Testing Library for web tests.

## Commands (implemented runtime)

```bash
docker compose up --build --wait --wait-timeout 180
# In offline provider/local Agent mode:
docker compose exec -T api python scripts/docker_smoke.py
docker compose down
```

Quality tests run in developer/CI environments rather than production containers (which exclude
dev dependencies). See README for pytest, lint/type/build and evaluation commands, and
docs/DEPLOYMENT.md for configuration/clean-start status. The legacy demo remains runnable with
`python server.py`; Docker is absent on the author's Windows host and was not run locally.

## Project structure (target)

```text
apps/web/                 Next.js application
services/api/app/         FastAPI routes, domain use cases, adapters
services/api/tests/       unit and integration tests
infra/                    Compose, migrations, local configuration
docs/specs/               accepted specs and phased plans
ARCHITECTURE.md           current technical architecture
DECISIONS.md              durable architectural rationale
```

## API contract rules

- REST endpoints live under `/v1`; request and response models are explicit Pydantic types.
- `POST /v1/agent/chat/stream` streams Server-Sent Events and never uses WebSockets for the
  first release.
- A recommendation response includes `items`, `request_id`, and per-item explanations.
- Provider names are normalized enum values; clients never depend on a provider's raw payload.

## Testing strategy

- Provider adapters: fixture-based mapping and failure-isolation tests.
- Recommender: score, diversity, deduplication, and personalization-lift unit tests.
- API: health, anonymous identity, recommendations, feedback, and SSE integration tests.
- Agent: tool allow-list and intent-to-tool selection tests without an external model.
- Web: API client and primary recommendation/chat states.

## Boundaries

- **Always:** validate user input, record traceable recommendation/tool events, update docs
  and TODO status after each phase, run affected tests before committing.
- **Ask first:** add a hosted model/provider dependency, change the public API after release,
  or remove the legacy runtime.
- **Never:** commit credentials, make the LLM rank results, require user signup, or introduce
  microservices/Kubernetes/multi-Agent orchestration for this project.

## Success criteria

- `docker compose up --build` starts web, API, PostgreSQL/pgvector, and Redis locally.
- A device can receive explainable multi-source recommendations and persist feedback.
- Agent chat streams responses and its tool calls are observable and test-covered.
- RAG, MCP, offline evaluation, structured observability, integration tests, and a bilingual
  README are all present and runnable/documented.

## Open questions

- External LLM provider is optional; Phase 5 provides a deterministic local fallback without a Key.
  Real model compatibility remains unverified.
- iTunes and NetEase are default target adapters; QQ is opt-in. NetEase/QQ use undocumented
  endpoints, so fixture mapping tests do not establish stability or licensing guarantees.
- Phase 6 adds standard read-only MCP stdio; existing HTTP routes remain MCP-style façade.
