"""Frontera bytes ↔ matrices."""

from __future__ import annotations

import numpy as np
import pytest

from core.exceptions import InvalidImage
from core.io import encode_png, read_photo


def test_read_photo_decodes_png(png_bytes: bytes):
    photo = read_photo(png_bytes)
    assert photo.format == "PNG"
    assert (photo.width, photo.height) == (240, 240)
    assert photo.image.dtype == np.uint8
    assert photo.image.shape == (240, 240, 3)


def test_read_photo_rejects_garbage():
    with pytest.raises(InvalidImage):
        read_photo(b"no soy una imagen")


def test_read_photo_rejects_empty():
    with pytest.raises(InvalidImage):
        read_photo(b"")


def test_encode_png_is_lossless(leaf_image: np.ndarray):
    decoded = read_photo(encode_png(leaf_image))
    assert np.array_equal(decoded.image, leaf_image)


def test_encode_png_validates_input():
    with pytest.raises(ValueError):
        encode_png(np.zeros((10, 10), dtype=np.uint8))
