"""Puerta de dominio: acepta hojas y rechaza escenas que no lo son."""

from __future__ import annotations

import numpy as np
import pytest

from core.domain import DomainThresholds, LeafDomainGate


def _valid(image: np.ndarray) -> np.ndarray:
    return np.ones(image.shape[:2], dtype=bool)


def test_leaf_is_in_domain(leaf_image: np.ndarray):
    report = LeafDomainGate().evaluate(leaf_image, _valid(leaf_image))

    assert report.in_domain is True
    assert report.score <= 1
    assert report.gate == "envelope_v1"
    assert set(report.features) == {
        "exg_mean",
        "green_fraction",
        "green_hue_fraction",
        "bright_fraction",
        "local_variance",
        "entropy",
    }


def test_green_closeup_is_in_domain():
    """Un primer plano de hoja verde debe pasar aunque no tenga fondo."""
    rng = np.random.default_rng(3)
    base = np.zeros((240, 240, 3), dtype=np.float32)
    base[..., 0], base[..., 1], base[..., 2] = 60, 150, 55
    yy = np.linspace(-20, 20, 240, dtype=np.float32)[:, None, None]
    image = np.clip(base + yy + rng.normal(0, 12, base.shape), 0, 255).astype(np.uint8)

    report = LeafDomainGate().evaluate(image, _valid(image))

    assert report.in_domain is True
    assert report.score <= 1


def test_document_is_rejected_with_reasons(document_image: np.ndarray):
    report = LeafDomainGate().evaluate(document_image, _valid(document_image))

    assert report.in_domain is False
    assert report.score >= 2
    assert any("verde insuficiente" in reason for reason in report.reasons)
    assert any("demasiado brillo" in reason for reason in report.reasons)


def test_flat_wall_is_rejected():
    wall = np.full((240, 240, 3), 188, dtype=np.uint8)

    report = LeafDomainGate().evaluate(wall, _valid(wall))

    assert report.in_domain is False
    assert any("textura plana" in reason for reason in report.reasons)


def test_blue_sky_is_rejected():
    sky = np.zeros((240, 240, 3), dtype=np.uint8)
    for row in range(240):
        t = row / 239
        sky[row, :] = (120 + 80 * t, 170 + 55 * t, 235 - 10 * t)

    report = LeafDomainGate().evaluate(sky, _valid(sky))

    assert report.in_domain is False
    assert any("verde insuficiente" in reason for reason in report.reasons)


def test_noise_is_rejected():
    rng = np.random.default_rng(11)
    noise = np.clip(rng.normal(120, 45, (240, 240, 3)), 0, 255).astype(np.uint8)

    report = LeafDomainGate().evaluate(noise, _valid(noise))

    assert report.in_domain is False
    assert report.score >= 2


def test_one_violation_is_tolerated(leaf_image: np.ndarray):
    # La hoja sintética tiene ExG ≈ 0.42: con el mínimo en 0.90 falla un solo rasgo.
    one_failure = DomainThresholds(min_exg=0.90, min_entropy=0.0, allowed_violations=1)
    strict = DomainThresholds(min_exg=0.90, min_entropy=0.0, allowed_violations=0)

    tolerant = LeafDomainGate(one_failure).evaluate(leaf_image, _valid(leaf_image))
    strict_report = LeafDomainGate(strict).evaluate(leaf_image, _valid(leaf_image))

    assert tolerant.score == 1
    assert tolerant.in_domain is True
    assert strict_report.in_domain is False


def test_without_valid_pixels_is_rejected(leaf_image: np.ndarray):
    report = LeafDomainGate().evaluate(leaf_image, np.zeros(leaf_image.shape[:2], dtype=bool))

    assert report.in_domain is False
    assert report.features == {}
    assert "no hay píxeles válidos" in report.reasons[0]


def test_is_deterministic(leaf_image: np.ndarray):
    gate = LeafDomainGate()

    assert gate.evaluate(leaf_image, _valid(leaf_image)) == gate.evaluate(
        leaf_image, _valid(leaf_image)
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_exg": -0.1},
        {"min_green_fraction": 1.5},
        {"min_local_variance": 500.0, "max_local_variance": 10.0},
        {"min_entropy": 7.0, "max_entropy": 6.0},
        {"allowed_violations": -1},
    ],
)
def test_rejects_invalid_thresholds(kwargs):
    with pytest.raises(ValueError):
        DomainThresholds(**kwargs)


def test_rejects_mask_shape_mismatch(leaf_image: np.ndarray):
    with pytest.raises(ValueError):
        LeafDomainGate().evaluate(leaf_image, np.ones((10, 10), dtype=bool))


def test_rejects_non_rgb_input():
    with pytest.raises(ValueError):
        LeafDomainGate().evaluate(np.zeros((10, 10), dtype=np.uint8), np.ones((10, 10), dtype=bool))
