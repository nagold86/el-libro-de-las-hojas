"""Validación del archivo subido antes de tocar el dominio.

Frodo gobierna esta frontera. Orden de controles: tamaño → decodificable →
formato permitido. Así un archivo enorme nunca se decodifica y un formato no
permitido nunca llega al pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from core.exceptions import InvalidImage, UploadTooLarge
from core.io import Photo, read_photo


@dataclass(frozen=True)
class Upload:
    filename: str
    content_type: str | None
    size_bytes: int
    photo: Photo


def read_upload(
    data: bytes,
    filename: str | None,
    content_type: str | None,
    settings: Settings,
) -> Upload:
    if not data:
        raise InvalidImage("El archivo está vacío.")
    if len(data) > settings.max_upload_bytes:
        raise UploadTooLarge(
            f"El archivo supera el máximo de {settings.max_upload_bytes // 1024} KB."
        )

    photo = read_photo(data)
    if photo.format not in settings.allowed_formats:
        allowed = ", ".join(sorted(settings.allowed_formats))
        raise InvalidImage(f"Formato {photo.format} no permitido. Se aceptan: {allowed}.")

    safe_name = Path(filename or "imagen").name[:120] or "imagen"
    return Upload(
        filename=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        photo=photo,
    )
