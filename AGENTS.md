# Codex Working Agreement

## Scope and phase discipline

- Read `PROJECT_PLAN.md`, `TODO.md`, `ARCHITECTURE.md`, and `DECISIONS.md` before changing code.
- Work on exactly one checked-out TODO item at a time. Do not begin a later phase merely because
  its dependencies are familiar.
- Phase 0 is documentation-only. Do not add Next.js, FastAPI, Docker, databases, LLMs,
  embeddings, Agent/RAG/MCP code, or large datasets while it is active.
- Preserve `index.html`, `app.js`, `styles.css`, and `server.py` as the runnable legacy demo
  until an approved migration task explicitly replaces a behaviour.

## Engineering rules

- Inspect `git status` first; do not alter unrelated or user-owned changes.
- Use environment variables for every credential. Commit only `.env.example` placeholders.
- Keep provider payloads at adapter boundaries; domain and UI code use canonical models only.
- The deterministic recommender owns recall and rank. An Agent may select approved tools and
  explain results, but never silently replaces ranking policy.
- Anonymous device IDs are identifiers for preference linkage, not authentication or privilege.
- Validate all external HTTP input and provider payloads. Bound timeouts, concurrency, retries,
  and result sizes.
- Use structured errors and structured logs. Never log credentials, authorization headers, or
  full private chat content.

## Change workflow

1. State the task, assumptions, files in scope, and verification command.
2. Write or update a focused test before changing behaviour.
3. Make the smallest vertical slice that leaves the project runnable.
4. Run relevant tests, lint/type checks, and a targeted runtime check.
5. Update `TODO.md`; update `ARCHITECTURE.md` and `DECISIONS.md` for architecture changes.
6. Make one focused commit. Do not stage generated files, `.env`, caches, or build output.

## Documentation and compatibility

- Public HTTP endpoints are additive under `/v1`, use typed request/response schemas, and return
  a consistent error envelope.
- Keep the README bilingual as target-runtime work progresses; distinguish implemented features
  from planned ones.
- Record major trade-offs as compact ADRs in `DECISIONS.md`; do not silently re-decide them.

## Definition of done

- Acceptance criteria and tests pass.
- No secret or generated artifact is staged.
- Documentation reflects the current, not intended, state.
- Existing legacy command `python server.py` still works unless its replacement task says otherwise.
