# Observability / 轻量可观测性

## Operational questions / 要回答的问题

1. Which route is slow or failing? / 哪个接口慢或失败？
2. Which music provider failed, and did recommendations degrade? / 来源失败是否造成降级？
3. Which tools/model did the Agent use and how long did each take? / Agent 时间花在哪里？
4. Can an error be traced without reading private content? / 能否不看聊天内容定位错误？

## Event contract / 事件契约

`music_api` emits one JSON object per line to **stderr**. No Prometheus, Grafana, tracing collector,
OTel SDK or stored telemetry database is required. This is lightweight correlation, not a complete
distributed tracing system. Logs can be collected by the host; no alerting/aggregation service ships.

| Event | Safe fields / 字段 |
| --- | --- |
| `http_request` | method, route template, HTTP status, latency_ms through final SSE frame |
| `request_error` | stable error code/status; unexpected exception class only |
| `provider_call` | provider, operation, status, code, latency_ms, capped result_count |
| `recommendation` | candidate_count, result_count, source_count, failed_sources, personalized, latency_ms |
| `agent_tool` | allowlisted tool name, status, latency_ms |
| `llm_call` | provider, configured model, operation plan/answer, status, latency_ms; optional token counts |
| `agent_error` / `agent_failed` | stable code and status |
| `auth_event` | operation and safe status only; no username, password, Cookie or token |
| `mcp_tool` | read-only tool name, status, latency_ms |

All events include timestamp, level, request_id, trace_id and route. Correlation from a valid
`X-Request-Id` (1–64 ASCII letters/digits/underscore/hyphen) and W3C v00 `traceparent` is accepted;
otherwise fresh hex IDs are generated. Invalid/zero trace IDs are regenerated. Responses expose
`X-Request-Id` and `X-Trace-Id` through CORS; the recommendation body uses the same request ID.
Provider and LLM HTTP calls forward a safe request ID and traceparent. ContextVars propagate into
FastAPI threads, async work and shielded worker threads. IDs reset after each response.
CORS preflight is handled outside application telemetry; application requests and early errors
remain correlated. / CORS 预检由外层中间件处理，业务请求及早期错误仍带关联信息。

不匹配路由只记录 `unmatched`，避免泄露任意路径/查询。MCP 每次工具调用生成独立关联 ID，route 为
`unmatched`（它没有 HTTP 路由）；业务层直接离线调用可能没有请求 ID。纯 stdio stdout 只输出协议消息。

Optional provider usage logs allow only integer `prompt_tokens`, `completion_tokens`, `total_tokens`
between 0 and 1e9. Missing/malformed counts are omitted; no estimates are invented. Local routing
is marked `provider=local`, `model=rule-router`, with no token counts because it is not a model.

## Redaction and boundaries / 脱敏边界

Events use an explicit field allowlist and log aggregates instead of payloads. No seed, query,
account/session/device/conversation identifier, password, Cookie/CSRF/session token, chat/history, LLM prompt/answer, tool arguments, provider payload,
API key, Authorization header, raw URL or exception message is emitted. `httpx`/`httpcore` logs are
suppressed; the documented Uvicorn command disables access logs (which otherwise contain query URLs).
Do not enable transport debug logging or SQL echo when collecting private traffic.

字段白名单只保留必要元数据。未知异常返回通用错误；验证错误不回显输入。请求体限制为 64 KiB，
读取期限 10 秒；Provider 4 秒、有界结果、无重试；模型 HTTP 10 秒、64 KiB 响应、1200 输出 token；
Agent 默认整轮 30 秒（1–60 可配）、四个并发和四个工作槽。SSE 错误发生在 HTTP 200 之后，需看
`agent_error` 和流中的 `error` 事件，不能只统计 HTTP 状态。

## Read and diagnose / 查看与定位

```bash
docker compose logs --no-log-prefix api
# Manual runtime: python -m uvicorn app.main:app --no-access-log 2> api-events.log
```

Locate the response request ID, filter JSON events by that ID, then compare provider/tool durations
and stable error codes. Use the latency samples to calculate percentiles and count statuses offline;
there is no in-process histogram endpoint. / 按 ID 串联事件，以单次耗时样本计算分位数、以状态计算错误率。

| Symptom / 现象 | Next check / 排查 |
| --- | --- |
| source errors but HTTP 200 | `provider_call` code; local recommendation counts / 上游降级 |
| Agent error with SSE HTTP 200 | `agent_error` and final SSE error / 流终止原因 |
| `agent_busy` | active request/worker saturation; retry after current work / 有界并发 |
| `agent_timeout` | provider/tool durations; synchronous jobs may still finish / 超时后工作可能完成 |
| `auth_rate_limited` / `auth_unavailable` | Retry-After; Redis availability/source bucket / 认证限流与 Redis |
| `database_unavailable` | readiness, migration/startup and DB connectivity / 数据库依赖 |
| invalid model output | inspect mocked fixture validation first; never log full private payload / 模型结构校验 |

Validation: correlation and no-private-content tests cover HTTP, unknown routes, Provider errors,
SSE/tool/thread work and LLM usage. A forced unexpected error proves safe JSON and content-free logs.
Real model telemetry and a hosted aggregation/alerting pipeline remain unverified/unimplemented.
