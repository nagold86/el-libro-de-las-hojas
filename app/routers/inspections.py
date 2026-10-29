"""Recurso ``inspections``. Valida, delega en el orquestador y persiste.

El router no sabe qué es una máscara, un umbral ni un código de error: solo
traduce HTTP ↔ dominio. El alcance por usuario solo cambia qué dueño se pide al
almacén y qué registros ajenos se esconden como inexistentes (ADR-018).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status

from app.auth import User
from app.schemas import InspectionOut
from app.security import can_see, current_user, owner_scope
from app.store import InspectionStore
from app.uploads import read_upload
from core.exceptions import InspectionNotFound
from core.io import encode_png
from core.orchestrator import LeafInspector
from core.render import render_overlay, to_rgb
from core.version import __version__

router = APIRouter(prefix="/api/inspections", tags=["inspections"])

DEFAULT_PAGE = 200
MAX_PAGE = 500


def _repository(request: Request) -> InspectionStore:
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
def create_inspection(
    request: Request,
    file: UploadFile = File(...),
    user: User | None = Depends(current_user),
) -> InspectionOut:
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
        # Con qué método se midió: el informe del lote no promedia huellas
        # distintas sin avisar (ADR-016).
        "method_version": request.app.state.method_version,
        "app_version": __version__,
        # Quién la subió (ADR-017). Sin login activo queda ausente.
        "owner": user.as_owner() if user else None,
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
def list_inspections(
    request: Request,
    limit: int = Query(DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0),
    version: str | None = Query(None, max_length=32, description="Versión del software"),
    owner: str | None = Query(None, max_length=32, description="Usuario que la subió"),
    unassigned: bool = Query(
        False, description="Solo las hojas sin cuenta detrás (administrador)"
    ),
    since: datetime | None = Query(None, description="Desde (ISO 8601)"),
    until: datetime | None = Query(None, description="Hasta (ISO 8601, excluido)"),
    q: str | None = Query(None, max_length=80, description="Busca en el nombre de archivo"),
    user: User | None = Depends(current_user),
) -> list[InspectionOut]:
    """Historial de subidas, de la más nueva a la más vieja (ADR-017).

    El operador ve solo lo suyo: el filtro ``owner`` se ignora en su caso
    (ADR-018).
    """
    scope = owner_scope(user, owner)
    return [
        InspectionOut.model_validate(record)
        for record in _repository(request).list(
            limit=limit,
            offset=offset,
            app_version=version,
            owner=scope,
            # Solo el administrador puede pedir las huérfanas, y solo si no
            # está filtrando por un dueño concreto.
            unassigned=unassigned and scope is None,
            since=since,
            until=until,
            query=q,
        )
    ]


@router.get("/{inspection_id}", response_model=InspectionOut, summary="Obtiene una inspección")
def get_inspection(
    request: Request,
    inspection_id: str,
    user: User | None = Depends(current_user),
) -> InspectionOut:
    record = _repository(request).get(inspection_id)
    if not can_see(record, user):
        # Mismo 404 que una hoja inexistente: no se delata que existe.
        raise InspectionNotFound(f"No existe la inspección {inspection_id}.")
    return InspectionOut.model_validate(record)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina las inspecciones del almanaque",
)
def delete_all_inspections(
    request: Request,
    unassigned: bool = Query(
        False, description="Solo las hojas sin cuenta detrás (administrador)"
    ),
    user: User | None = Depends(current_user),
) -> Response:
    """Vacía el almanaque: el administrador todo o solo las huérfanas; el
    operador, únicamente lo que subió él (ADR-018)."""
    repository = _repository(request)
    scope = owner_scope(user)
    if scope is None:
        repository.clear(unassigned=unassigned)
    else:
        repository.clear(owner=scope)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{inspection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina una inspección",
)
def delete_inspection(
    request: Request,
    inspection_id: str,
    user: User | None = Depends(current_user),
) -> Response:
    repository = _repository(request)
    if not can_see(repository.get(inspection_id), user):
        raise InspectionNotFound(f"No existe la inspección {inspection_id}.")
    repository.delete(inspection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
