# Deployment and account operations / 部署与账号维护

## Runtime and configuration / 环境与配置

Python 3.12, Node.js 24, PostgreSQL 16/pgvector, Redis 7 and Docker Compose v2.
Copy `.env.example` to `.env`, set a database password and matching URL-encoded `DATABASE_URL`.
Never commit credentials. Existing `.env` and provider/model settings are preserved during upgrades.

新版所有 HTTP 业务接口必须登录，账号在网页自助注册；无需邮箱、手机号或第三方登录。
旧版 `python server.py` 仍是独立演示，不使用新版账号。旧匿名数据保留且不自动认领。

| Variable | Purpose / 用途 |
| --- | --- |
| `APP_ENVIRONMENT=development` | Explicit local HTTP mode / 本地开发模式 |
| `AUTH_COOKIE_SECURE=false` | Local HTTP only; production must use true / 生产必须为 true |
| `ALLOWED_ORIGINS=http://localhost:3000` | Exact browser Origin(s), no wildcard or trailing slash / 精确网页来源 |
| `API_INTERNAL_URL=http://127.0.0.1:8000` | Server-only web proxy target; Compose fixes `http://api:8000` / 服务端固定转发地址 |
| `AUTH_LOGIN_ACCOUNT_LIMIT=10` | Login attempts per username per 15 min / 每账号登录限流 |
| `AUTH_LOGIN_SOURCE_LIMIT=60` | Login attempts per source per 15 min / 每来源登录限流 |
| `AUTH_REGISTER_SOURCE_LIMIT=5` | Registration attempts per source per 15 min / 每来源注册限流 |
| `ENABLE_MUSIC_PROVIDERS=false`, `LLM_PROVIDER=local` | Offline business acceptance / 离线验收 |

Browsers always call same-origin `/api/v1/*`; no `NEXT_PUBLIC_API_BASE_URL` is used.
The proxy preserves Cookie, CSRF/session guards, correlation headers, Set-Cookie and SSE;
request bodies are capped at 64 KiB/10s, upstream lifetime at 70s with disconnect cancellation.
The API checks Cookie authentication and CSRF/Origin independently of frontend routing.
Redis login/register limits fail closed with retryable 503; 429 includes Retry-After.
Forwarded client IP headers are deliberately ignored: clients behind the Next proxy share its
source bucket, while the username bucket remains separate. Configure limits for expected traffic;
a future trusted-proxy policy must explicitly establish which forwarding hop can be trusted.

注册及登录使用 Redis 原子限流；故障时不会跳过限流。代理用户共享来源桶，客户端伪造 IP 不会绕过限制。
密码使用 Argon2id（19 MiB、2 次、并行度 1），最多四个并发哈希工作；会话令牌只存摘要。
Cookie 为 HttpOnly、SameSite=Lax、host-only；24 小时或保持登录 30 天。所有写操作校验来源及 CSRF。

## Start and acceptance / 启动与验收

```bash
docker compose config --quiet
docker compose up --build --wait --wait-timeout 180
# Disposable offline stack only:
docker compose exec -T api python scripts/docker_smoke.py
docker compose exec -T api python scripts/account_postgres_check.py
docker compose exec -T api alembic current
docker compose exec -T api alembic check
```

Open `http://localhost:3000/register`. Choose a 6–20 character ASCII username (letters/digits/_)
and 6–20 character password; both bounds are inclusive. Registration signs in automatically. The username menu supports
password change and logout. Password changes revoke every login; all devices must sign in again.
No default account/password is shipped. Forgot-password text directs users to the administrator.

打开注册页自行创建账号；无默认账户。喜欢、不喜欢、画像及向量随账号跨设备可用；助手历史与语言不跨设备同步。
账号切换、退出或检测到失效时清空私有内容，取消旧请求；页面加载、焦点恢复与业务操作刷新画像。

Startup upgrades Alembic before serving; ordering is PostgreSQL/Redis → API → web. Current head is
`0008_account_preferences`; `0007_accounts`/`0008_account_preferences` are additive to
`0006_recording_resolution`. The smoke uses two Cookie jars through the real Next proxy and tests
401 access, registration/login, shared preferences, different-account isolation, Agent JSON/SSE,
login-session isolation and logout. The PostgreSQL check tests concurrent feedback, vector equality
and untouched anonymous archives. Both scripts write uniquely named test accounts and fixture rows;
use a disposable offline environment. First image/package downloads still require network.

## Local administrator password reset / 本地管理员重置

