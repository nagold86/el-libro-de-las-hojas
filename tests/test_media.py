"""La ruta ``/media`` con la base atrás (ADR-016).

El registro guarda un solo PNG; el overlay y las capas se regeneran al pedirlas.
Estos tests prueban que lo servido es lo mismo que se vio al inspeccionar, que es
lo único que hace aceptable no guardarlas.
"""

from __future__ import annotations

from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import media as media_module
from app.media import MediaCache, RenderedRecord
from core.io import encode_png, read_photo
from core.orchestrator import LeafInspector
from core.render import render_overlay, to_rgb


def upload(client: TestClient, content: bytes, filename: str = "hoja.png"):
    return client.post(
        "/api/inspections",
        files={"file": (filename, content, "image/png")},
    )


def test_original_is_served_from_the_database(sql_client: TestClient, png_bytes: bytes):
    from app.db.connection import connect

    body = upload(sql_client, png_bytes).json()

    response = sql_client.get(body["original_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    dsn = sql_client.app.state.settings.database_url
    with closing(connect(dsn)) as connection:
        stored = connection.execute(
            "SELECT original_png FROM inspections WHERE id = %s", (body["id"],)
        ).fetchone()
    assert response.content == bytes(stored["original_png"])
    # Y no es cualquier PNG: es la imagen que se analizó, entera.
    assert read_photo(response.content).image.shape == (240, 240, 3)


def test_regenerated_overlay_matches_the_inspection(
    sql_client: TestClient, png_bytes: bytes
):
    body = upload(sql_client, png_bytes).json()
    original = read_photo(sql_client.app.state.repository.original_bytes(body["id"]))
    result = LeafInspector().inspect(original.image)
    expected = render_overlay(
        result.image,
        result.lesion_mask,
        result.vein_mask,
        chlorosis_mask=result.chlorosis_mask,
        annotate=True,
    )

    response = sql_client.get(body["result_url"])

    assert response.status_code == 200
    assert response.content == encode_png(expected)


def test_regenerated_layers_match_the_inspection_byte_by_byte(
    sql_client: TestClient, png_bytes: bytes
):
    body = upload(sql_client, png_bytes).json()
    original = read_photo(sql_client.app.state.repository.original_bytes(body["id"]))
    result = LeafInspector().inspect(original.image)
    expected = {layer.key: encode_png(to_rgb(layer.image)) for layer in result.layers}

    assert set(body["layer_urls"]) == set(expected)
    for key, url in body["layer_urls"].items():
        served = sql_client.get(url)
        assert served.status_code == 200, key
        assert served.content == expected[key], key


def test_second_request_does_not_rerun_the_pipeline(
    sql_client: TestClient, png_bytes: bytes, monkeypatch
):
    body = upload(sql_client, png_bytes).json()
    calls: list[str] = []
    original_render = media_module.render

    def counting(*args, **kwargs):
        calls.append("render")
        return original_render(*args, **kwargs)

    monkeypatch.setattr(media_module, "render", counting)
    first = sql_client.get(body["result_url"])
    second = sql_client.get(body["result_url"])
    layer = sql_client.get(body["layer_urls"]["clorosis_mascara"])

    assert first.status_code == second.status_code == layer.status_code == 200
    assert first.content == second.content
    assert calls == ["render"]
    assert len(sql_client.app.state.media_cache) == 1


def test_unknown_record_is_404(sql_client: TestClient):
    response = sql_client.get("/media/" + "0" * 32 + "-original.png")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "INSPECTION_NOT_FOUND"


def test_unknown_layer_of_an_existing_record_is_404(sql_client: TestClient, png_bytes: bytes):
    body = upload(sql_client, png_bytes).json()

    response = sql_client.get(f"/media/{body['id']}-layer-noexiste.png")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "MEDIA_NOT_FOUND"


@pytest.mark.parametrize(
    "filename",
    [
        "raro.png",
        "abc$def-original.png",
        "x" * 65 + "-original.png",
        "abcdef-layer-AB.png",
        "abcdef-layer-.png",
        "abcdef-result.jpg",
    ],
)
def test_invalid_filenames_are_404_not_500(sql_client: TestClient, filename: str):
    response = sql_client.get(f"/media/{filename}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] in {"MEDIA_NOT_FOUND", "INSPECTION_NOT_FOUND"}


def test_file_store_keeps_serving_media(client: TestClient, png_bytes: bytes):
    """Sin base, las capas se leen del disco como antes de ADR-016."""
    body = upload(client, png_bytes).json()

    overlay = client.get(body["result_url"])
    layer = client.get(body["layer_urls"]["clorosis_mascara"])

    assert overlay.status_code == 200
    assert layer.status_code == 200
    assert layer.headers["content-type"] == "image/png"


def test_media_cache_evicts_the_oldest():
    cache = MediaCache(1)
    first = RenderedRecord(result=b"uno")
    second = RenderedRecord(result=b"dos")

    cache.put("a", first)
    cache.put("b", second)

    assert len(cache) == 1
    assert cache.get("a") is None
    assert cache.get("b") is second


def test_media_cache_can_be_disabled():
    cache = MediaCache(0)

    cache.put("a", RenderedRecord(result=b"uno"))

    assert len(cache) == 0
