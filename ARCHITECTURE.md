# Architecture / 架构

## Purpose / 目标

Music Recommendation Platform is a portfolio-grade, maintainable web application.
Its recommendation engine remains deterministic and measurable; the Agent interprets
requests, selects tools, and explains results rather than replacing the recommender.

## Target topology / 目标拓扑

```text
Next.js web (apps/web)
        | REST + Server-Sent Events
FastAPI API (services/api)
        |-- PostgreSQL + pgvector: catalog, anonymous users, feedback, embeddings
        |-- Redis: short-lived session and response cache
        |-- Provider plugins: stable music-source adapters
        |-- Recommender: recall -> feature scoring -> reranking -> explanations
        |-- Agent: intent -> approved tool calls -> streamed response
        |-- MCP server: a small, read-oriented façade over music tools
        `-- Observability: structured logs, traces, metrics events
```

`index.html`, `app.js`, `styles.css`, and `server.py` are the legacy demo. They stay
available during migration and are not dependencies of the target runtime.

## Service boundaries / 服务边界

| Area | Responsibility | Must not do |
| --- | --- | --- |
| Web | Present UI, persist anonymous device ID, consume REST/SSE | Rank songs or store secrets |
| API | Validate requests, coordinate use cases, expose OpenAPI | Embed provider-specific HTTP details in routes |
| Provider | Convert an external source into the canonical song model | Make recommendation policy decisions |
| Recommender | Candidate recall, feature scoring, reranking, offline evaluation | Call an LLM |
| Agent | Intent extraction, tool choice, result composition | Invent song metadata or bypass access checks |
| MCP | Expose a small tool subset for compatible clients | Become a second business-logic implementation |

## Data ownership / 数据归属

- PostgreSQL is the system of record for songs, user profiles, feedback, recommendation
  events, knowledge documents, and embedding vectors.
- Redis holds only expirable session, cache, and rate-limit data; it is safe to clear.
- The browser retains a random anonymous device identifier. It is sent as `X-Device-Id`
  and is not an authentication credential.
- API keys are environment variables only. `.env` is never committed.

## Request paths / 关键请求路径

### Recommendation

1. The client sends a seed, filters, and anonymous device ID to `POST /v1/recommendations`.
2. The API resolves the user preference profile and asks provider plugins plus local catalog
   for candidates.
3. The recommender deduplicates candidates, applies feature scores and diversity reranking,
   then records an evaluation-friendly recommendation event.
4. The API returns songs, score factors, provider provenance, and an explanation.

### Agent chat

1. The client opens `POST /v1/agent/chat/stream` with a device ID and message.
2. The Agent loads the current session plus durable preference summary.
3. It calls an allow-listed tool (search, recommend, save feedback, music knowledge) when
   needed. Tool calls are traced.
4. The API streams typed SSE events: `message`, `tool_call`, `tool_result`, `done`, `error`.

## Reliability and security / 可靠性与安全

- Provider failures are isolated and surfaced as partial-source metadata, never as a full
  recommendation outage when local candidates remain.
- Request models use explicit validation, bounded page sizes, and timeouts.
- External provider URLs and user-provided text are treated as untrusted input.
- Logs redact authorization headers, API keys, and user message contents by default.

## Verification architecture / 验证架构

- Unit tests cover provider mapping, scoring, reranking, profile updates, and Agent tool
  selection.
- API integration tests use a disposable PostgreSQL/Redis environment.
- Offline evaluation reports relevance, personalization lift, diversity, coverage, and tool
  selection accuracy from versioned fixtures.
- Docker Compose is the authoritative local end-to-end environment.
