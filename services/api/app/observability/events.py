import json
import logging
import re
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

_context: ContextVar[dict | None] = ContextVar("telemetry_context", default=None)
_fields = {"method", "status", "latency_ms", "provider", "model", "operation", "tool",
           "code", "error_type", "result_count", "candidate_count", "source_count",
           "failed_sources", "personalized", "prompt_tokens", "completion_tokens", "total_tokens", "stage"}


def configure_logging() -> None:
    logger = logging.getLogger("music_api")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)  # stdout is reserved for MCP JSON-RPC.
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # SDK/root handlers must not duplicate JSON events.
    # HTTP client debug logs can include query strings and sensitive payloads.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.CRITICAL)


def request_id() -> str:
    return (_context.get() or {}).get("request_id", uuid4().hex)


def correlation_headers() -> dict[str, str]:
    context = _context.get() or {}
    if not context:
        return {}
    return {"X-Request-Id": context["request_id"],
            "traceparent": f"00-{context['trace_id']}-{uuid4().hex[:16]}-01"}


@contextmanager
def tool_correlation():
    token = _context.set({"request_id": uuid4().hex, "trace_id": uuid4().hex})
    try:
        yield
    finally:
        _context.reset(token)


def emit(event: str, *, level: int = logging.INFO, **fields) -> None:
    context = _context.get() or {}
    route = context.get("scope", {}).get("route")
    record = {"timestamp": datetime.now(UTC).isoformat(), "level": logging.getLevelName(level),
              "event": event, "request_id": context.get("request_id"),
              "trace_id": context.get("trace_id"), "route": getattr(route, "path", "unmatched")}
    record.update({key: value for key, value in fields.items() if key in _fields
                   and (value is None or isinstance(value, (str, bool, int, float)))})
    logging.getLogger("music_api").log(level, json.dumps(record, ensure_ascii=False))


class RequestTelemetry:
    """Pure ASGI middleware keeps correlation alive through the last SSE frame."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        supplied = headers.get("x-request-id", "")
        correlation = supplied if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", supplied) else uuid4().hex
        parent = re.fullmatch(r"00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}",
                              headers.get("traceparent", ""))
        trace = parent[1] if parent and int(parent[1], 16) and int(parent[2], 16) else uuid4().hex
        token = _context.set({"request_id": correlation, "trace_id": trace, "scope": scope})
        started, status, sent = perf_counter(), 500, False

        async def response_send(message):
            nonlocal status, sent
            if message["type"] == "http.response.start":
                status, sent = message["status"], True
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-Id"] = correlation
                response_headers["X-Trace-Id"] = trace
                response_headers["X-Content-Type-Options"] = "nosniff"
                if scope["path"].startswith("/v1/"):
                    response_headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, response_send)
        except Exception as error:
            emit("request_error", level=logging.ERROR, code="internal_error", error_type=type(error).__name__)
            if sent:
                raise
            await JSONResponse(status_code=500, content={"error": {
                "code": "internal_error", "message": "Service unavailable."}})(scope, receive, response_send)
        finally:
            emit("http_request", method=scope["method"], status=status,
                 latency_ms=round((perf_counter() - started) * 1000, 3))
            _context.reset(token)
