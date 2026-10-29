"""Alcance por dueño, baja de usuarios y limpieza de huérfanas (ADR-018).

Cada operador ve solo sus hojas; el administrador ve el almanaque completo y
administra las cuentas. Lo ajeno se responde como inexistente: ni el historial,
ni el detalle, ni los PNG delatan que existe.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import ADMIN_PASSWORD, ADMIN_USER

OPERADOR = "sam"
CLAVE = "clave-de-sam-2026"


# -- atajos --------------------------------------------------------------


def upload(client: TestClient, content: bytes, filename: str) -> dict:
    response = client.post(
        "/api/inspections",
        files={"file": (filename, content, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, username: str, password: str = CLAVE) -> dict:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def add_operador(client: TestClient) -> dict:
    """Da de alta al operador de prueba. La pide el administrador."""
    response = client.post(
        "/api/auth/users",
        json={
            "username": OPERADOR,
            "password": CLAVE,
            "display_name": "Sam",
            "role": "operador",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def filenames(client: TestClient, **params: object) -> list[str]:
    response = client.get("/api/inspections", params=params)
    assert response.status_code == 200, response.text
    return [item["image"]["filename"] for item in response.json()]


def user_id(client: TestClient, username: str) -> str:
    for user in client.get("/api/auth/users").json():
        if user["username"] == username:
            return user["id"]
    raise AssertionError(f"No está {username} en la lista de usuarios.")


# -- cada uno ve lo suyo --------------------------------------------------


def test_operator_sees_only_own_leaves(sql_client: TestClient, png_bytes: bytes):
    upload(sql_client, png_bytes, "de-nico.png")
    add_operador(sql_client)
    login(sql_client, OPERADOR)
    upload(sql_client, png_bytes, "de-sam.png")

    assert filenames(sql_client) == ["de-sam.png"]
    # Pedir el archivo de otro no cambia nada: el filtro se ignora.
    assert filenames(sql_client, owner=ADMIN_USER) == ["de-sam.png"]

    login(sql_client, ADMIN_USER, ADMIN_PASSWORD)

    assert sorted(filenames(sql_client)) == ["de-nico.png", "de-sam.png"]
    assert filenames(sql_client, owner=OPERADOR) == ["de-sam.png"]


def test_foreign_leaf_is_not_found(sql_client: TestClient, png_bytes: bytes):
    ajeno = upload(sql_client, png_bytes, "de-nico.png")
    add_operador(sql_client)
    login(sql_client, OPERADOR)

    detail = sql_client.get(f"/api/inspections/{ajeno['id']}")
    removed = sql_client.delete(f"/api/inspections/{ajeno['id']}")

    # Mismo 404 que una hoja inexistente: no se delata que existe.
    assert detail.status_code == 404
    assert detail.json()["detail"]["code"] == "INSPECTION_NOT_FOUND"
    assert removed.status_code == 404

    login(sql_client, ADMIN_USER, ADMIN_PASSWORD)
    assert filenames(sql_client) == ["de-nico.png"]


def test_foreign_media_is_not_found(sql_client: TestClient, png_bytes: bytes):
    ajeno = upload(sql_client, png_bytes, "de-nico.png")
    add_operador(sql_client)
    login(sql_client, OPERADOR)
    propio = upload(sql_client, png_bytes, "de-sam.png")

    assert sql_client.get(f"/media/{ajeno['id']}-original.png").status_code == 404
    assert sql_client.get(f"/media/{propio['id']}-original.png").status_code == 200

    login(sql_client, ADMIN_USER, ADMIN_PASSWORD)
    assert sql_client.get(f"/media/{ajeno['id']}-original.png").status_code == 200


def test_lot_report_sums_only_own_leaves(sql_client: TestClient, png_bytes: bytes):
    upload(sql_client, png_bytes, "de-nico.png")
    add_operador(sql_client)
    login(sql_client, OPERADOR)
    upload(sql_client, png_bytes, "de-sam.png")

    propio = sql_client.get("/api/reports/lot")
    assert propio.status_code == 200
    assert propio.json()["totals"]["images"] == 1

    login(sql_client, ADMIN_USER, ADMIN_PASSWORD)
    assert sql_client.get("/api/reports/lot").json()["totals"]["images"] == 2


def test_clear_removes_only_own_leaves(sql_client: TestClient, png_bytes: bytes):
    upload(sql_client, png_bytes, "de-nico.png")
    add_operador(sql_client)
    login(sql_client, OPERADOR)
    upload(sql_client, png_bytes, "de-sam.png")

    assert sql_client.delete("/api/inspections").status_code == 204
    assert filenames(sql_client) == []

    login(sql_client, ADMIN_USER, ADMIN_PASSWORD)
    assert filenames(sql_client) == ["de-nico.png"]


# -- la conserjería -------------------------------------------------------


def test_admin_deletes_a_user_and_their_leaves_become_orphans(
    sql_client: TestClient, png_bytes: bytes
):
    add_operador(sql_client)
    login(sql_client, OPERADOR)
    upload(sql_client, png_bytes, "de-sam.png")
    login(sql_client, ADMIN_USER, ADMIN_PASSWORD)

    removed = sql_client.delete(f"/api/auth/users/{user_id(sql_client, OPERADOR)}")

    assert removed.status_code == 204
    assert [user["username"] for user in sql_client.get("/api/auth/users").json()] == [
        ADMIN_USER
    ]
    # La cuenta ya no existe: la puerta no lo deja pasar.
    denied = sql_client.post(
        "/api/auth/login", json={"username": OPERADOR, "password": CLAVE}
    )
    assert denied.status_code == 401
    assert denied.json()["detail"]["code"] == "CREDENCIALES_INVALIDAS"
    # Sus hojas quedan en el almanaque, sin dueño detrás.
    orphans = sql_client.get("/api/inspections", params={"unassigned": "true"}).json()
    assert [item["image"]["filename"] for item in orphans] == ["de-sam.png"]
    assert filenames(sql_client) == ["de-sam.png"]


def test_admin_purges_the_orphan_leaves(sql_client: TestClient, png_bytes: bytes):
    upload(sql_client, png_bytes, "de-nico.png")
    add_operador(sql_client)
    login(sql_client, OPERADOR)
    upload(sql_client, png_bytes, "de-sam.png")
    login(sql_client, ADMIN_USER, ADMIN_PASSWORD)
    sql_client.delete(f"/api/auth/users/{user_id(sql_client, OPERADOR)}")

    assert sql_client.delete("/api/inspections", params={"unassigned": "true"}).status_code == 204

    assert filenames(sql_client) == ["de-nico.png"]
    assert sql_client.get("/api/inspections", params={"unassigned": "true"}).json() == []


def test_admin_cannot_delete_own_account(sql_client: TestClient):
    me = sql_client.get("/api/auth/me").json()["user"]

    response = sql_client.delete(f"/api/auth/users/{me['id']}")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "SIN_PERMISO"


def test_deleting_an_unknown_user_is_not_found(sql_client: TestClient):
    response = sql_client.delete("/api/auth/users/no-existe")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "USUARIO_NO_ENCONTRADO"


def test_operator_cannot_manage_users(sql_client: TestClient):
    add_operador(sql_client)
    login(sql_client, OPERADOR)

    listing = sql_client.get("/api/auth/users")
    creation = sql_client.post(
        "/api/auth/users", json={"username": "otro", "password": "otra-clave-larga"}
    )
    removal = sql_client.delete("/api/auth/users/un-id-cualquiera")

    for response in (listing, creation, removal):
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "SIN_PERMISO"


def test_operator_cannot_ask_for_orphans(sql_client: TestClient, png_bytes: bytes):
    upload(sql_client, png_bytes, "de-nico.png")
    add_operador(sql_client)
    login(sql_client, OPERADOR)

    # El filtro de huérfanas es cosa del administrador: el operador ve lo suyo.
    assert filenames(sql_client, unassigned="true") == []
