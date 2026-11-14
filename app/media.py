"""Imágenes de un registro: el original sale de la persistencia y el resto se
regenera (ADR-016).

El registro guarda un solo PNG —el original— y publica URLs para el overlay y
sus capas. Este módulo las produce cuando alguien las pide, reusando el mismo
pipeline: como es determinista, la imagen servida coincide con la que se vio al
crear el registro. El resultado se recuerda en memoria del proceso para no
recalcular en cada recarga; en serverless la caché vive lo que vive la instancia.

El pipeline con el que se rehace no es siempre el de la aplicación: si el
registro se creó con umbrales movidos, el mismo PNG del overlay exige el mismo
ajuste. El registro guarda lo que se movió y acá se vuelve a armar el inspector
(ADR-022); sin ajustes se usa el de la aplicación y no se paga nada.

Con login activo, la descarga también respeta el dueño: la imagen de una hoja
ajena responde 404 igual que una inexistente (ADR-018).
"""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.security import can_see, current_user
from core.exceptions import InspectionNotFound, InvalidTuning
from core.io import encode_png, read_photo
from core.layers import LAYER_KEY_PATTERN
from core.manual_annotations import apply_manual_annotations
from core.orchestrator import LeafInspector
from core.pipeline import build_pipeline
from core.render import render_overlay, to_rgb
from core.tuning import Tuning

logger = logging.getLogger("fellowship.media")

router = APIRouter(tags=["media"])

PNG_MEDIA_TYPE = "image/png"
CACHE_HEADER = {"Cache-Control": "private, max-age=300"}

# Tres formas de nombre, todas ya publicadas en ``layer_urls`` y compañía.
FILENAME = re.compile(
    r"^(?P<id>[a-zA-Z0-9_-]{1,64})"
    r"(?P<kind>-original\.png|-result\.png|-layer-(?P<key>[a-z0-9_]{3,41})\.png)$"
)


@dataclass(frozen=True)
class RenderedRecord:
    """Los PNG de un registro ya regenerados."""

    result: bytes
    layers: dict[str, bytes] = field(default_factory=dict)


def render(
    original_png: bytes,
    inspector: LeafInspector,
    manual_annotations: dict[str, Any] | None = None,
) -> RenderedRecord:
    """Vuelve a correr el pipeline sobre el original guardado."""
    photo = read_photo(original_png)
    result = inspector.inspect(photo.image)
    strokes = (manual_annotations or {}).get("strokes") or []
    if strokes:
        result = apply_manual_annotations(
            result,
            strokes,
            inspector.pipeline.measurer,
            inspector.pipeline.describer,
        )
    # Anotado, igual que al crear el registro: el overlay guardado y el servido
    # tienen que ser el mismo PNG (ADR-019).
    overlay = render_overlay(
        result.image,
        result.lesion_mask,
        result.vein_mask,
        chlorosis_mask=result.chlorosis_mask,
        annotate=True,
    )
    layers: dict[str, bytes] = {}
    for layer in result.layers:
        layers[layer.key] = encode_png(to_rgb(layer.image))
    return RenderedRecord(result=encode_png(overlay), layers=layers)


def inspector_for(request: Request, record: dict[str, Any]) -> LeafInspector:
    """Inspector con el que se midió el registro, no el que corra hoy.

    Lo guardado es solo lo movido (``trace.tuning``). Si ese ajuste ya no se
    puede reconstruir —un parámetro que se retiró del catálogo, un valor que
    ahora cae fuera de rango— se avisa y se cae al defecto: una imagen vieja no
    puede dejar la descarga en error.
    """
    trace = record.get("trace") or {}
    method = str(trace.get("analysis_method") or "core")
    try:
        tuning = Tuning.from_public(trace.get("tuning")).validate_for_method(method)
    except InvalidTuning:
        logger.warning(
            "Umbrales guardados fuera de catálogo en %s; se usa el defecto",
            record.get("id"),
            exc_info=True,
        )
        tuning = Tuning()
    if tuning.is_default() and method == "core":
        return request.app.state.inspector
    return LeafInspector(
        pipeline=build_pipeline(tuning.to_settings(), segmentation_method=method)
    )


class MediaCache:
    """Últimos registros vistos, en memoria y con expulsión FIFO."""

    def __init__(self, size: int) -> None:
        self._size = max(0, int(size))
        self._items: OrderedDict[str, RenderedRecord] = OrderedDict()

    def get(self, identifier: str) -> RenderedRecord | None:
        rendered = self._items.get(identifier)
        if rendered is not None:
            self._items.move_to_end(identifier)
        return rendered

    def put(self, identifier: str, rendered: RenderedRecord) -> None:
        if self._size == 0:
            return
        self._items[identifier] = rendered
        self._items.move_to_end(identifier)
        while len(self._items) > self._size:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)

    def rendered(
        self,
        identifier: str,
        original_png: bytes,
        inspector: LeafInspector,
        manual_annotations: dict[str, Any] | None = None,
    ) -> RenderedRecord:
        cached = self.get(identifier)
        if cached is not None:
            return cached
        produced = render(original_png, inspector, manual_annotations)
        self.put(identifier, produced)
        return produced


def _png(data: bytes) -> Response:
    return Response(content=data, media_type=PNG_MEDIA_TYPE, headers=CACHE_HEADER)


def _not_found(message: str, code: str = "MEDIA_NOT_FOUND") -> HTTPException:
    return HTTPException(status_code=404, detail={"code": code, "message": message})


@router.get(
    "/media/{filename}",
    summary="Imagen de un registro: original guardada o capa regenerada",
)
def media(filename: str, request: Request) -> Response:
    match = FILENAME.match(filename)
    if match is None:
        raise _not_found(f"No hay ninguna imagen con ese nombre: {filename!r}.")

    identifier = match.group("id")
    key = match.group("key")

    if key is not None and not LAYER_KEY_PATTERN.fullmatch(key):
        raise _not_found(f"Clave de capa inválida: {key!r}.")

    store = request.app.state.repository
    user = current_user(request)
    # El registro se pide siempre: antes solo hacía falta para el alcance, ahora
    # también para saber con qué umbrales regenerar.
    try:
        record = store.get(identifier)
    except InspectionNotFound as exc:
        raise _not_found(str(exc), code="INSPECTION_NOT_FOUND") from exc
    if not can_see(record, user):
        # Mismo mensaje que un identificador desconocido: no se delata que existe.
        raise _not_found(f"No existe la inspección {identifier}.", code="INSPECTION_NOT_FOUND")

    try:
        original = store.original_bytes(identifier)
    except InspectionNotFound as exc:
        raise _not_found(str(exc), code="INSPECTION_NOT_FOUND") from exc

    if match.group("kind") == "-original.png":
        return _png(original)

    rendered = request.app.state.media_cache.rendered(
        identifier,
        original,
        inspector_for(request, record),
        record.get("manual_annotations"),
    )
    if key is None:
        return _png(rendered.result)
    if key not in rendered.layers:
        raise _not_found(f"La capa {key!r} no pertenece a este registro.")
    return _png(rendered.layers[key])
