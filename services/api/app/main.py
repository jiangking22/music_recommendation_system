import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.routes import router
from app.infrastructure.config import get_settings

settings = get_settings()
logger = logging.getLogger("music_api")
app = FastAPI(title="Music Recommendation API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Device-Id", "Content-Type"],
)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, _error: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Invalid request."}})


@app.exception_handler(HTTPException)
async def http_error(_request: Request, error: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"error": {"code": "http_error", "message": str(error.detail)}})


@app.exception_handler(SQLAlchemyError)
async def database_error(_request: Request, _error: SQLAlchemyError) -> JSONResponse:
    logger.error(json.dumps({"event": "database_unavailable"}))
    return JSONResponse(status_code=503, content={"error": {"code": "database_unavailable", "message": "Database unavailable."}})
