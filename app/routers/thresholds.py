"""Catálogo de umbrales que el operario puede mover (ADR-022).

La pantalla no cablea rangos ni defectos: los pide acá. El catálogo vive en
``core/tuning.py`` y es el mismo objeto que valida lo que llega en el POST, así
que no hay dos verdades sobre qué se puede ajustar ni hasta dónde.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import ThresholdsOut
from core.pipeline import method_fingerprint
from core.tuning import catalogue, defaults

router = APIRouter(prefix="/api/thresholds", tags=["thresholds"])


@router.get(
    "",
    response_model=ThresholdsOut,
    summary="Umbrales ajustables, con rango, defecto y explicación",
)
def read_thresholds() -> ThresholdsOut:
    return ThresholdsOut(
        method_version=method_fingerprint(),
        parameters=catalogue(),
        defaults=defaults(),
    )
