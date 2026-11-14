"""El contrato de persistencia, corrido sobre las dos implementaciones.

Si un test de acá falla solo para ``postgres`` o solo para ``archivos``, las dos
no son intercambiables y ``build_store`` estaría mintiendo (ADR-016).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.store import InspectionStore
from core.exceptions import InspectionNotFound

LAYER_KEYS = ("aislamiento_prior", "clorosis_mascara")


def payload(created_at: str = "2026-01-01T10:00:00+00:00", **overrides: Any) -> dict[str, Any]:
    """Registro mínimo pero con la forma completa que publica el pipeline."""
    record: dict[str, Any] = {
        "created_at": created_at,
        "method_version": "1a2b3c4d",
        "app_version": "0.1.1",
        "image": {"filename": "hoja.png", "width": 240, "height": 240, "format": "PNG"},
        "lesions": {"count": 2, "area_fraction": 0.02, "max_feret_px": 12.5},
        "chlorosis": {"area_fraction": 0.1},
        "trace": {"layers": [{"key": key, "title": key} for key in LAYER_KEYS]},
    }
    record.update(overrides)
    return record


def layers() -> list[tuple[str, bytes]]:
    return [(key, b"capas") for key in LAYER_KEYS]


def test_both_stores_satisfy_the_protocol(any_store):
    assert isinstance(any_store, InspectionStore)


def test_save_and_get_roundtrip(any_store):
    record = any_store.save(b"original", b"resultado", payload(), layers())

    assert len(record["id"]) == 32
    assert record["result_url"] == f"/media/{record['id']}-result.png"
    assert record["original_url"] == f"/media/{record['id']}-original.png"
    assert record["layer_urls"] == {
        key: f"/media/{record['id']}-layer-{key}.png" for key in LAYER_KEYS
    }

    stored = any_store.get(record["id"])
    assert stored["image"]["filename"] == "hoja.png"
    assert stored["lesions"]["area_fraction"] == pytest.approx(0.02)
    # Leer devuelve exactamente lo que guardar prometió: mismo diccionario.
    assert stored == record


def test_update_persists_metadata_without_changing_media_urls(any_store):
    record = any_store.save(b"original", b"resultado", payload(), layers())
    record["manual_annotations"] = {
        "updated_at": "2026-11-13T10:00:00+00:00",
        "strokes": [],
    }

    updated = any_store.update(record)

    assert updated["manual_annotations"] == record["manual_annotations"]
    assert updated["result_url"] == record["result_url"]
    assert any_store.get(record["id"]) == updated


def test_original_bytes_are_the_original(any_store):
    record = any_store.save(b"original-crudo", b"resultado", payload())

    assert any_store.original_bytes(record["id"]) == b"original-crudo"


def test_ids_are_unique(any_store):
    first = any_store.save(b"a", b"b", payload())
    second = any_store.save(b"a", b"b", payload())

    assert first["id"] != second["id"]
    assert len(any_store.list()) == 2


def test_list_sorts_newest_first(any_store):
    older = any_store.save(b"a", b"b", payload("2025-01-01T00:00:00+00:00"))
    newer = any_store.save(b"a", b"b", payload("2026-06-01T00:00:00+00:00"))

    assert [record["id"] for record in any_store.list()] == [newer["id"], older["id"]]


def test_list_paginates(any_store):
    identifiers = [
        any_store.save(b"a", b"b", payload(f"2025-0{month}-01T00:00:00+00:00"))["id"]
        for month in (1, 2, 3)
    ]

    page = any_store.list(limit=1, offset=1)

    assert [record["id"] for record in page] == [identifiers[1]]
    assert any_store.list(limit=0) == []


def test_get_unknown_raises(any_store):
    with pytest.raises(InspectionNotFound):
        any_store.get("no-existe")


@pytest.mark.parametrize("bad_id", ["../evil", "abc$def", "", "x" * 65])
def test_invalid_ids_are_rejected(any_store, bad_id: str):
    with pytest.raises(InspectionNotFound):
        any_store.get(bad_id)


def test_original_bytes_of_unknown_raises(any_store):
    with pytest.raises(InspectionNotFound):
        any_store.original_bytes("no-existe")


def test_delete_removes_the_record(any_store):
    record = any_store.save(b"a", b"b", payload())

    any_store.delete(record["id"])

    with pytest.raises(InspectionNotFound):
        any_store.get(record["id"])
    with pytest.raises(InspectionNotFound):
        any_store.original_bytes(record["id"])


def test_delete_unknown_raises(any_store):
    with pytest.raises(InspectionNotFound):
        any_store.delete("no-existe")


def test_clear_removes_every_record(any_store):
    any_store.save(b"a", b"b", payload())
    any_store.save(b"c", b"d", payload())

    assert any_store.clear() == 2
    assert any_store.list() == []


# -- Historial con filtros y versiones del software (ADR-017) --------------
# Los filtros tienen que devolver lo mismo con archivos y con Postgres: son la
# misma pantalla del almanaque.


def with_owner(username: str, **overrides: Any) -> dict[str, Any]:
    """Payload con dueño, tal como lo arma la API cuando hay sesión."""
    return payload(
        owner={"id": f"id-{username}", "username": username, "display_name": username},
        **overrides,
    )


def test_list_filters_by_version(any_store):
    old = any_store.save(
        b"a", b"b", payload("2025-01-01T00:00:00+00:00", app_version="0.1.1")
    )
    new = any_store.save(
        b"a", b"b", payload("2025-02-01T00:00:00+00:00", app_version="0.2.0")
    )

    assert [item["id"] for item in any_store.list(app_version="0.2.0")] == [new["id"]]
    assert [item["id"] for item in any_store.list(app_version="0.1.1")] == [old["id"]]
    assert any_store.list(app_version="0.0.9") == []


def test_list_filters_by_owner(any_store):
    mine = any_store.save(
        b"a", b"b", with_owner("nico", created_at="2025-01-01T00:00:00+00:00")
    )
    other = any_store.save(
        b"a", b"b", with_owner("sam", created_at="2025-01-02T00:00:00+00:00")
    )
    # Los registros viejos no tienen dueño y no pueden romper el filtro.
    any_store.save(b"a", b"b", payload("2025-01-03T00:00:00+00:00"))

    assert [item["id"] for item in any_store.list(owner="sam")] == [other["id"]]
    assert [item["id"] for item in any_store.list(owner="nico")] == [mine["id"]]
    assert len(any_store.list()) == 3


def test_list_filters_by_filename(any_store):
    tabaco = any_store.save(b"a", b"b", payload("2025-01-01T00:00:00+00:00"))
    any_store.save(
        b"a",
        b"b",
        payload(
            "2025-01-02T00:00:00+00:00",
            image={"filename": "IMG_0007.png", "width": 240, "height": 240, "format": "PNG"},
        ),
    )

    # La búsqueda no distingue mayúsculas en ninguna de las dos implementaciones.
    assert [item["id"] for item in any_store.list(query="HOJA")] == [tabaco["id"]]
    assert any_store.list(query="no-existe") == []


def test_list_filters_by_date_window(any_store):
    january = any_store.save(b"a", b"b", payload("2025-01-01T00:00:00+00:00"))
    march = any_store.save(b"a", b"b", payload("2025-03-01T00:00:00+00:00"))
    limit = datetime(2025, 2, 1, tzinfo=timezone.utc)

    assert [item["id"] for item in any_store.list(since=limit)] == [march["id"]]
    # ``until`` es exclusivo: el borde no entra en ninguna de las dos páginas.
    assert [item["id"] for item in any_store.list(until=limit)] == [january["id"]]


def test_versions_count_what_each_one_measured(any_store):
    for month in (1, 2):
        any_store.save(
            b"a", b"b", payload(f"2025-0{month}-01T00:00:00+00:00", app_version="0.1.1")
        )
    any_store.save(
        b"a", b"b", payload("2025-03-01T00:00:00+00:00", app_version="0.2.0")
    )

    versions = {item["version"]: item for item in any_store.versions()}

    assert versions["0.1.1"]["inspections"] == 2
    assert versions["0.2.0"]["inspections"] == 1
    assert versions["0.2.0"]["method_version"] == "1a2b3c4d"
    assert versions["0.2.0"]["first_seen"] <= versions["0.2.0"]["last_seen"]


def test_versions_are_empty_without_records(any_store):
    assert any_store.versions() == []


# -- Alcance por dueño (ADR-018) ------------------------------------------
# Borrar «lo de un dueño» se filtra por el payload y coincide en las dos
# implementaciones. «Sin dueño» coincide en el caso común —la hoja que nunca
# trajo ``owner``—; en la base, además, cuenta la hoja cuyo usuario se dio de
# baja, porque ahí sí hay cuentas (se prueba en ``test_scope.py``).


def test_list_filters_unassigned(any_store):
    any_store.save(b"a", b"b", payload("2025-01-01T00:00:00+00:00"))
    any_store.save(b"a", b"b", payload("2025-01-02T00:00:00+00:00"))

    assert len(any_store.list(unassigned=True)) == 2
    assert any_store.list(owner="nico") == []


def test_clear_by_owner_leaves_the_rest(any_store):
    mine = any_store.save(
        b"a", b"b", with_owner("nico", created_at="2025-01-01T00:00:00+00:00")
    )
    any_store.save(b"a", b"b", with_owner("sam", created_at="2025-01-02T00:00:00+00:00"))

    assert any_store.clear(owner="sam") == 1
    assert [item["id"] for item in any_store.list()] == [mine["id"]]


def test_clear_unassigned_removes_only_the_orphans(any_store):
    any_store.save(b"a", b"b", payload("2025-01-01T00:00:00+00:00"))
    any_store.save(b"a", b"b", payload("2025-01-02T00:00:00+00:00"))

    assert any_store.clear(unassigned=True) == 2
    assert any_store.list() == []
