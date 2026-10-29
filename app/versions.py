"""Versiones del software registradas en el almanaque (ADR-017).

En Postgres la lista sale de la tabla ``software_versions``, que el propio
guardado mantiene al día. En el modo archivos no hay tabla: se agrega desde los
registros, con la misma forma, para que el contrato HTTP no cambie.

La versión no es decoración: promediar hojas medidas por 0.1.1 con hojas medidas
por 0.2.0 da un número que no significa nada, así que el historial se puede
filtrar por versión y el informe del lote ya avisa cuando mezcla huellas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

UNKNOWN_VERSION = "sin_versión"
UNKNOWN_METHOD = "sin_huella"


def timestamp_of(value: Any) -> datetime:
    """``created_at`` llega como texto en el JSON y como datetime desde la base."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return datetime.now(timezone.utc)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def summarize_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa registros por versión, con conteo y ventana temporal."""
    groups: dict[str, dict[str, Any]] = {}
    for record in records:
        version = str(record.get("app_version") or UNKNOWN_VERSION)
        method = str(record.get("method_version") or UNKNOWN_METHOD)
        stamp = timestamp_of(record.get("created_at"))
        entry = groups.get(version)
        if entry is None:
            entry = {
                "version": version,
                "method_version": method,
                "notes": "",
                "inspections": 0,
                "first_seen": stamp,
                "last_seen": stamp,
            }
            groups[version] = entry
        entry["inspections"] += 1
        if stamp < entry["first_seen"]:
            entry["first_seen"] = stamp
        if stamp > entry["last_seen"]:
            entry["last_seen"] = stamp

    return sorted(groups.values(), key=lambda item: item["first_seen"], reverse=True)
