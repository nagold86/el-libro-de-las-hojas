"""Miniaturas WebP y caché de las imágenes de muestra.

**Validates: Requirements 1.1, 1.2, 1.5, 2.1, 2.2, 3.1, 3.2, 3.3**
"""

from __future__ import annotations

import json
import random
import string
import subprocess
from pathlib import Path

import pytest

from app.routers import examples as examples_module

ROOT = Path(__file__).resolve().parents[1]
PREVIEW_DIR = ROOT / "app" / "example_images" / "previews"
FILENAMES = [example["filename"] for example in examples_module.EXAMPLES]
IMMUTABLE = "public, max-age=31536000, immutable"


def test_catalogue_entries_include_preview_url(client):
    for entry in client.get("/api/examples").json():
        stem = entry["filename"].removesuffix(".png")
        assert entry["preview_url"] == f"/api/examples/previews/{stem}.webp"
        assert entry["image_url"] == f"/api/examples/{entry['filename']}"


@pytest.mark.parametrize("filename", FILENAMES)
def test_preview_is_served_as_webp_with_immutable_cache(client, filename):
    entry = next(e for e in client.get("/api/examples").json() if e["filename"] == filename)

    response = client.get(entry["preview_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == IMMUTABLE
    assert response.content[:4] == b"RIFF" and response.content[8:12] == b"WEBP"


def test_all_previews_together_weigh_less_than_150_kb(client):
    total = sum(
        len(client.get(entry["preview_url"]).content)
        for entry in client.get("/api/examples").json()
    )
    assert total < 150 * 1024


@pytest.mark.parametrize("filename", FILENAMES)
def test_png_keeps_content_type_and_gets_immutable_cache(client, filename):
    response = client.get(f"/api/examples/{filename}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == IMMUTABLE


def _random_names(count: int = 40, seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    alphabet = string.ascii_letters + string.digits + "._-"
    return [
        "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 24))) + ".webp"
        for _ in range(count)
    ]


@pytest.mark.parametrize(
    "name",
    ["augmented_0_0.webp", "..%2Fapp%2Fmain.py", "..%2F..%2Fpyproject.toml", "%2e%2e%2fx.webp"]
    + _random_names(),
)
def test_unlisted_preview_names_are_404_without_long_cache(client, name):
    response = client.get(f"/api/examples/previews/{name}")

    assert response.status_code == 404
    assert "immutable" not in response.headers.get("cache-control", "")


def test_unlisted_png_404_has_no_long_cache(client):
    response = client.get("/api/examples/augmented_0_0.png")

    assert response.status_code == 404
    assert "immutable" not in response.headers.get("cache-control", "")


def test_preview_files_exist_for_every_example():
    for filename in FILENAMES:
        assert (PREVIEW_DIR / filename.replace(".png", ".webp")).is_file(), filename


def _exclusion_patterns() -> list[str]:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    raw = config["functions"]["app/main.py"]["excludeFiles"]
    return [part.strip() for part in raw.strip("{}").split(",")]


def test_previews_are_not_excluded_from_the_vercel_bundle():
    ignore_lines = [
        line.strip()
        for line in (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for directory in ("imgs", "sandbox", "storage", "tests", "docs"):
        assert any(line.startswith(f"{directory}/") for line in ignore_lines)
    for line in ignore_lines:
        assert not "app/example_images".startswith(line.rstrip("/*")) or line.startswith("!")
    for pattern in _exclusion_patterns():
        assert not pattern.startswith("app/")


def test_previews_are_not_ignored_by_git():
    paths = [f"app/example_images/previews/{f.replace('.png', '.webp')}" for f in FILENAMES]
    result = subprocess.run(
        ["git", "check-ignore", *paths], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 1, result.stdout
