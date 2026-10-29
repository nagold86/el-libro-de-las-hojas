"""Recurso ``reports``: lectura agregada del archivo, sin persistencia nueva.

El lote que se agrega depende de quién pide: el operador suma solo sus hojas y
el administrador el almanaque completo (ADR-018).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth import User
from app.reporting import build_lot_report
from app.schemas import LotReportOut
from app.security import current_user, owner_scope

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get(
    "/lot",
    response_model=LotReportOut,
    summary="Informe agregado del lote escaneado",
)
def lot_report(
    request: Request,
    user: User | None = Depends(current_user),
) -> LotReportOut:
    repository = request.app.state.repository
    return LotReportOut.model_validate(
        build_lot_report(repository.list(owner=owner_scope(user)))
    )
