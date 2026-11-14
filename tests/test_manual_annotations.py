"""Manual brush overrides recalculate masks and retain an automatic erase path."""

from __future__ import annotations

from core.descriptors import ColorTextureDescriber
from core.manual_annotations import apply_manual_annotations
from core.morphometry import DefectMeasurer
from core.orchestrator import LeafInspector


def _stroke(label: str, x: float, y: float, width: float = 0.04) -> dict:
    return {"label": label, "width": width, "points": [{"x": x, "y": y}]}


def test_manual_disease_and_chlorosis_strokes_change_both_measures(leaf_image):
    inspector = LeafInspector()
    original = inspector.inspect(leaf_image)
    updated = apply_manual_annotations(
        original,
        [_stroke("diseased", 0.1, 0.1), _stroke("chlorosis", 0.9, 0.9)],
        inspector.pipeline.measurer,
        inspector.pipeline.describer,
    )

    assert updated.lesion_mask[24, 24]
    assert updated.chlorosis_mask[216, 216]
    assert updated.lesions.area_fraction > original.lesions.area_fraction
    assert updated.chlorosis.area_fraction > original.chlorosis.area_fraction
    assert updated.segmentation["manual_annotations_applied"] is True
    assert updated.layers[-1].key == "edicion_manual_mascaras"


def test_healthy_override_removes_auto_disease_and_eraser_restores_it(leaf_image):
    inspector = LeafInspector()
    original = inspector.inspect(leaf_image)
    healthy = apply_manual_annotations(
        original,
        [_stroke("healthy", 170 / 239, 90 / 239, 0.08)],
        inspector.pipeline.measurer,
        inspector.pipeline.describer,
    )
    restored = apply_manual_annotations(
        original,
        [
            _stroke("diseased", 0.1, 0.1),
            _stroke("erase", 0.1, 0.1),
        ],
        inspector.pipeline.measurer,
        inspector.pipeline.describer,
    )

    assert not healthy.lesion_mask[90, 170]
    assert healthy.lesions.area_fraction < original.lesions.area_fraction
    assert (restored.lesion_mask == original.lesion_mask).all()
    assert (restored.chlorosis_mask == original.chlorosis_mask).all()


def test_manual_correction_uses_the_injected_measurement_strategies(leaf_image):
    inspector = LeafInspector()
    original = inspector.inspect(leaf_image)
    measurer = DefectMeasurer(min_area_px=1)
    updated = apply_manual_annotations(
        original,
        [_stroke("diseased", 0.1, 0.1, 0.02)],
        measurer,
        ColorTextureDescriber(),
    )

    assert updated.lesions.count >= original.lesions.count
