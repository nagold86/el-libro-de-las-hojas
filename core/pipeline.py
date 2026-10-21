"""Composición del pipeline. Aragorn decide el orden y las dependencias.

Este módulo es el único lugar donde se eligen las implementaciones concretas.
El orquestador recibe un ``Pipeline`` ya armado; los routers no construyen
etapas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.descriptors import ColorTextureDescriber, Describer
from core.domain import DomainGate, DomainThresholds, LeafDomainGate
from core.isolation import LeafIsolator
from core.morphometry import DefectMeasurer, Measurer
from core.preprocess import Preprocessor, StandardPreprocessor
from core.quality import QualityGate
from core.segmentation import LesionSegmenter, Segmenter


@dataclass(frozen=True)
class PipelineSettings:
    """Parámetros declarados de la corrida. Cambiarlos exige revisar Boromir."""

    clip_limit: float = 2.0
    tile_grid: int = 8
    denoise: bool = True
    isolation_max_side: int = 1100
    isolation_closeup_fraction: float = 0.97
    isolation_min_leaf_fraction: float = 0.005
    min_lesion_area_fraction: float = 0.0002
    min_sharpness: float = 15.0
    max_saturated_fraction: float = 0.20
    min_valid_fraction: float = 0.50
    domain_thresholds: DomainThresholds = field(default_factory=DomainThresholds)


@dataclass(frozen=True)
class Pipeline:
    isolator: LeafIsolator
    preprocessor: Preprocessor
    domain_gate: DomainGate
    segmenter: Segmenter
    measurer: Measurer
    describer: Describer
    quality_gate: QualityGate


def build_pipeline(settings: PipelineSettings | None = None) -> Pipeline:
    """Arma el pipeline clásico con las implementaciones por defecto."""
    config = settings or PipelineSettings()
    return Pipeline(
        isolator=LeafIsolator(
            max_side=config.isolation_max_side,
            closeup_fraction=config.isolation_closeup_fraction,
            min_leaf_fraction=config.isolation_min_leaf_fraction,
        ),
        preprocessor=StandardPreprocessor(
            clip_limit=config.clip_limit,
            tile_grid=config.tile_grid,
            denoise=config.denoise,
        ),
        domain_gate=LeafDomainGate(config.domain_thresholds),
        segmenter=LesionSegmenter(min_area_fraction=config.min_lesion_area_fraction),
        measurer=DefectMeasurer(),
        describer=ColorTextureDescriber(),
        quality_gate=QualityGate(
            min_sharpness=config.min_sharpness,
            max_saturated_fraction=config.max_saturated_fraction,
            min_valid_fraction=config.min_valid_fraction,
        ),
    )
