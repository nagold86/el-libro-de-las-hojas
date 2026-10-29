"""Versiones del software que midió cada hoja (ADR-017).

La lista sirve para dos cosas concretas: filtrar el historial y avisar cuando el
almanaque mezcla métodos. El informe del lote ya declara ``method_versions``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import VersionOut
from app.store import InspectionStore

router = APIRouter(prefix="/api/versions", tags=["versions"])


@router.get(
    "",
    response_model=list[VersionOut],
    summary="Versiones registradas, de la más nueva a la más vieja",
)
def list_versions(request: Request) -> list[VersionOut]:
    store: InspectionStore = request.app.state.repository
    return [VersionOut.model_validate(item) for item in store.versions()]
