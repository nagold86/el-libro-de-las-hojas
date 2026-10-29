"""Fachada pública del core. Nada de FastAPI ni de ``app`` acá."""

from __future__ import annotations

from core.descriptors import AppearanceMetrics, ColorTextureDescriber, Describer
from core.domain import DomainGate, DomainReport, DomainThresholds, LeafDomainGate
from core.exceptions import (
    InspectionNotFound,
    InvalidImage,
    LeafError,
    NotALeaf,
    UnusableImage,
    UploadTooLarge,
)
from core.io import Photo, encode_png, read_photo
from core.metrics import MaskAgreement, compare_masks
from core.morphometry import DefectMeasurer, DefectMetrics, Measurer
from core.orchestrator import InspectionResult, LeafInspector
from core.pipeline import Pipeline, PipelineSettings, build_pipeline, method_fingerprint
from core.preprocess import PreprocessResult, Preprocessor, StandardPreprocessor
from core.quality import QualityGate, QualityReport
from core.render import render_overlay
from core.segmentation import LesionSegmenter, SegmentationResult, Segmenter
from core.version import __version__

__all__ = [
    "AppearanceMetrics",
    "ColorTextureDescriber",
    "DefectMeasurer",
    "DefectMetrics",
    "Describer",
    "DomainGate",
    "DomainReport",
    "DomainThresholds",
    "InspectionNotFound",
    "InspectionResult",
    "InvalidImage",
    "LeafError",
    "LeafInspector",
    "LeafDomainGate",
    "LesionSegmenter",
    "MaskAgreement",
    "Measurer",
    "NotALeaf",
    "Photo",
    "Pipeline",
    "PipelineSettings",
    "PreprocessResult",
    "Preprocessor",
    "QualityGate",
    "QualityReport",
    "SegmentationResult",
    "Segmenter",
    "StandardPreprocessor",
    "UnusableImage",
    "UploadTooLarge",
    "__version__",
    "build_pipeline",
    "compare_masks",
    "encode_png",
    "method_fingerprint",
    "read_photo",
    "render_overlay",
]
