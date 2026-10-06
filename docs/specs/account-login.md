# Mandatory account login / 强制登录与账号个性化

Approved 2026-10-06. Implement sequential TODO items; new accounts start empty. Only music feedback,
profile and vectors follow accounts across devices. UI language stays browser-local. Assistant
retains six turns per login session, without cross-device history. Legacy source remains unchanged.

## Product and contracts

- Open username/password registration. ASCII letters/digits/underscore, 6–20 characters,
  case-insensitive uniqueness; password 6–20 Unicode characters including spaces, never trimmed.
  Limits are inclusive and apply to registration/login, password changes and administrator reset.
- Login/register/show password/remember login, safe local return path, account menu/change password.
  Login is 24 hours or 30 days remembered. Registration logs in. Reset is local administrator CLI.
- Typed `/v1/auth/csrf`, `/register`, `/login`, `/me`, `/logout`, `/change-password`; consistent errors.
  Only health/auth bootstrap are anonymous; business HTTP including SSE/search/MCP requires login.
- Argon2id hashes, opaque random tokens with server-side digest storage, revocable PostgreSQL
  sessions, HttpOnly/SameSite=Lax cookies, production Secure/HTTPS; no token in localStorage.
- Fixed same-origin `/api/v1/*` transport to FastAPI, internal API origin from server environment.
  Origin and CSRF validation on all writes. Redis auth limits fail closed, return 429/Retry-After.
- Feedback key `(user_id, track_key)`; serialize writes per account, rebuild unchanged profile/vector
  in the same transaction. Business ownership comes only from authenticated server context.
- Anonymous tables remain archived. `/v1/device` is retired; no claim endpoint. Assistant records
  additionally bind login session. Public recording memory stays shared; stdio MCP stays read-only.
- Abort requests and discard results on logout/expiry/account changes. Reload profile on page load,
  focus, feedback and recommendation. No WebSocket. Reset/change-password revoke all sessions.

## Trust boundaries and acceptance

Untrusted browser fields, cookies and identifiers never select another user's data. LLM tools get
server-provided ownership. Test unauthenticated routes, cross-account/session conversation IDs,
CSRF, expired/revoked cookies, duplicate registration, enumeration-safe invalid login, Redis failure,
auth concurrency limits and logs without passwords/tokens/private chat content.

Two browser sessions on one account must share feedback/profile/recommendation effects; different
accounts remain isolated, concurrent feedback loses no updates, anonymous archives stay unchanged.
390px and desktop flows cover register → recommend → feedback → logout → second-device login,
safe redirects, late responses, account changes, streamed chat and form keyboard/accessibility.

## Delivery and verification

1. Spec/ADR. 2. Authentication foundation. 3. Account business ownership. 4. Web integration.
5. Deployment/CI/current-state documentation and runtime checks. One TODO/commit at a time.

API: pytest, Ruff, compileall, evaluation. Web: tests, ESLint, types, production build, npm audit.
PostgreSQL: upgrade from 0006, drift check, isolated downgrade/upgrade and concurrent writes.
Compose: health, authenticated HTTP/SSE smoke; legacy: `python scripts/legacy_smoke.py`.
Back up existing DB before deploying; preserve .env/volumes. Rollback via maintenance window and
verified backup restoration, never drop live account data. Record actual results, not intentions.
