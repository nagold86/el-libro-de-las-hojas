"""Property 1 (Bug Condition): las muestras del catálogo se sirven sin ``imgs/``.

Simula Vercel: el directorio ``imgs/`` del repositorio no existe en el despliegue.
La simulación redirige a un directorio vacío solo la fuente que apunte a ``imgs/``;
si el módulo ya sirve desde ``app/example_images`` (tras el arreglo) no se toca,
de modo que la prueba sigue representando a Vercel.

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.routers import examples as examples_module

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DIR = ROOT / "imgs"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FILENAMES = [example["filename"] for example in examples_module.EXAMPLES]


@pytest.fixture
def without_imgs(monkeypatch, tmp_path):
    """Oculta ``imgs/`` al router, sin tocar ``app/example_images``."""
    empty = tmp_path / "vercel_sin_imgs"
    empty.mkdir()
    root = getattr(examples_module, "IMAGE_ROOT", None)
    if root is not None and Path(root).resolve() == ORIGINAL_DIR.resolve():
        monkeypatch.setattr(examples_module, "IMAGE_ROOT", empty)
    return empty


def _assert_served(client, filename: str) -> bytes:
    response = client.get(f"/api/examples/{filename}")
    assert response.status_code == 200, (
        f"{filename}: {response.status_code} {response.text}"
    )
    assert response.headers["content-type"] == "image/png"
    body = response.content
    assert body.startswith(PNG_SIGNATURE)
    original = ORIGINAL_DIR / filename
    if original.is_file():
        assert body == original.read_bytes()
    return body


@pytest.mark.parametrize("filename", FILENAMES)
def test_example_is_served_without_imgs_directory(client, without_imgs, filename):
    _assert_served(client, filename)


def test_example_can_be_downloaded_and_analyzed_without_imgs_directory(client, without_imgs):
    example = client.get("/api/examples").json()[0]
    body = _assert_served(client, example["filename"])

    analyzed = client.post(
        "/api/inspections",
        data={"method": "core2"},
        files={"file": (example["filename"], body, "image/png")},
    )

    assert analyzed.status_code == 201, analyzed.text
    assert analyzed.json()["trace"]["analysis_method"] == "core2"
