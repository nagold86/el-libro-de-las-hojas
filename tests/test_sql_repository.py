"""Detalles que solo la implementación de Postgres tiene (ADR-016).

El payload ``jsonb`` es la fuente de verdad; las columnas tipadas son derivadas y
existen para consultar sin abrir el JSON. Estos tests cuidan que no se separen.
"""

from __future__ import annotations

import hashlib
import re
from contextlib import closing
from typing import Any

import pytest

from app.db.connection import connect
from app.store import InspectionStore
from core.exceptions import InspectionNotFound
from core.pipeline import method_fingerprint
from core.version import __version__
from tests.test_store_contract import LAYER_KEYS, layers, payload

URL_KEYS = {"result_url", "original_url", "layer_urls"}


def insert_columns() -> list[str]:
    """Nombres de columna que declara el ``INSERT`` del repositorio."""
    from app.sql_repository import INSERT

    block = INSERT.split("(", 1)[1].split(")", 1)[0]
    return [name.strip() for name in block.split(",") if name.strip()]


def row(dsn: str, identifier: str) -> dict[str, Any]:
    """La fila cruda, para compararla contra el payload que se guardó."""
    with closing(connect(dsn)) as connection:
        fetched = connection.execute(
            "SELECT * FROM inspections WHERE id = %s", (identifier,)
        ).fetchone()
    assert fetched is not None, f"No se insertó la fila {identifier}."
    return fetched


def test_columns_are_derived_from_the_payload(sql_store, postgres_dsn: str):
    record = sql_store.save(b"original", b"resultado", payload(), layers())
    stored = row(postgres_dsn, record["id"])

    assert stored["payload"]["image"]["filename"] == "hoja.png"
    assert stored["filename"] == stored["payload"]["image"]["filename"]
    assert stored["width"] == stored["payload"]["image"]["width"]
    assert stored["height"] == stored["payload"]["image"]["height"]
    assert stored["format"] == stored["payload"]["image"]["format"]
    assert stored["lesion_count"] == stored["payload"]["lesions"]["count"]
    assert stored["area_fraction"] == pytest.approx(stored["payload"]["lesions"]["area_fraction"])
    assert stored["chlorosis_fraction"] == pytest.approx(
        stored["payload"]["chlorosis"]["area_fraction"]
    )
    assert stored["method_version"] == stored["payload"]["method_version"]
    assert stored["app_version"] == stored["payload"]["app_version"]
    assert str(stored["created_at"].year) == stored["payload"]["created_at"][:4]


def test_urls_are_not_stored(sql_store, postgres_dsn: str):
    record = sql_store.save(b"original", b"resultado", payload(), layers())
    stored = row(postgres_dsn, record["id"])

    assert URL_KEYS.isdisjoint(stored["payload"])
    assert set(record["layer_urls"]) == set(LAYER_KEYS)


def test_urls_depend_on_the_prefix_of_the_reader(sql_store, postgres_dsn: str):
    from app.sql_repository import SqlInspectionRepository

    record = sql_store.save(b"original", b"resultado", payload())

    other = SqlInspectionRepository(postgres_dsn, media_prefix="/imagenes", use_pool=False)
    assert other.get(record["id"])["result_url"] == f"/imagenes/{record['id']}-result.png"


def test_original_png_is_stored_with_its_sha256(sql_store, postgres_dsn: str):
    original = b"\x89PNG\r\n\x1a\noriginal-de-prueba"
    record = sql_store.save(original, b"resultado", payload())

    stored = row(postgres_dsn, record["id"])

    assert bytes(stored["original_png"]) == original
    assert stored["image_sha256"] == hashlib.sha256(original).hexdigest()


def test_result_and_layers_are_discarded(sql_store, postgres_dsn: str):
    record = sql_store.save(b"original", b"resultado-enorme", payload(), layers())

    stored = row(postgres_dsn, record["id"])

    assert bytes(stored["original_png"]) == b"original"
    assert "resultado-enorme" not in repr(stored)
    # Las fichas de las capas sí viajan: son lo que el visor lista.
    assert [layer["key"] for layer in stored["payload"]["trace"]["layers"]] == list(LAYER_KEYS)


def test_method_and_app_version_fall_back_to_the_current_build(sql_store, postgres_dsn: str):
    legacy = payload()
    legacy.pop("method_version")
    legacy.pop("app_version")

    record = sql_store.save(b"original", b"resultado", legacy)

    stored = row(postgres_dsn, record["id"])

    assert stored["method_version"] == method_fingerprint()
    assert stored["app_version"] == __version__


def test_known_owner_is_linked_to_the_user_table(sql_store, postgres_dsn: str):
    from app.auth import AuthService

    auth = AuthService(postgres_dsn, "secreto-de-prueba", use_pool=False)
    user = auth.create_user("sam", "clave-larga-123")

    record = sql_store.save(b"original", b"resultado", payload(owner=user.as_owner()))

    stored = row(postgres_dsn, record["id"])

    assert stored["user_id"] == user.id
    assert stored["payload"]["owner"]["username"] == "sam"


