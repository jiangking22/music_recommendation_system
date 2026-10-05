from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.agent import router as agent_router
from app.api.discovery import router as discovery_router
from app.api.mcp import router as mcp_router
from app.api.middleware import RequestBodyLimit
from app.api.routes import router
from app.infrastructure.config import get_settings
from app.observability.events import RequestTelemetry, configure_logging, emit

settings = get_settings()
configure_logging()
app = FastAPI(title="Music Recommendation API", version="1.0.0")
app.add_middleware(RequestBodyLimit)
app.add_middleware(RequestTelemetry)
# CORS wraps early rejections and unexpected-error responses too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Device-Id", "Content-Type", "X-Request-Id", "traceparent"],
    expose_headers=["X-Request-Id", "X-Trace-Id"],
)
app.include_router(router)
app.include_router(agent_router)
app.include_router(discovery_router)
app.include_router(mcp_router)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, _error: RequestValidationError) -> JSONResponse:
    emit("request_error", code="validation_error", status=422)
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Invalid request."}})


@app.exception_handler(HTTPException)
async def http_error(_request: Request, error: HTTPException) -> JSONResponse:
    emit("request_error", code="http_error", status=error.status_code)
    return JSONResponse(status_code=error.status_code, content={"error": {"code": "http_error", "message": str(error.detail)}})


@app.exception_handler(SQLAlchemyError)
async def database_error(_request: Request, _error: SQLAlchemyError) -> JSONResponse:
    emit("request_error", code="database_unavailable", status=503)
    return JSONResponse(status_code=503, content={"error": {"code": "database_unavailable", "message": "Database unavailable."}})
