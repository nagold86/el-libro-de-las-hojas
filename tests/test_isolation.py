"""Aislamiento hoja/fondo: recorte, primer plano, sin hoja y determinismo."""

from __future__ import annotations

import json

import numpy as np
import pytest

from core.isolation import LeafIsolator
from core.orchestrator import LeafInspector
from core.render import render_overlay


def test_isolates_a_leaf_from_the_background(leaf_on_background: np.ndarray):
    result = LeafIsolator().isolate(leaf_on_background)

    assert result.has_leaf is True
    assert result.report.method == "grabcut"
    assert result.report.analysis_width == result.image.shape[1]
    assert result.report.analysis_height == result.image.shape[0]
    assert result.report.bbox[0] > 0
    assert result.report.bbox[1] > 0
    assert result.report.bbox[2] < leaf_on_background.shape[1]
    assert result.report.bbox[3] < leaf_on_background.shape[0]
    assert result.mask.mean() > 0.5

    # El fondo del recorte viaja en negro; la hoja conserva su color.
    assert np.all(result.image[~result.mask] == 0)
    center = result.image[result.image.shape[0] // 2, result.image.shape[1] // 2]
    assert int(center[1]) > int(center[0])


def test_closeup_is_preserved(leaf_image: np.ndarray):
    result = LeafIsolator().isolate(leaf_image)

    assert result.report.method == "primer_plano"
    assert result.image.shape == leaf_image.shape
    assert np.array_equal(result.image, leaf_image)
    assert result.mask.all()


def test_document_without_leaf_is_empty(document_image: np.ndarray):
    result = LeafIsolator().isolate(document_image)

    assert result.has_leaf is False
    assert result.report.method == "sin_hoja"
    assert result.report.warnings == ("sin_hoja",)
    assert not result.mask.any()


def test_isolation_is_deterministic(leaf_on_background: np.ndarray):
    first = LeafIsolator().isolate(leaf_on_background)
    second = LeafIsolator().isolate(leaf_on_background)

    assert np.array_equal(first.mask, second.mask)
    assert np.array_equal(first.image, second.image)
    assert first.report == second.report


def test_inspector_analyses_the_isolated_crop(leaf_on_background: np.ndarray):
    result = LeafInspector().inspect(leaf_on_background)

    assert result.isolation.method == "grabcut"
    assert result.image.shape[:2] == result.lesion_mask.shape
    assert result.image.shape[:2] == result.vein_mask.shape
    assert result.image.shape[0] < leaf_on_background.shape[0]
    assert result.quality.valid_fraction <= 1.0
    assert result.lesions.area_fraction >= 0.0

    payload = result.to_dict()
    isolation = payload["trace"]["isolation"]
    assert isolation["method"] == "grabcut"
    assert isolation["analysis"]["width"] == result.image.shape[1]
    assert isolation["analysis"]["height"] == result.image.shape[0]
    json.dumps(payload)

    # El overlay del router debe aceptar exactamente el recorte y sus máscaras.
    overlay = render_overlay(result.image, result.lesion_mask, result.vein_mask)
    assert overlay.shape == result.image.shape


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_side": 10},
        {"closeup_fraction": 0.0},
        {"min_leaf_fraction": 0.0},
        {"rng_seed": -1},
    ],
)
def test_rejects_invalid_options(kwargs):
    with pytest.raises(ValueError):
        LeafIsolator(**kwargs)


def test_rejects_non_rgb_input():
    with pytest.raises(ValueError):
        LeafIsolator().isolate(np.zeros((20, 20), dtype=np.uint8))
