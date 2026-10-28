"""El corrector de máscaras escribe una máscara binaria y marca el origen humano."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from sandbox import anotar


@pytest.fixture()
def anotador(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    (tmp_path / "imgs").mkdir()
    image = np.full((40, 60, 3), 120, dtype=np.uint8)
    cv2.imwrite(str(tmp_path / "imgs" / "hoja.png"), image)
    masks = tmp_path / "data" / "golden" / "masks"
    masks.mkdir(parents=True)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "leaves": [
                    {
                        "id": "hoja",
                        "leaf": "hoja",
                        "file": "imgs/hoja.png",
                        "mask": "data/golden/masks/hoja.png",
                        "split": "calibration",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(anotar, "ROOT", tmp_path)
    monkeypatch.setattr(anotar, "MANIFEST", manifest)
    monkeypatch.setattr(anotar, "MASKS", masks)
    monkeypatch.setattr(anotar, "PROVENANCE", masks / "_provenance.json")
    return TestClient(anotar.app)


def _data_url(mask: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".png", mask)
    assert ok
    return "data:image/png;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def test_lists_only_the_requested_split(anotador: TestClient):
    rows = anotador.get("/api/entries?split=calibration").json()
    assert [row["id"] for row in rows] == ["hoja"]
    assert rows[0]["origin"] == "sin_mascara"
    assert anotador.get("/api/entries?split=test").json() == []


def test_save_marks_the_mask_as_human(anotador: TestClient, tmp_path: Path):
    mask = np.zeros((40, 60), dtype=np.uint8)
    mask[10:20, 5:30] = 255

    response = anotador.post("/api/save", json={"id": "hoja", "png": _data_url(mask)})

    assert response.status_code == 200
    assert response.json()["lesion_fraction_image"] == pytest.approx(250 / 2400, abs=1e-4)
    written = cv2.imread(str(tmp_path / "data" / "golden" / "masks" / "hoja.png"))
    assert written.shape == (40, 60, 3)
    assert int(written.max()) == 255 and int(written.min()) == 0
    provenance = json.loads(
        (tmp_path / "data" / "golden" / "masks" / "_provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["masks"]["hoja"]["origin"] == "human"
    assert anotador.get("/api/entries").json()[0]["origin"] == "human"


def test_save_rejects_a_mask_of_the_wrong_size(anotador: TestClient):
    small = np.zeros((10, 10), dtype=np.uint8)
    response = anotador.post("/api/save", json={"id": "hoja", "png": _data_url(small)})
    assert response.status_code == 400
