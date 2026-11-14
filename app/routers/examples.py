"""Curated leaf examples available to every signed-in app visitor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/examples", tags=["examples"])
IMAGE_ROOT = Path(__file__).resolve().parents[2] / "imgs"

EXAMPLES: tuple[dict[str, str], ...] = (
    {
        "filename": "IMG_20231015_110457_19.png",
        "title": "Muestra 01 · Casi uniforme",
        "description": "Superficie verde con muy pocas marcas visibles.",
    },
    {
        "filename": "IMG_20231015_110842_18.png",
        "title": "Muestra 02 · Marcas puntuales",
        "description": "Pequeños focos pardos separados.",
    },
    {
        "filename": "IMG_20231015_111557_12.png",
        "title": "Muestra 03 · Señal tenue",
        "description": "Cambios de color pequeños sobre tejido verde.",
    },
    {
        "filename": "IMG_20231015_110750_9.png",
        "title": "Muestra 04 · Lesión aislada",
        "description": "Una marca pequeña en una zona amplia de hoja.",
    },
    {
        "filename": "IMG_20231015_110842_7.png",
        "title": "Muestra 05 · Varias marcas",
        "description": "Manchas visibles junto a las nervaduras.",
    },
    {
        "filename": "IMG_20231015_110616_8.png",
        "title": "Muestra 06 · Cambios dispersos",
        "description": "Señales pequeñas distribuidas por el recorte.",
    },
    {
        "filename": "IMG_20231015_110457_16.png",
        "title": "Muestra 07 · Zonas contrastadas",
        "description": "Manchas pardas sobre tejido con variación de verde.",
    },
    {
        "filename": "IMG_20231015_110932_9.png",
        "title": "Muestra 08 · Áreas múltiples",
        "description": "Varios focos de color y zonas amarillentas.",
    },
    {
        "filename": "IMG_20231015_111000_11.png",
        "title": "Muestra 09 · Manchas oscuras",
        "description": "Contraste de lesiones oscuras y nervaduras.",
    },
    {
        "filename": "IMG_20231015_111757_15.png",
        "title": "Muestra 10 · Tejido amarillento",
        "description": "Recorte con zonas amplias amarillas y pardas.",
    },
)

_EXAMPLES_BY_FILENAME = {example["filename"]: example for example in EXAMPLES}


def catalogue() -> list[dict[str, Any]]:
    return [
        {
            **example,
            "image_url": f"/api/examples/{example['filename']}",
        }
        for example in EXAMPLES
    ]


@router.get("", summary="Muestras de hojas disponibles para probar")
def list_examples() -> list[dict[str, Any]]:
    return catalogue()


@router.get("/{filename}", summary="Imagen de ejemplo incluida en la lista permitida")
def get_example(filename: str) -> FileResponse:
    if filename not in _EXAMPLES_BY_FILENAME:
        raise HTTPException(status_code=404, detail="No existe esa imagen de ejemplo.")
    path = IMAGE_ROOT / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="La imagen de ejemplo no está disponible.")
    return FileResponse(path, media_type="image/png")
