"""compete API - FastAPI app over the DuckDB marts.

Run: ``uv run uvicorn api.main:app --reload`` (or ``compete-api``).
Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pipeline.config import get_settings
from pipeline.logging_setup import get_logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import marketing_store, research_store
from api.db import ApiDB
from api.routers import (
    analytics,
    assistant,
    competitors,
    marketing,
    pipeline,
    reports,
    research,
    signals,
)

log = get_logger("api")


def _autoseed_if_empty(db_path) -> None:
    """First boot on a fresh server (e.g. Emergent): seed demo data and build marts.

    Disabled with COMPETE_AUTOSEED=0. Runs before the API opens its DuckDB
    connection (file lock). Never blocks startup on failure.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    import duckdb

    if os.environ.get("COMPETE_AUTOSEED", "1") == "0":
        return
    try:
        con = duckdb.connect(str(db_path))
        try:
            exists = con.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='raw' AND table_name='competitors'"
            ).fetchone()[0]
            n = con.execute("SELECT count(*) FROM raw.competitors").fetchone()[0] if exists else 0
        finally:
            con.close()
        if n:
            return
        script = Path(__file__).resolve().parents[1] / "scripts" / "seed_demo.py"
        log.info("empty warehouse: seeding demo data and building marts (first boot)")
        root = str(script.parents[1])
        # The seed script imports `pipeline`; on hosts that install only
        # requirements.txt (Docker, Emergent) the repo root must be on the path.
        env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONPATH": os.pathsep.join(p for p in (root, os.environ.get("PYTHONPATH", "")) if p),
        }
        subprocess.run(
            [sys.executable, str(script), "--build"], check=False, timeout=900, env=env, cwd=root
        )
    except Exception as exc:  # pragma: no cover - startup must not fail
        log.warning("autoseed skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.ensure_dirs()
    _autoseed_if_empty(settings.duckdb_path)
    app.state.db = ApiDB(settings.duckdb_path)
    research_store.bootstrap(app.state.db)
    marketing_store.bootstrap(app.state.db)
    log.info("API connected to warehouse at %s", settings.duckdb_path)
    try:
        yield
    finally:
        app.state.db.close()


app = FastAPI(
    title="compete API",
    version="0.2.0",
    description="Competitive Intelligence Platform - typed read API over the DuckDB marts.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,  # "*" allowed for hosted previews
    allow_credentials="*" not in get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------- consistent error envelopes ----------------------- #
def _envelope(type_: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"type": type_, "message": message}})


@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _envelope("http_error", str(exc.detail), exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _envelope("validation_error", str(exc.errors()), 422)


@app.exception_handler(Exception)
async def unhandled_exc_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error")
    return _envelope("internal_error", "An unexpected error occurred.", 500)


@app.get("/api/health", include_in_schema=False)
@app.get("/health", tags=["meta"])
def health(request: Request) -> dict:
    from pipeline.config import Settings

    from api import llm_settings

    db = getattr(request.app.state, "db", None)
    try:
        mode = llm_settings.load(Settings()).get("mode") or "off"
    except Exception:
        mode = "unknown"
    from api import guard

    return {"status": "ok", "version": app.version, "llm_mode": mode, "public_mode": guard.public_mode(),
            "snapshots": marketing_store.counts(db) if db else {}}


for r in (
    competitors.router, signals.router, analytics.router, reports.router, pipeline.router,
    research.router, assistant.router, marketing.router,
):
    app.include_router(r)
    # Hosted deployments (e.g. Emergent) route /api/* to the backend without
    # stripping the prefix, so every route is also served under /api.
    app.include_router(r, prefix="/api", include_in_schema=False)


def main() -> None:
    """Console entrypoint: ``compete-api``."""
    import uvicorn

    settings = get_settings()
    uvicorn.run("api.main:app", host=settings.api_host, port=settings.api_port, reload=False)


if __name__ == "__main__":
    main()
