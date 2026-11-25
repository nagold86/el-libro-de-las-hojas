"""Curated leaf examples available to every signed-in app visitor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/examples", tags=["examples"])
IMAGE_ROOT = Path(__file__).resolve().parents[1] / "example_images"

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

PREVIEW_ROOT = IMAGE_ROOT / "previews"
# Los archivos de muestra no cambian: si se reemplaza una imagen hay que cambiarle el nombre.
IMMUTABLE_CACHE = {"Cache-Control": "public, max-age=31536000, immutable"}


def _preview_name(filename: str) -> str:
    return Path(filename).with_suffix(".webp").name


_PREVIEWS_BY_NAME = {_preview_name(name): name for name in _EXAMPLES_BY_FILENAME}


def catalogue() -> list[dict[str, Any]]:
    return [
        {
            **example,
            "image_url": f"/api/examples/{example['filename']}",
            "preview_url": f"/api/examples/previews/{_preview_name(example['filename'])}",
        }
        for example in EXAMPLES
    ]


@router.get("", summary="Muestras de hojas disponibles para probar")
def list_examples() -> list[dict[str, Any]]:
    return catalogue()


@router.get("/previews/{filename}", summary="Miniatura WebP de una muestra")
def get_example_preview(filename: str) -> FileResponse:
    if filename not in _PREVIEWS_BY_NAME:
        raise HTTPException(status_code=404, detail="No existe esa miniatura de ejemplo.")
    path = PREVIEW_ROOT / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="La miniatura de ejemplo no está disponible.")
    return FileResponse(path, media_type="image/webp", headers=IMMUTABLE_CACHE)


@router.get("/{filename}", summary="Imagen de ejemplo incluida en la lista permitida")
def get_example(filename: str) -> FileResponse:
    if filename not in _EXAMPLES_BY_FILENAME:
        raise HTTPException(status_code=404, detail="No existe esa imagen de ejemplo.")
    path = IMAGE_ROOT / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="La imagen de ejemplo no está disponible.")
    return FileResponse(path, media_type="image/png", headers=IMMUTABLE_CACHE)
