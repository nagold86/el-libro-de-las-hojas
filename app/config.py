"""Configuración de la API. Todo ``os.environ`` se lee acá y en ningún otro lado."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
VERCEL_MAX_UPLOAD_BYTES = 4 * 1024 * 1024
VERCEL_STORAGE_DIR = Path("/tmp/fellowship-storage")
DEFAULT_MEDIA_CACHE_SIZE = 8
DEFAULT_SESSION_HOURS = 12


@dataclass(frozen=True)
class Settings:
    storage_dir: Path
    frontend_dir: Path
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    allowed_formats: frozenset[str] = frozenset({"PNG", "JPEG"})
    # Cadena de conexión a Postgres (ADR-016). Vacía = almacén de archivos.
    database_url: str = ""
    # Cuántos registros completos se recuerdan para no regenerar sus capas.
    media_cache_size: int = DEFAULT_MEDIA_CACHE_SIZE
    # En serverless cada invocación es un proceso nuevo: no conviene un pool.
    is_serverless: bool = False
    # Login (ADR-017). La clave firma la cookie de sesión; el administrador
    # inicial solo se crea si la tabla de usuarios está vacía.
    secret_key: str = ""
    admin_username: str = ""
    admin_password: str = ""
    session_hours: int = DEFAULT_SESSION_HOURS

    def __post_init__(self) -> None:
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes debe ser positivo.")
        if self.media_cache_size < 0:
            raise ValueError("media_cache_size no puede ser negativo.")
        if not self.allowed_formats:
            raise ValueError("allowed_formats no puede estar vacío.")
        if self.session_hours <= 0:
            raise ValueError("session_hours debe ser positivo.")

    @property
    def uses_database(self) -> bool:
        return bool(self.database_url)

    @property
    def auth_required(self) -> bool:
        """Los usuarios viven en Postgres: sin base no hay login (ADR-017)."""
        return self.uses_database

    @classmethod
    def from_env(cls) -> "Settings":
        # En Vercel el disco del proyecto es de solo lectura y solo /tmp es
        # escribible; además el cuerpo de una función está limitado a 4,5 MB.
        on_vercel = bool(os.environ.get("VERCEL"))
        default_storage = VERCEL_STORAGE_DIR if on_vercel else PROJECT_ROOT / "storage"
        default_max_bytes = VERCEL_MAX_UPLOAD_BYTES if on_vercel else DEFAULT_MAX_UPLOAD_BYTES
        storage = Path(os.environ.get("FELLOWSHIP_STORAGE_DIR", default_storage))
        frontend = Path(os.environ.get("FELLOWSHIP_FRONTEND_DIR", PROJECT_ROOT / "frontend"))
        max_bytes = int(
            os.environ.get("FELLOWSHIP_MAX_UPLOAD_BYTES", str(default_max_bytes))
        )
        formats = frozenset(
            item.strip().upper()
            for item in os.environ.get("FELLOWSHIP_ALLOWED_FORMATS", "PNG,JPEG").split(",")
            if item.strip()
        )
        return cls(
            storage_dir=storage,
            frontend_dir=frontend,
            max_upload_bytes=max_bytes,
            allowed_formats=formats,
            database_url=os.environ.get("DATABASE_URL", "").strip(),
            media_cache_size=int(
                os.environ.get("FELLOWSHIP_MEDIA_CACHE_SIZE", str(DEFAULT_MEDIA_CACHE_SIZE))
            ),
            is_serverless=on_vercel,
            secret_key=os.environ.get("FELLOWSHIP_SECRET_KEY", "").strip(),
            admin_username=os.environ.get("FELLOWSHIP_ADMIN_USER", "").strip(),
            admin_password=os.environ.get("FELLOWSHIP_ADMIN_PASSWORD", ""),
            session_hours=int(
                os.environ.get("FELLOWSHIP_SESSION_HOURS", str(DEFAULT_SESSION_HOURS))
            ),
        )
