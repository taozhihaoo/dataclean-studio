"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import (
    error_handlers,
    routes_files,
    routes_inference,
    routes_jobs,
    routes_output,
    routes_processing,
)
from app.config import get_settings
from app.db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.ensure_dirs()
    init_db()
    logger.info("DataClean Studio %s ready (data dir: %s)", __version__, settings.data_dir)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="DataClean Studio",
        description="CSV / Excel data cleaning and transformation tool.",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # local-first tool; frontend runs on a dev port
        allow_methods=["*"],
        allow_headers=["*"],
    )
    error_handlers.register_exception_handlers(app)
    app.include_router(routes_files.router)
    app.include_router(routes_jobs.router)
    app.include_router(routes_processing.router)
    app.include_router(routes_output.router)
    app.include_router(routes_inference.router)

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    if (STATIC_DIR / "index.html").exists():
        # Serve the built SPA: real files by name, everything else falls
        # back to index.html so client-side routes like /jobs/<id> work.
        # A missing static file must never swallow API 404s (mounted below
        # the API routers, and /api/* paths keep the JSON error shape).
        from fastapi.responses import FileResponse

        @app.get("/{asset_path:path}", include_in_schema=False)
        async def spa_fallback(asset_path: str) -> FileResponse:
            if asset_path.startswith("api/") or asset_path == "health":
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Not Found")
            candidate = (STATIC_DIR / asset_path).resolve()
            if candidate.is_file() and str(candidate).startswith(str(STATIC_DIR.resolve())):
                return FileResponse(candidate)
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
