"""Recurso ``reports``: lectura agregada del archivo, sin persistencia nueva."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.reporting import build_lot_report
from app.schemas import LotReportOut

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get(
    "/lot",
    response_model=LotReportOut,
    summary="Informe agregado del lote escaneado",
)
def lot_report(request: Request) -> LotReportOut:
    repository = request.app.state.repository
    return LotReportOut.model_validate(build_lot_report(repository.list()))
