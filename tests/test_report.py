"""Informe del lote: agregados, severidad, compatibilidad y endpoint."""

from __future__ import annotations

import pytest

from app.reporting import build_lot_report
from app.schemas import LotReportOut
from core.io import encode_png


def _record(
    record_id: str,
    area_fraction: float,
    *,
    count: int = 1,
    flags: list[str] | None = None,
    method: str = "grabcut",
    feret: float = 30.0,
) -> dict:
    return {
        "id": record_id,
        "created_at": "2026-10-21T12:00:00+00:00",
        "image": {
            "filename": f"{record_id}.png",
            "width": 200,
            "height": 200,
            "format": "PNG",
        },
        "quality": {
            "usable": True,
            "sharpness": 40.0,
            "saturated_fraction": 0.0,
            "valid_fraction": 0.8,
            "flags": flags or [],
        },
        "lesions": {
            "count": count,
            "area_fraction": area_fraction,
            "mean_area_px": 12.0,
            "max_feret_px": feret,
            "mean_circularity": 0.6,
            "orientation_deg": None,
            "vein_density": 0.1,
        },
        "appearance": {
            "lab_mean": [50.0, 0.0, 0.0],
            "lab_std": [1.0, 1.0, 1.0],
            "exg_mean": 0.2,
            "browning_index": 0.3,
            "texture_entropy": 6.0,
            "local_variance": 30.0,
            "gradient_mean": 2.0,
            "lesion_color_delta": 10.0,
        },
        "trace": {
            "isolation": {"method": method},
            "preprocess": {},
            "domain": {},
            "segmentation": {},
        },
    }


def test_empty_report_is_serializable():
    report = build_lot_report([])
    validated = LotReportOut.model_validate(report)

    assert validated.totals.images == 0
    assert validated.totals.lesions == 0
    assert validated.dominant_severity == "sin_datos"
    assert validated.has_severe is False
    assert validated.points == []
    assert validated.worst == []
    assert len(validated.severity) == 4
    assert sum(bin.count for bin in validated.severity) == 0


def test_aggregates_totals_severity_and_worst():
    records = [
        _record("sana", 0.005, count=1, flags=["poca_superficie_valida"]),
        _record("leve", 0.03, count=2, method="primer_plano", feret=40.0),
        _record("moderada", 0.10, count=3, feret=50.0),
        _record("severa", 0.20, count=4, method="primer_plano", feret=60.0),
    ]

    validated = LotReportOut.model_validate(build_lot_report(records))

    assert validated.totals.images == 4
    assert validated.totals.lesions == 10
    assert validated.totals.mean_lesions == 2.5
    assert validated.totals.median_lesions == 2.5
    assert validated.totals.mean_area_fraction == pytest.approx(0.08375)
    assert validated.totals.median_area_fraction == pytest.approx(0.065)
    assert validated.totals.max_area_fraction == pytest.approx(0.20)
    assert validated.totals.max_feret_px == pytest.approx(60.0)
    assert validated.totals.mean_feret_px == pytest.approx(45.0)
    assert validated.has_severe is True
    assert validated.dominant_severity == "severo"  # empate: no se subestima
    assert [bin.count for bin in validated.severity] == [1, 1, 1, 1]
    assert validated.worst[0].id == "severa"
    assert validated.quality_flags == {"poca_superficie_valida": 1}
    assert validated.isolation_methods == {"grabcut": 2, "primer_plano": 2}


def test_legacy_record_without_optional_data_is_readable():
    record = _record("vieja", 0.02)
    record["trace"].pop("isolation")
    record["quality"].pop("flags")

    validated = LotReportOut.model_validate(build_lot_report([record]))

    assert validated.points[0].isolation_method == "desconocido"
    assert validated.points[0].quality_flags == []
    assert validated.isolation_methods == {"desconocido": 1}


def test_method_versions_are_counted_per_fingerprint():
    records = [_record("una", 0.02), _record("otra", 0.03), _record("vieja", 0.01)]
    records[0]["method_version"] = "aaaa1111"
    records[1]["method_version"] = "bbbb2222"

    validated = LotReportOut.model_validate(build_lot_report(records))

    # Un lote con dos huellas mezcla métodos y sus promedios no son comparables.
    assert validated.method_versions == {"aaaa1111": 1, "bbbb2222": 1, "sin_huella": 1}


def test_lot_endpoint_publishes_one_method_version(client, png_bytes: bytes):
    from core.pipeline import method_fingerprint

    client.post("/api/inspections", files={"file": ("hoja.png", png_bytes, "image/png")})

    body = client.get("/api/reports/lot").json()

    assert body["method_versions"] == {method_fingerprint(): 1}


def test_lot_endpoint_is_empty_without_inspections(client):
    response = client.get("/api/reports/lot")

    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["images"] == 0
    assert body["dominant_severity"] == "sin_datos"
    assert body["has_severe"] is False
    assert len(body["severity"]) == 4
    assert body["points"] == []


def test_lot_endpoint_aggregates_uploaded_leaves(client, leaf_image, leaf_on_background):
    for image, name in ((leaf_image, "hoja.png"), (leaf_on_background, "mesa.png")):
        response = client.post(
            "/api/inspections",
            files={"file": (name, encode_png(image), "image/png")},
        )
        assert response.status_code == 201, response.text

    response = client.get("/api/reports/lot")
    assert response.status_code == 200
    body = response.json()

    assert body["generated_at"]
    assert body["totals"]["images"] == 2
    assert len(body["points"]) == 2
    assert sum(bin["count"] for bin in body["severity"]) == 2
    assert set(body["isolation_methods"]) == {"primer_plano", "grabcut"}
    assert all(point["filename"] for point in body["points"])
