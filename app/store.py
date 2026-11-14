"""Contrato de persistencia de inspecciones (ADR-016).

Dos implementaciones lo cumplen: el almacén de archivos (``app/repository.py``)
y el registro en Postgres (``app/sql_repository.py``). ``create_app`` elige una
sola vez y el resto del código no sabe cuál está activa.

La firma de ``save`` admite todo lo que produce el pipeline —original, overlay y
capas— porque el almacén de archivos escribe los tres. El registro en base
guarda solo el original y regenera el resto bajo demanda, que es determinista.

Semántica común:
- ``save`` devuelve el registro completo, con ``id`` y URLs incluidas.
- ``list`` ordena por ``created_at`` descendente y acepta ``limit``/``offset`` más
  los filtros del historial (ADR-017): ``app_version`` exacta, ``owner`` por
  nombre de usuario, ventana ``since``/``until`` y ``query`` sobre el nombre de
  archivo. ``unassigned`` pide solo las hojas **sin cuenta detrás** (ADR-018):
  en archivos, las que no traen ``owner`` en el payload; en la base, las que
  quedaron con ``user_id`` en NULL porque su usuario se dio de baja.
- ``clear`` borra todo, o solo lo de un ``owner``, o solo las ``unassigned``, y
  devuelve cuántas hojas eliminó (ADR-018).
- ``versions`` resume las versiones del software con cuántas hojas midió cada
  una; en archivos se agrega al vuelo.
- ``get``, ``delete`` y ``original_bytes`` lanzan ``InspectionNotFound`` si el
  registro no existe o el identificador no tiene el formato permitido. El
  dueño no se filtra acá: el alcance por usuario lo decide la API (ADR-018).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
LAYER_SUFFIX = "-layer-{key}.png"


def record_id() -> str:
    """Identificador nuevo, con el mismo formato que ya publican las URLs."""
    return uuid4().hex


def media_urls(
    identifier: str, layer_keys: Iterable[str], media_prefix: str = "/media"
) -> dict[str, Any]:
    """URLs del registro, recalculadas al leer.

    Guardar solo claves —y no URLs— permite cambiar el prefijo sin migrar datos.
    """
    prefix = media_prefix.rstrip("/")
    return {
        "result_url": f"{prefix}/{identifier}-result.png",
        "original_url": f"{prefix}/{identifier}-original.png",
        "layer_urls": {
            key: f"{prefix}/{identifier}" + LAYER_SUFFIX.format(key=key)
            for key in layer_keys
        },
    }


@runtime_checkable
class InspectionStore(Protocol):
    """Lo que la API necesita de una persistencia para funcionar."""

    media_prefix: str

    def save(
        self,
        original_png: bytes,
        result_png: bytes,
        payload: dict[str, Any],
        layers: Iterable[tuple[str, bytes]] = (),
    ) -> dict[str, Any]: ...

    def get(self, identifier: str) -> dict[str, Any]: ...

    def update(
        self,
        record: dict[str, Any],
        *,
        result_png: bytes | None = None,
        layers: Iterable[tuple[str, bytes]] | None = None,
    ) -> dict[str, Any]: ...

    def list(
        self,
        limit: int | None = None,
        offset: int = 0,
        *,
        app_version: str | None = None,
        owner: str | None = None,
        unassigned: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def versions(self) -> list[dict[str, Any]]: ...

    def delete(self, identifier: str) -> None: ...

    def clear(
        self,
        *,
        owner: str | None = None,
        unassigned: bool = False,
    ) -> int: ...

    def original_bytes(self, identifier: str) -> bytes: ...
