# Deployment and clean start / 部署与启动验收

## Supported runtime / 支持环境

Python 3.12; Node.js 24/npm 11; PostgreSQL 16 with pgvector; Redis 7; Docker Compose v2.
The reference setup is local Compose. Web/API bind to loopback on ports 3000/8000; database and
Redis are internal. This is a portfolio demo without authentication, not a public multi-tenant service.

参考运行环境为本地 Compose。无认证的匿名标识不提供安全隔离；公开部署需要入口认证、HTTPS、
限流、备份和聊天保留/删除策略，这些不在当前实现范围。

## Configure / 配置

Copy `.env.example` to `.env` at repository root. Replace `POSTGRES_PASSWORD` and its matching
value in `DATABASE_URL`. Use a URL-safe password or percent-encode it in the URL. Template names
`postgres` and `redis` resolve inside Compose only. Never commit `.env` or keys.

复制模板，设置密码并同步连接 URL；密码若有 URL 保留字符需编码。模板主机名仅用于容器网络。
`ENABLE_MUSIC_PROVIDERS=false` disables all outbound music requests for an offline catalog demo.
`ENABLE_QQ_PROVIDER` takes effect only when music providers are enabled. `LLM_PROVIDER=local`
is the deterministic default. `openai_compatible` with no Key falls back to local; a failing real
model with a Key returns a safe error, not a fabricated local answer.

`NEXT_PUBLIC_API_BASE_URL` is a web **build-time**, browser-reachable URL, not the internal API
service name. `ALLOWED_ORIGINS` is a comma-separated explicit origin list; default localhost:3000.
Container LLM credentials are read only by the API. / 浏览器 URL 需构建时配置；密钥仅进入 API 容器。

## Start and acceptance / 启动与验收

For a fresh clone with no existing volumes / 新克隆且没有旧数据卷：

```bash
docker compose config --quiet
docker compose up --build --wait --wait-timeout 180
# With ENABLE_MUSIC_PROVIDERS=false and LLM_PROVIDER=local:
docker compose exec -T api python scripts/docker_smoke.py
docker compose exec -T api alembic current
docker compose exec -T api alembic check
```

The API runs `alembic upgrade head` before Uvicorn. Health ordering is PostgreSQL/Redis → API → web.
The smoke checks revision 0005, pgvector extension and a real cosine query, four seeded RAG chunks,
Redis ping, readiness, both web pages, recommendations, feedback/profile/personalized result,
local Agent/RAG and persisted follow-up conversation. It writes an isolated `smoke_...` device
and a fixture embedding to the local database. It makes no external business calls in offline mode.

迁移失败会阻止 API 启动。验收脚本覆盖真实数据库向量查询与业务链路，会写入独立 smoke 设备记录。
脚本必须在禁用音乐外网且启用本地助手的环境运行。Dependency/package/image downloads still need network
on first build; “offline” here means no music/LLM business API calls.

Inspect logs / 排错：

```bash
docker compose ps
docker compose logs --tail 100 api
docker compose logs --tail 100 web
```

JSON event codes and request IDs identify provider failures and deadlines. See [observability](OBSERVABILITY.md).
A port conflict requires changing host mappings and rebuilding the browser API URL accordingly.

## Manual services / 不使用 Docker 的开发运行

Provision PostgreSQL/pgvector and Redis yourself. Run the following from `services/api`, after
creating/activating `.venv` and installing `python -m pip install -e '.[dev,mcp]'`:

```powershell
$env:DATABASE_URL='postgresql+psycopg://music:YOUR_URL_ENCODED_PASSWORD@localhost:5432/music_recommendation'
$env:REDIS_URL='redis://localhost:6379/0'
$env:ENABLE_MUSIC_PROVIDERS='false'
$env:LLM_PROVIDER='local'
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second shell at `apps/web`: `npm ci`, `npm run dev`. Bash users use `export NAME=value`
in place of PowerShell `$env:NAME=...`. SQLite tests are not a replacement for target PostgreSQL;
no PostgreSQL server is required for pytest or the offline MCP stdio demo.

## Stop, reset, rollback / 停止与回退

`docker compose down` stops the stack and keeps data. Only for your disposable demo project,
`docker compose down --volumes` removes its database/Redis data permanently; back up valued data first.
For a separate clean project use a distinct `COMPOSE_PROJECT_NAME`, avoiding unrelated stacks.

停止保留数据；删除卷仅用于可丢弃演示环境。CI 使用每次运行独有项目名与随机密码，结束后删除自己的卷。
数据库回退有 downgrade SQL，但会删除相关表；部署回退优先恢复已备份数据库和匹配的代码版本。
上述命令仅启动本地环境，不会部署到公网。

## Verification status / 验证状态

Author Windows host, 2026-09-30: **Docker CLI absent, clean start not executed / 未实机执行**.
Static Compose topology/environment/health dependencies, Dockerfiles/build boundaries, editable
install/wheel assets, and complete offline PostgreSQL upgrade/downgrade SQL were checked locally.
These do not prove container or PostgreSQL runtime success.

[GitHub Actions](../.github/workflows/ci.yml) runs a fresh stack and the smoke on an Ubuntu Docker
host. Refer to the actual workflow run and commit SHA for remote runtime evidence; the author's
local absence of Docker remains a separate fact. Image tags and transitive Python packages are
not locked by digest/hash, so this setup is reproducible at the command level, not fully hermetic.
