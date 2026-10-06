from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from app.api.discovery import router as discovery_router
from app.api.mcp import router as mcp_router
from app.api.middleware import RequestBodyLimit
from app.api.recordings import router as recordings_router
from app.api.routes import router
from app.auth.service import AuthError
from app.infrastructure.config import get_settings
from app.observability.events import RequestTelemetry, configure_logging, emit

settings = get_settings()
configure_logging()
if settings.app_environment == "production" and (not settings.auth_cookie_secure or
        any(not origin.startswith("https://") for origin in settings.allowed_origins_list)):
    raise ValueError("Production requires secure auth cookies and HTTPS origins")
app = FastAPI(title="Music Recommendation API", version="1.0.0",
              docs_url=None if settings.app_environment == "production" else "/docs",
              redoc_url=None if settings.app_environment == "production" else "/redoc",
              openapi_url=None if settings.app_environment == "production" else "/openapi.json")
app.add_middleware(RequestBodyLimit)
app.add_middleware(RequestTelemetry)
# CORS wraps early rejections and unexpected-error responses too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Device-Id", "Content-Type", "X-CSRF-Token", "X-Session-Id", "X-Request-Id", "traceparent"],
    allow_credentials=True,
    expose_headers=["X-Request-Id", "X-Trace-Id"],
)
app.include_router(router)
app.include_router(agent_router)
app.include_router(discovery_router)
app.include_router(mcp_router)
app.include_router(recordings_router)
app.include_router(auth_router)


@app.exception_handler(AuthError)
async def auth_error(_request: Request, error: AuthError) -> JSONResponse:
    emit("auth_event", operation="request", status="error", code=error.code)
    return JSONResponse(status_code=error.status,
                        content={"error": {"code": error.code, "message": error.message}},
                        headers={"Cache-Control": "no-store", **({"Retry-After": str(error.retry_after)}
                                 if error.retry_after else {})})


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
