"""Orquestador único del pipeline.

Aragorn es el dueño de esta clase: es la única que compone etapas y la única que
puede lanzar ``UnusableImage`` antes de medir. La API la usa como caja negra.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from core.chlorosis import ChlorosisDetector
from core.descriptors import AppearanceMetrics, Describer
from core.domain import DomainGate, DomainReport
from core.exceptions import NotALeaf, UnusableImage
from core.isolation import IsolationReport, LeafIsolator
from core.layers import Layer
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
    # Clorosis: pérdida de verde. Se mide y se publica aparte porque no es una
    # mancha parda y sumarla a ``lesions`` inflaría el área afectada.
    chlorosis: DefectMetrics
    chlorosis_params: dict[str, Any]
    appearance: AppearanceMetrics
    preprocess: dict[str, Any]
    segmentation: dict[str, Any]
    lesion_mask: np.ndarray
    vein_mask: np.ndarray
    chlorosis_mask: np.ndarray
    valid_mask: np.ndarray
    # Imagen efectivamente analizada: recorte de hoja con fondo en negro, o la
    # original si el aislamiento no tenía nada que separar. El overlay se
    # renderiza sobre esta imagen, no sobre el archivo subido.
    image: np.ndarray
    isolation: IsolationReport
    # Traza visual del pipeline, en orden de ejecución. No viaja en ``to_dict``:
    # la API guarda cada capa como PNG y publica su ficha en ``trace.layers``.
    layers: tuple[Layer, ...] = ()

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
            "chlorosis": asdict(self.chlorosis),
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
                "chlorosis": dict(self.chlorosis_params),
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
        chlorosis: ChlorosisDetector | None = None,
    ) -> None:
        injected = (
            isolator,
            preprocessor,
            domain_gate,
            segmenter,
            measurer,
            describer,
            quality_gate,
            chlorosis,
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
                chlorosis=chlorosis or base.chlorosis,
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
        # La nitidez y la exposición se juzgan sobre la vista de presentación:
        # es la imagen con la que se calibró el umbral. Medirla sobre la vista
        # canónica exigiría recalibrar ``min_sharpness`` (ADR-013).
        quality = self.pipeline.quality_gate.evaluate(
            preprocessed.display, preprocessed.valid_mask
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
        # Familia aparte: mide tejido amarillo, no tejido pardo. Se pasa la
        # máscara de lesiones solo para dejar registrado cuánto se solapan.
        chlorosis = self.pipeline.chlorosis.detect(
            preprocessed.image, preprocessed.valid_mask, segmentation.lesions
        )
        chlorosis_metrics = self.pipeline.measurer.measure(
            chlorosis.mask, segmentation.veins, preprocessed.valid_mask
        )
        # Los descriptores describen la hoja, no la corrección que se le hizo.
        appearance = self.pipeline.describer.describe(
            preprocessed.image, segmentation.lesions, preprocessed.valid_mask
        )

        return InspectionResult(
            quality=quality,
            domain=domain,
            lesions=lesions,
            chlorosis=chlorosis_metrics,
            chlorosis_params=chlorosis.params,
            appearance=appearance,
            preprocess=preprocessed.params,
            segmentation=segmentation.params,
            lesion_mask=segmentation.lesions,
            vein_mask=segmentation.veins,
            chlorosis_mask=chlorosis.mask,
            valid_mask=preprocessed.valid_mask,
            image=analysis,
            isolation=isolation.report,
            # Orden de ejecución: lo que entró, lo que se corrigió y lo que se
            # decidió. La pantalla lo muestra tal cual.
            layers=(
                *isolation.layers,
                *preprocessed.layers,
                *segmentation.layers,
                *chlorosis.layers,
            ),
        )
