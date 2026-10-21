"""Punto de entrada de la API.

La capa HTTP valida, delega y persiste. No compone etapas: eso es del
``LeafInspector``.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.errors import register_exception_handlers
from app.repository import InspectionRepository
from app.routers import inspections, reports
from app.schemas import ConfigOut, HealthOut
from core import __version__
from core.orchestrator import LeafInspector

TITLE = "Fellowship · El Libro de las Hojas"
DESCRIPTION = "Análisis de superficie de hojas de tabaco con visión clásica."


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    app = FastAPI(title=TITLE, version=__version__, description=DESCRIPTION)
    app.state.settings = config
    app.state.repository = InspectionRepository(config.storage_dir)
    app.state.inspector = LeafInspector()

    register_exception_handlers(app)
    app.include_router(inspections.router)
    app.include_router(reports.router)

    @app.get("/api/health", response_model=HealthOut, tags=["meta"], summary="Estado del servicio")
    def health() -> HealthOut:
        return HealthOut(status="ok", version=__version__)

    @app.get("/api/config", response_model=ConfigOut, tags=["meta"], summary="Límites vigentes")
    def read_config() -> ConfigOut:
        return ConfigOut(
            max_upload_bytes=config.max_upload_bytes,
            allowed_formats=sorted(config.allowed_formats),
        )

    app.mount("/media", StaticFiles(directory=str(config.storage_dir)), name="media")
    if config.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(config.frontend_dir), html=True), name="frontend")

    return app


app = create_app()
