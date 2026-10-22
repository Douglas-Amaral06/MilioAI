import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx
import jwt
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.log_context import request_id_context
from app.db.session import database
from app.llm.ollama import Ollama
from app.orchestration.graph import build_graph
from app.storage.files import PrivateStorage


class JsonFormatter(logging.Formatter):
    def format(self, record):
        fields = {
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for key in (
            "request_id",
            "duration_ms",
            "agent",
            "chunk_count",
            "conversation_id",
            "domains",
            "intent_count",
            "domain",
            "stage",
            "outcome",
            "repair_attempt",
            "coverage",
            "error_type",
            "success",
            "status",
        ):
            if hasattr(record, key):
                fields[key] = getattr(record, key)
        return json.dumps(fields)


def create_app(settings=None):
    settings = settings or get_settings()
    logger = logging.getLogger("milioai")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    engine, sessions = database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            base_url=settings.ollama_url, timeout=settings.ollama_timeout, trust_env=False
        ) as client:
            app.state.ollama = Ollama(client, settings)
            app.state.graph = build_graph(sessions, app.state.ollama, settings)
            yield
        await engine.dispose()

    app = FastAPI(
        title="MilioAI",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.app_env == "production" else "/docs",
    )
    app.state.settings, app.state.sessions, app.state.engine = settings, sessions, engine
    app.state.storage = PrivateStorage(settings.storage_path)
    app.state.jwks = (
        jwt.PyJWKClient(settings.jwt_jwks_url, cache_keys=True, lifespan=300, timeout=10)
        if settings.auth_mode == "jwt"
        else None
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request_id_context.set(request_id)
        start = time.monotonic()
        # Enforce raw multipart/body limits before Starlette can spool arbitrary input.
        limit = (
            settings.upload_max_bytes + 65536
            if request.url.path.endswith("/attachments")
            else 65536
        )
        received = 0
        original_receive = request._receive

        async def limited_receive():
            nonlocal received
            event = await original_receive()
            received += len(event.get("body", b""))
            if received > limit:
                raise AppError(413, "request_too_large", "O envio excede o tamanho permitido.")
            return event

        request._receive = limited_receive
        try:
            if int(request.headers.get("content-length", "0")) > limit:
                response = JSONResponse(
                    {"code": "request_too_large", "message": "O envio excede o tamanho permitido."},
                    status_code=413,
                )
            else:
                response = await call_next(request)
        except Exception as error:
            logger.error(
                "request_failed",
                extra={"request_id": request_id, "error_type": type(error).__name__},
            )
            response = JSONResponse(
                {"code": "internal_error", "message": "Não foi possível concluir a solicitação."},
                status_code=500,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - start) * 1000),
            },
        )
        return response

    @app.exception_handler(AppError)
    async def controlled(request, error):
        return JSONResponse(
            {"code": error.code, "message": error.message}, status_code=error.status
        )

    @app.exception_handler(RequestValidationError)
    async def validation(request, error):
        return JSONResponse(
            {"code": "invalid_request", "message": "Verifique os dados enviados."}, status_code=422
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_error(request, error):
        logger.error(
            "database_failed",
            extra={"request_id": request.state.request_id, "error_type": type(error).__name__},
        )
        return JSONResponse(
            {
                "code": "database_unavailable",
                "message": "O armazenamento está temporariamente indisponível.",
            },
            status_code=503,
        )

    app.include_router(router)
    return app
