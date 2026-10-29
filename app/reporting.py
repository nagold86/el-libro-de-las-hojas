"""Agregación del lote para el informe del almanaque.

Este módulo no dibuja: convierte una lista de registros persistidos en números
y series listas para el contrato. Los cortes de severidad son operativos
(1 %, 5 % y 15 % de superficie afectada), no un diagnóstico agronómico. La
decisión está en ``docs/DECISIONES.md`` (ADR-010).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import fmean, median
from typing import Any, Iterable

SEVERITY_BINS: tuple[tuple[str, str, float, float], ...] = (
    ("sano", "Sano", 0.0, 0.01),
    ("leve", "Leve", 0.01, 0.05),
    ("moderado", "Moderado", 0.05, 0.15),
    ("severo", "Severo", 0.15, 1.0),
)


def build_lot_report(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Resume todas las inspecciones aceptadas en un informe serializable."""
    batch = list(records)
    points = [_point(record) for record in batch]
    areas = [point["area_fraction"] for point in points]
    counts = [point["lesion_count"] for point in points]
    ferets = [point["max_feret_px"] for point in points]
    veins = [point["vein_density"] for point in points]
    brownings = [point["browning_index"] for point in points]
    sharpness = [point["sharpness"] for point in points]

    severity_counts = {key: 0 for key, _, _, _ in SEVERITY_BINS}
    for point in points:
        severity_counts[_severity_key(point["area_fraction"])] += 1
    total = len(points)
    severity = [
        {
            "key": key,
            "label": label,
            "count": severity_counts[key],
            "fraction": severity_counts[key] / total if total else 0.0,
            "min_area_fraction": low,
            "max_area_fraction": high,
        }
        for key, label, low, high in SEVERITY_BINS
    ]

    dominant = _dominant_severity(severity_counts)
    worst = sorted(points, key=lambda point: point["area_fraction"], reverse=True)[:5]
    quality_flags = Counter(
        flag for point in points for flag in point["quality_flags"]
    )
    isolation_methods = Counter(point["isolation_method"] for point in points)
    # Huella de método por registro (ADR-016): si aparece más de una, el lote
    # mezcla métodos y los promedios de área no son comparables.
    method_versions = Counter(
        str(record.get("method_version") or "sin_huella") for record in batch
    )

    return {
        "generated_at": datetime.now(timezone.utc),
        "totals": {
            "images": total,
            "lesions": sum(counts),
            "mean_lesions": _mean(counts),
            "median_lesions": _median(counts),
            "mean_area_fraction": _mean(areas),
            "median_area_fraction": _median(areas),
            "max_area_fraction": max(areas) if areas else 0.0,
            "mean_feret_px": _mean(ferets),
            "max_feret_px": max(ferets) if ferets else 0.0,
            "mean_vein_density": _mean(veins),
            "mean_browning_index": _mean(brownings),
            "mean_sharpness": _mean(sharpness),
        },
        "severity": severity,
        "dominant_severity": dominant,
        "has_severe": severity_counts["severo"] > 0,
        "points": points,
        "worst": worst,
        "quality_flags": dict(sorted(quality_flags.items())),
        "isolation_methods": dict(sorted(isolation_methods.items())),
        "method_versions": dict(sorted(method_versions.items())),
    }


def _point(record: dict[str, Any]) -> dict[str, Any]:
    image = record.get("image") or {}
    quality = record.get("quality") or {}
    lesions = record.get("lesions") or {}
    appearance = record.get("appearance") or {}
    trace = record.get("trace") or {}
    isolation = trace.get("isolation") or {}
    flags = quality.get("flags") or []
    if not isinstance(flags, list):
        flags = []

    return {
        "id": str(record.get("id", "")),
        "filename": str(image.get("filename", "")),
        "created_at": record.get("created_at") or datetime.now(timezone.utc),
        "area_fraction": _float(lesions.get("area_fraction")),
        "lesion_count": _int(lesions.get("count")),
        "max_feret_px": _float(lesions.get("max_feret_px")),
        "mean_circularity": _float(lesions.get("mean_circularity")),
        "vein_density": _float(lesions.get("vein_density")),
        "browning_index": _float(appearance.get("browning_index")),
        "sharpness": _float(quality.get("sharpness")),
        "quality_flags": [str(flag) for flag in flags],
        "isolation_method": str(isolation.get("method") or "desconocido"),
    }


def _severity_key(area_fraction: float) -> str:
    for key, _, low, high in SEVERITY_BINS:
        if low <= area_fraction < high:
            return key
    return "severo"


def _dominant_severity(counts: dict[str, int]) -> str:
    if not any(counts.values()):
        return "sin_datos"
    order = {key: index for index, (key, _, _, _) in enumerate(SEVERITY_BINS)}
    maximum = max(counts.values())
    candidates = [key for key, count in counts.items() if count == maximum]
    # Ante un empate no se subestima: gana el nivel más severo.
    return max(candidates, key=lambda key: order[key])


def _mean(values: list[float]) -> float:
    return float(fmean(values)) if values else 0.0


def _median(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
