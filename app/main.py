"""Punto de entrada de la API.

La capa HTTP valida, delega y persiste. No compone etapas: eso es del
``LeafInspector``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.auth import AuthService
from app.config import Settings
from app.db.connection import check as database_answers
from app.errors import register_exception_handlers
from app.media import MediaCache
from app.media import router as media_router
from app.repository import InspectionRepository
from app.routers import auth as auth_router
from app.routers import inspections, reports
from app.routers import thresholds as thresholds_router
from app.routers import versions as versions_router
from app.schemas import ConfigOut, HealthOut
from app.security import require_user
from app.store import InspectionStore
from core import __version__
from core.orchestrator import LeafInspector
from core.pipeline import method_fingerprint

TITLE = "Fellowship · El Libro de las Hojas"
DESCRIPTION = "Análisis de superficie de hojas de tabaco con visión clásica."

logger = logging.getLogger("fellowship.main")


def build_store(settings: Settings) -> InspectionStore:
    """Elige la persistencia una sola vez (ADR-016).

    Con ``DATABASE_URL`` el registro vive en Postgres; sin ella, el almacén de
    archivos sigue siendo el camino de la demo y del desarrollo sin Docker.
    """
    if settings.uses_database:
        # Import perezoso: sin base configurada no hace falta el driver.
        from app.sql_repository import SqlInspectionRepository

        return SqlInspectionRepository(
            settings.database_url,
            use_pool=not settings.is_serverless,
        )
    return InspectionRepository(settings.storage_dir)


def build_auth(settings: Settings) -> AuthService | None:
    """Los usuarios viven en Postgres: sin base no hay login (ADR-017)."""
    if not settings.auth_required:
        return None
    return AuthService(
        settings.database_url,
        settings.secret_key,
        settings.session_hours,
        use_pool=not settings.is_serverless,
    )


def database_status(settings: Settings) -> str:
    if not settings.uses_database:
        return "archivos"
    return "ok" if database_answers(settings.database_url) else "sin conexión"


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    auth = build_auth(config)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        # El administrador inicial se crea una sola vez y nunca frena el arranque:
        # sin base, /api/health ya cuenta lo que pasa.
        if auth is not None:
            try:
                auth.bootstrap_admin(config.admin_username, config.admin_password)
            except Exception:  # pragma: no cover - depende del servidor
                logger.warning("No se pudo preparar el administrador inicial", exc_info=True)
        yield
        store = getattr(application.state, "repository", None)
        closer = getattr(store, "close", None)
        if callable(closer):
            closer()
        if auth is not None:
            auth.close()

    app = FastAPI(
        title=TITLE,
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.settings = config
    app.state.repository = build_store(config)
    app.state.auth = auth
    app.state.inspector = LeafInspector()
    app.state.method_version = method_fingerprint()
    app.state.media_cache = MediaCache(config.media_cache_size)

    # Con base, todo lo que no sea /api/health, /api/config ni el login exige
    # sesión (ADR-017). Sin base no hay usuarios: la demo queda abierta.
    guards = [Depends(require_user)] if config.auth_required else []

    register_exception_handlers(app)
    app.include_router(auth_router.router)
    app.include_router(inspections.router, dependencies=guards)
    app.include_router(reports.router, dependencies=guards)
    # El catálogo de umbrales es la única fuente de rangos de la pantalla
    # (ADR-022): se sirve antes de cualquier análisis.
    app.include_router(thresholds_router.router, dependencies=guards)
    app.include_router(versions_router.router, dependencies=guards)

    @app.get("/api/health", response_model=HealthOut, tags=["meta"], summary="Estado del servicio")
    def health() -> HealthOut:
        return HealthOut(
            status="ok",
            version=__version__,
            database=database_status(config),
        )

    @app.get("/api/config", response_model=ConfigOut, tags=["meta"], summary="Límites vigentes")
    def read_config() -> ConfigOut:
        return ConfigOut(
            max_upload_bytes=config.max_upload_bytes,
            allowed_formats=sorted(config.allowed_formats),
            auth_required=config.auth_required,
        )

    # Las imágenes del registro (ADR-016). Con base, las capas se regeneran bajo
    # demanda; con archivos, se sirven del disco como siempre y no se recalcula
    # nada.
    if config.uses_database:
        app.include_router(media_router, dependencies=guards)
    else:
        app.mount(
            "/media",
            StaticFiles(directory=str(config.storage_dir)),
            name="media",
        )

    if config.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(config.frontend_dir), html=True), name="frontend")

    return app


app = create_app()
