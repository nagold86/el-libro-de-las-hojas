"""Orquestador único del pipeline.

Aragorn es el dueño de esta clase: es la única que compone etapas y la única que
puede lanzar ``UnusableImage`` antes de medir. La API la usa como caja negra.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from core.descriptors import AppearanceMetrics, Describer
from core.domain import DomainGate, DomainReport
from core.exceptions import NotALeaf, UnusableImage
from core.isolation import IsolationReport, LeafIsolator
from core.morphometry import DefectMetrics, Measurer
from core.pipeline import Pipeline, build_pipeline
from core.preprocess import Preprocessor
from core.quality import QualityGate, QualityReport
from core.segmentation import Segmenter


@dataclass(frozen=True)
class InspectionResult:
    quality: QualityReport
    domain: DomainReport
    lesions: DefectMetrics
    appearance: AppearanceMetrics
    preprocess: dict[str, Any]
    segmentation: dict[str, Any]
    lesion_mask: np.ndarray
    vein_mask: np.ndarray
    # Imagen efectivamente analizada: recorte de hoja con fondo en negro, o la
    # original si el aislamiento no tenía nada que separar. El overlay se
    # renderiza sobre esta imagen, no sobre el archivo subido.
    image: np.ndarray
    isolation: IsolationReport

    def to_dict(self) -> dict[str, Any]:
        """Resumen serializable. Las máscaras no viajan: solo su medición."""
        return {
            "quality": {
                "usable": self.quality.usable,
                "sharpness": self.quality.sharpness,
                "saturated_fraction": self.quality.saturated_fraction,
                "valid_fraction": self.quality.valid_fraction,
                "flags": list(self.quality.flags),
            },
            "lesions": asdict(self.lesions),
            "appearance": asdict(self.appearance),
            "trace": {
                "isolation": self.isolation.to_dict(),
                "preprocess": dict(self.preprocess),
                "domain": {
                    "gate": self.domain.gate,
                    "score": self.domain.score,
                    "features": dict(self.domain.features),
                },
                "segmentation": dict(self.segmentation),
            },
        }


class LeafInspector:
    """Aislamiento → preproceso → calidad → dominio → segmentación → morfometría → descriptores."""

    def __init__(
        self,
        pipeline: Pipeline | None = None,
        *,
        isolator: LeafIsolator | None = None,
        preprocessor: Preprocessor | None = None,
        domain_gate: DomainGate | None = None,
        segmenter: Segmenter | None = None,
        measurer: Measurer | None = None,
        describer: Describer | None = None,
        quality_gate: QualityGate | None = None,
    ) -> None:
        injected = (
            isolator,
            preprocessor,
            domain_gate,
            segmenter,
            measurer,
            describer,
            quality_gate,
        )
        if pipeline is not None and any(part is not None for part in injected):
            raise ValueError("Inyectá un Pipeline completo o estrategias sueltas, no ambos.")

        if pipeline is None:
            base = build_pipeline()
            pipeline = Pipeline(
                isolator=isolator or base.isolator,
                preprocessor=preprocessor or base.preprocessor,
                domain_gate=domain_gate or base.domain_gate,
                segmenter=segmenter or base.segmenter,
                measurer=measurer or base.measurer,
                describer=describer or base.describer,
                quality_gate=quality_gate or base.quality_gate,
            )
        self.pipeline = pipeline

    def inspect(self, image: np.ndarray) -> InspectionResult:
        isolation = self.pipeline.isolator.isolate(image)
        if not isolation.has_leaf:
            raise NotALeaf(
                "La imagen no parece superficie de hoja: no se encontró una hoja "
                "dominante sobre el fondo."
            )

        analysis = isolation.image
        preprocessed = self.pipeline.preprocessor.apply(analysis)
        quality = self.pipeline.quality_gate.evaluate(
            preprocessed.image, preprocessed.valid_mask
        )
        if not quality.usable:
            reason = ", ".join(quality.flags) or "reglas de calidad"
            raise UnusableImage(f"Imagen no utilizable: {reason}.")

        # La compuerta mide color original del recorte: el balance de blancos
        # neutraliza escenas dominadas por verde y volvería invisible una hoja
        # legítima.
        domain = self.pipeline.domain_gate.evaluate(analysis, preprocessed.valid_mask)
        if not domain.in_domain:
            reasons = "; ".join(domain.reasons) or "rasgos fuera de la envolvente foliar"
            raise NotALeaf(f"La imagen no parece superficie de hoja: {reasons}.")

        segmentation = self.pipeline.segmenter.segment(
            preprocessed.image, preprocessed.valid_mask
        )
        lesions = self.pipeline.measurer.measure(
            segmentation.lesions, segmentation.veins, preprocessed.valid_mask
        )
        appearance = self.pipeline.describer.describe(
            preprocessed.image, segmentation.lesions, preprocessed.valid_mask
        )

        return InspectionResult(
            quality=quality,
            domain=domain,
            lesions=lesions,
            appearance=appearance,
            preprocess=preprocessed.params,
            segmentation=segmentation.params,
            lesion_mask=segmentation.lesions,
            vein_mask=segmentation.veins,
            image=analysis,
            isolation=isolation.report,
        )