def test_unknown_owner_does_not_break_the_save(sql_store, postgres_dsn: str):
    # Un registro importado puede traer un dueño que ya no está en ``users``:
    # la columna queda NULL y el nombre se conserva en el payload.
    orphan = payload(
        owner={"id": "usuario-borrado", "username": "sam", "display_name": "Sam"}
    )

    record = sql_store.save(b"original", b"resultado", orphan)

    stored = row(postgres_dsn, record["id"])

    assert stored["user_id"] is None
    assert stored["payload"]["owner"]["username"] == "sam"


def test_record_reads_back_through_the_protocol(sql_store):
    assert isinstance(sql_store, InspectionStore)
    record = sql_store.save(b"original", b"resultado", payload())

    assert sql_store.list()[0]["id"] == record["id"]
    assert sql_store.original_bytes(record["id"]) == b"original"


def test_unknown_record_in_the_database_raises(sql_store):
    with pytest.raises(InspectionNotFound):
        sql_store.get("0" * 32)
    with pytest.raises(InspectionNotFound):
        sql_store.original_bytes("0" * 32)


def test_empty_dsn_is_refused():
    from app.sql_repository import SqlInspectionRepository

    with pytest.raises(ValueError):
        SqlInspectionRepository("")


# -- Lo que se puede cuidar sin servidor ---------------------------------
# Si el esquema y el INSERT se separan, la base falla recién en producción.
# Estos tests comparan los tres lugares que tienen que decir lo mismo.


def test_insert_columns_exist_in_the_migration():
    from app.db.connection import MIGRATIONS_DIR

    # El esquema crece por migraciones: la columna puede venir de cualquiera.
    migration = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
    )
    columns = insert_columns()

    assert columns
    for name in columns:
        # Las columnas nuevas llegan por ``ALTER TABLE ... ADD COLUMN``, así que
        # el nombre no siempre abre la línea después del margen.
        assert re.search(
            rf"^\s+(?:ADD COLUMN IF NOT EXISTS\s+)?{name}\s",
            migration,
            re.MULTILINE,
        ), f"La columna {name!r} del INSERT no está en las migraciones."


def test_insert_has_one_placeholder_per_column():
    from app.sql_repository import INSERT

    columns = insert_columns()

    assert len(columns) == len(set(columns))
    assert INSERT.count("%s") == len(columns)


def test_columns_builds_exactly_what_the_insert_expects():
    from app.sql_repository import _columns

    record = {**payload(), "id": "a" * 32}
    values = _columns(record, b"original")

    assert len(values) == len(insert_columns())
    assert values[0] == record["id"]
    assert b"original" in values
    assert any(isinstance(value, str) and "hoja.png" in value for value in values)


# -- alcance por dueño (ADR-018) -----------------------------------------


def insert_user(dsn: str, identifier: str, username: str, role: str = "operador") -> None:
    """Cuenta mínima: al repositorio solo le importa que la fila exista."""
    with closing(connect(dsn)) as connection:
        connection.execute(
            "INSERT INTO users (id, username, display_name, password_hash, role) "
            "VALUES (%s, %s, %s, 'no-se-usa', %s)",
            (identifier, username, username.title(), role),
        )
        connection.commit()


def owned(identifier: str, username: str, created_at: str = "2025-01-01T00:00:00+00:00"):
    return payload(
        created_at,
        owner={"id": identifier, "username": username, "display_name": username.title()},
    )


def test_leaf_without_account_is_unassigned(sql_store, postgres_dsn: str):
    insert_user(postgres_dsn, "u-sam", "sam")
    with_account = sql_store.save(b"a", b"b", owned("u-sam", "sam"))
    without = sql_store.save(b"a", b"b", payload("2025-01-02T00:00:00+00:00"))

    assert [item["id"] for item in sql_store.list(unassigned=True)] == [without["id"]]
    # La hoja con cuenta no es huérfana aunque tenga el mismo formato de payload.
    assert sql_store.get(with_account["id"])["owner"]["username"] == "sam"


def test_deleting_the_user_leaves_the_leaf_unassigned(sql_store, postgres_dsn: str):
    insert_user(postgres_dsn, "u-sam", "sam")
    record = sql_store.save(b"a", b"b", owned("u-sam", "sam"))

    with closing(connect(postgres_dsn)) as connection:
        connection.execute("DELETE FROM users WHERE id = 'u-sam'")
        connection.commit()

    # ON DELETE SET NULL: la hoja queda, sin dueño detrás.
    assert [item["id"] for item in sql_store.list(unassigned=True)] == [record["id"]]
    assert sql_store.original_bytes(record["id"]) == b"a"


def test_clear_unassigned_leaves_the_owned(sql_store, postgres_dsn: str):
    insert_user(postgres_dsn, "u-nico", "nico", role="admin")
    kept = sql_store.save(b"a", b"b", owned("u-nico", "nico"))
    sql_store.save(b"a", b"b", payload("2025-01-02T00:00:00+00:00"))

    assert sql_store.clear(unassigned=True) == 1
    assert [item["id"] for item in sql_store.list()] == [kept["id"]]
