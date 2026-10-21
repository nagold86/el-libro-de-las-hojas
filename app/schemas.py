"""Contrato con el cliente. Es la forma que ven el frontend y los tests."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str
    version: str


class ConfigOut(BaseModel):
    max_upload_bytes: int
    allowed_formats: list[str]


class ImageOut(BaseModel):
    filename: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    format: str


class QualityOut(BaseModel):
    usable: bool
    sharpness: float = Field(ge=0)
    saturated_fraction: float = Field(ge=0, le=1)
    valid_fraction: float = Field(ge=0, le=1)
    flags: list[str]


class LesionsOut(BaseModel):
    count: int = Field(ge=0)
    area_fraction: float = Field(ge=0, le=1)
    mean_area_px: float = Field(ge=0)
    max_feret_px: float = Field(ge=0)
    mean_circularity: float = Field(ge=0, le=1)
    orientation_deg: float | None = None
    vein_density: float = Field(ge=0, le=1)


class AppearanceOut(BaseModel):
    lab_mean: list[float]
    lab_std: list[float]
    exg_mean: float
    browning_index: float
    texture_entropy: float
    local_variance: float
    gradient_mean: float
    lesion_color_delta: float


class TraceOut(BaseModel):
    preprocess: dict[str, Any]
    # Vacío en registros anteriores a la compuerta de dominio; los nuevos
    # siempre traen {gate, score, features}.
    domain: dict[str, Any] = Field(default_factory=dict)
    # Vacío en registros anteriores al aislamiento de hoja; los nuevos traen
    # método, bbox, dimensiones y fracciones.
    isolation: dict[str, Any] = Field(default_factory=dict)
    segmentation: dict[str, Any]


class InspectionOut(BaseModel):
    id: str
    created_at: datetime
    image: ImageOut
    quality: QualityOut
    lesions: LesionsOut
    appearance: AppearanceOut
    trace: TraceOut
    result_url: str
    original_url: str


class LotTotalsOut(BaseModel):
    images: int = Field(ge=0)
    lesions: int = Field(ge=0)
    mean_lesions: float = Field(ge=0)
    median_lesions: float = Field(ge=0)
    mean_area_fraction: float = Field(ge=0, le=1)
    median_area_fraction: float = Field(ge=0, le=1)
    max_area_fraction: float = Field(ge=0, le=1)
    mean_feret_px: float = Field(ge=0)
    max_feret_px: float = Field(ge=0)
    mean_vein_density: float = Field(ge=0, le=1)
    mean_browning_index: float = Field(ge=0)
    mean_sharpness: float = Field(ge=0)


class SeverityBinOut(BaseModel):
    key: str
    label: str
    count: int = Field(ge=0)
    fraction: float = Field(ge=0, le=1)
    min_area_fraction: float = Field(ge=0, le=1)
    max_area_fraction: float = Field(ge=0, le=1)


class LotPointOut(BaseModel):
    id: str
    filename: str
    created_at: datetime
    area_fraction: float = Field(ge=0, le=1)
    lesion_count: int = Field(ge=0)
    max_feret_px: float = Field(ge=0)
    mean_circularity: float = Field(ge=0, le=1)
    vein_density: float = Field(ge=0, le=1)
    browning_index: float = Field(ge=0)
    sharpness: float = Field(ge=0)
    quality_flags: list[str]
    isolation_method: str


class LotReportOut(BaseModel):
    generated_at: datetime
    totals: LotTotalsOut
    severity: list[SeverityBinOut]
    dominant_severity: str
    has_severe: bool
    points: list[LotPointOut]
    worst: list[LotPointOut]
    quality_flags: dict[str, int]
    isolation_methods: dict[str, int]
