"""Historial de subidas y registro de versiones por HTTP (ADR-017).

Lo que se ve en la pantalla del almanaque: quién subió cada hoja, con qué
versión del software se midió y cómo se recorta esa lista. La forma de la
respuesta es la misma con archivos y con Postgres.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.version import __version__


def upload(client: TestClient, content: bytes, filename: str) -> dict:
    response = client.post(
        "/api/inspections",
        files={"file": (filename, content, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


# -- con sesión y base ---------------------------------------------------


def test_upload_records_who_and_with_which_version(sql_client: TestClient, png_bytes: bytes):
    body = upload(sql_client, png_bytes, "hoja-norte.png")

    assert body["owner"]["username"] == "nico"
    assert body["owner"]["display_name"]
    assert body["app_version"] == __version__
    assert body["method_version"]


def test_history_filters_by_filename(sql_client: TestClient, png_bytes: bytes):
    upload(sql_client, png_bytes, "hoja-norte.png")
    upload(sql_client, png_bytes, "hoja-sur.png")

    found = sql_client.get("/api/inspections", params={"q": "norte"}).json()

    assert [item["image"]["filename"] for item in found] == ["hoja-norte.png"]


def test_history_filters_by_owner_and_version(sql_client: TestClient, png_bytes: bytes):
    upload(sql_client, png_bytes, "hoja-norte.png")

    by_owner = sql_client.get("/api/inspections", params={"owner": "nico"})
    by_version = sql_client.get("/api/inspections", params={"version": __version__})
    missing = sql_client.get("/api/inspections", params={"version": "0.0.1"})

    assert by_owner.status_code == 200
    assert len(by_owner.json()) == 1
    assert len(by_version.json()) == 1
    # Una versión que nunca midió nada devuelve la lista vacía, no un error.
    assert missing.json() == []


def test_history_records_are_the_ones_measured(sql_client: TestClient, png_bytes: bytes):
    created = upload(sql_client, png_bytes, "hoja-norte.png")

    history = sql_client.get("/api/inspections").json()

    assert [item["id"] for item in history] == [created["id"]]
    assert history[0]["lesions"] == created["lesions"]


def test_versions_endpoint_lists_what_was_measured(sql_client: TestClient, png_bytes: bytes):
    upload(sql_client, png_bytes, "hoja-norte.png")

    versions = sql_client.get("/api/versions").json()

    assert versions[0]["version"] == __version__
    assert versions[0]["inspections"] == 1
    assert versions[0]["method_version"]


def test_versions_endpoint_is_empty_without_uploads(sql_client: TestClient):
    assert sql_client.get("/api/versions").json() == []


# -- sin base (modo archivos) --------------------------------------------


def test_file_store_summarizes_versions_too(client: TestClient, png_bytes: bytes):
    upload(client, png_bytes, "hoja-norte.png")

    versions = client.get("/api/versions").json()

    assert [item["version"] for item in versions] == [__version__]
    assert versions[0]["inspections"] == 1


def test_file_store_history_has_no_owner(client: TestClient, png_bytes: bytes):
    body = upload(client, png_bytes, "hoja-norte.png")

    # Sin login no hay dueño, y la respuesta no inventa uno.
    assert body["owner"] is None
    assert client.get("/api/inspections").json()[0]["owner"] is None
