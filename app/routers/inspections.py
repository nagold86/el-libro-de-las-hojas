"""Recurso ``inspections``. Valida, delega en el orquestador y persiste.

El router no sabe qué es una máscara, un umbral ni un código de error: solo
traduce HTTP ↔ dominio.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, File, Request, Response, UploadFile, status

from app.repository import InspectionRepository
from app.schemas import InspectionOut
from app.uploads import read_upload
from core.io import encode_png
from core.orchestrator import LeafInspector
from core.render import render_overlay, to_rgb

router = APIRouter(prefix="/api/inspections", tags=["inspections"])


def _repository(request: Request) -> InspectionRepository:
    return request.app.state.repository


def _inspector(request: Request) -> LeafInspector:
    return request.app.state.inspector


@router.post(
    "",
    response_model=InspectionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Inspecciona una imagen de hoja",
    responses={
        400: {"description": "Archivo ilegible o formato no permitido"},
        413: {"description": "Archivo demasiado grande"},
        422: {"description": "Imagen legible pero no analizable o que no parece una hoja"},
    },
)
def create_inspection(request: Request, file: UploadFile = File(...)) -> InspectionOut:
    settings = request.app.state.settings
    data = file.file.read(settings.max_upload_bytes + 1)
    upload = read_upload(data, file.filename, file.content_type, settings)

    result = _inspector(request).inspect(upload.photo.image)
    # El overlay se dibuja sobre la imagen analizada: si el aislamiento recortó
    # la hoja, el resultado muestra la hoja sin fondo y las máscaras coinciden.
    overlay = render_overlay(
        result.image, result.lesion_mask, result.vein_mask, chlorosis_mask=result.chlorosis_mask
    )

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "image": {
            "filename": upload.filename,
            "width": upload.photo.width,
            "height": upload.photo.height,
            "format": upload.photo.format,
        },
        **result.to_dict(),
    }
    # La traza visual viaja como ficha; los píxeles se guardan aparte.
    payload["trace"]["layers"] = [layer.to_dict() for layer in result.layers]

    record = _repository(request).save(
        encode_png(upload.photo.image),
        encode_png(overlay),
        payload,
        layers=[(layer.key, encode_png(to_rgb(layer.image))) for layer in result.layers],
    )
    return InspectionOut.model_validate(record)


@router.get("", response_model=list[InspectionOut], summary="Lista las inspecciones")
def list_inspections(request: Request) -> list[InspectionOut]:
    return [InspectionOut.model_validate(record) for record in _repository(request).list()]


@router.get("/{inspection_id}", response_model=InspectionOut, summary="Obtiene una inspección")
def get_inspection(request: Request, inspection_id: str) -> InspectionOut:
    return InspectionOut.model_validate(_repository(request).get(inspection_id))


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina todas las inspecciones del almanaque",
)
def delete_all_inspections(request: Request) -> Response:
    _repository(request).clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{inspection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina una inspección",
)
def delete_inspection(request: Request, inspection_id: str) -> Response:
    _repository(request).delete(inspection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
