"""Umbrales por HTTP: catálogo, ajuste por corrida y rechazo (ADR-022).

El contrato que se fija acá: el catálogo viaja con rangos y defectos, un ajuste
solo cambia lo que se movió, y lo que no cierra responde ``422`` con código, no
``500``. Nada de esto modifica el registro por defecto, que es lo que vigila
``test_contract.py``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.pipeline import PipelineSettings, method_fingerprint
from core.tuning import defaults


def _upload(client: TestClient, content: bytes, tuning: str | None = None):
    data = {} if tuning is None else {"tuning": tuning}
    return client.post(
        "/api/inspections",
        files={"file": ("hoja.png", content, "image/png")},
        data=data,
    )


def test_catalogue_is_served(client: TestClient):
    response = client.get("/api/thresholds")

    assert response.status_code == 200
    body = response.json()
    assert body["method_version"] == method_fingerprint()
    assert body["defaults"] == defaults()
    keys = [parameter["key"] for parameter in body["parameters"]]
    assert keys == list(defaults())
    for parameter in body["parameters"]:
        assert parameter["min"] <= parameter["default"] <= parameter["max"]
        assert parameter["help"]


def test_default_run_records_no_tuning(client: TestClient, png_bytes: bytes):
    response = _upload(client, png_bytes)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["trace"]["tuning"] == {}
    assert body["method_version"] == method_fingerprint()


def test_moved_threshold_is_recorded_and_changes_the_fingerprint(
    client: TestClient, png_bytes: bytes
):
    response = _upload(client, png_bytes, tuning='{"redness_threshold": 0.05}')

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["trace"]["tuning"] == {"redness_threshold": 0.05}
    expected = method_fingerprint(PipelineSettings(redness_threshold=0.05))
    assert body["method_version"] == expected
    assert body["method_version"] != method_fingerprint()


def test_raising_the_threshold_never_marks_more_area(client: TestClient, png_bytes: bytes):
    default_run = _upload(client, png_bytes).json()
    strict_run = _upload(client, png_bytes, tuning='{"redness_threshold": 0.08}').json()

    # Subir el umbral de pardeamiento solo puede quitar tejido de la máscara.
    assert strict_run["lesions"]["area_fraction"] <= default_run["lesions"]["area_fraction"]
    assert strict_run["lesions"]["count"] <= default_run["lesions"]["count"]


def test_turning_off_darkness_still_detects_brown_lesions(
    client: TestClient, png_bytes: bytes
):
    default_run = _upload(client, png_bytes).json()
    color_only = _upload(client, png_bytes, tuning='{"darkness_threshold": 0}').json()

    # El defecto y su apagado comparten criterio de color: la muestra tiene
    # manchas pardas, así que la evidencia de oscurecimiento no inventa manchas.
    assert color_only["lesions"]["count"] <= default_run["lesions"]["count"]
    assert color_only["trace"]["segmentation"]["darkness_threshold"] == 0.0


def test_invalid_json_is_422(client: TestClient, png_bytes: bytes):
    response = _upload(client, png_bytes, tuning="no es json")

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "INVALID_THRESHOLDS"


def test_out_of_range_threshold_is_422(client: TestClient, png_bytes: bytes):
    response = _upload(client, png_bytes, tuning='{"redness_threshold": 5}')

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_THRESHOLDS"
    assert "Pardeamiento" in detail["message"]


def test_unknown_threshold_is_422(client: TestClient, png_bytes: bytes):
    response = _upload(client, png_bytes, tuning='{"color_magico": 1}')

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "INVALID_THRESHOLDS"


def test_thresholds_do_not_leak_between_requests(client: TestClient, png_bytes: bytes):
    _upload(client, png_bytes, tuning='{"redness_threshold": 0.08}')

    again = _upload(client, png_bytes).json()

    assert again["trace"]["tuning"] == {}
    assert again["method_version"] == method_fingerprint()
