"""Métricas de acuerdo: valores exactos sobre máscaras conocidas."""

from __future__ import annotations

import json

import numpy as np
import pytest

from core.metrics import MaskAgreement, compare_masks


def test_identical_masks_agree_perfectly():
    mask = np.zeros((6, 6), dtype=bool)
    mask[1:3, 1:3] = True

    agreement = compare_masks(mask, mask.copy())

    assert agreement.intersection == 4
    assert agreement.union == 4
    assert agreement.iou == 1.0
    assert agreement.dice == 1.0
    assert agreement.precision == 1.0
    assert agreement.recall == 1.0


def test_disjoint_masks_score_zero():
    predicted = np.zeros((4, 4), dtype=bool)
    reference = np.zeros((4, 4), dtype=bool)
    predicted[0, 0] = True
    reference[3, 3] = True

    agreement = compare_masks(predicted, reference)

    assert agreement.intersection == 0
    assert agreement.union == 2
    assert agreement.iou == 0.0
    assert agreement.dice == 0.0
    assert agreement.precision == 0.0
    assert agreement.recall == 0.0


def test_partial_overlap_uses_iou_and_dice_by_hand():
    # 4 px predichos, 4 px anotados, 2 en común: IoU 2/6, Dice 4/8.
    predicted = np.zeros((3, 3), dtype=bool)
    reference = np.zeros((3, 3), dtype=bool)
    predicted[0, 0] = predicted[0, 1] = predicted[1, 0] = predicted[1, 1] = True
    reference[1, 0] = reference[1, 1] = reference[2, 0] = reference[2, 1] = True

    agreement = compare_masks(predicted, reference)

    assert agreement.intersection == 2
    assert agreement.union == 6
    assert agreement.iou == pytest.approx(2 / 6, abs=1e-6)
    assert agreement.dice == pytest.approx(4 / 8, abs=1e-6)
    assert agreement.precision == pytest.approx(2 / 4, abs=1e-6)
    assert agreement.recall == pytest.approx(2 / 4, abs=1e-6)


def test_excess_is_punished_by_precision_not_recall():
    predicted = np.zeros((5, 5), dtype=bool)
    reference = np.zeros((5, 5), dtype=bool)
    predicted[:4, :4] = True
    reference[:2, :2] = True

    agreement = compare_masks(predicted, reference)

    assert agreement.recall == 1.0  # encontró todo lo anotado
    assert agreement.precision == pytest.approx(4 / 16, abs=1e-6)  # y tres veces más


def test_two_empty_masks_are_agreement_not_undefined():
    empty = np.zeros((8, 8), dtype=bool)

    agreement = compare_masks(empty, empty.copy())

    assert agreement.union == 0
    assert agreement.iou == 1.0
    assert agreement.dice == 1.0
    assert agreement.precision == 0.0


def test_shape_mismatch_is_rejected():
    with pytest.raises(ValueError):
        compare_masks(np.zeros((4, 4), dtype=bool), np.zeros((4, 5), dtype=bool))


def test_two_dimensional_masks_required():
    with pytest.raises(ValueError):
        compare_masks(np.zeros((4, 4, 3), dtype=bool), np.zeros((4, 4, 3), dtype=bool))


def test_integer_masks_are_accepted():
    predicted = np.array([[0, 1], [0, 0]], dtype=np.uint8)
    reference = np.array([[0, 1], [0, 0]], dtype=np.uint8)

    assert compare_masks(predicted, reference).iou == 1.0


def test_agreement_travels_as_json():
    agreement = compare_masks(np.ones((2, 2), dtype=bool), np.ones((2, 2), dtype=bool))

    assert isinstance(agreement, MaskAgreement)
    payload = json.loads(json.dumps(agreement.to_dict()))
    assert payload["union"] == 4
    assert payload["iou"] == 1.0
