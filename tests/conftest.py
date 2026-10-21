"""Fixtures compartidas. El storage se aísla ANTES de importar la app."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from core.io import encode_png  # noqa: E402


@pytest.fixture
def settings_factory(tmp_path: Path):
    def make(**overrides) -> Settings:
        values = {
            "storage_dir": tmp_path / "storage",
            "frontend_dir": ROOT / "frontend",
            "max_upload_bytes": 2 * 1024 * 1024,
            "allowed_formats": frozenset({"PNG", "JPEG"}),
        }
        values.update(overrides)
        return Settings(**values)

    return make


@pytest.fixture
def settings(settings_factory) -> Settings:
    return settings_factory()


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def leaf_image() -> np.ndarray:
    """Superficie verde con dos manchas pardas y ruido reproducible."""
    height, width = 240, 240
    rng = np.random.default_rng(7)

    base = np.zeros((height, width, 3), dtype=np.float32)
    base[..., 0] = 74
    base[..., 1] = 122
    base[..., 2] = 58

    xx = np.linspace(-12, 12, width, dtype=np.float32)[None, :, None]
    yy = np.linspace(-12, 12, height, dtype=np.float32)[:, None, None]
    image = np.clip(base + xx + 0.6 * yy + rng.normal(0, 4, base.shape), 0, 255).astype(np.uint8)

    cv2.ellipse(image, (170, 90), (28, 20), 0, 0, 360, (92, 60, 38), -1)
    cv2.ellipse(image, (70, 170), (14, 10), 25, 0, 360, (110, 78, 48), -1)
    return image


@pytest.fixture
def leaf_on_background() -> np.ndarray:
    """Hoja verde sobre una mesa parda: el aislamiento debe recortar el fondo."""
    height, width = 320, 420
    rng = np.random.default_rng(11)

    background = np.zeros((height, width, 3), dtype=np.float32)
    background[..., 0] = 158
    background[..., 1] = 126
    background[..., 2] = 96
    image = np.clip(
        background + rng.normal(0, 6, background.shape), 0, 255
    ).astype(np.uint8)

    leaf = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(leaf, (220, 160), (120, 65), 12, 0, 360, 255, -1)
    cv2.line(leaf, (105, 190), (60, 230), 255, 8)

    leaf_color = np.zeros_like(image, dtype=np.float32)
    leaf_color[..., 0] = 78
    leaf_color[..., 1] = 126
    leaf_color[..., 2] = 60
    leaf_rgb = np.clip(
        leaf_color + rng.normal(0, 8, leaf_color.shape), 0, 255
    ).astype(np.uint8)
    selected = leaf > 0
    image[selected] = leaf_rgb[selected]

    cv2.ellipse(image, (250, 150), (18, 12), 0, 0, 360, (96, 62, 40), -1)
    return image


@pytest.fixture
def png_bytes(leaf_image: np.ndarray) -> bytes:
    return encode_png(leaf_image)


@pytest.fixture
def blank_image() -> np.ndarray:
    """Imagen legible pero sin nitidez: la puerta de calidad debe rechazarla."""
    return np.full((120, 120, 3), (100, 140, 70), dtype=np.uint8)


@pytest.fixture
def document_image() -> np.ndarray:
    """Nítida y bien expuesta, pero no es una hoja: la puerta de dominio la rechaza."""
    image = np.full((240, 240, 3), 246, dtype=np.uint8)
    rng = np.random.default_rng(5)
    for row in range(20, 220, 18):
        width = int(rng.integers(60, 200))
        cv2.rectangle(image, (20, row), (20 + width, row + 7), (30, 30, 34), -1)
    return image
