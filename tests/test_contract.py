"""La consigna en forma ejecutable: contrato HTTP y persistencia."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import create_app


def _upload(client: TestClient, content: bytes = None, filename: str = "hoja.png"):
    return client.post(
        "/api/inspections",
        files={"file": (filename, content, "image/png")},
    )


def test_health_and_config(client: TestClient):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["version"]

    config = client.get("/api/config")
    assert config.status_code == 200
    assert config.json()["max_upload_bytes"] > 0
    assert "PNG" in config.json()["allowed_formats"]


def test_upload_returns_201_with_contract(client: TestClient, png_bytes: bytes):
    response = _upload(client, png_bytes)
    assert response.status_code == 201, response.text

    body = response.json()
    assert len(body["id"]) == 32
    assert body["created_at"]
    assert body["image"]["width"] == 240
    assert body["image"]["height"] == 240
    assert body["image"]["format"] == "PNG"
    assert body["image"]["filename"] == "hoja.png"
    assert body["quality"]["usable"] is True
    assert body["lesions"]["count"] >= 1
    assert 0 < body["lesions"]["area_fraction"] < 0.5
    assert 0 <= body["lesions"]["mean_circularity"] <= 1
    assert len(body["appearance"]["lab_mean"]) == 3
    assert body["trace"]["isolation"]["method"] == "primer_plano"
    assert body["trace"]["isolation"]["analysis"]["width"] == 240
    assert body["trace"]["preprocess"]["step"] == "standard"
    assert body["trace"]["domain"]["gate"] == "envelope_v1"
    assert body["trace"]["domain"]["score"] <= 1
    assert body["trace"]["segmentation"]["step"] == "redness_threshold"
    assert body["result_url"].startswith("/media/")
    assert body["original_url"].startswith("/media/")

    image = client.get(body["result_url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"

    original = client.get(body["original_url"])
    assert original.status_code == 200


def test_list_and_get(client: TestClient, png_bytes: bytes):
    created = _upload(client, png_bytes).json()

    listing = client.get("/api/inspections")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [created["id"]]

    fetched = client.get(f"/api/inspections/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_unknown_inspection_is_404(client: TestClient):
    response = client.get("/api/inspections/no-existe")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "INSPECTION_NOT_FOUND"


def test_invalid_id_is_404_not_500(client: TestClient):
    response = client.get("/api/inspections/abc$def")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "INSPECTION_NOT_FOUND"


def test_delete_then_404(client: TestClient, png_bytes: bytes):
    created = _upload(client, png_bytes).json()
    deleted = client.delete(f"/api/inspections/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/inspections/{created['id']}").status_code == 404


def test_clear_removes_every_inspection(client: TestClient, png_bytes: bytes):
    first = _upload(client, png_bytes, "primera.png").json()
    second = _upload(client, png_bytes, "segunda.png").json()

    cleared = client.delete("/api/inspections")

    assert cleared.status_code == 204
    assert client.get("/api/inspections").json() == []
    assert client.get(f"/api/inspections/{first['id']}").status_code == 404
    assert client.get(f"/api/inspections/{second['id']}").status_code == 404


def test_non_image_is_400_with_shape(client: TestClient):
    response = client.post(
        "/api/inspections",
        files={"file": ("nota.txt", b"esto no es una imagen", "text/plain")},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_FILE"
    assert detail["message"]


def test_oversize_is_413(tmp_path: Path, settings_factory, png_bytes: bytes):
    settings = settings_factory(max_upload_bytes=512)
    with TestClient(create_app(settings)) as client:
        response = _upload(client, png_bytes)
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "FILE_TOO_LARGE"


def test_flat_image_is_422(tmp_path: Path, settings_factory, blank_image):
    from core.io import encode_png

    settings = settings_factory()
    with TestClient(create_app(settings)) as client:
        response = _upload(client, encode_png(blank_image))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "IMAGE_UNUSABLE"


def test_non_leaf_image_is_422(client: TestClient, document_image):
    from core.io import encode_png

    response = _upload(client, encode_png(document_image))
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "IMAGE_NOT_A_LEAF"
    assert "hoja" in detail["message"]


def test_isolated_upload_returns_cropped_overlay(client: TestClient, leaf_on_background: np.ndarray):
    from core.io import encode_png

    response = _upload(client, encode_png(leaf_on_background))
    assert response.status_code == 201, response.text
    body = response.json()

    isolation = body["trace"]["isolation"]
    assert isolation["method"] == "grabcut"
    assert body["image"]["width"] == 420
    assert body["image"]["height"] == 320
    assert isolation["analysis"]["width"] < body["image"]["width"]
    assert isolation["analysis"]["height"] < body["image"]["height"]

    image = client.get(body["result_url"])
    assert image.status_code == 200
    decoded = cv2.imdecode(np.frombuffer(image.content, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[1] == isolation["analysis"]["width"]
    assert decoded.shape[0] == isolation["analysis"]["height"]

    original = client.get(body["original_url"])
    assert original.status_code == 200
    original_decoded = cv2.imdecode(
        np.frombuffer(original.content, np.uint8), cv2.IMREAD_COLOR
    )
    assert original_decoded.shape[:2] == (320, 420)


def test_legacy_record_without_optional_trace_is_still_readable(settings_factory, png_bytes: bytes):
    """Un registro guardado antes de dominio o aislamiento no rompe la API."""
    import json

    settings = settings_factory()
    with TestClient(create_app(settings)) as client:
        created = _upload(client, png_bytes).json()
        path = settings.storage_dir / f"{created['id']}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["trace"].pop("domain", None)
        record["trace"].pop("isolation", None)
        path.write_text(json.dumps(record), encoding="utf-8")

        listing = client.get("/api/inspections")
        assert listing.status_code == 200
        assert listing.json()[0]["trace"]["domain"] == {}
        assert listing.json()[0]["trace"]["isolation"] == {}
        fetched = client.get(f"/api/inspections/{created['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["trace"]["domain"] == {}
        assert fetched.json()["trace"]["isolation"] == {}


def test_persistence_across_app_instances(settings_factory, png_bytes: bytes):
    settings = settings_factory()
    with TestClient(create_app(settings)) as first:
        created = _upload(first, png_bytes).json()

    with TestClient(create_app(settings)) as second:
        fetched = second.get(f"/api/inspections/{created['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["image"]["filename"] == "hoja.png"

    storage = settings.storage_dir
    assert (storage / f"{created['id']}.json").is_file()
    assert (storage / f"{created['id']}-result.png").is_file()
    assert (storage / f"{created['id']}-original.png").is_file()
