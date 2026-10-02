# Changelog / 版本记录

This record describes code present on merged `main`, checked against Git history and the
implementation. Planned roadmap work and the reverted early API prototype are not release features.
本文件依据真实提交与当前实现整理；不把路线图或已回退的早期 API 原型计入交付。

## [1.0.0] — Unreleased / 待发布

Prepared on 2026-10-02 against `4c54239a46d1cc32a813d3f841c3d0ca0d5c7c30`.
No tag or GitHub Release has been created by this preparation. Release date is not assigned.
License and component-version decisions remain open; see the [release audit](docs/releases/v1.0.0-readiness.md).

### Engineering foundation

- Introduced a Python 3.12 FastAPI service and Node.js 24 / Next.js TypeScript client alongside
  the preserved legacy demo. Added typed `/v1` contracts, consistent error envelopes,
  configuration validation, liveness and PostgreSQL/Redis readiness checks.
- Added PostgreSQL/pgvector, Redis, Docker Compose, Alembic migrations, anonymous device
  persistence, pinned direct dependencies and the web lockfile. Redis currently checks readiness;
  caching, sessions and rate limiting are not implemented in Redis.
- Established the project plan, architecture, ADRs, incremental checklist and legacy smoke check.

History: [8c65e5e](https://github.com/jiangking22/music_recommendation_system/commit/8c65e5e),
[ff38218](https://github.com/jiangking22/music_recommendation_system/commit/ff38218),
[7df79b9](https://github.com/jiangking22/music_recommendation_system/commit/7df79b9),
[5773116](https://github.com/jiangking22/music_recommendation_system/commit/5773116),
[420abb6](https://github.com/jiangking22/music_recommendation_system/commit/420abb6),
[41abaff](https://github.com/jiangking22/music_recommendation_system/commit/41abaff).

### Providers

- Added canonical Track, Artist, Album, ProviderSource, capability, result and health models.
- Added iTunes and NetEase default adapters and an opt-in QQ adapter, with offline mapping tests.
  The registry bounds calls and response sizes and preserves partial results and source errors.
- Exposed provider discovery, last-operation health and canonical track search under `/v1`.
  NetEase and QQ use undocumented endpoints and are explicitly marked `unverified`.

History: [0d7da38](https://github.com/jiangking22/music_recommendation_system/commit/0d7da38).

### Recommendation/personalization

- Added provider recall with local catalog fallback, normalized cross-provider deduplication,
  explicit deterministic scoring, diversity reranking, provenance and factor explanations.
- Persisted latest-rating-wins feedback and bounded, recency-weighted preference snapshots;
  later recommendations use affinities and disliked-track penalties. Anonymous device IDs link
  preferences and provide no authentication.
- Added local 16-dimensional feature-hash embeddings, pgvector storage/cosine retrieval and
  versioned offline evaluation for relevance, personalization rank lift, diversity and coverage.
  Embeddings do not change ranking policy implicitly.

History: [1c6212b](https://github.com/jiangking22/music_recommendation_system/commit/1c6212b),
[802ba53](https://github.com/jiangking22/music_recommendation_system/commit/802ba53),
[dfbaa08](https://github.com/jiangking22/music_recommendation_system/commit/dfbaa08).

### Product client

- Added the responsive recommendation homepage with seed/result-count inputs, artwork/fallback
  cards, source provenance, score explanations, like/dislike and a durable preference panel.
- Added stable browser device linkage, optimistic feedback with rollback, refreshed profiles,
  and explicit loading, empty, error and partial-provider states.
- Added the read-only profile projection and component/API-client tests. Published three actual
  offline browser screenshots with their capture conditions and a bilingual README/demo guide.

History: [5a34241](https://github.com/jiangking22/music_recommendation_system/commit/5a34241),
[1c76b33](https://github.com/jiangking22/music_recommendation_system/commit/1c76b33),
[2d74a0a](https://github.com/jiangking22/music_recommendation_system/commit/2d74a0a).

### Agent/RAG/MCP

- Added one bounded Agent with a validated plan of 1–4 allowlisted tools: profile,
  recommendation, knowledge retrieval and explanation. The deterministic recommender retains
  ownership of scores and order; the Agent cannot write feedback or replace ranking policy.
- Added a default local rule router and an optional OpenAI-compatible adapter, JSON/SSE chat
  and the `/agent` page with public tool statuses, canonical results and citations.
- Persisted six-turn conversation context and derived preference summaries. Added a four-document
  knowledge fixture with local hash vectors, pgvector candidates and a lexical evidence guard.
- Added a read-only MCP-style HTTP search façade, then a separate standard MCP stdio server using
  the optional official Python SDK. Stdio exposes `music_search` and unpersonalized
  `recommend_tracks`; a real SDK subprocess test covers protocol initialization/discovery/calls.

History: [b89de81](https://github.com/jiangking22/music_recommendation_system/commit/b89de81),
[3bee4e0](https://github.com/jiangking22/music_recommendation_system/commit/3bee4e0).

### Observability/CI/release quality

- Added content-free structured JSON events, request/trace correlation across HTTP, SSE and
  worker threads, provider/tool/model durations, error codes and optional validated token counts.
- Added request-body limits, safe unexpected-error responses, correlation headers through CORS,
  offline provider mode, non-root containers and explicit wheel fixture packaging.
- Added API/web quality gates and a disposable offline Compose clean start covering migrations,
  pgvector, Redis, readiness, both web pages, recommendation, feedback, local Agent/RAG and context.
- Added deployment, observability, evaluation and demo documentation. The audited main CI
  [run 36971477031](https://github.com/jiangking22/music_recommendation_system/actions/runs/36971477031)
  passed API, web and clean-start jobs on 2026-10-02.

History: [3bee4e0](https://github.com/jiangking22/music_recommendation_system/commit/3bee4e0),
[1c76b33](https://github.com/jiangking22/music_recommendation_system/commit/1c76b33).

### Compatibility and limits / 兼容与限制

`python server.py` remains available; `index.html`, `app.js`, `styles.css` and `server.py` are
unchanged from the pre-migration baseline `6758d77`. Legacy-only Spotify/YouTube fallbacks are
not target-runtime providers. The tiny fixtures are regression evidence, not real-user quality
benchmarks. Live provider availability and real-model compatibility are not release guarantees.
There is no account authentication, licensed music streaming, remote MCP HTTP/OAuth transport,
distributed monitoring stack, Redis caching or automatic chat-retention cleanup.

组件版本目前仍为 `0.1.0`；本节是拟定的仓库 `v1.0.0` 发布记录，不表示已发布。
