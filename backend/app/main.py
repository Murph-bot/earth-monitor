from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import ConnectionPool

from app.api.errors import install_handlers
from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.logging import configure_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # autocommit=True so conn.transaction() blocks are real commits —
    # the same transaction model the ingest pipeline uses.
    # check_connection on checkout: serverless Postgres (Neon) drops idle
    # conns when compute suspends — a stale pooled conn must not reach a
    # request. Cheap: the check is skipped for recently-used connections.
    pool = ConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=8,
        kwargs={"autocommit": True},
        check=ConnectionPool.check_connection,
        open=False,
    )
    pool.open()
    app.state.pool = pool
    if settings.environment == "prod" and settings.jwt_secret.startswith("dev-secret"):
        logger.warning("jwt_secret_is_default")  # set EM_JWT_SECRET
    logger.info("app_started", environment=settings.environment)
    yield
    pool.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.environment)

    app = FastAPI(
        title="earth-monitor API",
        version="0.1.0",
        lifespan=lifespan,
    )
    install_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(v1_router, prefix="/v1")
    return app


app = create_app()