```bash
# Interactive TTY required. Never pass a password as a CLI argument.
docker compose exec api python -m app.auth.reset USERNAME
# Or from services/api with the configured environment:
python -m app.auth.reset USERNAME
```

Enter and confirm the new password at hidden prompts. The CLI updates the hash and revokes all
account sessions in one transaction; it does not log passwords or tokens. No web admin endpoint.

必须在交互终端输入并确认新密码，输入隐藏；不可用命令行参数或管道传密码。重置后所有设备重新登录。

## Upgrade, backup and rollback / 升级、备份与回退

Before touching the existing database, create a PostgreSQL custom-format backup outside the repo
and verify restoration into a **separate** database. Stop serving old web/API traffic, validate
`0006_recording_resolution` → head, migration drift and a round-trip back to 0006 in that disposable
copy. Downgrade drops new account tables and is **only** an isolated validation operation.

```bash
# Use these only in the disposable verification Compose project:
docker compose exec -T api alembic downgrade 0006_recording_resolution
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic check
```

Deploy frontend and backend together; old anonymous clients are incompatible with authenticated
business routes. For rollback, enter a maintenance window and restore the verified pre-upgrade
application/database backup. Preserve a separate post-upgrade backup so new account data is not
silently discarded. Never downgrade a live database containing user accounts as a shortcut.
`docker compose down` retains data. Remove volumes only for an explicitly disposable test project.

部署前备份并验证独立库恢复；前后端同时切换。正式回退使用维护窗口与匹配的应用/数据库备份，
另存新增账号数据；不要直接删除正式账号表。现有匿名表、公共曲库和确定性排序策略保持原状。

## Production and manual development / 生产与手动开发

Production requires HTTPS termination, `APP_ENVIRONMENT=production`, `AUTH_COOKIE_SECURE=true`
and exact HTTPS `ALLOWED_ORIGINS`; unsafe production configuration fails startup. Public
`/docs`, `/redoc`, `/openapi.json` are disabled in production. Keep PostgreSQL/Redis internal;
provide routine backups and a retention policy for login-scoped chat and expired session rows.
This task does not configure a public domain, certificates or an external deployment.

生产必须启用 HTTPS 与 Secure Cookie，精确允许来源，关闭公开文档。数据库和 Redis 不暴露公网。
本次提供本地 Compose 与生产配置约束，不安装公网域名/证书，不新增会话清理或聊天历史管理功能。

For manual development, provision PostgreSQL/pgvector and Redis, install `.[dev,mcp]` in
`services/api`, set `DATABASE_URL`, `REDIS_URL`, development auth settings and allowed web Origin,
then run `python -m alembic upgrade head` and
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`.
In `apps/web`, set server-only `API_INTERNAL_URL=http://127.0.0.1:8000`, then `npm ci; npm run dev`.
SQLite is for tests only. Local stdio MCP keeps public music lookup without account preferences.

Model HTTPS verifies certificates against the system trust store. Keep verification enabled;
operator-reviewed CA installation may be needed on some networks. See [observability](OBSERVABILITY.md)
for safe event codes and correlation; never enable request/SQL/transport debug logs with credentials.

## Verification record / 验证记录

2026-10-06 local acceptance: 276 API and 67 web tests, static/build checks, legacy smoke and
unchanged evaluation pass. Existing 0006 backup restored into the isolated music-account-verify
project; upgrade/rollback/upgrade, empty-database migration, drift (including intentional vector
mismatch) and concurrent account writes pass. Original anonymous archives remain identical.
Real Redis 429/outage-503, Cookie/CSRF/SSE proxy and hidden-input CLI reset pass. Real Edge at
1440px/390px passes full registration/music/feedback/two-device/login/logout/change-password,
account/history isolation, keyboard/remember, Chinese layout, Unicode and automatic expiry checks.
Local services are updated at localhost:3000 with 0008 head and four healthy containers.
Backups/evidence are outside Git at the operator's local Codex backups directory; credentials
and existing provider/model configuration were preserved. Public HTTPS deployment was not performed. Historical 2026-10-02 main CI evidence belongs to its own commit, not this branch.
Image tags and transitive Python dependencies remain unlocked by digest/hash.


Dependency audit: source-map-js is patched to 1.2.2. `npm audit --omit=dev --audit-level=high`
has no findings. The full audit still reports the development ESLint glob chain's unpatched
[braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm); `npm run audit` allows only
that exact development-only chain and blocks every other high/critical finding (ADR-030).
完整审计仍有已记录的开发工具告警，不宣称零告警；不影响生产依赖审计，等待上游补丁后移除此例外。
