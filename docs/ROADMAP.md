# Delivery Roadmap / 交付路线图

This roadmap is intentionally incremental. A phase is complete only when its stated
verification passes and its documentation status is updated.

## Phase 0 — Baseline and architecture

- [x] Inventory the legacy demo and preserve its runtime.
- [x] Record the target architecture and ADRs.
- [x] Write the migration specification and phased plan.
- [ ] Update the README to distinguish legacy and target runtimes.

**Verify:** `python server.py --help` succeeds; architecture documents describe current and
target states accurately.

## Phase 1 — Runnable engineering foundation

- [ ] Scaffold Next.js TypeScript and FastAPI services.
- [ ] Add Compose for web, API, PostgreSQL/pgvector, and Redis.
- [ ] Add health endpoint, configuration validation, migration skeleton, lint/test commands.
- [ ] Deliver one vertical slice: anonymous device -> catalog seed -> REST recommendation.

**Verify:** `docker compose up --build`; API integration test returns a validated response.

## Phase 2 — Recommendation core and providers

- [ ] Define canonical song and provider plugin interfaces.
- [ ] Keep 2–3 verified providers; model other providers as optional adapters.
- [ ] Implement multi-source recall, profile features, embeddings, reranking, explanations.
- [ ] Add offline fixtures and relevance/personalization/diversity evaluation.

**Verify:** provider fixture tests and offline evaluator run reproducibly.

## Phase 3 — Product client and durable personalization

- [ ] Build recommendation UI, anonymous-device bootstrap, feedback controls, and profile view.
- [ ] Persist feedback and long-term preference embeddings.
- [ ] Add API and browser-facing state tests.

**Verify:** feedback survives a restart and changes a subsequent recommendation response.

## Phase 4 — Agent, memory, RAG, MCP

- [ ] Implement one Agent, session memory, long-term preference summary, and SSE chat.
- [ ] Add music knowledge RAG and explanation enrichment.
- [ ] Expose a minimal read-oriented MCP server.
- [ ] Add deterministic Agent tool-selection tests.

**Verify:** streaming chat calls only allow-listed tools; test trace captures selection.

## Phase 5 — Observability, quality, and portfolio release

- [ ] Trace recommendations and Agent tools: latency, status, model, tokens, errors.
- [ ] Add unit, API integration, and Agent tool test coverage to CI.
- [ ] Complete bilingual README, architecture diagrams, evaluation results, and demo data.
- [ ] Validate clean one-command local startup.

**Verify:** documented quality commands pass from a clean clone.
