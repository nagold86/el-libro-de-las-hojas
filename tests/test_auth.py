"""Login, sesión y permisos (ADR-017).

Sin ``DATABASE_URL`` no hay tabla de usuarios y la aplicación queda abierta, que
es el modo demo del almacén de archivos. Con base, todo lo que no sea
``/api/health``, ``/api/config`` ni el propio login pide sesión.

Los fixtures ``sql_client_anon`` (sin cookie) y ``sql_client`` (con sesión ya
iniciada como administrador) viven en ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest

from app.auth import COOKIE_NAME, WeakPassword, hash_password, validate_password, verify_password
from conftest import ADMIN_PASSWORD, ADMIN_USER

OPERATOR = "operador-de-prueba"
OPERATOR_PASSWORD = "otra-clave-larga"


# -- contraseñas ---------------------------------------------------------


def test_passwords_are_salted_and_verifiable():
    first = hash_password("clave-larga-1")
    second = hash_password("clave-larga-1")

    # Misma clave, dos hashes: la sal es nueva en cada uno.
    assert first != second
    assert verify_password("clave-larga-1", first)
    assert not verify_password("otra-clave-1", first)


def test_hash_records_its_own_cost():
    algorithm, n, r, p, salt, digest = hash_password("clave-larga-1").split("$")

    # El costo viaja en el hash: subirlo mañana no invalida las claves viejas.
    assert (algorithm, n, r, p) == ("scrypt", "16384", "8", "1")
    assert salt and digest


@pytest.mark.parametrize("stored", ["", "texto-suelto", "scrypt$x$8$1$a$b"])
def test_broken_hashes_never_verify(stored: str):
    assert not verify_password("clave-larga-1", stored)


def test_short_passwords_are_rejected():
    with pytest.raises(WeakPassword):
        validate_password("corta")


# -- sesión --------------------------------------------------------------


def test_login_opens_a_session(sql_client_anon):
    response = sql_client_anon.post(
        "/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["username"] == ADMIN_USER
    assert response.json()["role"] == "admin"
    assert COOKIE_NAME in sql_client_anon.cookies

    me = sql_client_anon.get("/api/auth/me").json()
    assert me["user"]["username"] == ADMIN_USER
    assert me["auth_required"] is True


def test_wrong_password_is_rejected(sql_client_anon):
    response = sql_client_anon.post(
        "/api/auth/login",
        json={"username": ADMIN_USER, "password": "no-es-esta-clave"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "CREDENCIALES_INVALIDAS"


def test_unknown_user_looks_exactly_like_a_wrong_password(sql_client_anon):
    # Mismo código y mismo mensaje: el login no revela qué usuarios existen.
    response = sql_client_anon.post(
        "/api/auth/login",
        json={"username": "nadie", "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "CREDENCIALES_INVALIDAS"


def test_data_routes_require_a_session(sql_client_anon):
    anonymous = sql_client_anon.get("/api/auth/me").json()
    assert anonymous["user"] is None
    assert anonymous["auth_required"] is True

    for path in ("/api/inspections", "/api/versions", "/api/reports/lot"):
        response = sql_client_anon.get(path)
        assert response.status_code == 401, path
        assert response.json()["detail"]["code"] == "NO_AUTENTICADO"


def test_media_requires_a_session(sql_client_anon):
    response = sql_client_anon.get("/media/abc-original.png")

    assert response.status_code == 401


def test_session_opens_the_history(sql_client):
    assert sql_client.get("/api/inspections").status_code == 200
    assert sql_client.get("/api/auth/me").json()["user"]["username"] == ADMIN_USER


def test_logout_closes_the_session(sql_client):
    assert sql_client.post("/api/auth/logout").status_code == 204

    assert sql_client.get("/api/auth/me").json()["user"] is None
    assert sql_client.get("/api/inspections").status_code == 401


def test_tampered_cookie_is_ignored(sql_client):
    token = sql_client.cookies[COOKIE_NAME]
    sql_client.cookies.set(COOKIE_NAME, f"{token[:-4]}aaaa")

    assert sql_client.get("/api/auth/me").json()["user"] is None


# -- usuarios ------------------------------------------------------------


def test_admin_creates_an_operator(sql_client):
    created = sql_client.post(
        "/api/auth/users",
        json={
            "username": OPERATOR,
            "password": OPERATOR_PASSWORD,
            "display_name": "Operador de prueba",
        },
    )

    assert created.status_code == 201, created.text
    assert created.json()["role"] == "operador"

    users = sql_client.get("/api/auth/users").json()
    assert {item["username"] for item in users} >= {ADMIN_USER, OPERATOR}


def test_duplicate_username_is_rejected(sql_client):
    body = {"username": OPERATOR, "password": OPERATOR_PASSWORD}
    assert sql_client.post("/api/auth/users", json=body).status_code == 201

    again = sql_client.post("/api/auth/users", json=body)

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "USUARIO_EXISTENTE"


def test_operator_cannot_manage_users(sql_client):
    sql_client.post(
        "/api/auth/users",
        json={"username": OPERATOR, "password": OPERATOR_PASSWORD},
    )
    sql_client.post("/api/auth/logout")
    # El alta ya pasó; ahora entramos como operador.
    assert (
        sql_client.post(
            "/api/auth/login",
            json={"username": OPERATOR, "password": OPERATOR_PASSWORD},
        ).status_code
        == 200
    )

    assert sql_client.get("/api/inspections").status_code == 200
    forbidden = sql_client.get("/api/auth/users")
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "SIN_PERMISO"


def test_password_change_requires_the_current_one(sql_client):
    wrong = sql_client.post(
        "/api/auth/password",
        json={"current": "no-es-esta", "new": "clave-nueva-123"},
    )
    assert wrong.status_code == 401

    changed = sql_client.post(
        "/api/auth/password",
        json={"current": ADMIN_PASSWORD, "new": "clave-nueva-123"},
    )
    assert changed.status_code == 204

    sql_client.post("/api/auth/logout")
    assert (
        sql_client.post(
            "/api/auth/login",
            json={"username": ADMIN_USER, "password": "clave-nueva-123"},
        ).status_code
        == 200
    )


# -- sin base ------------------------------------------------------------


def test_login_without_database_explains_itself(client):
    response = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SIN_AUTENTICACION"
    # Sin base la demo queda abierta y el frontend no pide credenciales.
    assert client.get("/api/config").json()["auth_required"] is False
    assert client.get("/api/inspections").status_code == 200
