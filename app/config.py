"""Configuración de la API. Todo ``os.environ`` se lee acá y en ningún otro lado."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
VERCEL_MAX_UPLOAD_BYTES = 4 * 1024 * 1024
VERCEL_STORAGE_DIR = Path("/tmp/fellowship-storage")


@dataclass(frozen=True)
class Settings:
    storage_dir: Path
    frontend_dir: Path
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    allowed_formats: frozenset[str] = frozenset({"PNG", "JPEG"})

    def __post_init__(self) -> None:
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes debe ser positivo.")
        if not self.allowed_formats:
            raise ValueError("allowed_formats no puede estar vacío.")

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
        )
