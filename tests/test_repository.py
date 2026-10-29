"""Repositorio: escritura atómica, identificadores y tolerancia a corrupción."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.repository import InspectionRepository
from core.exceptions import InspectionNotFound

PAYLOAD = {
    "created_at": "2026-01-01T10:00:00+00:00",
    "image": {"filename": "hoja.png", "width": 240, "height": 240},
}


def _repository(tmp_path: Path) -> InspectionRepository:
    return InspectionRepository(tmp_path / "storage")


def test_save_and_get_roundtrip(tmp_path: Path):
    repository = _repository(tmp_path)

    record = repository.save(b"original", b"result", dict(PAYLOAD))

    assert len(record["id"]) == 32
    assert record["result_url"] == f"/media/{record['id']}-result.png"
    assert record["original_url"] == f"/media/{record['id']}-original.png"
    assert (record["id"] + "-original.png") in {p.name for p in repository.root.iterdir()}

    stored = repository.get(record["id"])
    assert stored["image"]["filename"] == "hoja.png"
    assert stored["id"] == record["id"]


def test_ids_are_unique(tmp_path: Path):
    repository = _repository(tmp_path)

    first = repository.save(b"a", b"b", dict(PAYLOAD))
    second = repository.save(b"a", b"b", dict(PAYLOAD))

    assert first["id"] != second["id"]
    assert len(repository.list()) == 2


def test_no_temporary_files_are_left_behind(tmp_path: Path):
    repository = _repository(tmp_path)

    repository.save(b"original", b"result", dict(PAYLOAD))

    assert list(repository.root.glob("*.tmp")) == []
    assert len(list(repository.root.iterdir())) == 3


def test_layer_artifacts_are_saved_and_removed(tmp_path: Path):
    repository = _repository(tmp_path)

    record = repository.save(
        b"original",
        b"result",
        dict(PAYLOAD),
        layers=[("preproceso_balance", b"png")],
    )

    assert record["layer_urls"] == {
        "preproceso_balance": f"/media/{record['id']}-layer-preproceso_balance.png"
    }
    layer_path = repository.root / f"{record['id']}-layer-preproceso_balance.png"
    assert layer_path.read_bytes() == b"png"

    repository.delete(record["id"])

    assert not layer_path.exists()


def test_list_sorts_newest_first(tmp_path: Path):
    repository = _repository(tmp_path)

    older = repository.save(
        b"a", b"b", {**PAYLOAD, "created_at": "2025-01-01T00:00:00+00:00"}
    )
    newer = repository.save(
        b"a", b"b", {**PAYLOAD, "created_at": "2026-06-01T00:00:00+00:00"}
    )

    assert [record["id"] for record in repository.list()] == [newer["id"], older["id"]]


def test_get_unknown_raises(tmp_path: Path):
    with pytest.raises(InspectionNotFound):
        _repository(tmp_path).get("no-existe")


@pytest.mark.parametrize("bad_id", ["../evil", "abc$def", "", "x" * 65])
def test_invalid_ids_are_rejected_before_touching_disk(tmp_path: Path, bad_id: str):
    with pytest.raises(InspectionNotFound):
        _repository(tmp_path).get(bad_id)


def test_delete_removes_all_three_files(tmp_path: Path):
    repository = _repository(tmp_path)
    record = repository.save(b"original", b"result", dict(PAYLOAD))

    repository.delete(record["id"])

    assert list(repository.root.iterdir()) == []
    with pytest.raises(InspectionNotFound):
        repository.get(record["id"])


def test_delete_unknown_raises(tmp_path: Path):
    with pytest.raises(InspectionNotFound):
        _repository(tmp_path).delete("no-existe")


def test_clear_removes_every_record_and_artifacts(tmp_path: Path):
    repository = _repository(tmp_path)
    repository.save(b"a", b"b", dict(PAYLOAD))
    repository.save(b"c", b"d", dict(PAYLOAD))
    (repository.root / ".gitkeep").write_text("", encoding="utf-8")

    assert repository.clear() == 2

    assert [path.name for path in repository.root.iterdir()] == [".gitkeep"]
    assert repository.list() == []


def test_list_skips_corrupt_and_non_object_records(tmp_path: Path):
    repository = _repository(tmp_path)
    record = repository.save(b"original", b"result", dict(PAYLOAD))
    (repository.root / "roto.json").write_text("{no es json", encoding="utf-8")
    (repository.root / "lista.json").write_text("[1, 2, 3]", encoding="utf-8")

    listing = repository.list()

    assert [item["id"] for item in listing] == [record["id"]]


# -- alcance por dueño (ADR-018) -----------------------------------------


def test_clear_unassigned_leaves_the_owned(tmp_path: Path):
    repository = _repository(tmp_path)
    owned = repository.save(
        b"a",
        b"b",
        {
            **PAYLOAD,
            "owner": {"id": "u-nico", "username": "nico", "display_name": "Nico"},
        },
    )
    repository.save(b"a", b"b", dict(PAYLOAD))

    assert repository.clear(unassigned=True) == 1
    assert [item["id"] for item in repository.list()] == [owned["id"]]
    assert repository.list(unassigned=True) == []
