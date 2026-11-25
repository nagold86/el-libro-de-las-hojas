"""Preservation: el comportamiento que el arreglo de las imágenes de ejemplo no debe cambiar.

Observado sobre el código sin arreglar. No depende de dónde viva IMAGE_ROOT.
Hypothesis no está en el proyecto, así que las propiedades se ejercitan con
casos parametrizados y un generador pseudoaleatorio con semilla fija.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

from __future__ import annotations

import hashlib
import json
import random
import string
from pathlib import Path

import pytest

from app.routers import examples as examples_module

ROOT = Path(__file__).resolve().parents[1]
ORIGINALS = ROOT / "imgs"

EXPECTED_FILENAMES = [
    "IMG_20231015_110457_19.png",
    "IMG_20231015_110842_18.png",
    "IMG_20231015_111557_12.png",
    "IMG_20231015_110750_9.png",
    "IMG_20231015_110842_7.png",
    "IMG_20231015_110616_8.png",
    "IMG_20231015_110457_16.png",
    "IMG_20231015_110932_9.png",
    "IMG_20231015_111000_11.png",
    "IMG_20231015_111757_15.png",
]


def _random_names(count: int = 60, seed: int = 20231015) -> list[str]:
    rng = random.Random(seed)
    alphabet = string.ascii_letters + string.digits + "._-"
    names = []
    for _ in range(count):
        stem = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 24)))
        ext = rng.choice([".png", ".jpg", ".py", ".toml", ""])
        name = stem + ext
        if name not in EXPECTED_FILENAMES and name.strip("."):
            names.append(name)
    return names


# --- Requirement 3.1: el catálogo no cambia -------------------------------------


def test_catalogue_has_ten_entries_with_expected_fields(client):
    response = client.get("/api/examples")

    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 10
    assert [e["filename"] for e in entries] == EXPECTED_FILENAMES
    for entry in entries:
        assert set(entry) == {"filename", "title", "description", "image_url", "preview_url"}
        assert entry["title"] and entry["description"]
        assert entry["image_url"] == f"/api/examples/{entry['filename']}"


def test_catalogue_is_identical_across_requests(client):
    first = client.get("/api/examples").json()
    second = client.get("/api/examples").json()

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# --- Requirements 3.2 y 3.3: nada fuera del catálogo se sirve -------------------


@pytest.mark.parametrize(
    "name",
    ["augmented_0_0.png", "..%2Fapp%2Fmain.py", "..%2Fpyproject.toml", "%2e%2e%2fpyproject.toml"],
)
def test_known_unlisted_and_traversal_names_return_404(client, name):
    assert client.get(f"/api/examples/{name}").status_code == 404


def test_dotdot_path_traversal_never_serves_files(client):
    for url in ("/api/examples/../pyproject.toml", "/api/examples/..%5Cpyproject.toml"):
        response = client.get(url)
        assert response.status_code in (404, 405)
        assert "[project]" not in response.text


@pytest.mark.parametrize("name", _random_names())
def test_random_names_outside_catalogue_are_404_without_touching_disk(client, monkeypatch, name):
    touched: list[Path] = []
    original_is_file = Path.is_file

    def spy_is_file(self, *args, **kwargs):
        if self.name == name:
            touched.append(self)
        return original_is_file(self, *args, **kwargs)

    monkeypatch.setattr(Path, "is_file", spy_is_file)

    response = client.get(f"/api/examples/{name}")

    assert response.status_code == 404
    assert touched == []


def test_catalogue_names_are_the_only_allowed_set():
    assert set(examples_module._EXAMPLES_BY_FILENAME) == set(EXPECTED_FILENAMES)


# --- Requirement 3.4: el empaquetado de Vercel sigue excluyendo todo lo demás ---

EXCLUDED_DIRS = ["imgs", "sandbox", "storage", "tests", "docs"]


def test_vercelignore_excludes_heavy_directories():
    lines = {
        line.strip()
        for line in (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    for directory in EXCLUDED_DIRS:
        assert any(line.startswith(f"{directory}/") for line in lines), directory


def test_vercel_json_excludes_heavy_directories():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    exclude = config["functions"]["app/main.py"]["excludeFiles"]
    for directory in EXCLUDED_DIRS:
        assert f"{directory}/**" in exclude, directory


# --- Requirement 3.5: con las originales presentes, se sirven igual -------------


@pytest.mark.skipif(not ORIGINALS.is_dir(), reason="imgs/ no existe localmente")
@pytest.mark.parametrize("filename", EXPECTED_FILENAMES)
def test_sample_bytes_match_original_when_present(client, filename):
    original = ORIGINALS / filename
    if not original.is_file():
        pytest.skip(f"{filename} no está en imgs/")

    response = client.get(f"/api/examples/{filename}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert hashlib.sha256(response.content).hexdigest() == hashlib.sha256(original.read_bytes()).hexdigest()
