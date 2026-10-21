"""Orquestador: composición de etapas, rechazo temprano y resumen serializable."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

import core
from core.domain import DomainGate, DomainReport, DomainThresholds
from core.exceptions import NotALeaf, UnusableImage
from core.morphometry import DefectMeasurer
from core.orchestrator import LeafInspector
from core.pipeline import PipelineSettings, build_pipeline


class _RecordingGate(DomainGate):
    """Espía: guarda la imagen que recibe la compuerta de dominio."""

    name = "recording"

    def __init__(self) -> None:
        self.image: np.ndarray | None = None

    def evaluate(self, image: np.ndarray, valid_mask: np.ndarray) -> DomainReport:
        self.image = image.copy()
        return DomainReport(gate=self.name, in_domain=True, score=0, features={}, reasons=())


def test_inspection_exposes_the_contract(leaf_image: np.ndarray):
    result = LeafInspector().inspect(leaf_image)

    assert result.quality.usable is True
    assert result.lesions.count >= 1
    assert result.lesion_mask.shape == leaf_image.shape[:2]
    assert result.vein_mask.shape == leaf_image.shape[:2]

    payload = result.to_dict()
    assert set(payload) == {"quality", "lesions", "appearance", "trace"}
    assert payload["trace"]["isolation"]["method"] == "primer_plano"
    assert payload["trace"]["isolation"]["analysis"]["width"] == leaf_image.shape[1]
    assert payload["trace"]["domain"]["gate"] == "envelope_v1"
    assert payload["trace"]["segmentation"]["step"] == "redness_threshold"
    json.dumps(payload)  # nada de numpy ni tuplas: debe viajar como JSON


def test_unusable_image_raises_before_measuring(blank_image: np.ndarray):
    with pytest.raises(UnusableImage):
        LeafInspector().inspect(blank_image)


def test_non_leaf_raises_before_measuring(document_image: np.ndarray):
    with pytest.raises(NotALeaf) as excinfo:
        LeafInspector().inspect(document_image)

    assert "no parece superficie de hoja" in str(excinfo.value)


def test_domain_gate_measures_the_original_image(leaf_image: np.ndarray):
    # El balance de blancos neutraliza escenas verdes cerradas: la compuerta
    # debe decidir sobre los píxeles originales, no sobre la versión balanceada.
    gate = _RecordingGate()
    inspector = LeafInspector(pipeline=replace(build_pipeline(), domain_gate=gate))

    inspector.inspect(leaf_image)

    assert np.array_equal(gate.image, leaf_image)


def test_quality_threshold_can_be_relaxed(blank_image: np.ndarray):
    settings = PipelineSettings(
        min_sharpness=0.0,
        # La imagen plana tampoco es una hoja: se relajan ambas puertas para
        # probar solo la propagación del umbral de nitidez.
        domain_thresholds=DomainThresholds(allowed_violations=6),
    )
    inspector = LeafInspector(pipeline=build_pipeline(settings))

    result = inspector.inspect(blank_image)

    assert result.quality.usable is True
    assert result.lesions.count == 0


def test_pipeline_and_strategy_cannot_be_mixed():
    with pytest.raises(ValueError):
        LeafInspector(pipeline=build_pipeline(), measurer=DefectMeasurer())


def test_settings_reach_the_concrete_stages():
    pipeline = build_pipeline(PipelineSettings(min_lesion_area_fraction=0.01, tile_grid=4))

    assert pipeline.segmenter.min_area_fraction == 0.01
    assert pipeline.preprocessor.tile_grid == 4


def test_facade_is_importable():
    assert core.__version__
    assert core.LeafInspector is LeafInspector
    assert core.render_overlay is not None


def test_inspection_rejects_non_rgb():
    with pytest.raises(ValueError):
        LeafInspector().inspect(np.zeros((20, 20), dtype=np.uint8))
